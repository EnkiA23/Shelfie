"""Stage 1: local, CPU-only spine detection.

Primary backend is a pretrained YOLOv8n checkpoint (COCO, "book" class).
If the weights or the ultralytics package are unavailable, we fall back to an
OpenCV vertical-edge projection that segments the shelf into spine columns.
Both paths return the same BoundingBox list, so the pipeline never branches.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from PIL import Image

COCO_BOOK_CLASS_ID = 73

_model_lock = threading.Lock()
_model_cache: object | None = None
_model_load_failed = False


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    source: str = "opencv"

    def crop(self, image: Image.Image) -> Image.Image:
        return image.crop((self.x, self.y, self.x + self.width, self.y + self.height))


def _load_yolo_model():
    """Load YOLOv8n once per process. Returns None if unavailable."""
    global _model_cache, _model_load_failed

    if _model_cache is not None:
        return _model_cache
    if _model_load_failed:
        return None

    with _model_lock:
        if _model_cache is not None:
            return _model_cache
        if _model_load_failed:
            return None
        try:
            from pathlib import Path

            from ultralytics import YOLO

            weights = getattr(settings, "YOLO_WEIGHTS", "yolov8n.pt")
            # Weights are gitignored; fall back to the bare name so ultralytics
            # fetches the checkpoint on first run of a clean clone.
            if not Path(weights).exists():
                weights = "yolov8n.pt"
            _model_cache = YOLO(weights)
        except Exception:
            _model_load_failed = True
            return None
    return _model_cache


def _detect_with_yolo(image: Image.Image) -> list[BoundingBox]:
    model = _load_yolo_model()
    if model is None:
        return []

    conf = getattr(settings, "YOLO_MIN_CONFIDENCE", 0.15)
    results = model.predict(
        source=image,
        device="cpu",
        conf=conf,
        imgsz=getattr(settings, "YOLO_IMAGE_SIZE", 640),
        verbose=False,
    )

    boxes: list[BoundingBox] = []
    for result in results:
        for box in getattr(result, "boxes", []) or []:
            class_id = int(box.cls[0])
            if class_id != COCO_BOOK_CLASS_ID:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            width, height = x2 - x1, y2 - y1
            if width <= 0 or height <= 0:
                continue
            boxes.append(
                BoundingBox(
                    x=max(0, x1),
                    y=max(0, y1),
                    width=width,
                    height=height,
                    confidence=float(box.conf[0]),
                    source="yolov8n",
                )
            )
    return boxes


def _detect_with_opencv(image: Image.Image) -> list[BoundingBox]:
    """Segment spines by looking for vertical edge peaks across the shelf."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    width, height = image.size
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Vertical edges are the gaps between spines; horizontal ones are shelf boards.
    sobel_x = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    vertical_energy = np.abs(sobel_x).sum(axis=0)
    if vertical_energy.max() <= 0:
        return []

    normalized = vertical_energy / vertical_energy.max()
    threshold = float(normalized.mean() + normalized.std())
    min_spine_width = max(12, width // 60)

    separators = [0]
    last = 0
    for column in range(1, width - 1):
        if normalized[column] < threshold:
            continue
        if column - last < min_spine_width:
            continue
        separators.append(column)
        last = column
    separators.append(width)

    boxes: list[BoundingBox] = []
    for left, right in zip(separators, separators[1:]):
        spine_width = right - left
        if spine_width < min_spine_width:
            continue
        aspect = height / max(spine_width, 1)
        if aspect < 1.5:
            continue
        boxes.append(
            BoundingBox(
                x=left,
                y=0,
                width=spine_width,
                height=height,
                confidence=min(1.0, aspect / 10.0),
                source="opencv",
            )
        )
    return boxes


def detect_spines(image_bytes: bytes) -> list[BoundingBox]:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    backend = getattr(settings, "DETECTOR_BACKEND", "auto").lower()

    boxes: list[BoundingBox] = []
    if backend in {"auto", "yolo"}:
        boxes = _detect_with_yolo(image)
    if not boxes and backend in {"auto", "opencv"}:
        boxes = _detect_with_opencv(image)

    boxes.sort(key=lambda b: b.confidence * b.width * b.height, reverse=True)
    return boxes[:40]
