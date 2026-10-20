# WebcamTuner — initial design (DIL-3027)

WebcamTuner makes camera framing and appearance an OS-owned, portable profile. An Omarchy bar plugin is the control surface; a separate user-session service will publish the processed video as one virtual webcam. The first target is the Framework Laptop 16 integrated second-generation webcam, followed by standard Linux V4L2 cameras.

## Operator journey

1. Open WebcamTuner from the bar. Restore the last saved profile and show whether output is stopped, starting, broadcasting, or failed.
2. Select a camera, explicitly enable its preview, scroll to zoom, and drag the image to position the crop. A camera-off framing card supports design review without capture.
3. Name and save the profile. Validate framing, write atomically, read it back, and only then show Saved. Preserve the unsaved edit on failure; refuse conflicting saves from another panel. Reloading saved settings asks before discarding edits.
4. Choose Original, Blur, or an image background. Image mode now loads a local background immediately; opt-in camera preview uses local person segmentation to replace the room or blur it. Loading, unreadable paths and background readiness are visible. A Browse action and save/reload support the same image path.
5. In the next stage, start virtual output and select WebcamTuner once in each meeting app. Closing the panel leaves output running; stopping output explicitly stops capture.
6. Restore framing on service restart, resume, and camera reconnection. This restoration lifecycle belongs to the future processing service; the current editor restores stored preferences when opened.

## Persistent model

Store versioned profiles at $XDG_CONFIG_HOME/webcamtuner/profiles.json, defaulting to ~/.config/webcamtuner/profiles.json. Keep plugin source and generated runtime state separate. Store future imported background assets below $XDG_DATA_HOME/webcamtuner/backgrounds, with runtime sockets/status below $XDG_RUNTIME_DIR/webcamtuner. Profiles carry a schema version, store revision, active profile, source descriptor, normalized crop, background preference and restore policy.

The normalized crop uses zoom plus source-relative center coordinates. The equivalent rectangle is width=height=1/zoom, x=centerX-width/2 and y=centerY-height/2, constrained inside the source. Convert to even source-pixel coordinates for YUV pipelines. Do not promise crop quality independent of source resolution: 2x zoom on 1920x1080 retains 960x540 source pixels. Aspect-ratio changes require an explicit fit/crop policy in the processing implementation.

The prototype stores Qt's camera selection identifier. Before automatic restoration is implemented, bind local devices to stable /dev/v4l/by-id identities where available, distinguish identical devices, and handle absent serials through explicit reassociation. Never blindly reuse a changed /dev/videoN number. Export/import must include background assets; synchronization is explicit, not automatic. Moving a USB camera alone does not move an OS-owned profile.

## Processing architecture

Physical capture -> supported hardware adjustments -> saved software crop -> local person segmentation and background composition -> fixed-size/frame-rate virtual-camera output. Keep all continuous capture, inference and encoding outside Omarchy's long-running shell. The panel must eventually preview the actual output rather than open the physical camera a second time. The current local preview uses a separate Python/OpenCV worker: full supported source capture -> recurrent RVM alpha matte on the full view -> matched crop of camera/matte -> image/blur composition -> scaled JPEG frames over the parent pipe to QML. It negotiates UHD 3840x2160/30 for the BRIO and 1920x1080/30 for the Framework camera, then renders a panel preview no larger than 960x540 at up to 15 fps. Full source pixels remain available for framing; the displayed metadata distinguishes capture resolution, retained crop pixels, and scaled preview. The renderer keeps the last decoded frame while loading the next. Capture runs only while the panel is open and Preview camera has been pressed. Model inference and image processing remain local; no frames are written to disk or uploaded.

Start with a 1080p source and measure 720p/30 output. Compare a dedicated pipeline with an OBS-based proof before choosing the backend. v4l2loopback needs matching kernel support and WebRTC-compatible capabilities; validate producer-before-consumer ordering. No kernel installation or loading has occurred. Processing failure must not silently expose the unprocessed room; define a placeholder/stopped-output policy. Physical camera privacy remains authoritative. Audio remains outside WebcamTuner's first implementation.

## Integration with the existing remote webcam work

Reviewed DIL-2782 and webcam_tool's CONTRACT, TypeScript interface, discovery, mode selection, profile ownership, and session supervision. Its public CLI exposes read-only hosts/devices inspection, saved connection defaults through setting_tool, and private SSH video with heartbeat cleanup. Live local inspection on this Framework correctly returned one capture camera, excluded its metadata node, and reported MJPEG 1080p/30 and 720p/30.

WebcamTuner's optional adapter calls webcam_tool hosts/devices --json. It does not import private Python functions, duplicate its machine database, start remote capture, or change its settings. Transport settings remain owned by webcam_tool; crop and appearance remain owned by WebcamTuner. A future remote source adapter should resolve host/device through webcam_tool and hand decoded frames to the processing service. webcam_tool currently creates an H.264/AAC stream capped at 720p and uses roughly one second of viewer buffering. That viewer path is not a low-latency virtual-camera backend; obtain a supported transport interface and benchmark before integration. Post-encode crop is limited by the transmitted resolution; source-side crop could retain more detail but needs an explicit supported remote contract.

Preserve EOF/heartbeat cleanup, reject ambiguous devices, keep existing output until a replacement source is ready, and do not open remote feeds merely by opening the panel. macOS live capture is still unverified in DIL-2782. DIL-2810's Dropcam recovery is separate work: its current setup USB device is not a standard UVC capture source and is not a ready remote source.

## Current implementation and next proofs

Implemented: valid Omarchy manifest, bar/panel entry, separate runnable preview, crop preview with a synthetic framing card, opt-in processed local camera preview, named profile editing, atomic revision-checked saves with readback, working local image loading/person segmentation/background replacement and blur, optional read-only remote discovery, agent-accessible incur commands, and a package with no npm symlinks or runtime npm dependencies.

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
