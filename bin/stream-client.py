#!/usr/bin/env python3
"""Bridge private camera IPC to the existing QML JSON frame interface."""
import argparse
import json
import socket
import sys
sys.dont_write_bytecode = True
import threading
import time
from camera_stream import MAX_COMMAND, command, connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure')
    parser.add_argument('--wait-applied', action='store_true')
    args = parser.parse_args()
    if args.configure:
        requested = json.loads(args.configure)
        result = command(requested)
        if args.wait_applied:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                result = command({'operation': 'status'})
                if result.get('failedConfigurationRevision', -1) >= requested.get('configurationRevision', 0):
                    print(json.dumps(dict(result, error=result.get('configurationError', 'Camera settings were not applied.'))))
                    raise SystemExit(1)
                if result.get('camera') == requested['camera'] and result.get('configurationRevision', -1) >= requested.get('configurationRevision', 0):
                    break
                time.sleep(.1)
            else:
                print(json.dumps(dict(result, error='The camera did not confirm the new settings.')))
                raise SystemExit(1)
        print(json.dumps(result))
        return
    with connect() as connection:
        connection.sendall(b'{"operation":"subscribe"}\n')
        connection.settimeout(None)
        def requests():
            try:
                for line in sys.stdin:
                    if len(line) > MAX_COMMAND:
                        raise ValueError('Camera command exceeds its size limit.')
                    value = json.loads(line)
                    if value.get('operation') != 'snapshot':
                        continue
                    connection.sendall(line.encode())
            except (OSError, ValueError):
                pass
            finally:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        threading.Thread(target=requests, daemon=True).start()
        with connection.makefile('rb') as incoming:
            while True:
                line = incoming.readline(1048577)
                if not line:
                    raise RuntimeError('Camera output stopped. Start output again in Setup.')
                if len(line) > 1048576:
                    raise RuntimeError('Preview frame exceeds its size limit.')
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({'error': str(error)[:500]}), flush=True)
        raise SystemExit(1)
