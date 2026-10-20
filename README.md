# WebcamTuner

An Omarchy plugin for persistent webcam framing and appearance profiles. Local camera preview implementation for DIL-3027 (v0.2).

The current preview supports scroll/drag framing, named profiles, persistent crop/background settings, opt-in local camera preview with person segmentation and image replacement/blur, and optional remote discovery through the existing webcam_tool. It does not broadcast a virtual camera yet. The camera stays off until Preview camera is clicked.

## Build and review

Requires Node.js 22+, npm, Bun for bundling, Qt Multimedia, Quickshell, Python 3 with OpenCV/NumPy/Pillow, and Omarchy for the bar plugin. The Apache-2.0 OpenCV Zoo PPHumanSeg model is bundled with a pinned source and SHA256; there are no runtime model downloads. webcam_tool is optional and needed only for remote inventory.

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
qs -p Preview.qml
npm run stage
omarchy plugin validate package/moo.webcamtuner
```

The staged package bundles the controller and has no runtime npm dependency. Copy package/moo.webcamtuner into ~/.config/omarchy/plugins/ for local review, rescan plugins, then enable moo.webcamtuner. Profiles are stored independently under $XDG_CONFIG_HOME/webcamtuner/profiles.json; updates do not replace them.

```bash
bin/webcamtuner doctor --json
bin/webcamtuner read --json
bin/webcamtuner plan --width 1920 --height 1080 --json
bin/webcamtuner remote --host framemoowork --json
```

Remote inspection calls webcam_tool's public CLI and never starts capture. See DESIGN.md for ownership boundaries, source identity, the proposed processing service, and remaining work.

For focused checks, set WEBCAMTUNER_TEST_ROOT to a disposable project-specific directory, run npm test, then python3 tests/ui_smoke.py. The UI smoke check runs offscreen, keeps the camera off, persists a crop through the controller, reloads it, and writes a design screenshot beneath that test directory.

## Backgrounds

Choose Image, then paste a local absolute image path or use Browse. The framing card immediately shows the selected image, with loading/error feedback. Choose your camera and click Preview camera to see your actual foreground over the image. Blur uses the same local person segmentation. Changing the image or effect updates a running preview. Save profile persists these settings with readback verification. Missing or unreadable images disable Save and Preview until corrected.

Preview capture and inference run in a separate Python worker. Capture is opt-in and stops when the panel closes. Frames remain in memory; there are no uploads or camera recordings. The live preview currently requests 720p capture, renders 640x360, and is capped at 15 fps. The output notice remains explicit: meeting apps do not receive these effects until virtual-camera output is implemented.

The background checks are `python3 tests/backgrounds_test.py` and `python3 tests/background_ui.py` with WEBCAMTUNER_TEST_ROOT set. `tests/live_preview.py` is an opt-in, bounded real-camera check that also requires WEBCAMTUNER_ACCEPTANCE_IMAGE; it changes image/blur/original effects over the real Quickshell pipe, then stops capture without recording frames.

## Keyboard and pointer

- Scroll over the preview to zoom; drag it to pan when zoomed.
- Tab and Shift+Tab move through controls; Enter/Space activate focused buttons.
- Escape closes the Omarchy panel when focus is in its editor.

Copyright 2026 Jason Benjamin Ziegler Sr. Apache-2.0. BrioTune by Shawn Yeager was a design reference; no upstream source was copied.
