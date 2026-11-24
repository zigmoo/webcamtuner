#!/usr/bin/env python3
"""Read a private background preview without reconfiguring the shared camera."""
import json
import sys
import time

sys.dont_write_bytecode = True
from camera_stream import MAX_PREVIEW_RESPONSE, command


def main():
    background = json.loads(sys.argv[1])
    if not command({'operation': 'status'}).get('backgroundPreview'):
        print(json.dumps({'restartRequired': True}), flush=True)
        return
    request = {'operation': 'background-preview', 'background': background}
    while True:
        result = command(request, response_limit=MAX_PREVIEW_RESPONSE)
        if result.get('frame'):
            print(json.dumps(result), flush=True)
        time.sleep(0.15)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({'error': str(error)[:200]}), flush=True)
        raise SystemExit(1)
