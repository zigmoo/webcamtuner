#!/usr/bin/env python3
"""Read user-local preview runtime status and select the existing CPU runtime."""
import argparse
import json
import os
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['status','cpu'])
args=parser.parse_args()
root=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'webcamtuner'
marker=root/'runtime-gpu/enabled.json'
if args.action=='cpu':marker.unlink(missing_ok=True)
try:
    result=subprocess.run(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],capture_output=True,text=True,timeout=5)
    device=result.stdout.strip() if result.returncode==0 else ''
except (OSError,subprocess.TimeoutExpired):device=''
print(json.dumps({'gpuEnabled':marker.is_file(),'gpu':device,'message':'GPU acceleration is selected for the next camera start.' if marker.is_file() else 'CPU processing is selected.'}))
