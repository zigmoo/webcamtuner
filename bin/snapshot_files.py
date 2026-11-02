#!/usr/bin/env python3
"""Store explicitly requested processed snapshots in the user's Pictures folder."""
from datetime import datetime
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid


def directory(create=True):
    override = os.environ.get('WEBCAMTUNER_SNAPSHOT_ROOT')
    if override:
        target = Path(override)
    else:
        try:
            result = subprocess.run(['xdg-user-dir', 'PICTURES'], capture_output=True, text=True, timeout=3)
            pictures = Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.home() / 'Pictures'
        except (OSError, subprocess.TimeoutExpired):
            pictures = Path.home() / 'Pictures'
        target = pictures / 'WebcamTuner'
    if not target.is_absolute():
        raise ValueError('Snapshot folder must be an absolute path.')
    if create:
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
    return target


def save(jpeg):
    if not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9') or len(jpeg) > 50 * 1024 * 1024:
        raise ValueError('Snapshot encoding was not a complete JPEG.')
    folder = directory()
    name = 'WebcamTuner-' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + '-' + uuid.uuid4().hex[:8] + '.jpg'
    target = folder / name
    temporary = folder / ('.' + uuid.uuid4().hex + '.partial')
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(jpeg)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(jpeg).digest():
            raise ValueError('Snapshot save could not be verified.')
    finally:
        temporary.unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    print(json.dumps({'directory': str(directory(create=args.create))}))
