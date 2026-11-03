"""Private output IPC stays bounded and independent of preview subscribers."""
import json
import os
from pathlib import Path
import socket
import sys
import time
import unittest
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from camera_stream import ControlServer, command, connect


class StreamIPC(unittest.TestCase):
    def setUp(self):
        self.directory = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('ipc-' + uuid.uuid4().hex[:8])
        self.directory.mkdir()
        os.environ['WEBCAMTUNER_RUNTIME_ROOT'] = str(self.directory)
        self.received = []
        self.server = ControlServer(self.received.append, lambda: None)

    def tearDown(self):
        self.server.close()

    def test_private_socket_single_owner(self):
        self.assertEqual(self.server.path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(BlockingIOError):
            ControlServer(self.received.append, lambda: None)
        self.assertEqual(command({'operation':'status'})['state'], 'starting')

    def test_configuration_and_latest_frame(self):
        self.assertTrue(command({'camera':'/dev/video99', 'configurationRevision':7})['accepted'])
        self.assertEqual(self.received[0]['configurationRevision'], 7)
        for n in range(100):
            self.server.emit({'frame': str(n), 'configurationRevision':7})
        with connect() as subscriber:
            subscriber.sendall(b'{"operation":"subscribe"}\n')
            with subscriber.makefile('rb') as incoming:
                frame = json.loads(incoming.readline())
                self.assertEqual(frame['frame'], '99')
        self.assertTrue(command({'operation':'status'})['published'])
        self.assertNotIn('frame', command({'operation':'status'}))

    def test_slow_preview_does_not_backpressure_producer(self):
        with connect() as subscriber:
            subscriber.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            subscriber.sendall(b'{"operation":"subscribe"}\n')
            began = time.monotonic()
            for n in range(100):
                self.server.emit({'frame':'x'*400000, 'sequence':n})
            self.assertLess(time.monotonic()-began, 1)
            self.assertTrue(command({'operation':'status'})['published'])
            self.assertEqual(self.server.latest['sequence'], 99)
        self.assertTrue(command({'operation':'status'})['published'])

    def test_oversized_request_rejected(self):
        with self.assertRaises(ValueError):
            command({'camera':'x'*17000})


if __name__=='__main__':
    unittest.main()
