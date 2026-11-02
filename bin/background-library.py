#!/usr/bin/env python3
"""Managed local image copies and rebuildable thumbnails for WebcamTuner."""
import argparse
import hashlib
import fcntl
import math
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid
import warnings
from urllib.parse import unquote, urlparse
from PIL import Image, ImageOps

MAX_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_IMAGES = 512
MAX_LIBRARY_BYTES = 1024 * 1024 * 1024
FORMATS = {'JPEG': '.jpg', 'MPO': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def xdg(key, default):
    path = Path(os.environ.get(key) or Path.home() / default)
    return path if path.is_absolute() else Path.home() / default


def directories():
    library = xdg('XDG_DATA_HOME', '.local/share') / 'webcamtuner/backgrounds'
    cache = xdg('XDG_CACHE_HOME', '.cache') / 'webcamtuner/thumbnails/v1'
    for path in (library, cache):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return library, cache


def local_path(value):
    if value.startswith('file:'):
        url = urlparse(value)
        if url.scheme != 'file' or url.netloc not in ('', 'localhost'):
            raise ValueError('Choose a local image.')
        value = unquote(url.path)
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Choose an image using an absolute path.')
    return path


def decode(data):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in FORMATS or (image.format != 'MPO' and getattr(image, 'n_frames', 1) != 1):
                raise ValueError('Choose a static JPEG, PNG or WebP image.')
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('Images must contain at most 40 million pixels.')
            extension = FORMATS[image.format]
            # iPhone JPEGs may carry auxiliary gain/depth pictures in MPO.
            # Their first image is the ordinary still background.
            image.seek(0)
            image.load()
            return ImageOps.exif_transpose(image).convert('RGB'), extension


def atomic_write(path, data):
    temporary = path.with_name('.' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def files(library):
    return sorted((p for p in library.iterdir() if not p.name.startswith('.')
                   and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')
                   and p.is_file() and not p.is_symlink()), key=lambda p: p.name.casefold())


def display_name(path):
    return path.name[66:] if re.fullmatch(r'[a-f0-9]{64}__.+', path.name) else path.name


def default_crop():
    return {'zoom': 1, 'centerX': 0.5, 'centerY': 0.5}


def validate_crop(crop):
    if not isinstance(crop, dict) or set(crop) != {'zoom', 'centerX', 'centerY'}:
        raise ValueError('Invalid background crop.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in crop.values()):
        raise ValueError('Invalid background crop.')
    if not 1 <= crop['zoom'] <= 4 or not 0 <= crop['centerX'] <= 1 or not 0 <= crop['centerY'] <= 1:
        raise ValueError('Background crop is outside its limits.')
    return crop


def crop_file():
    directory = Path(os.environ.get('WEBCAMTUNER_CONFIG_ROOT') or xdg('XDG_CONFIG_HOME', '.config') / 'webcamtuner')
    return directory / 'background-crops.json'


def read_crops():
    path = crop_file()
    if not path.exists():
        return {}
    with path.open('rb') as stream:
        data = stream.read(262145)
    if len(data) > 262144:
        raise ValueError('Background settings exceed their size limit.')
    value = json.loads(data)
    if not isinstance(value, dict) or value.get('schemaVersion') != 1 or not isinstance(value.get('crops'), dict):
        raise ValueError('Cannot read background crop settings.')
    for key, crop in value['crops'].items():
        if not re.fullmatch('[a-f0-9]{64}', key):
            raise ValueError('Invalid background identity.')
        validate_crop(crop)
    return value['crops']


def thumbnail(image, digest, cache):
    target = cache / (digest + '.jpg')
    if target.is_symlink():
        raise ValueError('Thumbnail path must not be a symbolic link.')
    if not target.exists():
        image.thumbnail((320, 180))
        output = io.BytesIO()
        image.save(output, 'JPEG', quality=85)
        atomic_write(target, output.getvalue())
    return target


def entry(path, cache, crops=None):
    # Cache identities by file metadata: polling does not rehash/decode every image.
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError('Choose a regular image no larger than 50 MiB.')
    stamp = [before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns]
    index = cache / ('file-' + hashlib.sha256(str(path).encode()).hexdigest() + '.json')
    cached = None
    try:
        candidate = json.loads(index.read_text()) if not index.is_symlink() else {}
        if candidate.get('stamp') == stamp and re.fullmatch('[a-f0-9]{64}', candidate.get('digest', '')):
            target = cache / (candidate['digest'] + '.jpg')
            if target.is_file() and not target.is_symlink():
                cached = candidate
    except (OSError, ValueError, TypeError):
        pass
    if cached is None:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('Choose a regular image.')
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Image exceeds 50 MiB.')
        image, _ = decode(data)
        after = path.lstat()
        if stamp != [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns]:
            raise ValueError('Image is still being copied. It will be retried automatically.')
        digest = hashlib.sha256(data).hexdigest()
        thumbnail(image, digest, cache)
        cached = {'stamp': stamp, 'digest': digest}
        atomic_write(index, json.dumps(cached).encode())
    digest = cached['digest']
    crops = read_crops() if crops is None else crops
    return {'id': digest, 'name': display_name(path), 'path': str(path),
            'thumbnail': (cache / (digest + '.jpg')).as_uri(), 'crop': crops.get(digest, default_crop())}


def listing(selected_path=None):
    library, cache = directories()
    items, failures = [], []
    crops = read_crops()
    images = files(library)
    for path in images[:MAX_IMAGES]:
        try:
            items.append(entry(path, cache, crops))
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            failures.append(display_name(path))
    result = {'directory': str(library), 'items': items, 'unreadable': failures, 'limited': len(images) > MAX_IMAGES}
    if selected_path:
        try:
            selected = entry(local_path(selected_path), cache, crops)
            selected['hasCrop'] = selected['id'] in crops
            result['selected'] = selected
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            result['selected'] = None
    return result


def save_crop(value, crop):
    library, cache = directories()
    path = local_path(value)
    validate_crop(crop)
    image = entry(path, cache)
    settings = crop_file()
    settings.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    lock = os.open(str(settings) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        crops = read_crops()
        if image['id'] not in crops and len(crops) >= MAX_IMAGES:
            raise ValueError('Background crop settings are full.')
        crops[image['id']] = crop
        atomic_write(settings, (json.dumps({'schemaVersion': 1, 'crops': crops}) + '\n').encode())
        if read_crops().get(image['id']) != crop:
            raise ValueError('Background crop could not be verified.')
    finally:
        os.close(lock)
    return {'path': str(path), 'crop': crop, 'id': image['id']}


def add(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 20 or any(not isinstance(v, str) or len(v) > 4096 for v in values):
        raise ValueError('Add between 1 and 20 images at a time.')
    library, cache = directories()
    added, errors = [], []
    for value in values:
        try:
            source = local_path(value)
            fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('Choose a regular image file.')
                data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('Images must be no larger than 50 MiB.')
            image, extension = decode(data)
            digest = hashlib.sha256(data).hexdigest()
            existing = files(library)
            target = None
            for candidate in existing:
                try:
                    if entry(candidate, cache)['id'] == digest:
                        target = candidate
                        break
                except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                    continue
            if target is None:
                if len(existing) >= MAX_IMAGES or sum(p.stat().st_size for p in existing) + len(data) > MAX_LIBRARY_BYTES:
                    raise ValueError('The library limit is 512 images or 1 GiB.')
                stem = re.sub(r'[^\w .()-]', '_', source.stem, flags=re.UNICODE).strip(' .')[:80] or 'Background'
                target = library / (digest + '__' + stem + extension)
                if target.is_symlink():
                    raise ValueError('Library image path must not be a symbolic link.')
                atomic_write(target, data)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('The copied image could not be verified.')
            added.append(entry(target, cache))
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            errors.append({'name': Path(value).name, 'message': str(error)[:300]})
    result = listing()
    result.update(added=added, errors=errors)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list', 'add', 'crop'])
    parser.add_argument('--paths', default='[]')
    parser.add_argument('--path')
    parser.add_argument('--crop')
    parser.add_argument('--selected-path')
    args = parser.parse_args()
    try:
        if args.action == 'crop':
            result = save_crop(args.path, json.loads(args.crop))
        else:
            result = listing(args.selected_path) if args.action == 'list' else add(json.loads(args.paths))
        print(json.dumps(result))
    except (OSError, ValueError) as error:
        print(json.dumps({'error': str(error)[:500]}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
