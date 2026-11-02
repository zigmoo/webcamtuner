#!/usr/bin/env python3
"""User-session synthetic publisher proof; never opens a physical camera."""
import argparse
import fcntl
import json
import os
import shutil
import struct
import subprocess
import time
import sys
from pathlib import Path

UNIT = 'webcamtuner-test.service'
NODE = 'webcamtuner.test'


def capture_info(path):
    # VIDIOC_QUERYCAP only: never negotiate a format or start camera capture.
    data = bytearray(104)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        fcntl.ioctl(fd, 0x80685600, data, True)
    finally:
        os.close(fd)
    driver, card, bus, version, capabilities, device_caps = struct.unpack_from('=16s32s32sIII', data)
    caps = device_caps if capabilities & 0x80000000 else capabilities
    if not caps & (0x1 | 0x1000):
        return None
    decode = lambda value: value.split(b'\0', 1)[0].decode('utf-8', errors='replace')
    return {'name': decode(card), 'driver': decode(driver), 'bus': decode(bus)}


def video_sources(dump):
    if not isinstance(dump, list):
        raise ValueError('PipeWire returned an invalid source list.')
    sources = []
    for item in dump:
        if not isinstance(item, dict) or item.get('type') != 'PipeWire:Interface:Node':
            continue
        info = item.get('info') or {}
        props = info.get('props') or {}
        if props.get('media.class') != 'Video/Source':
            continue
        sources.append({'id': item.get('id'), 'serial': props.get('object.serial'),
                        'name': props.get('node.description') or props.get('node.nick') or props.get('node.name', ''),
                        'node': props.get('node.name', ''), 'state': info.get('state', 'unknown'),
                        'path': props.get('api.v4l2.path', ''), 'testOutput': props.get('node.name') == NODE})
    return sorted(sources, key=lambda item: (str(item['name']).lower(), str(item['id'])))


def inventory():
    devices, errors, aliases = [], [], {}
    for alias in sorted(Path('/dev/v4l/by-id').glob('*')):
        aliases.setdefault(str(alias.resolve()), []).append(str(alias))
    for entry in sorted(Path('/sys/class/video4linux').glob('video*')):
        path = '/dev/' + entry.name
        try:
            info = capture_info(path)
            if info:
                devices.append(dict(info, path=path, aliases=aliases.get(path, [])))
        except OSError as error:
            errors.append(path + ': ' + (error.strerror or str(error)))
    nodes = []
    try:
        dump = run(['pw-dump'])
        if dump.returncode:
            raise RuntimeError('Cannot connect to your PipeWire session.')
        nodes = video_sources(json.loads(dump.stdout))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        errors.append(str(error)[:500])
    target = next((item for item in nodes if item['testOutput']), None)
    return {'devices': devices, 'pipewire': nodes, 'errors': errors,
            'output': {'name': 'WebcamTuner', 'node': NODE, 'nodeId': target['id'] if target else None,
                       'published': target is not None, 'kind': 'Synthetic test pattern', 'processed': False}}


def run(args, timeout=10):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def status():
    missing = [name for name in ('systemctl', 'systemd-run', 'pw-dump', 'gst-launch-1.0', 'gst-inspect-1.0') if not shutil.which(name)]
    if missing:
        return {'state': 'unavailable', 'published': False, 'missing': missing, 'message': 'Required desktop components are unavailable: ' + ', '.join(missing)}
    service = run(['systemctl', '--user', 'show', UNIT, '--property=ActiveState', '--value']).stdout.strip()
    dump = run(['pw-dump'])
    if dump.returncode:
        raise RuntimeError('Cannot connect to your PipeWire session.')
    nodes = [n for n in json.loads(dump.stdout) if n.get('type') == 'PipeWire:Interface:Node' and n.get('info', {}).get('props', {}).get('node.name') == NODE]
    node = nodes[0] if nodes else None
    active = service in ('active', 'activating')
    return {'state': 'test-published' if node and active else ('starting' if active else 'stopped'),
            'published': bool(node and active), 'nodeId': node['id'] if node else None,
            'nodeState': node['info']['state'] if node else None,
            'nodeSerial': node['info']['props']['object.serial'] if node else None,
            'format': {'width': 1280, 'height': 720, 'fps': 30},
            'synthetic': True, 'appCompatibility': 'unverified',
            'message': 'Synthetic test camera published. App compatibility is not yet verified.' if node and active else 'Test camera is stopped.'}


def start():
    current = status()
    if current['state'] == 'unavailable' or current['published']:
        return current
    probe = run([sys.executable, '-c', 'import gi; gi.require_version("Gst", "1.0"); from gi.repository import Gst'])
    if probe.returncode:
        raise RuntimeError('Python GStreamer support is unavailable on this desktop.')
    for element in ('videotestsrc', 'timeoverlay', 'pipewiresink'):
        if run(['gst-inspect-1.0', element]).returncode:
            raise RuntimeError('Missing desktop video component: ' + element)
    # Only our named transient unit is affected. No enable/linger or system changes.
    run(['systemctl', '--user', 'reset-failed', UNIT])
    result = run(['systemd-run', '--user', '--unit=' + UNIT, '--collect',
                  '--property=RuntimeMaxSec=1800', '--property=NoNewPrivileges=yes',
                  '--property=UMask=0077',
                  sys.executable, str(Path(__file__).resolve().with_name('synthetic-camera.py'))])
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1000])
    for _ in range(30):
        current = status()
        if current['published']:
            return current
        time.sleep(.1)
    run(['systemctl', '--user', 'stop', UNIT])
    raise RuntimeError('The test source did not register. Open diagnostics and retry.')


def stop():
    result = run(['systemctl', '--user', 'stop', UNIT])
    # Stopping an already collected transient unit is idempotent.
    current = status()
    if current.get('published') or current['state'] == 'starting':
        raise RuntimeError(result.stderr.strip() or 'Test source did not stop.')
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'start-test', 'stop-test', 'diagnostics', 'inventory'])
    args = parser.parse_args()
    try:
        result = inventory() if args.action == 'inventory' else start() if args.action == 'start-test' else stop() if args.action == 'stop-test' else status()
        if args.action == 'diagnostics':
            result['log'] = run(['journalctl', '--user', '-u', UNIT, '-n', '20', '--no-pager']).stdout[-6000:]
        print(json.dumps(result))
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        print(json.dumps({'state': 'error', 'published': False, 'message': str(error)[:1000]}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
