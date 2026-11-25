# WebcamTuner

## Install

```bash
omarchy plugin add https://github.com/zigmoo/webcamtuner.git --enable
```

## Remove

```bash
omarchy plugin remove moo.webcamtuner
```

Removal deletes the plugin checkout. It leaves profiles and the user-local ONNX Runtime in place.

Public source: [zigmoo/webcamtuner](https://github.com/zigmoo/webcamtuner). Application source is licensed under Apache-2.0; the bundled Robust Video Matting model retains its separate GPL-3.0 license and provenance in models/rvm/. See [First run](#first-run) for first use through the plugin’s Setup tab. The [Build and review](#build-and-review) steps are for working in this source tree.

WebcamTuner supplies a user-customized composite camera stream to video consumers. Camera is the workspace for adjusting that same shared stream.

In Camera, Start Camera starts the shared composite output and displays the preview when it is ready. Automatic startup follows the same path. Stop Camera stops both preview and shared output. Closing the editor leaves shared output running.

Select WebcamTuner in each consumer. In Setup, Enable browser camera support saves the PipeWire feature for Brave or Chromium; fully quit and reopen that browser to activate it. The normal browser is not restarted automatically. Native Zoom uses the separate user-local adapter. Test each consumer’s camera menu and received frames; a local preview alone does not establish compatibility.

Use **Camera** to choose a profile and camera, frame the live composite, and take full-resolution snapshots. The **Label**, **Crop & Mirror**, and **Person Mask** sections control text, framing, and the subject’s edge. Drag the Camera, Background, or Label grip to position that layer. In **Backgrounds**, choose or import an image, sample it with the eye icon, or open **Label…** to edit its text and placement. Profiles and per-image appearance save automatically. **Setup** contains runtime and integration settings, and **Setup → Test** shows independent PipeWire and V4L2 readbacks with measured receive FPS.

Snapshots are kept in $XDG_DATA_HOME/webcamtuner/snapshots. The Setup checkbox Mirror snapshots to the OS screenshot folder defaults on and adds a PNG copy to the system screenshots folder. The copy also appears in Recent Images with Omasnap 1.24.x and 1.26.2 when Python QtCore is available. Turning mirroring off skips the OS copy. If Revelator is running locally, WebcamTuner also registers snapshots as restricted personal media and prepares their URLs in the background.

Setup lists the actual V4L2 capture devices and PipeWire video sources with their paths/node IDs and current WebcamTuner output identity. Open Zoom desktop launches the installed native Linux app; Teams/Meet/Chat retain the optional separate browser profile. App compatibility requires checking the consumer’s actual camera menu and received frames.

Start Camera in Camera (also available in Setup) publishes the actual composite as WebcamTuner through your user PipeWire session. The desktop camera adapter prepares its signed matching library automatically in your home directory when output starts, and refreshes after PipeWire upgrades. Native Zoom’s user launcher connects automatically when Zoom is installed; reopen an already-running Zoom process to load a newly prepared adapter. Test reads the published pixels back through independent PipeWire and V4L2 consumers. Output continues when controls close; Stop Camera releases the camera and stops shared output. No sudo or kernel driver is required for this path. Native-app compatibility still requires a real check in each app, and live BRIO4K effects currently fall short of24/30fresh FPS on the development host. A separate synthetic diagnostic source remains available. Source capture resolution and measured preview FPS/backend are distinct; the preview shows live FPS and actual GPU/CPU use. Opening from any monitor's bar uses one shared floating editor, with remembered camera, saved mirror/autostart choice and draggable/resizable window controls.

## First run

Add this repository in Omarchy’s plugin manager and enable WebcamTuner. The first open checks readiness and opens Setup when preparation is needed.

1. Click **Prepare WebcamTuner**. Progress and individual readiness checks stay visible. This builds the controller in your cache when needed and prepares OpenCV, NumPy, Pillow and ONNX Runtime in a private environment under your home directory. The bundled matting model is verified without opening a camera.
2. Optionally click **Enable GPU acceleration** for a supported NVIDIA GPU. This prepares a separate GPU environment; CPU remains available.
3. Choose your camera and background in Camera/Background, then click **Start Camera** or **Preview camera** in Camera.
4. The desktop camera adapter prepares automatically. For native Zoom, open it (or reopen it if already running), then choose **WebcamTuner** in its camera settings.
5. Use **Test** to inspect independent published-video readbacks. Verify reception in each meeting app separately.

No build, pip, terminal or administrator commands are required after adding the plugin. Setup can check readiness again and repair the local runtime. Stop output before preparing or repairing the processing runtime or GPU libraries; the desktop camera adapter prepares while output stays live. existing profiles, backgrounds and snapshots are preserved. Preparation itself does not start capture.

Supported desktop baseline: Omarchy/Arch with Python3, Python GObject/GStreamer desktop libraries, mise and an active user PipeWire session. Missing video plugins can be extracted from signed Arch packages matching the installed desktop into WebcamTuner’s private data directory. Packages are never installed system-wide, and package scripts are never run. A missing base desktop library or unavailable matching repository version is reported as unsupported; Setup does not silently request sudo. These paths are tested with empty WebcamTuner data/cache folders and hidden system plugins on the development host; a clean Omarchy VM release check remains pending.

Profiles live under `$XDG_CONFIG_HOME/webcamtuner/profiles.json`. Backgrounds, snapshots, versioned processing runtimes and optional adapters live under `$XDG_DATA_HOME/webcamtuner`; generated controller builds live under `$XDG_CACHE_HOME/webcamtuner`. No npm dependencies or compiled artifacts are written into the installed plugin checkout during preparation.

## Build and review

Developer builds require Node.js22+, npm, Bun for bundling, Qt Multimedia, Quickshell and Omarchy. The Setup tab prepares Python processing dependencies for normal users. The GPL-3.0 Robust Video Matting MobileNetV3 model is bundled with its upstream license, release URL, and SHA256. Application source remains Apache-2.0; the model has its own GPL-3.0 license. Use Setup → Prepare WebcamTuner for the user-local runtime; developers can invoke bin/setup-preview as the same entry point. There are no runtime model downloads. webcam_tool is optional for local cameras and required for remote discovery and video capture.

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

For focused checks, set WEBCAMTUNER_TEST_ROOT to a disposable project-specific directory, run npm test, then python3 tests/ui_smoke.py. Isolated UI fixtures can set WEBCAMTUNER_RUNTIME_PYTHON to an absolute prepared Python interpreter. Opt-in first-use checks are tests/first_run_fresh.py and tests/media_runtime_fresh.py with WEBCAMTUNER_ACCEPT_SETUP_DOWNLOADS=1; they use only fixture-owned data/cache folders and never capture a camera. The UI smoke check runs offscreen, keeps the camera off, persists a crop through the controller, reloads it, and writes a design screenshot beneath that test directory.

## Mirror and window controls

Mirror is on by default, the opposite of the original unmirrored preview. Older profiles without a mirror field adopt the new default; an explicit saved choice is preserved. The checkbox saves its setting and verifies readback before changing orientation. Mirror changes preserve other unsaved draft settings. Mirror reflects the entire finished composite: camera/person, background and label, including their positions and label lettering. Preview, snapshots and the published camera use the same orientation. Dragging the camera, background or label follows the pointer in either mode; the label editing field stays readable while typing.

The plugin opens a native Quickshell floating window. Drag the WebcamTuner heading to move it, or use normal window-manager move/resize controls. Clicking elsewhere does not dismiss it. The native Close button, Escape, and Q hide the window and stop the current preview. Q remains a typing key in text fields. The standalone Preview.qml uses the same window component.

## Virtual-camera output

Start camera output in Setup to publish one persistent user-session PipeWire camera. The Camera selector can switch the physical source without recreating the published node. A new camera must deliver a frame before the previous capture is released; an unavailable source leaves the previous source live and reports the failure. The selector remembers the confirmed saved choice.

Native Zoom uses the signed, user-local PipeWire V4L2 adapter prepared automatically with camera output. Test independently reads both PipeWire and adapter paths. No kernel module, DKMS or system video device is installed. Other consumers still require separate compatibility verification.

## Backgrounds

Choose Image, then paste a local absolute image path or use Browse. The framing card immediately shows the selected image, with loading/error feedback. Choose your camera and click Preview camera to see your actual foreground over the image. Blur uses the same local person segmentation. Changing the image or effect updates a running preview. These settings save automatically with readback verification. Missing or unreadable images prevent an invalid preview from starting.

Preview capture and inference run in a separate Python worker. Capture starts on opening when the saved Autostart camera option is enabled, and stops when the window closes. Frames remain in memory; there are no uploads or camera recordings. Capture negotiates the largest supported 16:9 mode up to UHD: verified BRIO 3840x2160/30 and Framework 1920x1080/30. Framing uses that full-resolution source. The panel scales the processed crop to at most 960x540 and reports its measured fresh-frame rate; capture mode and preview size are shown separately. A 2x crop from 4K retains 1920x1080 source pixels. Recurrent video matting analyzes the full view before cropping, and the renderer retains the last frame while decoding its successor. Start output in Setup to send the same crop, background and label to compatible camera consumers.

The background checks are `bin/preview-python tests/backgrounds_test.py` and `python3 tests/background_ui.py` with WEBCAMTUNER_TEST_ROOT set. `tests/live_preview.py` is an opt-in, bounded real-camera check that also requires WEBCAMTUNER_ACCEPTANCE_IMAGE; it changes image/blur/original effects over the real Quickshell pipe, then stops capture without recording frames.

## Keyboard and pointer

- Drag the camera image to position it. Select Adjust: Camera or Background, then use the slider or Ctrl+scroll to zoom.
- Tab and Shift+Tab move through controls; Enter/Space activate focused buttons.
- Escape closes the Omarchy panel when focus is in its editor.

Copyright 2026 Jason Benjamin Ziegler Sr. Application source: Apache-2.0; bundled RVM model: GPL-3.0 (models/rvm/LICENSE). BrioTune by Shawn Yeager was a design reference; no upstream source was copied.

## Automatic webcam selection (v0.5)

WebcamTuner remembers camera selections immediately, independently of the profile Save button. On startup it restores the most recently selected webcam using its stable USB by-id identifier, resolving the current video node. If only one ordinary webcam is connected, it selects that camera automatically. With several cameras and no usable history, it uses the saved profile camera, then the OS default, then an available camera. Hotplug keeps a still-available current camera; unplugging it selects an available replacement. No-camera state gives a connection message. Secondary infrared/metadata UVC endpoints are excluded from the normal webcam list, so a BRIO's extra endpoint does not create an unnecessary choice.

Selection changes are saved and read back before the selected state is finalized. They preserve unrelated unsaved framing adjustments. Opening the window starts shared output and its preview once camera selection is confirmed if Autostart camera is enabled. With the option disabled, Preview camera starts it manually. Tests cover the sole-camera default, immediate persistence, restoration after device renumbering, unplug fallback, IR filtering, and confirmed camera state. The startup checks cover both disabled capture and an enabled real-camera preview delivering a processed frame.

## Autostart camera (v0.6)

The Autostart camera checkbox sits directly below Restore this profile when WebcamTuner starts. It defaults on for new and older profiles and is saved per profile. A checkbox click waits for the controller to save and read back the choice before changing its checked state; errors leave the last confirmed choice in place. Saving this preference preserves unrelated unsaved edits.

Each window open requests one shared-output and preview start after the remembered camera is confirmed and, in Image mode, the background image is ready. Closing the window stops preview. With autostart disabled, opening leaves the camera off and the manual Preview camera button works as before. Stop Camera cancels automatic startup for the current open session; inventory refreshes do not turn it back on. A missing camera can satisfy the pending startup request when connected. Failed previews do not retry automatically. Enabling Autostart camera in an open window starts preview once ready; disabling it controls future opens without interrupting an already running preview.

## Floating palette controls (v0.6)

A fixed 42-pixel title bar keeps the grip, WebcamTuner title, minimize/expand control, and close × visible above scrolling content. Drag the grip or title area to move the window. As in Revelator floating ActionPanel palettes, minimize collapses the body to its title bar; expand restores the previous size. A double-click on the drag area also toggles collapse. Preview keeps running while collapsed, and unsaved edits stay in memory. Close × hides the window and stops preview while keeping the draft for reopening through the bar icon. Opening from the bar expands a collapsed window.

## Use in other apps

The collapsible guide explains starting output, automatic user-only adapter preparation, selecting WebcamTuner and avoiding duplicate background effects. Selecting a physical BRIO or laptop camera directly bypasses WebcamTuner. Test provides independent readbacks; each actual app still needs verification.

## Toolbar and guide refinements (v0.6.2)

The fixed title bar optically centers the title lettering and uses geometric grip, minimize and close icons so font baselines cannot shift their visible centers. On Omarchy, collapse/expand applies an explicit, guarded Hyprland resize to this window after its size hints settle; preferred FloatingWindow dimensions alone do not resize a visible native window. The minimize regression clicks the real toolbar button, holds the title-strip state for nearly two seconds without a hide/remap, expands, and closes. Native Wayland verifies the restored height.

Use in other apps is a disclosure section, folded by default. Its heading and current publication status remain visible; click the heading to reveal or hide the setup guide. This display preference does not alter the saved camera profile.

## Concurrent camera use

The persistent user-session producer allows independent consumers without capturing the physical camera twice. Native Zoom rendering and two independent synthetic transport readers have passed. Actual Teams/Zoom concurrency and the Meet/Chat acceptance matrix remain open. Do not infer app compatibility from a source merely appearing in a menu.


## Shared physical capture

Physical capture now uses the session PipeWire camera node matched by api.v4l2.path and object.serial, instead of opening /dev/video exclusively. The selected native resolution and frame rate are retained. MJPEG modes explicitly negotiate image/jpeg and decode through jpegdec; raw YUYV/NV12 modes retain their native format. No fallback silently grabs the device exclusively. Missing camera or failed negotiation returns an error. Setup verifies/prepares jpegdec along with existing signed media components. The compositor reads bounded latest frames and propagates capture errors. Starting through Setup or IPC also requests preview while the editor is open. Composite output continues independently when the editor is hidden. Consumer-specific compatibility still requires an actual camera-menu and received-frame check.


## Native helper shutdown

The publisher’s confirmed SIGSEGV is in the oneTBB libtcm topology destructor immediately after hwloc_topology_destroy while a TBB worker dlcloses that library. Keep a loader reference by preloading libtcm only in WebcamTuner processing helpers, preserving existing preload libraries and camera-adapter preload across readback re-exec. Skip the pin when libtcm is absent; a task-scoped optional library path permits testing the exact affected native libraries without replacing host packages. Reference: https://github.com/frankier/tbb-tcm-exit-race . Remote Zbook test copied affected libtbb/libtcm into a private test directory and completed30 native oneTBB workloads/exits through the wrapper without crashes. The host’s older TBB lacks libtcm, explaining the initial test’s missing-preload assertion; no host library replacement was done.

Autostart retains the saved-camera request while readiness checks or other output actions finish. Closing and reopening requests one new start; explicit Stop and an unchecked Autostart setting stay off. Test cards display independent consumer connection state, process/source identity and received FPS. They reconnect after a source change or interrupted start, stop stuck readback helpers after a bounded grace period, and leave Retry available after three unsuccessful attempts.


Movement controls use fixed, labelled grips with36-pixel hit areas. Drag Camera to place the person anywhere in the frame, Background to pan the selected image within its cover crop, or Label to place its text independently. Background locks are respected; zoom Background in when an exact-fit image has no room to pan. Mirror keeps drag directions natural. Arrow keys on a focused grip move one preview pixel; Shift+arrows move ten. Profile and image-specific changes save automatically. These controls are editor overlays and never appear in snapshots or the published camera.


The desktop camera adapter checks the installed PipeWire version while output is running, even with the controls closed. Missing libraries and version upgrades trigger one automatic preparation attempt per version/start, separately from the camera producer. Failure is visible in Setup/Test and leaves PipeWire video running; **Repair camera adapter** retries. The matching package signature is verified before enabling its library. Readback works without native Zoom installed. **Use normal Zoom launcher** explicitly opts out of launcher integration and is preserved during automatic preparation; **Connect Zoom launcher** restores it. Preparation never restarts an active Zoom process.

The user Zoom launcher also prepares the adapter before starting Zoom, so opening Zoom before camera output is supported. It waits up to60seconds for a concurrent installer; preparation failures still allow native Zoom to open with its normal devices.
## Remote cameras — version 0.10.0 (DIL-3498)

In Setup → General, enable **Show Remotes tab**. Open Remotes, select a computer, and choose its camera and quality. Refresh and Inspect cameras discover devices. Connect camera explicitly starts video. Auto prefers an advertised smooth mode and preserves aspect ratio. Streams are capped at 1280x720. The microphone stays off; remote audio routing is not part of this release.

Connect opens a processed preview. Start Camera publishes the composed feed to apps. If output is already running, a new source is prepared in the background and replaces the old source only after it delivers frames. A failed connection retains the previous live source. Cancel connection cancels a pending replacement; Disconnect stops the remote source and its shared output. Closing a preview releases its capture; an explicitly started camera output retains the existing background-output lifecycle.

SSH capture is owned by webcam_tool through its supported stream-plan schema 1 interface. WebcamTuner decodes that video into the existing compositor, so framing, backgrounds, snapshots and camera output share the same processing path as local sources. Stream plans never open cameras. The consumer maintains heartbeat stdin, and EOF or a 12-second remote timeout releases capture after process/network loss. Discovery does not change remote profiles or select a microphone. No public listening port, persistent remote server or media recording is created.

Remote sources are saved with host plus a stable camera identity when Linux exposes by-id. They never silently follow a portable camera to a different host or reconnect automatically on panel open. Connect or Start Camera is explicit. macOS source enumeration is available, but its live capture remains unverified; do not treat Linux test results as macOS acceptance.

Verification: both DIL-3494 removable Logitechs delivered fresh SSH video. A separate test publisher switched between them, retained the old source after a missing-camera request and switched back. Two independent PipeWire consumers received changing frames without replacing the publisher. Production camera output and profiles were not used as test fixtures. See task evidence for measured rates, startup time, gaps, checks and remaining platform limits.
## Remotes navigation — 0.10.1

Remotes is off by default and appears immediately before About when enabled. Browsing the tab leaves the current camera and live output in place until you explicitly connect. Developer UI tests cover discovery, source selection and navigation. The opt-in live test in `tests/remote_compositor_live.py` takes two test hosts and device paths through its environment variables and uses a separate publisher.
