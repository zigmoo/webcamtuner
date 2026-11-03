"""Build and launch the profile controller from a source checkout in user storage."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import re

ROOT = Path(__file__).resolve().parents[1]
BUN_VERSION = '1.4.4'


def cache_root():
    path = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'webcamtuner'
    if not path.is_absolute():
        raise ValueError('XDG_CACHE_HOME must be an absolute path.')
    return path


def fingerprint():
    digest = hashlib.sha256(str(ROOT).encode())
    for path in [ROOT / 'package.json', ROOT / 'bun.lock', *sorted((ROOT / 'src').glob('*.ts'))]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:24]


def installed_runner(name):
    candidate = shutil.which(name)
    if candidate:
        candidate = Path(candidate).resolve()
        if 'shims' not in candidate.parts and candidate.name != 'mise':
            return str(candidate)
    # A lookup must never trigger a lazy download.
    if shutil.which('mise'):
        result = subprocess.run(['mise', 'which', name], cwd='/', env=dict(os.environ, MISE_OFFLINE='1', MISE_AUTO_INSTALL='0'), capture_output=True, text=True, timeout=5)
        candidate = Path(result.stdout.strip())
        if result.returncode == 0 and candidate.is_absolute() and candidate.is_file():
            return str(candidate.resolve())
    return None


def controller():
    bundle = ROOT / 'dist/cli.js'
    if bundle.is_file():
        runner = installed_runner('node')
        if runner:
            try:
                version = subprocess.check_output([runner, '--version'], text=True, timeout=5).strip()
                if not re.fullmatch(r'v\d+\.\d+\.\d+', version) or int(version[1:].split('.')[0]) < 22:
                    runner = None
            except (OSError, subprocess.SubprocessError):
                runner = None
        runner = runner or installed_runner('bun')
        if runner:
            return runner, bundle
    try:
        directory = cache_root() / 'controllers' / fingerprint()
        marker = json.loads((directory / 'ready.json').read_text())
        bundle, runner = directory / 'dist/cli.js', Path(marker['runner'])
        if runner.is_absolute() and runner.is_file() and bundle.is_file() and (directory / 'bin').resolve() == ROOT / 'bin':
            return str(runner), bundle
    except (OSError, KeyError, ValueError):
        pass
    return None


def prepare(progress):
    existing = controller()
    if existing:
        progress('Profile controller is ready.')
        return
    progress('Preparing the profile controller…')
    runner = installed_runner('bun')
    if not runner or subprocess.check_output([runner, '--version'], text=True, timeout=5).strip() != BUN_VERSION:
        if not shutil.which('mise'):
            raise RuntimeError('The Omarchy tool manager (mise) is missing. This installation is not supported yet.')
        subprocess.run(['mise', 'install', 'bun@' + BUN_VERSION], check=True, timeout=300)
        directory = subprocess.check_output(['mise', 'where', 'bun@' + BUN_VERSION], text=True, timeout=5).strip()
        runner = str(Path(directory) / 'bin/bun')
    base = cache_root() / 'controllers'
    base.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = base / fingerprint()
    with tempfile.TemporaryDirectory(prefix='build-', dir=base) as temporary:
        work = Path(temporary)
        for name in ('package.json', 'bun.lock'):
            shutil.copy2(ROOT / name, work / name)
        shutil.copytree(ROOT / 'src', work / 'src')
        environment = dict(os.environ, BUN_INSTALL_CACHE_DIR=str(cache_root() / 'bun'), DO_NOT_TRACK='1')
        subprocess.run([runner, 'install', '--ignore-scripts', '--frozen-lockfile', '--registry', 'https://registry.npmjs.org'], cwd=work, env=environment, check=True, timeout=300)
        subprocess.run([runner, 'build', 'src/cli.ts', '--target', 'node', '--outfile', 'dist/cli.js'], cwd=work, env=environment, check=True, timeout=60)
        (work / 'bin').symlink_to(ROOT / 'bin', target_is_directory=True)
        # Doctor reads capabilities and does not create or change a profile.
        checked = subprocess.check_output([runner, str(work / 'dist/cli.js'), 'doctor', '--json'], text=True, timeout=10)
        if not json.loads(checked).get('profilePersistence'):
            raise RuntimeError('The profile controller failed its readiness check.')
        shutil.rmtree(work / 'node_modules')
        (work / 'ready.json').write_text(json.dumps({'runner': runner}))
        (work / 'ready.json').chmod(0o600)
        if target.exists():
            raise RuntimeError('A controller build already exists; retry Check readiness.')
        work.rename(target)
    progress('Profile controller built and verified.')


def launch(arguments):
    value = controller()
    if not value:
        raise RuntimeError('Open WebcamTuner → Setup and click Prepare WebcamTuner.')
    runner, bundle = value
    os.execv(runner, [runner, str(bundle), *arguments])
