"""Opt-in signed media preparation with system plugins hidden, without camera capture."""
import json
import os
from pathlib import Path
import sys
import uuid
if os.environ.get('WEBCAMTUNER_ACCEPT_SETUP_DOWNLOADS') != '1':
    raise SystemExit('Set WEBCAMTUNER_ACCEPT_SETUP_DOWNLOADS=1 for the signed media-download check.')
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('media-' + uuid.uuid4().hex[:8])
(scratch / 'empty-plugins').mkdir(parents=True)
os.environ.update(XDG_DATA_HOME=str(scratch / 'data'), XDG_CACHE_HOME=str(scratch / 'cache'),
                  GST_PLUGIN_SYSTEM_PATH_1_0=str(scratch / 'empty-plugins'), GST_PLUGIN_PATH_1_0='', GST_REGISTRY_1_0=str(scratch / 'registry.bin'))
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import media_runtime as media
before = media.probe()
assert not before['ready'] and not before.get('unsupported'), before
media.prepare(lambda message: print(message, flush=True))
after = media.probe()
assert after['ready'], after
folder = Path(os.environ['XDG_DATA_HOME']) / 'webcamtuner/media/current'
assert folder.is_symlink()
proof = json.loads((folder / 'packages.json').read_text())
assert proof and all(p['signatureVerified'] for p in proof)
print(json.dumps({'result': 'PASS', 'missingSystemPlugins': before['missing'], 'readyAfterPrivateSetup': after['ready'],
                  'packages': proof, 'cameraOpened': False, 'fixture': str(scratch)}))
