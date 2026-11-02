#!/usr/bin/env python3
"""Managed local image copies and rebuildable thumbnails for WebcamTuner."""
import argparse
import hashlib
import fcntl
import subprocess
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


def read_settings():
    path = crop_file()
    if not path.exists():
        return {'schemaVersion': 1, 'crops': {}, 'locks': {}, 'labels': {}}
    with path.open('rb') as stream:
        data = stream.read(1048577)
    if len(data) > 1048576:
        raise ValueError('Background settings exceed their size limit.')
    value = json.loads(data)
    if not isinstance(value, dict) or value.get('schemaVersion') != 1 or not isinstance(value.get('crops'), dict):
        raise ValueError('Cannot read background crop settings.')
    for key, crop in value['crops'].items():
        if not re.fullmatch('[a-f0-9]{64}', key):
            raise ValueError('Invalid background identity.')
        validate_crop(crop)
    locks = value.setdefault('locks', {})
    if not isinstance(locks, dict) or any(not re.fullmatch('[a-f0-9]{64}', key) or not isinstance(locked, bool) for key, locked in locks.items()):
        raise ValueError('Invalid background locks.')
    labels = value.setdefault('labels', {})
    if not isinstance(labels, dict) or any(not re.fullmatch('[a-f0-9]{64}', key) or not isinstance(label, str) or len(label) > 80 or any(ord(c) < 32 for c in label) for key, label in labels.items()):
        raise ValueError('Invalid background labels.')
    return value


def read_crops():
    return read_settings()['crops']


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


def entry(path, cache, crops=None, locks=None, labels=None):
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
    settings = read_settings() if crops is None or locks is None or labels is None else None
    crops = settings['crops'] if crops is None else crops
    locks = settings['locks'] if locks is None else locks
    labels = settings['labels'] if labels is None else labels
    return {'id': digest, 'name': display_name(path), 'path': str(path),
            'thumbnail': (cache / (digest + '.jpg')).as_uri(), 'crop': crops.get(digest, default_crop()), 'locked': locks.get(digest, False), 'label': labels.get(digest, '')}


def listing(selected_path=None):
    library, cache = directories()
    items, failures = [], []
    settings = read_settings(); crops = settings['crops']; locks = settings['locks']; labels = settings['labels']
    images = files(library)
    for path in images[:MAX_IMAGES]:
        try:
            items.append(entry(path, cache, crops, locks, labels))
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            failures.append(display_name(path))
    result = {'directory': str(library), 'items': items, 'unreadable': failures, 'limited': len(images) > MAX_IMAGES}
    if selected_path:
        try:
            selected = entry(local_path(selected_path), cache, crops, locks, labels)
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
        document = read_settings(); crops = document['crops']
        if document['locks'].get(image['id'], False):
            raise ValueError('Unlock this background before changing its crop.')
        if image['id'] not in crops and len(crops) >= MAX_IMAGES:
            raise ValueError('Background crop settings are full.')
        crops[image['id']] = crop
        atomic_write(settings, (json.dumps(document) + '\n').encode())
        if read_crops().get(image['id']) != crop:
            raise ValueError('Background crop could not be verified.')
    finally:
        os.close(lock)
    return {'path': str(path), 'crop': crop, 'id': image['id']}


def managed_image(value, expected_id):
    library, cache = directories()
    path = local_path(value)
    if path.parent != library or path.is_symlink():
        raise ValueError('Only files inside the background library can be changed.')
    image = entry(path, cache)
    if image['id'] != expected_id:
        raise ValueError('This image changed outside WebcamTuner. Refresh and try again.')
    return path, image


def lock_image(value, expected_id, locked):
    if not isinstance(locked, bool):
        raise ValueError('Invalid lock state.')
    path, image = managed_image(value, expected_id)
    settings = crop_file(); settings.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(str(settings) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        document = read_settings()
        if image['id'] not in document['locks'] and len(document['locks']) >= MAX_IMAGES:
            raise ValueError('Background lock settings are full.')
        document['locks'][image['id']] = locked
        atomic_write(settings, (json.dumps(document) + '\n').encode())
        if read_settings()['locks'].get(image['id'], False) != locked:
            raise ValueError('Lock could not be verified.')
    finally:
        os.close(fd)
    return listing()


def label_image(value, expected_id, label):
    if not isinstance(label, str) or len(label) > 80 or any(ord(c) < 32 for c in label):
        raise ValueError('Use a label of up to 80 characters on one line.')
    _, image = managed_image(value, expected_id)
    label = label.strip()
    settings = crop_file(); settings.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(str(settings) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        document = read_settings()
        if label:
            if image['id'] not in document['labels'] and len(document['labels']) >= MAX_IMAGES:
                raise ValueError('Background label settings are full.')
            document['labels'][image['id']] = label
        else:
            document['labels'].pop(image['id'], None)
        atomic_write(settings, (json.dumps(document) + '\n').encode())
        if read_settings()['labels'].get(image['id'], '') != label:
            raise ValueError('Background label could not be verified.')
    finally:
        os.close(fd)
    return listing()


def trash_image(value, expected_id, keep_paths):
    path, image = managed_image(value, expected_id)
    if not isinstance(keep_paths, list) or len(keep_paths) > 30 or any(not isinstance(p, str) for p in keep_paths):
        raise ValueError('Invalid profile references.')
    library, cache = directories()
    settings = crop_file(); settings.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(str(settings) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    moved = False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        document = read_settings()
        if document['locks'].get(image['id'], False):
            raise ValueError('Unlock this background before moving it to Trash.')
        managed_image(value, expected_id)
        result = subprocess.run(['gio', 'trash', '--', str(path)], capture_output=True, text=True, timeout=15)
        if result.returncode or path.exists():
            raise ValueError(result.stderr.strip()[:500] or 'The image could not be moved to Trash.')
        moved = True
        remaining = listing()
        used = any(item['id'] == image['id'] for item in remaining['items'])
        for reference in keep_paths:
            if used: break
            try: used = entry(local_path(reference), cache)['id'] == image['id']
            except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning): pass
        if not used:
            document['crops'].pop(image['id'], None)
            document['locks'].pop(image['id'], None)
            document['labels'].pop(image['id'], None)
            atomic_write(settings, (json.dumps(document) + '\n').encode())
            (cache / (image['id'] + '.jpg')).unlink(missing_ok=True)
        (cache / ('file-' + hashlib.sha256(str(path).encode()).hexdigest() + '.json')).unlink(missing_ok=True)
        return remaining
    except (OSError, ValueError) as error:
        if not moved: raise
        # The move succeeded: do not tell the caller to restore dangling profile references.
        try:
            remaining = listing()
        except (OSError, ValueError):
            remaining = {'directory': str(library), 'items': [], 'unreadable': []}
        remaining['cleanupWarning'] = str(error)[:300]
        return remaining
    finally:
        os.close(fd)


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
    parser.add_argument('action', choices=['list', 'add', 'crop', 'lock', 'trash', 'inspect', 'label'])
    parser.add_argument('--paths', default='[]')
    parser.add_argument('--path')
    parser.add_argument('--crop')
    parser.add_argument('--selected-path')
    parser.add_argument('--id')
    parser.add_argument('--label', default='')
    parser.add_argument('--locked', choices=['true', 'false'])
    parser.add_argument('--keep-paths', default='[]')
    args = parser.parse_args()
    try:
        if args.action == 'inspect':
            _, result = managed_image(args.path, args.id)
        elif args.action == 'lock':
            result = lock_image(args.path, args.id, args.locked == 'true')
        elif args.action == 'label':
            result = label_image(args.path, args.id, args.label)
        elif args.action == 'trash':
            result = trash_image(args.path, args.id, json.loads(args.keep_paths))
        elif args.action == 'crop':
            result = save_crop(args.path, json.loads(args.crop))
        else:
            result = listing(args.selected_path) if args.action == 'list' else add(json.loads(args.paths))
        print(json.dumps(result))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'error': str(error)[:500]}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
