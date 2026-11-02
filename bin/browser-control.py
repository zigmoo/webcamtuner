#!/usr/bin/env python3
"""Open an opt-in, separate calling-browser profile with PipeWire cameras."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

URLS = {'zoom': 'https://app.zoom.us/wc/home', 'teams': 'https://teams.microsoft.com/',
        'meet': 'https://meet.google.com/', 'chat': 'https://chat.google.com/'}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('app', choices=URLS)
args = parser.parse_args()
try:
    browser = shutil.which('brave') or shutil.which('chromium')
    if not browser:
        raise RuntimeError('A supported browser is not installed. Brave or Chromium is needed for this test route.')
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    if not data.is_absolute():
        raise RuntimeError('XDG_DATA_HOME must be an absolute path.')
    profile = data / 'webcamtuner' / 'calling-browser'
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = subprocess.run(['systemd-run', '--user', '--collect',
                             '--unit=webcamtuner-browser-' + uuid.uuid4().hex[:12],
                             browser, '--user-data-dir=' + str(profile), '--no-first-run',
                             '--no-default-browser-check', '--enable-features=WebRtcPipeWireCamera',
                             URLS[args.app]], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1000])
    print(json.dumps({'message': 'Browser launch requested. Sign in if needed, then select WebcamTuner in camera settings. App compatibility still needs verification.'}))
except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
    print(json.dumps({'message': str(error)[:1000]}))
    raise SystemExit(1)
