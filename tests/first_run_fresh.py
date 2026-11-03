"""Opt-in real preparation in empty XDG folders, without camera capture or system changes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

if os.environ.get('WEBCAMTUNER_ACCEPT_SETUP_DOWNLOADS') != '1':
    raise SystemExit('Set WEBCAMTUNER_ACCEPT_SETUP_DOWNLOADS=1 for the isolated package-download check.')
root = Path(__file__).resolve().parents[1]
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('fresh-' + uuid.uuid4().hex[:8])
clone = scratch / 'plugin'; clone.mkdir(parents=True)
for name in ('bin', 'src', 'models'):
    shutil.copytree(root / name, clone / name, ignore=shutil.ignore_patterns('__pycache__'))
for name in ('package.json', 'bun.lock'):
    shutil.copy2(root / name, clone / name)
os.environ.update(XDG_DATA_HOME=str(scratch / 'data'), XDG_CACHE_HOME=str(scratch / 'cache'), WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
os.environ.pop('WEBCAMTUNER_RUNTIME_PYTHON', None)
sys.dont_write_bytecode = True
sys.path.insert(0, str(clone / 'bin'))
spec = importlib.util.spec_from_file_location('first_run_fresh', clone / 'bin/first-run.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
before = setup.status()
assert not before['ready'] and not before['controllerReady']
assert not (clone / 'dist').exists()
# This fixture owns different runtime/cache paths from the live app. The active
# output guard is tested separately; no live libraries or service are touched.
setup.ensure_idle = lambda: None
value = setup.prepare()
assert value['ready'], value
assert (scratch / 'data/webcamtuner/runtime').is_symlink()
runtime = (scratch / 'data/webcamtuner/runtime').resolve()
owned = subprocess.check_output([str(runtime / 'bin/python'), '-c', 'import cv2,numpy,PIL,onnxruntime,json;print(json.dumps([m.__file__ for m in (cv2,numpy,PIL,onnxruntime)]))'], text=True)
assert all(Path(path).is_relative_to(runtime) for path in json.loads(owned)), owned
assert not (clone / 'node_modules').exists() and not (clone / 'dist').exists()
read = json.loads(subprocess.check_output([str(clone / 'bin/webcamtuner'), 'read', '--json'], text=True))
assert read['revision'] == 0
backgrounds = json.loads(subprocess.check_output([str(clone / 'bin/webcamtuner'), 'backgrounds', '--json'], text=True))
assert backgrounds['items'] == []
print(json.dumps({'result': 'PASS', 'sourceCheckout': 'no dist/no node_modules', 'ready': value['ready'],
                  'profileReadback': True, 'backgroundLibraryReadback': True, 'cameraOpened': False, 'fixture': str(scratch)}))
