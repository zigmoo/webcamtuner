#!/usr/bin/env python3
"""Local preview compositor. Frames stay in memory and travel only over the parent pipe."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
from collections import deque
from functools import lru_cache
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
from PIL import Image, ImageOps, ImageDraw, ImageFont

# Runtime imports must not write into the watched plugin directory.
sys.dont_write_bytecode = True
_snapshot_spec = importlib.util.spec_from_file_location("webcamtuner_snapshots", Path(__file__).with_name("snapshot_files.py"))
snapshot_files = importlib.util.module_from_spec(_snapshot_spec)
_snapshot_spec.loader.exec_module(snapshot_files)

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
    if not isinstance(settings.get("mirror", True), bool):
        raise ValueError("Mirror must be on or off")
    camera = settings.get("camera", "")
    if not isinstance(camera, str) or not re.fullmatch(r"/dev/(?:video\d+|v4l/by-id/[^/]+)", camera):
        raise ValueError("Choose a local capture camera")
    crop = settings.get("crop", {})
    zoom, x, y = crop.get("zoom"), crop.get("centerX"), crop.get("centerY")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (zoom, x, y)):
        raise ValueError("Invalid crop values")
    if not 1 <= zoom <= 4 or not 0.5 / zoom <= x <= 1 - 0.5 / zoom or not 0.5 / zoom <= y <= 1 - 0.5 / zoom:
        raise ValueError("Crop must stay inside the source frame")
    foreground = settings.get("foreground", {"x": 0, "y": 0})
    if not isinstance(foreground, dict) or any(isinstance(foreground.get(k), bool) or not isinstance(foreground.get(k), (int, float)) or not math.isfinite(foreground[k]) or not -1 <= foreground[k] <= 1 for k in ('x', 'y')):
        raise ValueError("Invalid foreground position")
    background = settings.get("background", {})
    if background.get("mode") not in ("none", "blur", "image"):
        raise ValueError("Unknown background mode")
    if background["mode"] == "image" and not isinstance(background.get("imagePath"), str):
        raise ValueError("Choose a background image")
    bg_crop = background.get("crop", {"zoom": 1, "centerX": 0.5, "centerY": 0.5})
    if not isinstance(bg_crop, dict) or not all(isinstance(bg_crop.get(k), (int, float)) and not isinstance(bg_crop[k], bool) and math.isfinite(bg_crop[k]) for k in ("zoom", "centerX", "centerY")):
        raise ValueError("Invalid background crop")
    if not 1 <= bg_crop["zoom"] <= 32 or not 0 <= bg_crop["centerX"] <= 1 or not 0 <= bg_crop["centerY"] <= 1:
        raise ValueError("Background crop is outside its limits")
    overlay = background.get('labelOverlay')
    if overlay is not None:
        if not isinstance(overlay, dict) or not isinstance(overlay.get('enabled'), bool) or not isinstance(overlay.get('text'), str) or len(overlay['text']) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in overlay['text']):
            raise ValueError('Invalid background label overlay')
        opacity = overlay.get('opacity')
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('Invalid background label opacity')
        for key in ('x','y','fontSize'):
            if key in overlay:
                v=overlay[key]; low,high=(.012,.15) if key=='fontSize' else (0,1)
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high: raise ValueError('Invalid label position or size')
        for key in ('bold','italic','allCaps'):
            if key in overlay and not isinstance(overlay[key],bool): raise ValueError('Invalid label format')
        family=overlay.get('fontFamily','sans')
        if not isinstance(family,str) or len(family)>128 or any(ord(c)<32 or ord(c)==127 for c in family): raise ValueError('Invalid label font')
    return settings


@lru_cache(maxsize=32)
def label_font_path(family='sans', bold=False, italic=False):
    pattern = family.replace(':', ' ') + (':weight=bold' if bold else '') + (':slant=italic' if italic else '')
    try:
        result = subprocess.check_output(['fc-match', '-f', '%{file}', pattern], text=True, timeout=3)
        if Path(result).is_file(): return result
    except (OSError, subprocess.SubprocessError): pass
    return 'DejaVuSans.ttf'


@lru_cache(maxsize=16)
def label_bitmap(text, width, height, family='sans', bold=False, italic=False, font_size=.034, all_caps=False):
    size = max(10, round(height * font_size))
    margin = max(4, round(height * .02))
    stroke = max(1, round(size / 16))
    try: font = ImageFont.truetype(label_font_path(family,bold,italic), size)
    except OSError: font = ImageFont.load_default(size=size)
    available = max(1, width - 2 * margin - 2 * stroke)
    lines = ['']
    for character in text.upper() if all_caps else text:
        if font.getlength(lines[-1] + character) > available:
            if len(lines) == 2:
                while lines[-1] and font.getlength(lines[-1] + '…') > available: lines[-1] = lines[-1][:-1]
                lines[-1] += '…'
                break
            lines.append('')
        lines[-1] += character
    text = '\n'.join(lines)
    bounds = ImageDraw.Draw(Image.new('RGBA', (1,1))).multiline_textbbox((0,0), text, font=font, stroke_width=stroke, spacing=max(2,size//8))
    tile = Image.new('RGBA', (min(width,max(1,math.ceil(bounds[2]-bounds[0]+stroke*2))), min(height,max(1,math.ceil(bounds[3]-bounds[1]+stroke*2)))))
    draw = ImageDraw.Draw(tile)
    draw.multiline_text((stroke - bounds[0], stroke - bounds[1]), text, font=font, fill=(255,255,255,255),
        stroke_fill=(0,0,0,204), stroke_width=stroke, spacing=max(2, size//8))
    pixels = np.asarray(tile)
    return cv2.cvtColor(pixels[...,:3], cv2.COLOR_RGB2BGR), pixels[...,3:4].astype(np.float32) / 255


def apply_label_overlay(frame, overlay):
    """Output-space label uses the same style/position for snapshots and publication."""
    if not overlay or not overlay.get('enabled') or not overlay.get('text') or overlay.get('opacity', .75) <= 0:
        return frame
    h,w = frame.shape[:2]
    color, alpha = label_bitmap(overlay['text'], w, h, overlay.get('fontFamily','sans'), overlay.get('bold',False),
        overlay.get('italic',False), overlay.get('fontSize',.034), overlay.get('allCaps',False))
    alpha = alpha * overlay.get('opacity', .75)
    result = frame.copy()
    x = round((w-color.shape[1])*overlay.get('x',.02)); y = round((h-color.shape[0])*overlay.get('y',.96))
    target = result[y:y+color.shape[0], x:x+color.shape[1]]
    target[:] = np.clip(color.astype(np.float32) * alpha + target.astype(np.float32) * (1-alpha), 0,255).astype(np.uint8)
    return result


def fit_cover(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = max(width / image.shape[1], height / image.shape[0])
    sized = cv2.resize(image, (math.ceil(image.shape[1] * scale), math.ceil(image.shape[0] * scale)))
    x, y = (sized.shape[1] - width) // 2, (sized.shape[0] - height) // 2
    return sized[y:y + height, x:x + width]


def fit_background(image: np.ndarray, width: int, height: int, crop: dict | None = None) -> np.ndarray:
    if crop is None:
        return fit_cover(image, width, height)
    ih, iw = image.shape[:2]
    cover = max(width / iw, height / ih) * crop['zoom']
    cw, ch = max(1, min(iw, round(width / cover))), max(1, min(ih, round(height / cover)))
    x = max(0, min(iw - cw, round(crop['centerX'] * iw - cw / 2)))
    y = max(0, min(ih - ch, round(crop['centerY'] * ih - ch / 2)))
    return cv2.resize(image[y:y + ch, x:x + cw], (width, height))


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
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            if hasattr(ort, "preload_dlls"):
                with contextlib.redirect_stdout(sys.stderr):
                    ort.preload_dlls(directory="")
            providers = [("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC", "gpu_mem_limit": 2 * 1024 ** 3}), "CPUExecutionProvider"]
        with contextlib.redirect_stdout(sys.stderr):
            self.net = ort.InferenceSession(str(model), sess_options=options, providers=providers)
        self.provider = self.net.get_providers()[0]
        self.outputs = [value.name for value in self.net.get_outputs()][1:]
        self.run_options = ort.RunOptions()
        self.run_options.only_execute_path_to_fetches = True
        self.reset()

    def reset(self):
        self.recurrent = [np.zeros((1, 1, 1, 1), dtype=np.float32) for _ in range(4)]
        self.stabilizer = MaskStabilizer()

    def mask(self, frame: np.ndarray, full_resolution: bool = True) -> np.ndarray:
        # Recycle all four RVM states. Classifying independent frames discarded
        # the temporal context needed for stable heads, hair and glasses.
        scale = min(960 / frame.shape[1], 540 / frame.shape[0], 1)
        low = cv2.resize(frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale)))
        blob = cv2.dnn.blobFromImage(low, 1 / 255, swapRB=True)
        inputs = {"src": blob, "downsample_ratio": np.array([0.5], dtype=np.float32)}
        inputs.update({f"r{i + 1}i": value for i, value in enumerate(self.recurrent)})
        alpha, *self.recurrent = self.net.run(self.outputs, inputs, run_options=self.run_options)
        alpha = self.stabilizer.update(low, np.clip(alpha[0, 0], 0, 1)[..., None])
        return cv2.resize(alpha, (frame.shape[1], frame.shape[0]))[..., None] if full_resolution else alpha


def align_matte(mask, source_width, source_height, crop, width, height):
    x, y, w, h = crop_bounds(source_width, source_height, crop)
    sx, sy = mask.shape[1] / source_width, mask.shape[0] / source_height
    ax, ay = w / width * sx, h / height * sy
    matrix = np.array([[ax, 0, x * sx + ax / 2 - 0.5],
                       [0, ay, y * sy + ay / 2 - 0.5]], dtype=np.float32)
    return cv2.warpAffine(mask, matrix, (width, height), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_REPLICATE)[..., None]


def placed_foreground(source, matte, crop, mirror, placement, width, height):
    """Sample the full source, so moving a crop can reveal previously clipped pixels."""
    sh, sw = source.shape[:2]
    x, y, cw, ch = crop_bounds(sw, sh, crop)
    ax, ay = cw / width, ch / height
    tx = x + ax / 2 - 0.5 - placement.get('x', 0) * cw
    if mirror:
        ax = -ax
        tx = x + (width - 0.5) * cw / width - 0.5 + placement.get('x', 0) * cw
    ty = y + ay / 2 - 0.5 - placement.get('y', 0) * ch
    matrix = np.array([[ax, 0, tx], [0, ay, ty]], dtype=np.float32)
    image = cv2.warpAffine(source, matrix, (width, height), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    alpha = None
    if matte is not None:
        sx, sy = matte.shape[1] / sw, matte.shape[0] / sh
        mm = np.array([[ax * sx, 0, (tx + 0.5) * sx - 0.5],
                       [0, ay * sy, (ty + 0.5) * sy - 0.5]], dtype=np.float32)
        alpha = cv2.warpAffine(matte, mm, (width, height), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)[..., None]
    return image, alpha


def composite(frame: np.ndarray, mask: np.ndarray, mode: str, background: np.ndarray | None, background_crop: dict | None = None, blur_source: np.ndarray | None = None) -> np.ndarray:
    if mode == "none":
        return frame
    if mode == "blur":
        base = frame if blur_source is None else blur_source
        small = cv2.resize(base, (max(1, base.shape[1] // 4), max(1, base.shape[0] // 4)))
        backdrop = cv2.resize(cv2.GaussianBlur(small, (0, 0), 4.5), (frame.shape[1], frame.shape[0]))
    else:
        backdrop = fit_background(background, frame.shape[1], frame.shape[0], background_crop)
    alpha = cv2.cvtColor(mask.astype(np.float32, copy=False), cv2.COLOR_GRAY2BGR)
    foreground = cv2.multiply(frame, alpha, dtype=cv2.CV_32F)
    background_part = cv2.multiply(backdrop, 1 - alpha, dtype=cv2.CV_32F)
    return cv2.add(foreground, background_part, dtype=cv2.CV_8U)


def orient_camera(frame: np.ndarray, mask: np.ndarray | None, mirror: bool):
    if not mirror:
        return frame, mask
    return frame[:, ::-1].copy(), None if mask is None else mask[:, ::-1].copy()


def emit(value: dict) -> None:
    with OUTPUT_LOCK:
        print(json.dumps(value, separators=(",", ":")), flush=True)


def save_processed_snapshot(frame, matte, settings, background):
    h, w = frame.shape[:2]
    x, y, cw, ch = crop_bounds(w, h, settings['crop'])
    full = frame[y:y + ch, x:x + cw]
    mode = settings['background']['mode']
    alpha = None
    if mode != 'none':
        if matte is None:
            raise ValueError('The processed image is not ready for a snapshot.')
        alpha = align_matte(matte, w, h, settings['crop'], cw, ch)
    full, alpha = orient_camera(full, alpha, settings.get('mirror', True))
    base = full
    placement = settings.get('foreground', {'x':0, 'y':0})
    if placement.get('x', 0) or placement.get('y', 0):
        full, alpha = placed_foreground(frame, matte, settings['crop'], settings.get('mirror', True), placement, cw, ch)
    if mode != 'none':
        full = composite(full, alpha, mode, background, settings['background'].get('crop'), base)
    if mode == 'image': full = apply_label_overlay(full, settings['background'].get('labelOverlay'))
    okay, encoded = cv2.imencode('.jpg', full, [cv2.IMWRITE_JPEG_QUALITY, 96])
    if not okay:
        raise ValueError('Snapshot could not be encoded.')
    path = snapshot_files.save(encoded.tobytes())
    return {'path': str(path), 'width': cw, 'height': ch, **snapshot_files.mirror_snapshot(path)}


def run(initial: dict, frame_limit: int = 0, ui_overlay: bool = False) -> None:
    cv2.setNumThreads(2)
    current = validate_settings(initial)
    updates: list[dict] = []
    snapshots: list[dict] = []
    snapshot_thread = None
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
                value = json.loads(line)
                if value.get('operation') == 'snapshot':
                    if not isinstance(value.get('requestId'), str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', value['requestId']):
                        raise ValueError('Invalid snapshot request')
                    with guard:
                        if snapshots:
                            emit({'snapshotError': 'A snapshot is already pending', 'requestId': value['requestId']})
                        else:
                            snapshots.append(value)
                    continue
                parsed = validate_settings(value)
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
    reader = None
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
        source_fps = capture.get(cv2.CAP_PROP_FPS)
        target_fps = min(30, source_fps) if source_fps > 0 else 30
        condition = threading.Condition()
        latest = {"frame": None, "sequence": 0, "error": None}
        def grab_frames():
            while alive.is_set():
                okay, image = capture.read()
                with condition:
                    if not okay:
                        latest["error"] = "Camera stopped delivering frames; check its privacy switch and connection"
                        condition.notify_all()
                        return
                    latest["frame"] = image
                    latest["sequence"] += 1
                    condition.notify_all()
        reader = threading.Thread(target=grab_frames, daemon=True)
        reader.start()
        threading.Thread(target=read_updates, daemon=True).start()
        count, last_sequence, dropped = 0, 0, 0
        delivered = deque(maxlen=60)
        last_label_style = None
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
            with condition:
                deadline = time.monotonic() + (5 if last_sequence == 0 else 1)
                while latest["sequence"] == last_sequence and not latest["error"] and alive.is_set():
                    condition.wait(0.1)
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Camera stopped delivering fresh frames")
                if latest["error"]:
                    raise RuntimeError(latest["error"])
                if not alive.is_set():
                    break
                frame = latest["frame"]
                sequence = latest["sequence"]
            dropped += max(0, sequence - last_sequence - 1)
            last_sequence = sequence
            captured = time.monotonic()
            full_frame = frame
            matte = None
            source_height, source_width = frame.shape[:2]
            _, _, retained_width, retained_height = crop_bounds(source_width, source_height, current["crop"])
            mode = current["background"]["mode"]
            matte_ms = 0
            if mode != "none":
                # Detect the person in the full camera view. Tight user crops can otherwise
                # remove the shoulders/context the model needs to classify a head correctly.
                alpha = segmenter.mask(frame, full_resolution=False)
                matte = alpha
                matte_ms = (time.monotonic() - captured) * 1000
                frame = crop_frame(frame, current["crop"])
                alpha = align_matte(alpha, source_width, source_height, current["crop"], frame.shape[1], frame.shape[0])
                frame, alpha = orient_camera(frame, alpha, current.get("mirror", True))
                base = frame
                placement = current.get('foreground', {'x':0, 'y':0})
                if placement.get('x', 0) or placement.get('y', 0):
                    frame, alpha = placed_foreground(full_frame, matte, current['crop'], current.get('mirror', True), placement, frame.shape[1], frame.shape[0])
                frame = composite(frame, alpha, mode, background, current["background"].get("crop"), base)
            else:
                frame = crop_frame(frame, current["crop"])
                frame, _ = orient_camera(frame, None, current.get("mirror", True))
                placement = current.get('foreground', {'x':0, 'y':0})
                if placement.get('x', 0) or placement.get('y', 0):
                    frame, _ = placed_foreground(full_frame, None, current['crop'], current.get('mirror', True), placement, frame.shape[1], frame.shape[0])
            if mode == 'image' and not ui_overlay: frame = apply_label_overlay(frame, current['background'].get('labelOverlay'))
            with guard:
                snapshot = snapshots.pop() if snapshots else None
            if snapshot is not None:
                if snapshot_thread is not None and snapshot_thread.is_alive():
                    emit({'snapshotError': 'A snapshot is still being saved', 'requestId': snapshot['requestId']})
                elif snapshot.get('expectedRevision') != current.get('configurationRevision', 0):
                    emit({'snapshotError': 'Settings changed before the snapshot; try again.', 'requestId': snapshot['requestId']})
                else:
                    def write_snapshot(image, alpha, settings, backdrop, request_id):
                        try:
                            result = save_processed_snapshot(image, alpha, settings, backdrop)
                            emit({'snapshot': result, 'requestId': request_id})
                        except (OSError, ValueError, cv2.error) as error:
                            emit({'snapshotError': str(error), 'requestId': request_id})
                    snapshot_thread = threading.Thread(target=write_snapshot,
                        args=(full_frame, matte, current, background, snapshot['requestId']))
                    snapshot_thread.start()
            okay, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not okay:
                raise RuntimeError("Could not encode the processed preview")
            now = time.monotonic()
            delivered.append(now)
            actual_fps = (len(delivered) - 1) / (delivered[-1] - delivered[0]) if len(delivered) > 1 else 0
            source_record = {}
            overlay=current['background'].get('labelOverlay',{})
            if ui_overlay and mode=='image' and overlay.get('enabled') and overlay.get('text'):
                key=(overlay['text'],frame.shape[1],frame.shape[0],overlay.get('fontFamily') or 'sans',overlay.get('bold',False),overlay.get('italic',False),overlay.get('fontSize',.034),overlay.get('allCaps',False))
                if key!=last_label_style:
                    color,alpha=label_bitmap(*key)
                    rgba=cv2.cvtColor(color,cv2.COLOR_BGR2BGRA);rgba[...,3]=(alpha[...,0]*255).astype(np.uint8)
                    label_ok,png=cv2.imencode('.png',rgba)
                    if label_ok:
                        source_record.update(labelBitmap=base64.b64encode(png).decode('ascii'),labelKey=json.dumps(key),labelWidth=color.shape[1],labelHeight=color.shape[0])
                        last_label_style=key
            if current.get('sourcePreview', False):
                source_image = cv2.resize(full_frame, (960,540))
                if current.get('mirror',True): source_image = cv2.flip(source_image,1)
                source_ok, source_jpeg = cv2.imencode('.jpg', source_image, [cv2.IMWRITE_JPEG_QUALITY,82])
                if source_ok: source_record['sourceFrame'] = base64.b64encode(source_jpeg).decode('ascii')
            emit({**source_record, "frame": base64.b64encode(encoded).decode("ascii"), "effect": mode, "width": frame.shape[1], "height": frame.shape[0],
                  "captureWidth": source_width, "captureHeight": source_height, "captureFps": source_fps, "previewFps": actual_fps,
                  "configurationRevision": current.get("configurationRevision", 0),
                  "sequence": sequence, "dropped": dropped, "processingMs": (now - began) * 1000,
                  "provider": segmenter.provider if mode != "none" else "No matting",
                  "matteMs": matte_ms, "captureWaitMs": (captured - began) * 1000,
                  "retainedWidth": retained_width, "retainedHeight": retained_height})
            count += 1
            if frame_limit and count >= frame_limit:
                break
            time.sleep(max(0, 1 / target_fps - (time.monotonic() - began)))
    finally:
        alive.clear()
        if reader is not None:
            reader.join(timeout=2)
        if reader is None or not reader.is_alive():
            capture.release()
        if snapshot_thread is not None:
            snapshot_thread.join(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--ui-overlay", action="store_true")
    args = parser.parse_args()
    try:
        run(json.loads(args.request), args.frames, args.ui_overlay)
    except (ValueError, RuntimeError, OSError, cv2.error, subprocess.SubprocessError) as error:
        emit({"error": str(error)})
        raise SystemExit(1)
