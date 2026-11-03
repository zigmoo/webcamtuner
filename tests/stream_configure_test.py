"""Configuration acknowledgements confirm applied output pixels or retain the live source."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from camera_stream import ControlServer


class ConfigureTests(unittest.TestCase):
    def test_acknowledgement_waits_for_applied_source_and_reports_rejection(self):
        scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('cfg-' + uuid.uuid4().hex[:8])
        scratch.mkdir()
        previous = os.environ.get('WEBCAMTUNER_RUNTIME_ROOT')
        os.environ['WEBCAMTUNER_RUNTIME_ROOT'] = str(scratch)
        def receive(value):
            if value['camera'] == '/dev/video101':
                server.emit({'frame': 'test', 'camera': value['camera'], 'configurationRevision': value['configurationRevision']})
            else:
                server.emit({'frame': 'previous', 'camera': '/dev/video101', 'configurationRevision': 7,
                             'configurationError': 'Cannot open camera', 'failedConfigurationRevision': value['configurationRevision']})
        server = ControlServer(receive, lambda: None)
        try:
            for camera, revision, code in [('/dev/video101', 7, 0), ('/dev/video102', 8, 1)]:
                result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'bin/stream-client.py'), '--configure',
                    json.dumps({'camera': camera, 'configurationRevision': revision}), '--wait-applied'], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, code, result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['camera'], '/dev/video101')
                self.assertEqual(value['configurationRevision'], 7)
                self.assertEqual(bool(value.get('error')), bool(code))
        finally:
            server.close()
            if previous is None: os.environ.pop('WEBCAMTUNER_RUNTIME_ROOT', None)
            else: os.environ['WEBCAMTUNER_RUNTIME_ROOT'] = previous


if __name__ == '__main__': unittest.main()
