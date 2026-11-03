"""Install and scope the native-camera adapter entirely to the signed-in user."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request


def data_root():
    root = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'webcamtuner'
    if not root.is_absolute():
        raise ValueError('XDG_DATA_HOME must be an absolute path.')
    return root


def package_version():
    result = subprocess.check_output(['pacman', '-Q', 'libpipewire'], text=True, timeout=5)
    return result.split()[1]


def library_path():
    version = re.sub('[^a-zA-Z0-9._-]', '_', package_version())
    return data_root() / 'adapters' / version / 'libpw-v4l2.so'


def zoom_processes():
    result = []
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            if entry.stat().st_uid == os.getuid() and str((entry / 'exe').resolve()) in ('/usr/bin/zoom', '/opt/zoom/zoom'):
                result.append(int(entry.name))
        except (OSError, RuntimeError):
            pass
    return result


def status():
    path = library_path()
    processes = zoom_processes()
    loaded = False
    for pid in processes:
        try:
            if 'libpw-v4l2.so' in (Path('/proc') / str(pid) / 'maps').read_text():
                loaded = True
        except OSError:
            pass
    desktop = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications/Zoom.desktop'
    enabled = desktop.is_file() and 'webcamtuner-zoom' in desktop.read_text()
    ready = path.is_file() and path.read_bytes()[:4] == b'\x7fELF'
    return {'ready': ready, 'enabled': enabled, 'zoomRunning': bool(processes), 'adapterLoaded': loaded,
            'restartRequired': bool(processes) and enabled and not loaded,
            'library': str(path), 'version': package_version()}


def download(url, maximum):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == 'file' and not parsed.netloc:
        path = Path(urllib.parse.unquote(parsed.path)).resolve(strict=True)
        details = path.stat()
        if path.parent != Path('/var/cache/pacman/pkg') or details.st_uid != 0 or details.st_mode & 0o022 or not path.is_file():
            raise RuntimeError('Only root-owned pacman cache files can supply local signed packages.')
        if details.st_size > maximum:
            raise RuntimeError('Cached signed package exceeds its size limit.')
        return path.read_bytes()
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise RuntimeError('Signed packages require HTTPS or the root-owned pacman cache.')
    with urllib.request.urlopen(url, timeout=20) as response:
        if urllib.parse.urlparse(response.url).scheme != 'https':
            raise RuntimeError('Camera adapter download redirected away from HTTPS.')
        value = response.read(maximum + 1)
    if len(value) > maximum:
        raise RuntimeError('Camera adapter download exceeds its size limit.')
    return value


def setup():
    target = library_path()
    if not target.is_file() or target.open('rb').read(4) != b'\x7fELF':
        version = package_version()
        available = subprocess.check_output(['pacman', '-Si', 'pipewire-v4l2'], text=True, timeout=10)
        remote_version = re.search(r'^Version\s*:\s*(\S+)', available, re.M)
        if not remote_version or remote_version[1] != version:
            raise RuntimeError('A camera adapter matching the installed PipeWire is not available. No system changes were made.')
        urls = subprocess.check_output(['pacman', '-Sp', '--print-format', '%l', 'pipewire-v4l2'], text=True, timeout=10).splitlines()
        urls = [url for url in urls if '/pipewire-v4l2-' in url and url.endswith('.pkg.tar.zst')]
        if len(urls) != 1:
            raise RuntimeError('Cannot identify the matching camera adapter package.')
        cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'webcamtuner'
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adapter-', dir=cache) as scratch:
            package, signature = Path(scratch) / 'adapter.pkg.tar.zst', Path(scratch) / 'adapter.pkg.tar.zst.sig'
            package.write_bytes(download(urls[0], 2 * 1024 * 1024))
            signature.write_bytes(download(urls[0] + '.sig', 16384))
            checked = subprocess.run(['pacman-key', '--verify', str(signature), str(package)], capture_output=True, text=True, timeout=15)
            if checked.returncode:
                raise RuntimeError('Camera adapter package signature could not be verified. Nothing was enabled.')
            member = 'usr/lib/pipewire-0.3/v4l2/libpw-v4l2.so'
            payload = subprocess.check_output(['bsdtar', '-xOf', str(package), member], timeout=10)
            if len(payload) > 2 * 1024 * 1024 or not payload.startswith(b'\x7fELF'):
                raise RuntimeError('Camera adapter library failed validation.')
            license_text = subprocess.check_output(['bsdtar', '-xOf', str(package), 'usr/share/licenses/pipewire-v4l2/COPYING'], timeout=10)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary = target.with_suffix('.new')
            temporary.write_bytes(payload)
            temporary.chmod(0o600)
            if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(payload).digest():
                raise RuntimeError('Camera adapter library failed storage verification.')
            temporary.replace(target)
            (target.parent / 'COPYING').write_bytes(license_text)
    desktop_dir = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications'
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop = desktop_dir / 'Zoom.desktop'
    if desktop.is_file() and 'webcamtuner-zoom' not in desktop.read_text():
        backup = data_root() / 'backups'
        backup.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(desktop, backup / ('Zoom.desktop.' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')))
    wrapper = Path.home() / '.local/bin/webcamtuner-zoom'
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().with_name('zoom-camera.py')
    wrapper.write_text('#!/bin/bash\nexec python3 ' + shlex.quote(str(script)) + ' "$@"\n')
    wrapper.chmod(0o755)
    vendor = Path('/usr/share/applications/Zoom.desktop')
    if not vendor.is_file():
        raise RuntimeError('Install native Zoom before enabling its camera adapter.')
    content = vendor.read_text()
    executable = str(wrapper).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    content = re.sub(r'^Exec=.*$', lambda _: 'Exec="' + executable + '" %U', content, flags=re.M)
    desktop.write_text(content)
    subprocess.run(['update-desktop-database', str(desktop_dir)], capture_output=True, timeout=10)
    return dict(status(), message='User-only camera adapter enabled for Zoom. Quit and reopen Zoom once to apply it.')


def disable():
    desktop = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications/Zoom.desktop'
    if desktop.is_file() and 'webcamtuner-zoom' in desktop.read_text():
        backups=sorted((data_root()/'backups').glob('Zoom.desktop.*'))
        shutil.copy2(backups[-1] if backups else '/usr/share/applications/Zoom.desktop', desktop)
        subprocess.run(['update-desktop-database', str(desktop.parent)], capture_output=True, timeout=10)
    return dict(status(), message='Zoom now uses its normal native launcher. Restart Zoom to apply.')


def restart_zoom():
    pids = zoom_processes()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 6
    while zoom_processes() and time.monotonic() < deadline:
        time.sleep(.1)
    if zoom_processes():
        raise RuntimeError('Zoom has not exited. Quit it from its menu and try again; it was not force-killed.')
