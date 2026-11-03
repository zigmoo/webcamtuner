#!/usr/bin/env python3
"""Build a dependency-free plugin directory; npm symlinks cannot ship in Omarchy plugins."""
from pathlib import Path
import shutil
import json

root = Path(__file__).resolve().parent.parent
target = root / "package" / "moo.webcamtuner"
target.mkdir(parents=True, exist_ok=True)
version = json.loads((root / "manifest.json").read_text())["version"]
(root / "ui" / "BuildInfo.js").write_text(".pragma library\n// Generated from manifest.json by stage.py.\nvar version = " + json.dumps(version) + ";\n")
for filename in ("manifest.json", "BarWidget.qml", "Service.qml", "Preview.qml"):
    shutil.copy2(root / filename, target / filename)
if (target / "ui").exists():
    shutil.rmtree(target / "ui")
shutil.copytree(root / "ui", target / "ui", dirs_exist_ok=True)
shutil.copytree(root / "assets", target / "assets", dirs_exist_ok=True)
(target / "bin").mkdir(exist_ok=True)
(target / "dist").mkdir(exist_ok=True)
shutil.copy2(root / "bin" / "webcamtuner", target / "bin" / "webcamtuner")
shutil.copy2(root / "bin" / "process_preview.py", target / "bin" / "process_preview.py")
for helper in ("output-control.py", "synthetic-camera.py", "browser-control.py", "background-library.py", "setup-gpu", "runtime-control.py", "snapshot_files.py", "camera_stream.py", "camera_adapter.py", "stream-client.py", "zoom-camera.py", "readback-camera.py"):
    shutil.copy2(root / "bin" / helper, target / "bin" / helper)
shutil.copy2(root / "bin" / "preview-python", target / "bin" / "preview-python")
shutil.copy2(root / "bin" / "setup-preview", target / "bin" / "setup-preview")
if (target / "models").exists():
    shutil.rmtree(target / "models")
shutil.copytree(root / "models", target / "models")
shutil.copy2(root / "dist" / "cli.js", target / "dist" / "cli.js")
for filename in ("README.md", "DESIGN.md", "LICENSE"):
    if (root / filename).exists():
        shutil.copy2(root / filename, target / filename)
print(target)
