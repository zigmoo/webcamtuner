#!/usr/bin/env python3
"""Build a dependency-free plugin directory; npm symlinks cannot ship in Omarchy plugins."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
target = root / "package" / "moo.webcamtuner"
target.mkdir(parents=True, exist_ok=True)
for filename in ("manifest.json", "BarWidget.qml", "Preview.qml"):
    shutil.copy2(root / filename, target / filename)
shutil.copytree(root / "ui", target / "ui", dirs_exist_ok=True)
(target / "bin").mkdir(exist_ok=True)
(target / "dist").mkdir(exist_ok=True)
shutil.copy2(root / "bin" / "webcamtuner", target / "bin" / "webcamtuner")
shutil.copy2(root / "dist" / "cli.js", target / "dist" / "cli.js")
for filename in ("README.md", "DESIGN.md", "LICENSE"):
    if (root / filename).exists():
        shutil.copy2(root / filename, target / filename)
print(target)
