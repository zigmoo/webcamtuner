#!/usr/bin/env python3
"""Launch native Zoom with a camera adapter scoped to this process only."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from camera_adapter import library_path


def main():
    environment = dict(os.environ)
    library = library_path()
    if library.is_file():
        existing = environment.get('LD_PRELOAD', '')
        environment['LD_PRELOAD'] = str(library) + (' ' + existing if existing else '')
        # Enumerate all available sources, so physical cameras remain selectable.
        environment.pop('PIPEWIRE_V4L2_TARGET', None)
    os.execve('/usr/bin/zoom', ['/usr/bin/zoom', *sys.argv[1:]], environment)


if __name__ == '__main__':
    main()
