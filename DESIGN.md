# WebcamTuner — design and implementation status (DIL-3027)

WebcamTuner makes camera framing and appearance an OS-owned, portable profile. An Omarchy bar plugin is the control surface; a separate user-session service will publish the processed video as one virtual webcam. The first target is the Framework Laptop 16 integrated second-generation webcam, followed by standard Linux V4L2 cameras.

## Operator journey

1. Open WebcamTuner from the bar. Restore the last saved profile and show whether output is stopped, starting, broadcasting, or failed.
2. Use the remembered camera or select another, choose whether preview starts automatically, scroll to zoom, and drag the image to position the crop. A camera-off framing card supports design review without capture.
3. Name and save the profile. Validate framing, write atomically, read it back, and only then show Saved. Preserve the unsaved edit on failure; refuse conflicting saves from another panel. Reloading saved settings asks before discarding edits.
4. Choose Original, Blur, or an image background. Image mode now loads a local background immediately; camera preview uses local person segmentation to replace the room or blur it. Loading, unreadable paths and background readiness are visible. A Browse action and save/reload support the same image path.
5. In the next stage, start virtual output and select WebcamTuner once in each meeting app. Closing the panel leaves output running; stopping output explicitly stops capture.
6. Restore framing on service restart, resume, and camera reconnection. This restoration lifecycle belongs to the future processing service; the current editor restores stored preferences when opened.

## Persistent model

Store versioned profiles at $XDG_CONFIG_HOME/webcamtuner/profiles.json, defaulting to ~/.config/webcamtuner/profiles.json. Keep plugin source and generated runtime state separate. Store future imported background assets below $XDG_DATA_HOME/webcamtuner/backgrounds, with runtime sockets/status below $XDG_RUNTIME_DIR/webcamtuner. Profiles carry a schema version, store revision, active profile, source descriptor, normalized crop, background preference and restore policy.

The normalized crop uses zoom plus source-relative center coordinates. The equivalent rectangle is width=height=1/zoom, x=centerX-width/2 and y=centerY-height/2, constrained inside the source. Convert to even source-pixel coordinates for YUV pipelines. Do not promise crop quality independent of source resolution: 2x zoom on 1920x1080 retains 960x540 source pixels. Aspect-ratio changes require an explicit fit/crop policy in the processing implementation.

The prototype stores Qt's camera selection identifier. Before automatic restoration is implemented, bind local devices to stable /dev/v4l/by-id identities where available, distinguish identical devices, and handle absent serials through explicit reassociation. Never blindly reuse a changed /dev/videoN number. Export/import must include background assets; synchronization is explicit, not automatic. Moving a USB camera alone does not move an OS-owned profile.

## Processing architecture

Physical capture -> supported hardware adjustments -> saved software crop -> local person segmentation and background composition -> fixed-size/frame-rate virtual-camera output. Keep all continuous capture, inference and encoding outside Omarchy's long-running shell. The panel must eventually preview the actual output rather than open the physical camera a second time. The current local preview uses a separate Python/OpenCV worker: full supported source capture -> recurrent RVM alpha matte on the full view -> matched crop of camera/matte -> image/blur composition -> scaled JPEG frames over the parent pipe to QML. It negotiates UHD 3840x2160/30 for the BRIO and 1920x1080/30 for the Framework camera, then renders a panel preview no larger than 960x540 at up to 15 fps. Full source pixels remain available for framing; the displayed metadata distinguishes capture resolution, retained crop pixels, and scaled preview. The renderer keeps the last decoded frame while loading the next. Capture runs while the window is open, starting automatically when the saved Autostart camera option is enabled or manually through Preview camera. Model inference and image processing remain local; no frames are written to disk or uploaded.

Start with a 1080p source and measure 720p/30 output. Use a per-user PipeWire publisher and prove the required browser/app routes. End users must not need sudo, kernel module installation, terminal commands or compilation. All setup and recovery must be graphical. No kernel installation or loading has occurred. Processing failure must not silently expose the unprocessed room; define a placeholder/stopped-output policy. Physical camera privacy remains authoritative. Audio remains outside WebcamTuner's first implementation.

## Integration with the existing remote webcam work

Reviewed DIL-2782 and webcam_tool's CONTRACT, TypeScript interface, discovery, mode selection, profile ownership, and session supervision. Its public CLI exposes read-only hosts/devices inspection, saved connection defaults through setting_tool, and private SSH video with heartbeat cleanup. Live local inspection on this Framework correctly returned one capture camera, excluded its metadata node, and reported MJPEG 1080p/30 and 720p/30.

WebcamTuner's optional adapter calls webcam_tool hosts/devices --json. It does not import private Python functions, duplicate its machine database, start remote capture, or change its settings. Transport settings remain owned by webcam_tool; crop and appearance remain owned by WebcamTuner. A future remote source adapter should resolve host/device through webcam_tool and hand decoded frames to the processing service. webcam_tool currently creates an H.264/AAC stream capped at 720p and uses roughly one second of viewer buffering. That viewer path is not a low-latency virtual-camera backend; obtain a supported transport interface and benchmark before integration. Post-encode crop is limited by the transmitted resolution; source-side crop could retain more detail but needs an explicit supported remote contract.

Preserve EOF/heartbeat cleanup, reject ambiguous devices, keep existing output until a replacement source is ready, and do not open remote feeds merely by opening the panel. macOS live capture is still unverified in DIL-2782. DIL-2810's Dropcam recovery is separate work: its current setup USB device is not a standard UVC capture source and is not a ready remote source.

## Current implementation and next proofs

Implemented: valid Omarchy manifest, bar/panel entry, separate runnable preview, crop preview with a synthetic framing card, processed local camera preview with a persisted autostart choice, named profile editing, atomic revision-checked saves with readback, working local image loading/person segmentation/background replacement and blur, optional read-only remote discovery, agent-accessible incur commands, and a package with no npm symlinks or runtime npm dependencies.

Not implemented: hardware adjustment controls, stable camera reassociation, virtual output, service start/stop and resume/reconnect handling, profile export/import, or remote video ingestion. The prototype is for interaction review and is not a working meeting camera.

Next proofs: stabilize the panel through operator review; restore a saved crop into a synthetic stream and then the Framework camera; publish that stream through a virtual device; validate Teams/Zoom/Meet; measure compositor latency/CPU use/edge quality and raise preview/output quality as needed. Complete failure handling, translations and theme integration, accessibility, service recovery and regression checks before release. Do not mark DIL-3027 done for a design prototype.

## References

- BrioTune: https://github.com/shawnyeager/briotune (MIT; concept/source review, no copied implementation)
- v4l2loopback: https://github.com/v4l2loopback/v4l2loopback
- OBS virtual camera: https://obsproject.com/kb/virtual-camera-guide
- Segmentation reference: https://github.com/royshil/obs-backgroundremoval
- Existing remote work: DIL-2782; separate Dropcam exploration: DIL-2810

## Background implementation checkpoint (v0.2)

The operator reported that pasting an image path produced no visible result. That exposed a real missing implementation in the initial design preview. The Image control now loads and displays the image immediately, offers Browse, shows path/readiness errors, and gates Save and camera Preview on successful decoding. Live preview now actually composites the detected person over the selected image, or blurs the background, through a separate local OpenCV worker. The synthetic framing card remains useful when the camera is off.

Foreground-mask composition, blur preservation, EXIF/path decoding, real model inference and crop ordering have focused checks. A real QML test uses both special-character filenames and the operator's exact JPEG to verify display, save/reload and missing-path errors. A bounded live-camera Quickshell check verifies image, blur and original frames plus settings changes over stdin, and stops capture without recording frames. The selected image is preserved in the active profile. Virtual-camera output remains separate unfinished work.

The bundled PPHumanSeg ONNX model comes from OpenCV Zoo commit 2027dd2f5a8a5746b5d4964900a0465afc6d3a53, SHA256 552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24. See models/provenance.json and models/LICENSE. Source: https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg . The model was ingested into DIL as KI-20261020_024309_0262 (raw asset preserved; extraction status pending_tooling).

## Flicker, masking and BRIO 4K correction (v0.3)

Operator screenshots showed failures on both the Framework camera and BRIO: unstable cutouts, large misclassified head/room regions, and flicker. The v0.2 independent-frame PPHumanSeg classifier and crop-first ordering were replaced with recurrent Robust Video Matting MobileNetV3. All four recurrent states are fed into successive frames, and inference sees the full camera view before software framing. A motion-aware alpha filter damps static classification changes while following real image motion quickly. The renderer now uses asynchronous frame decoding with retainWhileLoading, preventing a new JPEG source from blanking the last rendered image.

The operator also identified an incorrect 720p source request. Local V4L2 mode enumeration now chooses supported high-resolution MJPEG modes, preferring the largest 16:9 mode up to UHD, and rejects a silent negotiated-size mismatch. Live checks confirmed BRIO 3840x2160 at 30 fps and Framework 1920x1080 at 30 fps for original, image and blur modes. The preview is deliberately scaled independently of the capture source; no 4K virtual-camera output is claimed. The UI reports the negotiated capture mode and retained crop detail rather than assuming a 1080p source.

The RVM v1.0.0 FP32 model has SHA256 88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828. Source: https://github.com/PeterL1n/RobustVideoMatting . Its GPL-3.0 license is preserved in models/rvm/LICENSE, separately from WebcamTuner's Apache-2.0 source. The plugin manifest describes the combined bundle licenses. Raw model asset was preserved through ingest_source as KI-20261020_030251_2165; extraction remains pending_tooling. The previous PPHumanSeg asset remains in Git history and its earlier DIL ingestion, but is no longer packaged or used.

ONNX Runtime 1.31.0 is installed in an XDG user-data virtual environment, outside plugin code and profiles, using system OpenCV/NumPy/Pillow. Recreate it with npm run setup:preview after a Python ABI change. The package does not download models at runtime and does not upload camera images. Tests now cover recurrent-state reuse, static mask noise versus real motion, aligned source/matte crops, UHD/1080p mode selection, actual rendered pixels across asynchronous frame replacements, and the real Quickshell streaming bridge on both cameras. Operator visual confirmation of edge quality and perceived flicker remains necessary; these checks are not a quality benchmark on all people or lighting conditions.

## Draggable window, mirror preference and publishing plan (v0.5)

Operator requested a draggable plugin window, an explicit mirror checkbox defaulting to the opposite of the existing orientation, and the route to a real webcam output. The existing rendering path was unmirrored. Profiles now default mirror=true when the field is absent, and preserve explicit booleans on reload. Mirror is saved through the existing atomic revision-checked controller and confirmed before UI/live orientation changes. Failed saves leave the prior confirmed value; other unsaved profile fields are preserved while mirror is committed independently.

Camera foreground and alpha are reflected together after crop; image backgrounds are left in their original orientation. The framing drag direction is adjusted for the mirrored view. The anchored KeyboardPanel has been replaced by a native FloatingWindow shared with the standalone preview. Its heading initiates startSystemMove. A title-scoped Hyprland Lua dispatcher makes just this window float, requiring no desktop-wide configuration rule. Native Close, bar toggle, and Escape stop preview/hide the window. Actual compositor inspection verified floating=true and successful position changes.

Publishing requires a separate persistent user-session producer. The November 2 objective supersedes the earlier V4L2-driver-first proposal: use PipeWire without administrator privileges. A new kernel module is not an onboarding fallback. An already available adapter may be separately tested, but it cannot be required. The panel must eventually subscribe to the same producer; closing controls must not stop explicitly started output. Verify independent readback and actual app capture before claiming compatibility.

Checks cover legacy profile defaults, explicit mirror persistence, camera/matte orientation with an unreflected background, actual checkbox clicks with delayed save confirmation and simulated failure, preservation of unsaved framing, and the heading move signal. Existing crop/profile and model/compositor checks also pass.

## Automatic webcam selection (v0.5)

WebcamTuner remembers camera selections immediately, independently of the profile Save button. On startup it restores the most recently selected webcam using its stable USB by-id identifier, resolving the current video node. If only one ordinary webcam is connected, it selects that camera automatically. With several cameras and no usable history, it uses the saved profile camera, then the OS default, then an available camera. Hotplug keeps a still-available current camera; unplugging it selects an available replacement. No-camera state gives a connection message. Secondary infrared/metadata UVC endpoints are excluded from the normal webcam list, so a BRIO's extra endpoint does not create an unnecessary choice.

Selection changes are saved and read back before the selected state is finalized. They preserve unrelated unsaved framing adjustments. Opening the window starts preview once camera selection is confirmed if Autostart camera is enabled. With the option disabled, Preview camera starts it manually. Tests cover the sole-camera default, immediate persistence, restoration after device renumbering, unplug fallback, IR filtering, and confirmed camera state. The startup checks cover both disabled capture and an enabled real-camera preview delivering a processed frame.

## Autostart camera (v0.6)

The Autostart camera checkbox sits directly below Restore this profile when WebcamTuner starts. It defaults on for new and older profiles and is saved per profile. A checkbox click waits for the controller to save and read back the choice before changing its checked state; errors leave the last confirmed choice in place. Saving this preference preserves unrelated unsaved edits.

Each window open requests one preview start after the remembered camera is confirmed and, in Image mode, the background image is ready. Closing the window stops preview. With autostart disabled, opening leaves the camera off and the manual Preview camera button works as before. Camera off cancels automatic startup for the current open session; inventory refreshes do not turn it back on. A missing camera can satisfy the pending startup request when connected. Failed previews do not retry automatically. Enabling Autostart camera in an open window starts preview once ready; disabling it controls future opens without interrupting an already running preview.

## Floating palette controls (v0.6)

A fixed 42-pixel title bar keeps the grip, WebcamTuner title, minimize/expand control, and close × visible above scrolling content. Drag the grip or title area to move the window. As in Revelator floating ActionPanel palettes, minimize collapses the body to its title bar; expand restores the previous size. A double-click on the drag area also toggles collapse. Preview keeps running while collapsed, and unsaved edits stay in memory. Close × hides the window and stops preview while keeping the draft for reopening through the bar icon. Opening from the bar expands a collapsed window.

## Toolbar and guide refinements (v0.6.2)

The fixed title bar optically centers the title lettering and uses geometric grip, minimize and close icons so font baselines cannot shift their visible centers. On Omarchy, collapse/expand applies an explicit, guarded Hyprland resize to this window after its size hints settle; preferred FloatingWindow dimensions alone do not resize a visible native window. The minimize regression clicks the real toolbar button, holds the title-strip state for nearly two seconds without a hide/remap, expands, and closes. Native Wayland verifies the restored height.

Use in other apps is now a disclosure section, folded by default. Its heading and current preview-only output status remain visible; click the heading to reveal or hide the setup guide. This display preference does not alter the saved camera profile.

## Concurrent camera use acceptance requirement

Jason confirmed that the same physical camera has worked in Teams and Zoom simultaneously. WebcamTuner must support both apps consuming its processed output concurrently. The existing worker explicitly captures through OpenCV CAP_V4L2 and sends processed preview JPEGs only to the editor; it does not yet publish a camera device or shared output node. Local PipeWire inventory contains video-source nodes for the BRIO and Framework webcam, but that inventory does not establish which capture/sharing path the earlier Teams/Zoom session used. No camera-protocol violation has been demonstrated.

Evaluate shared PipeWire/portal camera capture while implementing the persistent producer, and publish a processed camera through the appropriate app-compatible interface. One producer must own effects and serve the editor and all consumers, rather than opening a fresh physical capture for each client. Acceptance must verify Teams and Zoom receiving the processed camera simultaneously; framing/background changes appearing in both; either app opening or closing without interrupting the other; and editor minimize/close leaving an explicitly running output alive. Also test browser permissions and capture format negotiation. The current preview-only build does not meet this output requirement.


## User-session output proof and navigation (v0.7.0)

This build is an intermediate compatibility test, not processed-camera output. Camera contains source selection, framing, mirror and composite preview. Background contains effect and image controls. Setup contains startup choices, synthetic output start/stop, diagnostics and optional app launchers. About lists Jason Benjamin Ziegler Sr, licenses and https://github.com/zigmoo/webcamtuner. One editor owns the profile draft across tabs. Opening Setup through IPC does not start physical capture or change the saved preview-autostart choice.

Setup starts a transient systemd user service named webcamtuner-test.service, publishing a synthetic WebcamTuner Video/Source at 1280x720/30. No physical camera is opened. The source uses a monotonic system clock and a one-frame leaky queue; idle time does not become a burst of stale frames when a reader connects. Closing the editor leaves the test alive. Stop test camera ends it; a 30-minute safety limit also ends it. Nothing is enabled at login and no lingering session is requested.

The optional Zoom/Teams/Meet/Chat buttons open a separate Brave (or Chromium) profile below XDG_DATA_HOME/webcamtuner/calling-browser, enabling WebRtcPipeWireCamera only for that process. Normal browser profiles and launchers are untouched. The user may need to sign in again and grant camera permission. This is an explicitly labelled candidate compatibility route, not a claim of native-app support. Existing desktop GStreamer, Python GObject/GStreamer bindings, PipeWire and systemd user services are prerequisites for this test build; unavailable components produce a visible error rather than a terminal-install instruction.

Verified on the development host: both Brave and Chromium enumerate WebcamTuner and negotiate 720p30. A five-minute concurrent browser capture run sampled both tracks every five seconds, with two reopen operations each; all sampled tracks remained live. Separate GStreamer consumers confirmed changing pixel hashes, negotiated dimensions, and one consumer reopening without stopping the other. Actual Zoom/Teams/Meet/Chat acceptance remains pending. The existing compositor still supplies only the editor preview; output integration, a managed background gallery, full lifecycle recovery and zero-command distributable packaging remain later milestones in DIL-3027.

Developer checks: npm test with WEBCAMTUNER_TEST_ROOT pointing to disposable scratch; tests/tabs_ui.py for shared-draft navigation; tests/window_controls.py for palette lifecycle; tests/pipewire_readers.py against an explicitly started synthetic source. These are developer checks, not end-user setup steps.


## Background library and control layout (v0.7.1)

The Background tab now lists a managed image library with virtualized, scrollable thumbnails, selected-state feedback, Add images, Refresh and Open folder. Its visible storage path is XDG_DATA_HOME/webcamtuner/backgrounds (normally ~/.local/share/webcamtuner/backgrounds); rebuildable thumbnails live in XDG_CACHE_HOME/webcamtuner/thumbnails/v1. JPEG, PNG and static WebP inputs are decoded and validated before their original bytes are copied atomically and read back by SHA-256. Copies and thumbnails use private file permissions. Imports retain EXIF orientation for thumbnails, deduplicate by content, and leave original files untouched. Limits are 20 files per batch, 50 MiB and 40 million pixels per image, and 512 images or 1 GiB per library. Invalid items produce per-file errors while valid imports remain available.

Choosing an imported image edits the current profile draft; Save profile persists the managed path with the existing revision check and readback. Import completion does not overwrite unrelated crop/name changes. The previously selected saved image was copied into the operator library; its existing saved profile reference was deliberately preserved. Full migration of old profile references and governed removal/export remain future work.

Camera navigation resets to the top on entering or reopening a tab. The selector and Camera off/Preview camera button share a row, with Mirror on its own row. Camera zoom has a separate instruction: Zoom in, then drag the image above to adjust framing. About has 22px padding and explains the control panel, local worker, per-user PipeWire service, lack of privileged driver setup, and current limits. Actual processed meeting-camera output and app acceptance remain pending independently of these operator-requested library/UI changes.


## External-folder refresh, per-image framing and preview performance (v0.8.0)

The Background tab watches the library directory with a 1.2-second debounce and refreshes every 15 seconds while visible as a fallback. It also refreshes on tab entry. Ordinary JPEG/PNG/WebP filenames copied through a file manager are accepted directly without renaming or moving them. File metadata caches avoid decoding and hashing unchanged images on each poll; changed content gets a new thumbnail identity. Gallery refresh preserves selected background, dirty camera edits and gallery scroll position. Partially copied or unreadable files are retried on later scans.

Each image has independent pan/zoom framing in a 16:9 background editor. Crops are saved automatically after a 400ms debounce into private XDG_CONFIG_HOME/webcamtuner/background-crops.json, keyed by image-content SHA-256. Selecting another image and returning restores its crop. Concurrent edits to different image entries are merged under a file lock; saves are atomic and read back. Profile background.crop is an optional portable snapshot; old profiles remain valid. The compositor applies this crop to the image background, independently of camera framing and foreground orientation. Cropping an already selected legacy local image also works, without changing its original file.

The Camera preview now scales within the initial viewport to leave selector/preview control, Camera zoom, Mirror, profile actions and status visible. Overflow has a persistent scrollbar. The 15fps software cap is replaced by a 30fps target and bounded latest-frame capture. The RVM call only fetches matte/recurrent outputs, avoids upscaling the matte to full UHD before cropping, and uses native vector operations for blending and a small-image blur. Frames report actual fresh FPS, dropped source frames, processing time and active backend; advertised capture mode is labelled separately.

Setup offers Enable GPU acceleration and Use CPU. GPU setup creates a separate user-local runtime-gpu environment, installs ONNX Runtime GPU 1.31.0 and CUDA/cuDNN dependencies from prebuilt wheels, verifies actual CUDA model execution, then writes an enabled marker. The original CPU environment remains available. Changing the runtime applies on the next preview start. No sudo, kernel driver, compilation or manual terminal setup is needed. This host already had the NVIDIA driver; the plugin does not install a system display driver.

Performance evidence on framemoowork: RTX5070 CUDA execution verified. A native Wayland Quickshell receive/decode run with Framework 1920x1080 capture and image replacement measured 28.125 fresh fps and 27.969 decoded fps over the steady 180-frame sample after warm-up. An earlier pipeline benchmark reached 25.98 fresh fps; offscreen software-platform runs ranged approximately 21–23 fps and did not pass the 24fps threshold. A separate synthetic UHD processing-only benchmark measured 35.21 fps; it excludes physical capture and QML decoding. These results are not a claim of 4K BRIO live throughput: Brave held that camera during testing and was left running. A temporary exposure/framerate experiment did not improve performance, was reverted, and the original setting was restored. No frames were stored or uploaded. Actual FPS depends on the camera's delivered rate and system load; 30fps is the requested target, not an invented duplicate-frame count.

Draft recovery IPC is included for subsequent updates: draft exports the current profile draft and pending crop edits without saving; restoreDraft restores a compatible snapshot at the same saved-store revision. Its round-trip regression confirms dirty crop recovery without altering saved settings. The previously installed 0.7.1 lacks this interface; it must be saved or explicitly discarded before the first reload into this build.

Sources for backend choices: https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html and https://doc.qt.io/qt-6/qml-qt-labs-folderlistmodel-folderlistmodel.html.
