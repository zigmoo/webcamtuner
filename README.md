# WebcamTuner

Public source: [zigmoo/webcamtuner](https://github.com/zigmoo/webcamtuner). Application source is licensed under Apache-2.0; the bundled Robust Video Matting model retains its separate GPL-3.0 license and provenance in models/rvm/. Build and stage the source as described below before installing the plugin.

An Omarchy plugin for persistent webcam framing and appearance profiles. Local camera preview implementation for DIL-3027 (v0.6).

The current preview supports scroll/drag framing, named profiles, persistent crop/background settings, local camera preview with a saved autostart choice with person segmentation and image replacement/blur, and optional remote discovery through the existing webcam_tool. It does not broadcast a virtual camera yet. Opening WebcamTuner starts the remembered camera preview by default. Uncheck Autostart camera below the restore-profile option to start with the camera off instead; Preview camera remains available manually. The bar icon opens a normal floating window; drag the fixed title bar or its grip to move it and resize it with the window manager.

## Build and review

Requires Node.js 22+, npm, Bun for bundling, Qt Multimedia, Quickshell, Python 3 with OpenCV/NumPy/Pillow, and Omarchy for the bar plugin. The GPL-3.0 Robust Video Matting MobileNetV3 model is bundled with its upstream license, release URL, and SHA256. Application source remains Apache-2.0; the model has its own GPL-3.0 license. Run npm run setup:preview once to prepare a user-local ONNX Runtime environment. There are no runtime model downloads. webcam_tool is optional and needed only for remote inventory.

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm run setup:preview
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

## Mirror and window controls

Mirror is on by default, the opposite of the original unmirrored preview. Older profiles without a mirror field adopt the new default; an explicit saved choice is preserved. The checkbox saves its setting and verifies readback before changing the camera image. Mirror changes preserve other unsaved draft settings. Camera pixels and their matte are reflected together; an image background keeps its original orientation. Dragging the framed camera continues to follow the pointer in either mode.

The plugin opens a native Quickshell floating window. Drag the WebcamTuner heading to move it, or use normal window-manager move/resize controls. Clicking elsewhere does not dismiss it. The native Close button and Escape hide the window and stop the current preview. The standalone Preview.qml uses the same window component.

## Virtual-camera output route

The current build is still a local preview. To publish it to webcam consumers, use Linux v4l2loopback plus one persistent user-session producer:

1. Install v4l2loopback-dkms against matching kernel headers. On the current host, DKMS and running-kernel headers are present, but v4l2loopback is not installed.
2. Create a loopback device labelled WebcamTuner with exclusive_caps=1 so Chromium/WebRTC sees capture-only capabilities after a producer attaches. This requires a one-time privileged module setup.
3. Move capture and composition into one user service, which applies crop, mirror and backgrounds, then writes processed frames to that device (for example via FFmpeg's V4L2 output). The panel must preview that same producer rather than opening the physical camera twice.
4. Keep the producer alive when the controls window closes; expose explicit output start/stop and readiness/error states. A missing effect must never quietly switch output to the unprocessed room.
5. Select WebcamTuner once in each consumer, including Teams, Zoom or Meet. Validate Linux V4L2 capture and actual browser/app enumeration; sandbox permissions and supported formats remain part of compatibility testing.

Driver reference: https://github.com/v4l2loopback/v4l2loopback . Kernel installation, persistent publishing, and meeting-app integration are not implemented by this UI update.

## Backgrounds

Choose Image, then paste a local absolute image path or use Browse. The framing card immediately shows the selected image, with loading/error feedback. Choose your camera and click Preview camera to see your actual foreground over the image. Blur uses the same local person segmentation. Changing the image or effect updates a running preview. Save profile persists these settings with readback verification. Missing or unreadable images disable Save and Preview until corrected.

Preview capture and inference run in a separate Python worker. Capture starts on opening when the saved Autostart camera option is enabled, and stops when the window closes. Frames remain in memory; there are no uploads or camera recordings. Capture negotiates the largest supported 16:9 mode up to UHD: verified BRIO 3840x2160/30 and Framework 1920x1080/30. Framing uses that full-resolution source. The panel scales the processed crop to at most 960x540 and caps preview presentation at 15 fps; capture mode and preview size are shown separately. A 2x crop from 4K retains 1920x1080 source pixels. Recurrent video matting analyzes the full view before cropping, and the renderer retains the last frame while decoding its successor. The output notice remains explicit: meeting apps do not receive these effects until virtual-camera output is implemented.

The background checks are `bin/preview-python tests/backgrounds_test.py` and `python3 tests/background_ui.py` with WEBCAMTUNER_TEST_ROOT set. `tests/live_preview.py` is an opt-in, bounded real-camera check that also requires WEBCAMTUNER_ACCEPTANCE_IMAGE; it changes image/blur/original effects over the real Quickshell pipe, then stops capture without recording frames.

## Keyboard and pointer

- Scroll over the preview to zoom; drag it to pan when zoomed.
- Tab and Shift+Tab move through controls; Enter/Space activate focused buttons.
- Escape closes the Omarchy panel when focus is in its editor.

Copyright 2026 Jason Benjamin Ziegler Sr. Application source: Apache-2.0; bundled RVM model: GPL-3.0 (models/rvm/LICENSE). BrioTune by Shawn Yeager was a design reference; no upstream source was copied.

## Automatic webcam selection (v0.5)

WebcamTuner remembers camera selections immediately, independently of the profile Save button. On startup it restores the most recently selected webcam using its stable USB by-id identifier, resolving the current video node. If only one ordinary webcam is connected, it selects that camera automatically. With several cameras and no usable history, it uses the saved profile camera, then the OS default, then an available camera. Hotplug keeps a still-available current camera; unplugging it selects an available replacement. No-camera state gives a connection message. Secondary infrared/metadata UVC endpoints are excluded from the normal webcam list, so a BRIO's extra endpoint does not create an unnecessary choice.

Selection changes are saved and read back before the selected state is finalized. They preserve unrelated unsaved framing adjustments. Opening the window starts preview once camera selection is confirmed if Autostart camera is enabled. With the option disabled, Preview camera starts it manually. Tests cover the sole-camera default, immediate persistence, restoration after device renumbering, unplug fallback, IR filtering, and confirmed camera state. The startup checks cover both disabled capture and an enabled real-camera preview delivering a processed frame.

## Autostart camera (v0.6)

The Autostart camera checkbox sits directly below Restore this profile when WebcamTuner starts. It defaults on for new and older profiles and is saved per profile. A checkbox click waits for the controller to save and read back the choice before changing its checked state; errors leave the last confirmed choice in place. Saving this preference preserves unrelated unsaved edits.

Each window open requests one preview start after the remembered camera is confirmed and, in Image mode, the background image is ready. Closing the window stops preview. With autostart disabled, opening leaves the camera off and the manual Preview camera button works as before. Camera off cancels automatic startup for the current open session; inventory refreshes do not turn it back on. A missing camera can satisfy the pending startup request when connected. Failed previews do not retry automatically. Enabling Autostart camera in an open window starts preview once ready; disabling it controls future opens without interrupting an already running preview.

## Floating palette controls (v0.6)

A fixed 42-pixel title bar keeps the grip, WebcamTuner title, minimize/expand control, and close × visible above scrolling content. Drag the grip or title area to move the window. As in Revelator floating ActionPanel palettes, minimize collapses the body to its title bar; expand restores the previous size. A double-click on the drag area also toggles collapse. Preview keeps running while collapsed, and unsaved edits stay in memory. Close × hides the window and stops preview while keeping the draft for reopening through the bar icon. Opening from the bar expands a collapsed window.

## Use in other apps guidance (v0.6.1)

The editor includes a Use in other apps section below its profile controls. It identifies the current output as preview only and explains that no processed virtual webcam is published by this build. The guide describes selecting WebcamTuner in camera settings after virtual output is implemented and started, granting browser camera permission, disabling duplicate app background effects, and refreshing camera discovery. Choosing a physical BRIO or laptop camera bypasses WebcamTuner processing. These are instructions for the planned output flow, not a claim that the current preview is available to meeting apps.

## Toolbar and guide refinements (v0.6.2)

The fixed title bar optically centers the title lettering and uses geometric grip, minimize and close icons so font baselines cannot shift their visible centers. On Omarchy, collapse/expand applies an explicit, guarded Hyprland resize to this window after its size hints settle; preferred FloatingWindow dimensions alone do not resize a visible native window. The minimize regression clicks the real toolbar button, holds the title-strip state for nearly two seconds without a hide/remap, expands, and closes. Native Wayland verifies the restored height.

Use in other apps is now a disclosure section, folded by default. Its heading and current preview-only output status remain visible; click the heading to reveal or hide the setup guide. This display preference does not alter the saved camera profile.

## Concurrent camera use acceptance requirement

Jason confirmed that the same physical camera has worked in Teams and Zoom simultaneously. WebcamTuner must support both apps consuming its processed output concurrently. The existing worker explicitly captures through OpenCV CAP_V4L2 and sends processed preview JPEGs only to the editor; it does not yet publish a camera device or shared output node. Local PipeWire inventory contains video-source nodes for the BRIO and Framework webcam, but that inventory does not establish which capture/sharing path the earlier Teams/Zoom session used. No camera-protocol violation has been demonstrated.

Evaluate shared PipeWire/portal camera capture while implementing the persistent producer, and publish a processed camera through the appropriate app-compatible interface. One producer must own effects and serve the editor and all consumers, rather than opening a fresh physical capture for each client. Acceptance must verify Teams and Zoom receiving the processed camera simultaneously; framing/background changes appearing in both; either app opening or closing without interrupting the other; and editor minimize/close leaving an explicitly running output alive. Also test browser permissions and capture format negotiation. The current preview-only build does not meet this output requirement.
