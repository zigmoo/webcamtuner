#!/usr/bin/env python3
"""Managed local image copies and rebuildable thumbnails for WebcamTuner."""
import argparse
import hashlib
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
FORMATS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
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
            if image.format not in FORMATS or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Choose a static JPEG, PNG or WebP image.')
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('Images must contain at most 40 million pixels.')
            extension = FORMATS[image.format]
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
    return sorted((p for p in library.iterdir() if p.is_file() and not p.is_symlink()
                   and re.fullmatch(r'[a-f0-9]{64}__.+\.(jpg|png|webp)', p.name)), key=lambda p: p.name)


def thumbnail(path, cache, image=None):
    digest = path.name[:64]
    target = cache / (digest + '.jpg')
    if target.is_symlink():
        raise ValueError('Thumbnail path must not be a symbolic link.')
    if not target.exists():
        if image is None:
            data = path.read_bytes()
            if len(data) > MAX_BYTES:
                raise ValueError('Image exceeds 50 MiB.')
            image, _ = decode(data)
        image.thumbnail((320, 180))
        output = io.BytesIO()
        image.save(output, 'JPEG', quality=85)
        atomic_write(target, output.getvalue())
    return target


def entry(path, cache, image=None):
    return {'id': path.name[:64], 'name': path.name[66:], 'path': str(path),
            'thumbnail': thumbnail(path, cache, image).as_uri()}


def listing():
    library, cache = directories()
    items, failures = [], []
    for path in files(library)[:MAX_IMAGES]:
        try:
            items.append(entry(path, cache))
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            failures.append(path.name[66:])
    return {'directory': str(library), 'items': items, 'unreadable': failures}


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
            target = next((p for p in existing if p.name.startswith(digest + '__')), None)
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
            added.append(entry(target, cache, image))
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            errors.append({'name': Path(value).name, 'message': str(error)[:300]})
    result = listing()
    result.update(added=added, errors=errors)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list', 'add'])
    parser.add_argument('--paths', default='[]')
    args = parser.parse_args()
    try:
        print(json.dumps(listing() if args.action == 'list' else add(json.loads(args.paths))))
    except (OSError, ValueError) as error:
        print(json.dumps({'error': str(error)[:500]}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
