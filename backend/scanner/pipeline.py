from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

from django.conf import settings
from PIL import Image

from scanner.detector import BoundingBox, detect_spines
from scanner.matching import CatalogBook as MatchBook
from scanner.matching import match_against_catalog
from scanner.metrics import MetricsTracker, StageTimer, daily_vlm_calls_total, estimate_vlm_cost
from scanner.models import CatalogBook
from scanner.vlm import UNBILLED_FAILURES, VlmResult, extract_text_from_crop, is_configured


def _confidence_threshold() -> float:
    return float(getattr(settings, "CONFIDENCE_THRESHOLD", 0.85))


def _catalog_to_match_books() -> list[MatchBook]:
    books = []
    for row in CatalogBook.objects.all():
        books.append(
            MatchBook(
                id=row.external_id,
                title=row.title,
                author=row.author,
                alternate_titles=tuple(row.alternate_titles or []),
                edition_info=row.edition_info or "",
            )
        )
    return books


def _serialize_candidate(candidate, db_id_map: dict[int, int]) -> dict[str, Any]:
    book = candidate.catalog_book
    return {
        "catalog_book_id": db_id_map.get(book.id),
        "catalog_external_id": book.id,
        "title": book.title,
        "author": book.author,
        "edition_info": book.edition_info,
        "confidence_score": candidate.score,
        "alternatives": [],
    }


def _crop_thumbnail(crop: Image.Image | None) -> str | None:
    """Small base64 JPEG so the review screen can show what the VLM saw."""
    if crop is None or not getattr(settings, "INCLUDE_CROP_THUMBNAILS", True):
        return None
    try:
        max_edge = getattr(settings, "CROP_THUMBNAIL_MAX_EDGE", 160)
        thumb = crop.copy()
        thumb.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        thumb.convert("RGB").save(buffer, format="JPEG", quality=60)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return None


def _build_item(
    *,
    extracted_title: str,
    extracted_author: str,
    candidates: list,
    db_id_map: dict[int, int],
    crop_index: int,
    bbox: BoundingBox | None,
    warnings: list[str],
    crop: Image.Image | None = None,
) -> dict[str, Any]:
    top = candidates[0] if candidates else None
    score = top.score if top else 0.0
    item = {
        "crop_index": crop_index,
        "extracted_title": extracted_title,
        "extracted_author": extracted_author,
        "confidence_score": score,
        "matched_book": _serialize_candidate(top, db_id_map) if top else None,
        "alternatives": [
            _serialize_candidate(c, db_id_map) for c in (candidates[1:4] if candidates else [])
        ],
        "bbox": {
            "x": bbox.x,
            "y": bbox.y,
            "width": bbox.width,
            "height": bbox.height,
        }
        if bbox
        else None,
        "crop_thumbnail": _crop_thumbnail(crop),
        "warnings": warnings,
    }
    return item


def _extract_crops(crops: list[Image.Image]) -> list[VlmResult | None]:
    """Read every crop, in parallel, preserving order.

    Stage 2 is network-bound: measured sequentially, ten crops took ~16 s because
    each ~1.4 s round trip waited for the last. A small thread pool collapses that
    to roughly one round trip. The pool is bounded rather than unbounded so a
    wide shelf cannot open thirty sockets at once and trip provider rate limits.
    """
    if not crops:
        return []

    concurrency = max(1, int(getattr(settings, "VLM_CONCURRENCY", 5)))
    if concurrency == 1 or len(crops) == 1:
        return [_safe_extract(crop) for crop in crops]

    with ThreadPoolExecutor(max_workers=min(concurrency, len(crops))) as pool:
        return list(pool.map(_safe_extract, crops))


def _safe_extract(crop: Image.Image) -> VlmResult | None:
    """A single crop failing must never take down the other nine."""
    try:
        return extract_text_from_crop(crop)
    except Exception:
        return None


def run_scan_pipeline(image_bytes: bytes, *, use_stub: bool = False) -> dict[str, Any]:
    metrics = MetricsTracker()
    catalog = _catalog_to_match_books()
    db_id_map = {row.external_id: row.id for row in CatalogBook.objects.only("id", "external_id")}

    if use_stub:
        stub_items = [
            _build_item(
                extracted_title="The Great Gatsby",
                extracted_author="F. Scott Fitzgerald",
                candidates=match_against_catalog(
                    "The Great Gatsby", "F. Scott Fitzgerald", catalog
                ),
                db_id_map=db_id_map,
                crop_index=0,
                bbox=None,
                warnings=[],
            ),
            _build_item(
                extracted_title="The Road",
                extracted_author="Cormac McCarthy",
                candidates=match_against_catalog("The Road", "Cormac McCarthy", catalog),
                db_id_map=db_id_map,
                crop_index=1,
                bbox=None,
                warnings=[],
            ),
        ]
        threshold = _confidence_threshold()
        high = [i for i in stub_items if i["confidence_score"] >= threshold]
        review = [i for i in stub_items if i["confidence_score"] < threshold]
        metrics.spines_detected = len(stub_items)
        metrics.spines_matched = len(high)
        return {"high_confidence": high, "needs_review": review, "metrics": metrics.to_dict()}

    dry_run = bool(getattr(settings, "VLM_DRY_RUN", False))
    if not is_configured():
        # Live mode with no key would otherwise look like a model failure on every crop.
        metrics.warnings.append("vlm_not_configured")
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    boxes: list[BoundingBox] = []

    with StageTimer(metrics, "stage1_ms"):
        try:
            boxes = detect_spines(image_bytes)
        except Exception:
            metrics.warnings.append("detector_error")
            boxes = []

    if not boxes:
        metrics.warnings.append("zero_detections_fallback_full_image")
        boxes = [BoundingBox(0, 0, image.width, image.height, confidence=1.0, source="fallback")]

    metrics.detector_backend = boxes[0].source

    max_calls = getattr(settings, "MAX_VLM_CALLS_PER_SCAN", 10)
    daily_cap = getattr(settings, "DAILY_VLM_CALLS_CAP", 50)
    remaining_today = max(0, daily_cap - daily_vlm_calls_total())
    if remaining_today == 0:
        metrics.warnings.append("daily_vlm_cap_reached")
        return {
            "high_confidence": [],
            "needs_review": [],
            "metrics": metrics.to_dict(),
        }
    max_calls = min(max_calls, remaining_today)
    selected_boxes = boxes[:max_calls]
    if len(boxes) > max_calls:
        metrics.warnings.append(f"vlm_calls_capped_at_{max_calls}")

    metrics.spines_detected = len(selected_boxes)
    threshold = _confidence_threshold()
    high_confidence: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    unmetered_calls = 0
    input_tokens = 0
    output_tokens = 0

    crops = [bbox.crop(image) for bbox in selected_boxes]

    with StageTimer(metrics, "stage2_ms"):
        extractions = _extract_crops(crops)

        for index, (bbox, crop, extraction) in enumerate(
            zip(selected_boxes, crops, extractions, strict=True)
        ):
            item_warnings: list[str] = []
            extracted_title = ""
            extracted_author = ""

            if extraction is None:
                item_warnings.append("vlm_error")
            else:
                if extraction.input_tokens or extraction.output_tokens:
                    input_tokens += extraction.input_tokens
                    output_tokens += extraction.output_tokens
                elif extraction.failure_code not in UNBILLED_FAILURES:
                    unmetered_calls += 1
                if extraction.ok:
                    extracted_title = extraction.title
                    extracted_author = extraction.author
                else:
                    item_warnings.append(extraction.failure_code)

            try:
                candidates = match_against_catalog(extracted_title, extracted_author, catalog)
            except Exception:
                candidates = []
                item_warnings.append("matching_error")

            item = _build_item(
                extracted_title=extracted_title,
                extracted_author=extracted_author,
                candidates=candidates,
                db_id_map=db_id_map,
                crop_index=index,
                bbox=bbox,
                warnings=item_warnings,
                crop=crop,
            )

            if item["confidence_score"] >= threshold and extracted_title:
                high_confidence.append(item)
            else:
                needs_review.append(item)

    metrics.est_cost_usd = (
        0.0
        if dry_run
        else estimate_vlm_cost(
            unmetered_calls, input_tokens=input_tokens, output_tokens=output_tokens
        )
    )
    metrics.spines_matched = len(high_confidence)
    metrics.vlm_provider = "dry_run" if dry_run else getattr(settings, "VLM_PROVIDER", "gemini")

    # A key or model problem repeats on every crop. Surface it once at scan level so
    # the app can show one actionable banner instead of ten identical row warnings.
    for code in ("vlm_not_configured", "vlm_auth_failed", "vlm_model_unavailable"):
        if code not in metrics.warnings and any(
            code in item["warnings"] for item in (*high_confidence, *needs_review)
        ):
            metrics.warnings.append(code)

    return {
        "high_confidence": high_confidence,
        "needs_review": needs_review,
        "metrics": metrics.to_dict(),
    }
