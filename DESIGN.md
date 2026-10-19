# WebcamTuner — initial design (DIL-3027)

WebcamTuner makes camera framing and appearance an OS-owned, portable profile. An Omarchy bar plugin is the control surface; a separate user-session service will publish the processed video as one virtual webcam. The first target is the Framework Laptop 16 integrated second-generation webcam, followed by standard Linux V4L2 cameras.

## Operator journey

1. Open WebcamTuner from the bar. Restore the last saved profile and show whether output is stopped, starting, broadcasting, or failed.
2. Select a camera, explicitly enable its preview, scroll to zoom, and drag the image to position the crop. A camera-off framing card supports design review without capture.
3. Name and save the profile. Validate framing, write atomically, read it back, and only then show Saved. Preserve the unsaved edit on failure; refuse conflicting saves from another panel. Reloading saved settings asks before discarding edits.
4. Choose Original, Blur, or an image background. In the first prototype these choices are saved preferences only; segmentation is not yet connected.
5. In the next stage, start virtual output and select WebcamTuner once in each meeting app. Closing the panel leaves output running; stopping output explicitly stops capture.
6. Restore framing on service restart, resume, and camera reconnection. This restoration lifecycle belongs to the future processing service; the current editor restores stored preferences when opened.

## Persistent model

Store versioned profiles at $XDG_CONFIG_HOME/webcamtuner/profiles.json, defaulting to ~/.config/webcamtuner/profiles.json. Keep plugin source and generated runtime state separate. Store future imported background assets below $XDG_DATA_HOME/webcamtuner/backgrounds, with runtime sockets/status below $XDG_RUNTIME_DIR/webcamtuner. Profiles carry a schema version, store revision, active profile, source descriptor, normalized crop, background preference and restore policy.

The normalized crop uses zoom plus source-relative center coordinates. The equivalent rectangle is width=height=1/zoom, x=centerX-width/2 and y=centerY-height/2, constrained inside the source. Convert to even source-pixel coordinates for YUV pipelines. Do not promise crop quality independent of source resolution: 2x zoom on 1920x1080 retains 960x540 source pixels. Aspect-ratio changes require an explicit fit/crop policy in the processing implementation.

The prototype stores Qt's camera selection identifier. Before automatic restoration is implemented, bind local devices to stable /dev/v4l/by-id identities where available, distinguish identical devices, and handle absent serials through explicit reassociation. Never blindly reuse a changed /dev/videoN number. Export/import must include background assets; synchronization is explicit, not automatic. Moving a USB camera alone does not move an OS-owned profile.

## Processing architecture

Physical capture -> supported hardware adjustments -> saved software crop -> local person segmentation and background composition -> fixed-size/frame-rate virtual-camera output. Keep all continuous capture, inference and encoding outside Omarchy's long-running shell. The panel must eventually preview the actual output rather than open the physical camera a second time. Qt camera preview is temporary and runs only while the design panel is open and Preview camera has been pressed.

Start with a 1080p source and measure 720p/30 output. Compare a dedicated pipeline with an OBS-based proof before choosing the backend. v4l2loopback needs matching kernel support and WebRTC-compatible capabilities; validate producer-before-consumer ordering. No kernel installation or loading has occurred. Processing failure must not silently expose the unprocessed room; define a placeholder/stopped-output policy. Physical camera privacy remains authoritative. Audio remains outside WebcamTuner's first implementation.

## Integration with the existing remote webcam work

Reviewed DIL-2782 and webcam_tool's CONTRACT, TypeScript interface, discovery, mode selection, profile ownership, and session supervision. Its public CLI exposes read-only hosts/devices inspection, saved connection defaults through setting_tool, and private SSH video with heartbeat cleanup. Live local inspection on this Framework correctly returned one capture camera, excluded its metadata node, and reported MJPEG 1080p/30 and 720p/30.

WebcamTuner's optional adapter calls webcam_tool hosts/devices --json. It does not import private Python functions, duplicate its machine database, start remote capture, or change its settings. Transport settings remain owned by webcam_tool; crop and appearance remain owned by WebcamTuner. A future remote source adapter should resolve host/device through webcam_tool and hand decoded frames to the processing service. webcam_tool currently creates an H.264/AAC stream capped at 720p and uses roughly one second of viewer buffering. That viewer path is not a low-latency virtual-camera backend; obtain a supported transport interface and benchmark before integration. Post-encode crop is limited by the transmitted resolution; source-side crop could retain more detail but needs an explicit supported remote contract.

Preserve EOF/heartbeat cleanup, reject ambiguous devices, keep existing output until a replacement source is ready, and do not open remote feeds merely by opening the panel. macOS live capture is still unverified in DIL-2782. DIL-2810's Dropcam recovery is separate work: its current setup USB device is not a standard UVC capture source and is not a ready remote source.

## Current implementation and next proofs

Implemented: valid Omarchy manifest, bar/panel entry, separate runnable preview, crop preview with a synthetic framing card, opt-in local Qt camera preview, named profile editing, atomic revision-checked saves with readback, explicit background preferences, optional read-only remote discovery, agent-accessible incur commands, and a package with no npm symlinks or runtime npm dependencies.

Not implemented: hardware adjustment controls, stable camera reassociation, segmentation, image loading/composition, virtual output, service start/stop and resume/reconnect handling, profile export/import, or remote video ingestion. The prototype is for interaction review and is not a working meeting camera.

Next proofs: stabilize the panel through operator review; restore a saved crop into a synthetic stream and then the Framework camera; publish that stream through a virtual device; validate Teams/Zoom/Meet; add background composition and measure latency/CPU/GPU/edge quality. Complete failure handling, translations and theme integration, accessibility, service recovery and regression checks before release. Do not mark DIL-3027 done for a design prototype.

## References

- BrioTune: https://github.com/shawnyeager/briotune (MIT; concept/source review, no copied implementation)
- v4l2loopback: https://github.com/v4l2loopback/v4l2loopback
- OBS virtual camera: https://obsproject.com/kb/virtual-camera-guide
- Segmentation reference: https://github.com/royshil/obs-backgroundremoval
- Existing remote work: DIL-2782; separate Dropcam exploration: DIL-2810
