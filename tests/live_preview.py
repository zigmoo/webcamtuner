"""Bounded live-camera check through the real Quickshell process bridge; records no images."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
scratch.mkdir(parents=True, exist_ok=True)
image = os.environ["WEBCAMTUNER_ACCEPTANCE_IMAGE"]
camera = os.environ.get("WEBCAMTUNER_ACCEPTANCE_CAMERA", "/dev/video0")
settings = {"camera": camera, "crop": {"zoom": 1, "centerX": 0.5, "centerY": 0.5}, "background": {"mode": "image", "imagePath": image}}
harness = scratch / "LivePreviewCheck.qml"
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root / "ui").as_uri() + '''" as Tuner
ShellRoot {
    property int phase: 0
    property int frames: 0
    property int decodedFrames: 0
    property var modes: ["image", "blur", "none"]
    Image {
        source: preview.frameUrl
        cache: false
        onStatusChanged: if (status === Image.Ready) decodedFrames++
    }
    Tuner.ProcessedPreview {
        id: preview
        configuration: ''' + json.dumps(settings) + '''
        Component.onCompleted: active = true
        onFailed: function(message) { console.log("FAIL: " + message); active = false; Qt.quit() }
        onFrameUrlChanged: {
            if (frameUrl === "" || effect !== modes[phase]) return
            frames++
            if (frames < 4) return
            console.log("Verified processed camera frames: " + modes[phase])
            frames = 0; phase++
            if (phase === modes.length) {
                if (decodedFrames === 0) { console.log("FAIL: processed frames did not decode in QML"); active = false; Qt.quit(); return }
                console.log("PASS: live image, blur and original previews; settings updated over stdin")
                active = false; Qt.quit(); return
            }
            var next = JSON.parse(JSON.stringify(configuration))
            next.background.mode = modes[phase]
            configuration = next
        }
    }
    Timer { interval: 15000; running: true; onTriggered: { console.log("FAIL: live preview timed out"); preview.active = false; Qt.quit() } }
}
''')
env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
result = subprocess.run(["qs", "-p", str(harness)], env=env, text=True, capture_output=True, timeout=20)
output = result.stdout + result.stderr
print("\n".join(line for line in output.splitlines() if "Verified processed" in line or "PASS:" in line or "FAIL:" in line or "ERROR" in line))
if result.returncode or "PASS:" not in output or "FAIL:" in output:
    print(output[-5000:])
    raise SystemExit(1)
