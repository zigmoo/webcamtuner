#!/usr/bin/env python3
"""GUI readiness and user-owned preparation; never starts camera capture."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import uuid
from controller_runtime import ROOT, controller, prepare as prepare_controller
from media_runtime import environment, probe as media_probe, prepare as prepare_media
from camera_adapter import data_root

PACKAGES = ['opencv-python-headless==5.0.0.93', 'numpy==2.5.4', 'Pillow==13.0.0']


def progress(message):
    print(json.dumps({'progress': message}), flush=True)


def runtime_probe(path):
    if not path.is_file():
        return False
    code = "import cv2,numpy,PIL,onnxruntime;assert 'CPUExecutionProvider' in onnxruntime.get_available_providers()"
    try:
        result = subprocess.run([str(path), '-c', code], env=environment(), capture_output=True, timeout=20)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def model_ready():
    try:
        path = ROOT / 'models/rvm/rvm_mobilenetv3_fp32.onnx'
        expected = json.loads((path.parent / 'provenance.json').read_text())
        return path.stat().st_size == expected['size'] and hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']
    except (OSError, KeyError, ValueError):
        return False


def session_ready():
    if not all(shutil.which(name) for name in ('systemctl', 'systemd-run', 'pw-dump')):
        return False
    return subprocess.run(['pw-dump'], capture_output=True, timeout=5).returncode == 0


def status():
    media = media_probe()
    cpu = runtime_probe(data_root() / 'runtime/bin/python')
    gpu = (data_root() / 'runtime-gpu/enabled.json').is_file() and runtime_probe(data_root() / 'runtime-gpu/bin/python')
    checks = [
        {'id': 'controller', 'label': 'Profiles and background library', 'ready': controller() is not None},
        {'id': 'runtime', 'label': 'Local image processing', 'ready': cpu or gpu},
        {'id': 'model', 'label': 'Bundled person-matting model', 'ready': model_ready()},
        {'id': 'media', 'label': 'Desktop video transport', 'ready': media['ready'], 'detail': media['message']},
        {'id': 'session', 'label': 'User PipeWire session', 'ready': session_ready()},
    ]
    ready = all(item['ready'] for item in checks)
    return {'ready': ready, 'controllerReady': checks[0]['ready'], 'checks': checks,
            'directory': str(data_root()), 'message': 'WebcamTuner is ready. Choose your camera, then Start camera output.' if ready else 'Prepare WebcamTuner to complete the steps below.'}


def ensure_idle():
    for unit in ('webcamtuner-output.service', 'webcamtuner-test.service'):
        result = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True, timeout=5)
        if result.stdout.strip() in ('active', 'activating'):
            raise RuntimeError('Stop camera output in Setup before preparing or repairing the runtime. Your current feed has been kept running.')


def prepare_runtime(gpu=False):
    base = data_root() / 'runtimes'
    base.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = base / (('gpu-' if gpu else 'cpu-') + uuid.uuid4().hex[:12])
    progress('Preparing local GPU libraries…' if gpu else 'Preparing local image-processing libraries…')
    subprocess.run(['python3', '-m', 'venv', '--system-site-packages', str(target)], check=True, timeout=30)
    python = target / 'bin/python'
    packages = PACKAGES + [('onnxruntime-gpu[cuda,cudnn]' if gpu else 'onnxruntime') + '==1.31.0']
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--only-binary=:all:', '--ignore-installed',
                    '--index-url', 'https://pypi.org/simple', *packages], env=environment(), check=True, timeout=900)
    progress('Verifying person matting with generated pixels…')
    code = '''import importlib.util,sys
from pathlib import Path
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('wct_preview',Path(sys.argv[1])/'bin/process_preview.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ort.disable_telemetry_events()
s=m.Segmenter();a=s.mask(m.np.zeros((360,640,3),dtype=m.np.uint8))
assert m.np.isfinite(a).all()
if sys.argv[2]=='gpu':assert s.provider=='CUDAExecutionProvider','GPU unavailable; the previous runtime was preserved.'
'''
    subprocess.run([str(python), '-c', code, str(ROOT), 'gpu' if gpu else 'cpu'], env=dict(environment(), WEBCAMTUNER_FORCE_CPU='0' if gpu else '1'), check=True, timeout=60)
    if gpu:
        (target / 'enabled.json').write_text(json.dumps({'provider': 'CUDAExecutionProvider', 'onnxruntime': '1.31.0'}))
        (target / 'enabled.json').chmod(0o600)
    link = data_root() / ('runtime-gpu' if gpu else 'runtime')
    pending = link.with_name(link.name + '-' + uuid.uuid4().hex[:8])
    pending.symlink_to(target.relative_to(data_root()), target_is_directory=True)
    if link.exists() and not link.is_symlink():
        link.rename(link.with_name(link.name + '-previous-' + uuid.uuid4().hex[:8]))
    pending.replace(link)
    progress('Local GPU runtime verified.' if gpu else 'Local processing runtime verified.')


def prepare(gpu=False, repair=False):
    base = data_root()
    base.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (base / 'setup.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Setup is already running in another WebcamTuner window.')
        ensure_idle()
        if not model_ready():
            raise RuntimeError('The bundled model is missing or damaged. Reinstall WebcamTuner from its source repository.')
        prepare_controller(progress)
        prepare_media(progress)
        if gpu or repair or not runtime_probe(base / 'runtime/bin/python'):
            prepare_runtime(gpu)
        result = status()
        if not result['ready']:
            raise RuntimeError('Preparation finished, but a desktop prerequisite is unavailable. Review Check readiness; no system files were changed.')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'prepare', 'repair', 'gpu'])
    args = parser.parse_args()
    print(json.dumps(status() if args.action == 'status' else prepare(args.action == 'gpu', args.action == 'repair')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)[:1200]}), flush=True)
        raise SystemExit(1)
