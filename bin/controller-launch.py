#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
from controller_runtime import launch

try:
    launch(sys.argv[1:])
except (OSError, ValueError, RuntimeError) as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
