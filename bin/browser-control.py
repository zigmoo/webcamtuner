#!/usr/bin/env python3
"""Open native Zoom or a separate calling-browser profile for other apps."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

URLS = {'teams': 'https://teams.microsoft.com/',
        'meet': 'https://meet.google.com/', 'chat': 'https://chat.google.com/'}
CAMERA_FEATURE = 'WebRtcPipeWireCamera'


def enable_browser_camera():
    browser = shutil.which('brave') or shutil.which('chromium')
    if not browser:
        raise RuntimeError('Brave or Chromium is required for browser camera support.')
    directory = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    if not directory.is_absolute():
        raise RuntimeError('XDG_CONFIG_HOME must be an absolute path.')
    path = directory / ('brave-flags.conf' if 'brave' in Path(browser).name else 'chromium-flags.conf')
    target = path.resolve() if path.is_symlink() else path
    old = target.read_text() if target.exists() else ''
    if len(old) > 65536:
        raise RuntimeError('Browser flags file is too large to update safely.')
    lines, enabled = [], []
    for line in old.splitlines():
        stripped = line.strip()
        if stripped.startswith('--enable-features='):
            enabled.extend(value for value in stripped.split('=', 1)[1].split(',') if value)
        elif stripped.startswith('--disable-features='):
            remaining = [value for value in stripped.split('=', 1)[1].split(',')
                         if value and value.split(':', 1)[0].split('<', 1)[0] != CAMERA_FEATURE]
            if remaining:
                lines.append('--disable-features=' + ','.join(remaining))
        else:
            lines.append(line)
    enabled = [value for value in enabled if value.split(':', 1)[0].split('<', 1)[0] != CAMERA_FEATURE]
    enabled.append(CAMERA_FEATURE)
    lines.append('--enable-features=' + ','.join(dict.fromkeys(enabled)))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name('.' + target.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as output:
            temporary.chmod(target.stat().st_mode & 0o777 if target.exists() else 0o600)
            output.write('\n'.join(lines) + '\n')
            output.flush(); os.fsync(output.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    if CAMERA_FEATURE not in target.read_text():
        raise RuntimeError('Browser camera support could not be confirmed in the saved flags.')
    return {'message': 'PipeWire camera support saved. Fully quit and reopen your normal browser before using Meet. Existing browser windows and site permissions were not changed.',
            'browser': Path(browser).name, 'flagsFile': str(path), 'restartRequired': True}


def launch(app, restart=False):
    if app == 'enable-browser-camera':
        return enable_browser_camera()
    if app == 'zoom':
        zoom = shutil.which('zoom')
        if not zoom:
            raise RuntimeError('Zoom desktop is not installed. Install the Linux Zoom package first.')
        from camera_adapter import status, restart_zoom
        if restart:
            restart_zoom()
        adapter = status()
        command = ['python3', str(Path(__file__).resolve().with_name('zoom-camera.py'))] if adapter['enabled'] else [zoom]
        message = 'Zoom desktop launch requested. Open Video settings to check its camera menu. WebcamTuner output compatibility still needs verification.'
    else:
        browser = shutil.which('brave') or shutil.which('chromium')
        if not browser:
            raise RuntimeError('A supported browser is not installed. Brave or Chromium is needed for this test route.')
        data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        if not data.is_absolute():
            raise RuntimeError('XDG_DATA_HOME must be an absolute path.')
        profile = data / 'webcamtuner' / 'calling-browser'
        profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        command = [browser, '--user-data-dir=' + str(profile), '--no-first-run',
                   '--no-default-browser-check', '--enable-features=WebRtcPipeWireCamera', URLS[app]]
        message = 'Browser launch requested. Sign in if needed, then check camera settings. App compatibility still needs verification.'
    result = subprocess.run(['systemd-run', '--user', '--collect',
                             '--unit=webcamtuner-' + app + '-' + uuid.uuid4().hex[:12],
                             *command], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1000])
    return {'message': message}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', choices=['zoom', 'enable-browser-camera', *URLS])
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(launch(args.app, args.restart)))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'message': str(error)[:1000]}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
