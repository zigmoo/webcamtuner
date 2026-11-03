"""Prepare only missing GStreamer plugins, extracted from signed matching Arch packages."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from camera_adapter import data_root, download

ELEMENTS = ('appsrc', 'appsink', 'videoconvert', 'pipewiresrc', 'pipewiresink', 'v4l2src')
PLUGINS = {
    'appsrc': ('gst-plugins-base-libs', 'gst-plugins-base-libs', 'libgstapp.so'),
    'appsink': ('gst-plugins-base-libs', 'gst-plugins-base-libs', 'libgstapp.so'),
    'videoconvert': ('gst-plugins-base-libs', 'gst-plugins-base-libs', 'libgstvideoconvertscale.so'),
    'pipewiresrc': ('gst-plugin-pipewire', 'libpipewire', 'libgstpipewire.so'),
    'pipewiresink': ('gst-plugin-pipewire', 'libpipewire', 'libgstpipewire.so'),
    'v4l2src': ('gst-plugins-good', 'gst-plugins-base-libs', 'libgstvideo4linux2.so'),
}


def environment():
    env = dict(os.environ, ORT_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', PYTHONDONTWRITEBYTECODE='1')
    folder = data_root() / 'media/current'
    if folder.is_dir():
        env['GST_PLUGIN_PATH_1_0'] = str(folder.resolve()) + (os.pathsep + env['GST_PLUGIN_PATH_1_0'] if env.get('GST_PLUGIN_PATH_1_0') else '')
        if (folder / 'lib').is_dir():
            env['LD_LIBRARY_PATH'] = str(folder.resolve() / 'lib') + (os.pathsep + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return env


def probe():
    code = '''import json,gi
gi.require_version('Gst','1.0')
from gi.repository import Gst
Gst.init(None)
names='appsrc appsink videoconvert pipewiresrc pipewiresink v4l2src'.split()
print(json.dumps({'missing':[n for n in names if Gst.ElementFactory.make(n) is None]}))'''
    result = subprocess.run(['python3', '-c', code], env=environment(), capture_output=True, text=True, timeout=15)
    if result.returncode:
        return {'ready': False, 'missing': list(ELEMENTS), 'unsupported': True,
                'message': 'The Omarchy Python/GStreamer desktop libraries are unavailable. This desktop version is not supported yet.'}
    missing = json.loads(result.stdout)['missing']
    return {'ready': not missing, 'missing': missing, 'unsupported': False,
            'message': 'Desktop media components verified.' if not missing else 'Missing video plugins: ' + ', '.join(missing)}


def prepare(progress):
    before = probe()
    if before.get('unsupported'):
        raise RuntimeError(before['message'])
    if before['ready']:
        progress(before['message'])
        return
    base = data_root() / 'media'
    base.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = base / ('plugins-' + uuid.uuid4().hex[:12])
    target.mkdir(mode=0o700)
    current = base / 'current'
    if current.is_dir():
        for path in current.glob('*.so'):
            (target / path.name).write_bytes(path.read_bytes())
        if (current / 'lib').is_dir():
            import shutil
            shutil.copytree(current / 'lib', target / 'lib')
    grouped = {}
    provenance = []
    for name in before['missing']:
        package, anchor, member = PLUGINS[name]
        grouped.setdefault((package, anchor), set()).add(member)
    if 'v4l2src' in before['missing']:
        grouped[('v4l-utils', None)] = {'lib/libv4l2.so.0', 'lib/libv4lconvert.so.0'}
    for (package, anchor), members in grouped.items():
        progress('Preparing signed desktop video components: ' + package + '…')
        version = subprocess.check_output(['pacman', '-Q', anchor], text=True, timeout=5).split()[1] if anchor else None
        info = subprocess.check_output(['pacman', '-Si', package], text=True, timeout=10)
        remote = re.search(r'^Version\s*:\s*(\S+)', info, re.M)
        if not remote or (version is not None and remote[1] != version):
            raise RuntimeError('A signed ' + package + ' matching this desktop is unavailable. Your existing runtime was preserved.')
        urls = subprocess.check_output(['pacman', '-Sp', '--print-format', '%l', package], text=True, timeout=10).splitlines()
        urls = [url for url in urls if '/' + package + '-' in url and url.endswith('.pkg.tar.zst')]
        if len(urls) != 1:
            raise RuntimeError('Cannot identify the matching signed video package.')
        with tempfile.TemporaryDirectory(prefix='download-', dir=base) as scratch:
            archive = Path(scratch) / 'media.pkg.tar.zst'
            signature = Path(scratch) / 'media.pkg.tar.zst.sig'
            archive.write_bytes(download(urls[0], 12 * 1024 * 1024))
            signature.write_bytes(download(urls[0] + '.sig', 16384))
            checked = subprocess.run(['pacman-key', '--verify', str(signature), str(archive)], capture_output=True, timeout=15)
            if checked.returncode:
                raise RuntimeError('Video package signature failed verification. Nothing was enabled.')
            for member in members:
                archive_member = 'usr/lib/' + member[4:] + '.0.0' if member.startswith('lib/') else 'usr/lib/gstreamer-1.0/' + member
                payload = subprocess.check_output(['bsdtar', '-xOf', str(archive), archive_member], timeout=10)
                if not payload.startswith(b'\x7fELF') or len(payload) > 8 * 1024 * 1024:
                    raise RuntimeError('Video plugin failed validation.')
                (target / member).parent.mkdir(mode=0o700, exist_ok=True)
                (target / member).write_bytes(payload)
                (target / member).chmod(0o600)
            provenance.append({'package': package, 'version': remote[1], 'url': urls[0], 'signatureVerified': True})
            names = subprocess.check_output(['bsdtar', '-tf', str(archive)], text=True, timeout=10).splitlines()
            for name in names:
                if name.startswith('usr/share/licenses/' + package + '/') and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', name.rsplit('/', 1)[-1]):
                    license_data = subprocess.check_output(['bsdtar', '-xOf', str(archive), name], timeout=10)
                    if len(license_data) <= 256 * 1024:
                        licenses = target / 'licenses' / package
                        licenses.mkdir(parents=True, mode=0o700, exist_ok=True)
                        (licenses / name.rsplit('/', 1)[-1]).write_bytes(license_data)
    # Verify the candidate independently before switching the user-local plugin path.
    env = dict(environment(), GST_PLUGIN_PATH_1_0=str(target))
    if (target / 'lib').is_dir():env['LD_LIBRARY_PATH']=str(target / 'lib')+(os.pathsep+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    checked = subprocess.run(['python3', '-c', "import gi;gi.require_version('Gst','1.0');from gi.repository import Gst;Gst.init(None);assert all(Gst.ElementFactory.make(n) is not None for n in 'appsrc appsink videoconvert pipewiresrc pipewiresink v4l2src'.split())"], env=env, capture_output=True, timeout=15)
    if checked.returncode:
        raise RuntimeError('Prepared video components failed validation. The previous runtime is unchanged.')
    (target / 'packages.json').write_text(json.dumps(provenance))
    pending = base / ('current-' + uuid.uuid4().hex[:8])
    pending.symlink_to(target.name, target_is_directory=True)
    pending.replace(current)
    progress('User-local desktop video components verified.')
