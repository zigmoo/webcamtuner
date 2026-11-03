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
def launch(app, restart=False):
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
    parser.add_argument('app', choices=['zoom', *URLS])
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(launch(args.app, args.restart)))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'message': str(error)[:1000]}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
