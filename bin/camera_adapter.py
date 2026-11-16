"""Install and scope the native-camera adapter entirely to the signed-in user."""
import datetime
from contextlib import contextmanager
import fcntl
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

ZOOM_DESKTOP = Path('/usr/share/applications/Zoom.desktop')
NORMAL_LAUNCHER = 'X-WebcamTuner-NormalLauncher=true'


def data_root():
    root = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'webcamtuner'
    if not root.is_absolute():
        raise ValueError('XDG_DATA_HOME must be an absolute path.')
    return root


def package_version():
    result = subprocess.check_output(['pacman', '-Q', 'libpipewire'], text=True, timeout=5)
    return result.split()[1]


def library_path(version=None):
    version = re.sub('[^a-zA-Z0-9._-]', '_', version or package_version())
    return data_root() / 'adapters' / version / 'libpw-v4l2.so'


def desktop_path():
    return data_root().parent / 'applications/Zoom.desktop'


def wrapper_path():
    return Path.home() / '.local/bin/webcamtuner-zoom'


def library_ready(path):
    if not path.is_file():
        return False
    with path.open('rb') as library:
        return library.read(4) == b'\x7fELF'


@contextmanager
def adapter_update_lock():
    root = data_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / 'adapter-setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Camera adapter preparation is already running. Its readiness will refresh automatically.')
        yield


def atomic_text(path, text, mode=0o600):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(text)
    temporary.chmod(mode)
    temporary.replace(path)
    if path.read_text() != text:
        raise RuntimeError('Camera adapter launcher failed storage verification.')


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
    version = package_version()
    path = library_path(version)
    processes = zoom_processes()
    loaded = False
    for pid in processes:
        try:
            maps = (Path('/proc') / str(pid) / 'maps').read_text().splitlines()
            if any(line.split(None, 5)[-1] == str(path.resolve()) for line in maps):
                loaded = True
        except OSError:
            pass
    desktop = desktop_path()
    content = desktop.read_text() if desktop.is_file() else ''
    enabled = 'webcamtuner-zoom' in content and wrapper_path().is_file()
    ready = library_ready(path)
    return {'ready': ready, 'enabled': enabled, 'zoomRunning': bool(processes), 'adapterLoaded': loaded,
            'restartRequired': bool(processes) and enabled and not loaded,
            'library': str(path), 'version': version, 'zoomInstalled': ZOOM_DESKTOP.is_file(),
            'normalLauncher': NORMAL_LAUNCHER in content.splitlines()}


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


def prepare_library():
    target = library_path()
    if not library_ready(target):
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
    return target


def install_launcher():
    if not ZOOM_DESKTOP.is_file():
        raise RuntimeError('Install native Zoom before enabling its camera launcher.')
    desktop = desktop_path()
    desktop_dir = desktop.parent
    desktop_dir.mkdir(parents=True, exist_ok=True)
    if desktop.is_file() and 'webcamtuner-zoom' not in desktop.read_text():
        backup = data_root() / 'backups'
        backup.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(desktop, backup / ('Zoom.desktop.' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    wrapper = wrapper_path()
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().with_name('zoom-camera.py')
    atomic_text(wrapper, '#!/bin/bash\nexec python3 ' + shlex.quote(str(script)) + ' "$@"\n', 0o755)
    content = ZOOM_DESKTOP.read_text()
    executable = str(wrapper).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    content = re.sub(r'^Exec=.*$', lambda _: 'Exec="' + executable + '" %U', content, flags=re.M)
    atomic_text(desktop, content)
    subprocess.run(['update-desktop-database', str(desktop_dir)], capture_output=True, timeout=10)


def ensure():
    """Prepare readback for every user; scope Zoom integration when installed."""
    with adapter_update_lock():
        prepare_library()
        value = status()
        if value['zoomInstalled'] and not value['normalLauncher'] and not value['enabled']:
            install_launcher()
    value = status()
    return dict(value, message='Camera adapter is ready in your home directory.')


def setup():
    with adapter_update_lock():
        prepare_library()
        install_launcher()
    value = status()
    return dict(value, message='Camera adapter enabled. Restart Zoom to load it.' if value['restartRequired'] else 'Camera adapter enabled. Open Zoom and select WebcamTuner.')


def disable():
    with adapter_update_lock():
        desktop = desktop_path()
        content = None
        if desktop.is_file() and 'webcamtuner-zoom' in desktop.read_text():
            backups = sorted((data_root()/'backups').glob('Zoom.desktop.*'))
            content = (backups[-1] if backups else ZOOM_DESKTOP).read_text()
        elif desktop.is_file():
            content = desktop.read_text()
        elif ZOOM_DESKTOP.is_file():
            content = ZOOM_DESKTOP.read_text()
        if content is not None:
            desktop.parent.mkdir(parents=True, exist_ok=True)
            content = '\n'.join(line for line in content.splitlines() if not line.startswith('X-WebcamTuner-NormalLauncher='))
            atomic_text(desktop, content.rstrip() + '\n' + NORMAL_LAUNCHER + '\n')
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
