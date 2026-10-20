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
import sys
import threading
import time
from urllib.parse import unquote, urlparse

import cv2
import numpy as np
from PIL import Image, ImageOps

MODEL = Path(__file__).resolve().parent.parent / "models" / "human_segmentation_pphumanseg_2023mar.onnx"
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


def crop_frame(frame: np.ndarray, crop: dict) -> np.ndarray:
    height, width = frame.shape[:2]
    w = max(2, math.floor(width / crop["zoom"] / 2) * 2)
    h = max(2, math.floor(height / crop["zoom"] / 2) * 2)
    x = int(max(0, min(width - w, crop["centerX"] * width - w / 2)))
    y = int(max(0, min(height - h, crop["centerY"] * height - h / 2)))
    return cv2.resize(frame[y:y + h, x:x + w], (640, 360))


class Segmenter:
    def __init__(self, model: Path = MODEL):
        if not model.is_file():
            raise ValueError("Person segmentation model is missing; reinstall WebcamTuner")
        self.net = cv2.dnn.readNetFromONNX(str(model))

    def mask(self, frame: np.ndarray) -> np.ndarray:
        # OpenCV Zoo PPHumanSeg expects RGB NCHW pixels normalized to [-1, 1].
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        data = cv2.resize(rgb, (192, 192)).astype(np.float32) / 127.5 - 1
        self.net.setInput(cv2.dnn.blobFromImage(data))
        classes = self.net.forward()[0]
        if classes.shape[0] != 2:
            raise RuntimeError("Unexpected person segmentation model output")
        if classes.min() < 0 or classes.max() > 1:
            values = np.exp(classes - classes.max(axis=0, keepdims=True))
            classes = values / values.sum(axis=0, keepdims=True)
        alpha = np.clip((classes[1] - 0.25) / 0.5, 0, 1)
        alpha = cv2.resize(alpha, (frame.shape[1], frame.shape[0]))
        return cv2.GaussianBlur(alpha, (0, 0), 1.0)[..., None]


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
    capture = cv2.VideoCapture(current["camera"], cv2.CAP_V4L2)
    try:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            raise RuntimeError("Cannot open this camera. Close other camera previews and check its privacy switch.")
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
                    current, background = update, candidate
                except (ValueError, OSError) as error:
                    emit({"error": str(error), "retainedPreviousEffect": True})
            okay, frame = capture.read()
            if not okay:
                raise RuntimeError("Camera stopped delivering frames; check its privacy switch and connection")
            frame = crop_frame(frame, current["crop"])
            mode = current["background"]["mode"]
            if mode != "none":
                frame = composite(frame, segmenter.mask(frame), mode, background)
            okay, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not okay:
                raise RuntimeError("Could not encode the processed preview")
            emit({"frame": base64.b64encode(encoded).decode("ascii"), "effect": mode, "width": 640, "height": 360})
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
    except (ValueError, RuntimeError, OSError, cv2.error) as error:
        emit({"error": str(error)})
        raise SystemExit(1)
