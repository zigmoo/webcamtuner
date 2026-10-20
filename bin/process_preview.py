#!/usr/bin/env python3
"""Local preview compositor. Frames stay in memory and travel only over the parent pipe."""
from __future__ import annotations

import argparse
import base64
import json
import math
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urlparse

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

MODEL = Path(__file__).resolve().parent.parent / "models" / "rvm" / "rvm_mobilenetv3_fp32.onnx"
OUTPUT_LOCK = threading.Lock()


def image_path(value: str) -> Path:
    if value.startswith("file:"):
        url = urlparse(value)
        if url.netloc not in ("", "localhost"):
            raise ValueError("Choose a local background image")
        value = unquote(url.path)
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Use an absolute background image path")
    return path


def load_background(value: str) -> np.ndarray:
    path = image_path(value)
    if not path.is_file():
        raise ValueError(f"Background image not found: {path}")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Background image exceeds 50 MB")
    try:
        with Image.open(path) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Background image exceeds 40 million pixels")
            rgb = np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError(f"Cannot read background image: {path}") from error
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def validate_settings(settings: dict) -> dict:
    if not isinstance(settings, dict):
        raise ValueError("Invalid preview settings")
    camera = settings.get("camera", "")
    if not isinstance(camera, str) or not re.fullmatch(r"/dev/(?:video\d+|v4l/by-id/[^/]+)", camera):
        raise ValueError("Choose a local capture camera")
    crop = settings.get("crop", {})
    zoom, x, y = crop.get("zoom"), crop.get("centerX"), crop.get("centerY")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (zoom, x, y)):
        raise ValueError("Invalid crop values")
    if not 1 <= zoom <= 4 or not 0.5 / zoom <= x <= 1 - 0.5 / zoom or not 0.5 / zoom <= y <= 1 - 0.5 / zoom:
        raise ValueError("Crop must stay inside the source frame")
    background = settings.get("background", {})
    if background.get("mode") not in ("none", "blur", "image"):
        raise ValueError("Unknown background mode")
    if background["mode"] == "image" and not isinstance(background.get("imagePath"), str):
        raise ValueError("Choose a background image")
    return settings


def fit_cover(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = max(width / image.shape[1], height / image.shape[0])
    sized = cv2.resize(image, (math.ceil(image.shape[1] * scale), math.ceil(image.shape[0] * scale)))
    x, y = (sized.shape[1] - width) // 2, (sized.shape[0] - height) // 2
    return sized[y:y + height, x:x + width]


def crop_bounds(width: int, height: int, crop: dict) -> tuple[int, int, int, int]:
    w = max(2, math.floor(width / crop["zoom"] / 2) * 2)
    h = max(2, math.floor(height / crop["zoom"] / 2) * 2)
    x = int(max(0, min(width - w, crop["centerX"] * width - w / 2)))
    y = int(max(0, min(height - h, crop["centerY"] * height - h / 2)))
    return x, y, w, h


def crop_frame(frame: np.ndarray, crop: dict) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, w, h = crop_bounds(width, height, crop)
    scale = min(960 / w, 540 / h, 1)
    return cv2.resize(frame[y:y + h, x:x + w], (max(2, round(w * scale)), max(2, round(h * scale))))


def capture_modes(text: str) -> list[dict]:
    modes, fourcc, size = [], None, None
    for line in text.splitlines():
        match = re.search(r"\[\d+\]: '([^']+)'", line)
        if match:
            fourcc, size = match[1], None
        match = re.search(r"Size: Discrete (\d+)x(\d+)", line)
        if match:
            size = (int(match[1]), int(match[2]))
        match = re.search(r"\(([\d.]+) fps\)", line)
        if match and size and fourcc in ("MJPG", "YUYV", "NV12"):
            modes.append({"width": size[0], "height": size[1], "fps": float(match[1]), "fourcc": fourcc})
    return modes


def choose_capture_mode(modes: list[dict]) -> dict:
    suitable = [m for m in modes if m["fps"] >= 15 and m["width"] <= 3840 and m["height"] <= 2160]
    if not suitable:
        raise ValueError("No supported camera mode at 15 fps or above was found")
    # Prefer the largest supported 16:9 source, including UHD on a BRIO. MJPEG
    # avoids exhausting USB bandwidth at 4K. The negotiated mode is checked below.
    widescreen = [m for m in suitable if abs(m["width"] / m["height"] - 16 / 9) < 0.02]
    return max(widescreen or suitable, key=lambda m: (m["width"] * m["height"], m["fourcc"] == "MJPG", min(m["fps"], 30)))


class MaskStabilizer:
    """Smooth classification noise on stationary pixels, while following real motion quickly."""
    def __init__(self):
        self.previous: np.ndarray | None = None
        self.gray: np.ndarray | None = None

    def update(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if self.previous is None or self.previous.shape != mask.shape:
            output = mask
        else:
            movement = cv2.absdiff(gray, self.gray).astype(np.float32)
            movement = cv2.GaussianBlur(movement, (5, 5), 0)
            weight = (0.25 + 0.65 * np.clip(movement / 20, 0, 1))[..., None]
            output = self.previous * (1 - weight) + mask * weight
        self.previous, self.gray = output, gray
        return output


class Segmenter:
    def __init__(self, model: Path = MODEL):
        if not model.is_file():
            raise ValueError("Person segmentation model is missing; reinstall WebcamTuner")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.net = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        self.recurrent = [np.zeros((1, 1, 1, 1), dtype=np.float32) for _ in range(4)]
        self.stabilizer = MaskStabilizer()

    def mask(self, frame: np.ndarray) -> np.ndarray:
        # Recycle all four RVM states. Classifying independent frames discarded
        # the temporal context needed for stable heads, hair and glasses.
        scale = min(960 / frame.shape[1], 540 / frame.shape[0], 1)
        low = cv2.resize(frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale)))
        blob = cv2.dnn.blobFromImage(low, 1 / 255, swapRB=True)
        inputs = {"src": blob, "downsample_ratio": np.array([0.5], dtype=np.float32)}
        inputs.update({f"r{i + 1}i": value for i, value in enumerate(self.recurrent)})
        _, alpha, *self.recurrent = self.net.run(None, inputs)
        alpha = self.stabilizer.update(low, np.clip(alpha[0, 0], 0, 1)[..., None])
        return cv2.resize(alpha, (frame.shape[1], frame.shape[0]))[..., None]


def composite(frame: np.ndarray, mask: np.ndarray, mode: str, background: np.ndarray | None) -> np.ndarray:
    if mode == "none":
        return frame
    backdrop = cv2.GaussianBlur(frame, (0, 0), 18) if mode == "blur" else fit_cover(background, frame.shape[1], frame.shape[0])
    return np.clip(frame.astype(np.float32) * mask + backdrop.astype(np.float32) * (1 - mask), 0, 255).astype(np.uint8)


def emit(value: dict) -> None:
    with OUTPUT_LOCK:
        print(json.dumps(value, separators=(",", ":")), flush=True)


def run(initial: dict, frame_limit: int = 0) -> None:
    cv2.setNumThreads(2)
    current = validate_settings(initial)
    updates: list[dict] = []
    guard = threading.Lock()
    alive = threading.Event()
    alive.set()
    signal.signal(signal.SIGTERM, lambda *_: alive.clear())
    signal.signal(signal.SIGINT, lambda *_: alive.clear())

    def read_updates():
        for line in sys.stdin:
            try:
                if len(line) > 16384:
                    raise ValueError("Preview settings exceed the size limit")
                parsed = validate_settings(json.loads(line))
                with guard:
                    updates[:] = [parsed]
            except (ValueError, TypeError, AttributeError) as error:
                emit({"error": str(error)})
        alive.clear()

    background = load_background(current["background"]["imagePath"]) if current["background"]["mode"] == "image" else None
    segmenter = Segmenter() if current["background"]["mode"] != "none" else None
    listing = subprocess.check_output(["v4l2-ctl", "-d", current["camera"], "--list-formats-ext"], text=True, timeout=5)
    selected = choose_capture_mode(capture_modes(listing))
    capture = cv2.VideoCapture(current["camera"], cv2.CAP_V4L2)
    try:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*selected["fourcc"]))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, selected["width"])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, selected["height"])
        capture.set(cv2.CAP_PROP_FPS, min(selected["fps"], 30))
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            raise RuntimeError("Cannot open this camera. Close other camera previews and check its privacy switch.")
        if (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) != (selected["width"], selected["height"]):
            raise RuntimeError("Camera did not accept its selected full-resolution mode")
        threading.Thread(target=read_updates, daemon=True).start()
        count = 0
        while alive.is_set():
            began = time.monotonic()
            with guard:
                update = updates.pop() if updates else None
            if update is not None:
                try:
                    if update["camera"] != current["camera"]:
                        raise ValueError("Stop preview before switching cameras")
                    candidate = load_background(update["background"]["imagePath"]) if update["background"]["mode"] == "image" else None
                    if update["background"]["mode"] != "none" and segmenter is None:
                        segmenter = Segmenter()
                    if current["background"]["mode"] == "none" and update["background"]["mode"] != "none":
                        segmenter.reset()
                    current, background = update, candidate
                except (ValueError, OSError) as error:
                    emit({"error": str(error), "retainedPreviousEffect": True})
            okay, frame = capture.read()
            if not okay:
                raise RuntimeError("Camera stopped delivering frames; check its privacy switch and connection")
            source_height, source_width = frame.shape[:2]
            _, _, retained_width, retained_height = crop_bounds(source_width, source_height, current["crop"])
            mode = current["background"]["mode"]
            if mode != "none":
                # Detect the person in the full camera view. Tight user crops can otherwise
                # remove the shoulders/context the model needs to classify a head correctly.
                alpha = segmenter.mask(frame)
                alpha = crop_frame(alpha, current["crop"])[..., None]
                frame = crop_frame(frame, current["crop"])
                frame = composite(frame, alpha, mode, background)
            else:
                frame = crop_frame(frame, current["crop"])
            okay, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not okay:
                raise RuntimeError("Could not encode the processed preview")
            emit({"frame": base64.b64encode(encoded).decode("ascii"), "effect": mode, "width": frame.shape[1], "height": frame.shape[0],
                  "captureWidth": source_width, "captureHeight": source_height, "captureFps": capture.get(cv2.CAP_PROP_FPS),
                  "retainedWidth": retained_width, "retainedHeight": retained_height})
            count += 1
            if frame_limit and count >= frame_limit:
                break
            time.sleep(max(0, 1 / 15 - (time.monotonic() - began)))
    finally:
        capture.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--frames", type=int, default=0)
    args = parser.parse_args()
    try:
        run(json.loads(args.request), args.frames)
    except (ValueError, RuntimeError, OSError, cv2.error, subprocess.SubprocessError) as error:
        emit({"error": str(error)})
        raise SystemExit(1)
