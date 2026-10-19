# WebcamTuner

An Omarchy plugin for persistent webcam framing and appearance profiles. Initial design prototype for DIL-3027.

The current preview supports scroll/drag framing, named profiles, persistent crop/background preferences, opt-in local camera preview, and optional remote discovery through the existing webcam_tool. It does not broadcast a virtual camera or process backgrounds yet. The camera stays off until Preview camera is clicked.

## Build and review

Requires Node.js 22+, npm, Bun for bundling, Qt Multimedia, Quickshell, and Omarchy for the bar plugin. webcam_tool is optional and needed only for remote inventory.

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

## Keyboard and pointer

- Scroll over the preview to zoom; drag it to pan when zoomed.
- Tab and Shift+Tab move through controls; Enter/Space activate focused buttons.
- Escape closes the Omarchy panel when focus is in its editor.

Copyright 2026 Jason Benjamin Ziegler Sr. Apache-2.0. BrioTune by Shawn Yeager was a design reference; no upstream source was copied.
