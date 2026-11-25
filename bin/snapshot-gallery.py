#!/usr/bin/env python3
"""List, preview, copy, and trash WebcamTuner snapshots or open links in Revelator."""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from tempfile import NamedTemporaryFile, TemporaryFile
from urllib.parse import urlsplit

from PIL import Image

from snapshot_files import directory


SNAPSHOT_NAME = re.compile(r'WebcamTuner-[a-zA-Z0-9_-]+\.jpg')
MEDIA_ID = re.compile(r'[a-f0-9]{64}')


def tool(name):
    bundled = Path.home() / 'dil' / 'toolbox' / 'bin' / name
    return shutil.which(name) or (str(bundled) if os.access(bundled, os.X_OK) else None)


def output(command, timeout=8):
    return subprocess.run(command, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout).stdout.strip()


def available_revelator():
    url, store = (tool(name) for name in ('url_tool', 'media_store_tool'))
    if not all((url, store, shutil.which('curl'))):
        return False
    try:
        template = urlsplit(output([url, 'media', '--template', '--plain'], timeout=2))
        if template.scheme != 'https' or template.path != '/m/{media}' or not template.hostname:
            return False
        address = f'{template.hostname}:{template.port or 443}:127.0.0.1'
        html = output(['curl', '--fail', '--silent', '--noproxy', '*', '--resolve', address,
                       '--max-time', '2', '--max-filesize', '2097152',
                       f'{template.scheme}://{template.netloc}/'], timeout=3)
        return bool(re.search(r'<title>Revelator\b', html, flags=re.IGNORECASE))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return False


def cache_directory():
    cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'webcamtuner/snapshots/v1'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    return cache


def cache_key(path, file):
    return hashlib.sha256(os.fsencode(path) + f':{file.st_ino}:{file.st_size}:{file.st_mtime_ns}'.encode()).hexdigest()


def atomic_cache_write(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        try:
            temporary.write(data)
            temporary.close()
            os.replace(temporary.name, path)
        finally:
            Path(temporary.name).unlink(missing_ok=True)


def thumbnail(path, file, cache):
    target = cache / (cache_key(path, file) + '.jpg')
    if not target.is_file():
        with Image.open(path) as image:
            image.draft('RGB', (320, 180))
            image.thumbnail((320, 180))
            data = io.BytesIO()
            image.convert('RGB').save(data, 'JPEG', quality=83)
        atomic_cache_write(target, data.getvalue())
    return target.as_uri()


def snapshots(root):
    if not root.exists():
        return []
    cache = cache_directory()
    items = []
    for path in sorted(root.iterdir(), reverse=True):
        if not SNAPSHOT_NAME.fullmatch(path.name):
            continue
        try:
            file = path.lstat()
            if not stat.S_ISREG(file.st_mode):
                continue
            items.append({'name': path.name, 'thumbnail': thumbnail(path, file, cache)})
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    return items


def copy_bytes(data, mime):
    # The clipboard owner outlives wl-copy's launcher and can inherit stderr.
    with TemporaryFile() as diagnostics:
        try:
            subprocess.run(['wl-copy', '--sensitive', '--type', mime], input=data, stdout=subprocess.DEVNULL,
                           stderr=diagnostics, check=True, timeout=8)
        except subprocess.CalledProcessError as error:
            diagnostics.seek(0)
            details = diagnostics.read(160).decode(errors='replace').strip()
            raise ValueError('Could not write to the clipboard.' + (' ' + details if details else '')) from error


def store_record(store, *args):
    entry = json.loads(output([store, '--json', *args]))
    record = entry.get('data', {}).get('record', {})
    if (record.get('access_policy') != 'personal-restricted'
            or record.get('availability') != 'cached'
            or not record.get('short_id') or not MEDIA_ID.fullmatch(record.get('media_id') or '')):
        raise ValueError('This snapshot does not have a restricted Revelator link.')
    return record


def link_receipt(path, file):
    return cache_directory() / (cache_key(path, file) + '.link.json')


def read_link_receipt(receipt):
    try:
        data = json.loads(receipt.read_text())
        if (isinstance(data, dict) and MEDIA_ID.fullmatch(data.get('media_id') or '')
                and isinstance(data.get('link'), str) and isinstance(data.get('short_id'), str)
                and matches_link(data['link'], data['short_id'])):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {}


def matches_link(link, short_id):
    url = urlsplit(link)
    return bool(short_id) and url.scheme == 'https' and bool(url.hostname) and url.path == '/m/' + short_id


def snapshot_link(path, image, file, *, running=False):
    receipt = link_receipt(path, file)
    cached = read_link_receipt(receipt)
    if cached:
        return cached['link']
    url = tool('url_tool')
    store = tool('media_store_tool')
    if not all((url, store)):
        raise ValueError('Revelator is unavailable on this machine.')
    with receipt.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cached = read_link_receipt(receipt)
        if cached:
            return cached['link']
        if not running and not available_revelator():
            raise ValueError('Revelator is unavailable on this machine.')
        legacy = receipt.with_name(cache_key(path, file) + '.media-id')
        media_id = legacy.read_text().strip() if legacy.is_file() else ''
        if MEDIA_ID.fullmatch(media_id):
            record = store_record(store, 'get', '--media-id', media_id)
        else:
            digest = hashlib.file_digest(image, 'sha256').hexdigest()
            record = store_record(store, 'import-local', '--provider', 'webcamtuner',
                                  '--account', 'personal', '--provider-media-id', digest,
                                  '--path', str(path), '--kind', 'image', '--mime', 'image/jpeg',
                                  '--expected-sha256', digest, '--sensitivity', 'restricted',
                                  '--visibility', 'domain-gated', '--access-policy', 'personal-restricted')
        short_id = record['short_id']
        link = output([url, 'media', short_id, '--plain'])
        if not matches_link(link, short_id):
            raise ValueError('Revelator did not return an HTTPS link for this snapshot.')
        atomic_cache_write(receipt, json.dumps({'media_id': record['media_id'], 'short_id': short_id, 'link': link}).encode())
        return link


def register_missing(root):
    if not root.is_dir():
        return {}
    missing = []
    for path in sorted(root.iterdir(), reverse=True):
        if SNAPSHOT_NAME.fullmatch(path.name):
            try:
                file = path.lstat()
                if valid_snapshot(file) and not read_link_receipt(link_receipt(path, file)):
                    missing.append(path)
            except OSError:
                continue
    if not missing or not all((tool('url_tool'), tool('media_store_tool'), shutil.which('curl'))):
        return {}
    if not available_revelator():
        return {'retry': True}
    failed = 0
    for path in missing:
        try:
            with open_snapshot(path) as image:
                file = os.fstat(image.fileno())
                if valid_snapshot(file):
                    snapshot_link(path, image, file, running=True)
        except (OSError, ValueError, subprocess.SubprocessError):
            failed += 1
    return {'failed': failed}


def open_snapshot(path):
    return os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb')


def valid_snapshot(file):
    return stat.S_ISREG(file.st_mode) and 0 < file.st_size <= 50 * 1024 * 1024


def copy_image(image):
    with Image.open(image) as photo:
        data = io.BytesIO()
        photo.convert('RGB').save(data, 'PNG', compress_level=1)
    copy_bytes(data.getvalue(), 'image/png')


def open_window(command, failure):
    opener = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        if opener.wait(timeout=.25):
            raise ValueError(failure)
    except subprocess.TimeoutExpired:
        # A viewer can stay running until its window closes.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('list', 'revelator', 'register-missing', 'preview', 'copy-image', 'copy-path', 'copy-url', 'open-revelator', 'trash'))
    parser.add_argument('name', nargs='?')
    args = parser.parse_args()
    if args.action == 'revelator':
        return {'available': available_revelator()}
    root = directory(create=False)
    if args.action == 'list':
        return {'items': snapshots(root)}
    if args.action == 'register-missing':
        return register_missing(root)

    if not args.name or not SNAPSHOT_NAME.fullmatch(args.name):
        raise ValueError('Choose a saved WebcamTuner snapshot.')
    path = root / args.name
    with open_snapshot(path) as image:
        file = os.fstat(image.fileno())
        if not valid_snapshot(file):
            raise ValueError('The selected snapshot is unavailable.')
        if args.action == 'trash':
            try:
                output(['gio', 'trash', '--', str(path)], timeout=15)
            except subprocess.CalledProcessError as error:
                raise ValueError(error.stderr.strip() or 'Could not move the snapshot to Trash.') from error
            if os.path.lexists(path):
                raise ValueError('The snapshot is still in the gallery folder.')
        elif args.action == 'preview':
            folio = shutil.which('folio')
            if folio is None:
                raise ValueError('Folio is required to preview snapshots.')
            open_window([folio, 'preview', str(path)], 'Could not open the snapshot in Folio.')
        elif args.action == 'copy-image':
            copy_image(image)
        elif args.action == 'copy-path':
            copy_bytes(os.fsencode(path), 'text/plain')
        else:
            link = snapshot_link(path, image, file)
            if args.action == 'copy-url':
                copy_bytes(link.encode(), 'text/plain')
            else:
                open_window(['xdg-open', link], 'Could not open Revelator in the default browser.')
    return {}


if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except (OSError, ValueError, Image.DecompressionBombError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)[:200]}))
        raise SystemExit(1)
