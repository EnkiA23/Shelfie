"""Graceful-failure tests for the scan pipeline and the scan endpoint.

The brief requires that a detector crash, a VLM timeout, malformed model JSON,
or zero detections never crash the app or return an empty screen.
"""

import time
from io import BytesIO

import pytest
from django.urls import reverse
from PIL import Image

from scanner import pipeline as pipeline_module
from scanner.models import CatalogBook, LibraryEntry
from scanner.pipeline import run_scan_pipeline
from scanner.vlm import VlmResult

AUTH = {"HTTP_AUTHORIZATION": "Bearer dev-token"}


def make_image_bytes(width: int = 320, height: int = 240, color: str = "white") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def catalog(db):
    CatalogBook.objects.create(
        external_id=11, title="The Great Gatsby", author="F. Scott Fitzgerald"
    )
    CatalogBook.objects.create(external_id=5, title="The Road", author="Cormac McCarthy")
    return CatalogBook.objects.all()


@pytest.fixture
def api_client(settings):
    from rest_framework.test import APIClient

    settings.APP_SHARED_TOKEN = "dev-token"
    settings.VLM_DRY_RUN = True
    return APIClient()


def test_zero_detections_falls_back_to_full_image(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = True
    monkeypatch.setattr(pipeline_module, "detect_spines", lambda _bytes: [])

    result = run_scan_pipeline(make_image_bytes())

    assert "zero_detections_fallback_full_image" in result["metrics"]["warnings"]
    assert result["metrics"]["spines_detected"] == 1
    assert result["high_confidence"] or result["needs_review"]


def test_detector_exception_is_contained(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = True

    def boom(_bytes):
        raise RuntimeError("detector exploded")

    monkeypatch.setattr(pipeline_module, "detect_spines", boom)
    result = run_scan_pipeline(make_image_bytes())

    assert "detector_error" in result["metrics"]["warnings"]
    assert isinstance(result["high_confidence"], list)


def test_vlm_timeout_routes_item_to_review(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = False
    monkeypatch.setattr(
        pipeline_module,
        "extract_text_from_crop",
        lambda _crop: VlmResult(failure_code="vlm_timeout"),
    )

    result = run_scan_pipeline(make_image_bytes())

    assert result["high_confidence"] == []
    assert result["needs_review"], "a failed read must still surface to the user"
    assert "vlm_timeout" in result["needs_review"][0]["warnings"]


@pytest.mark.parametrize(
    "failure_code",
    ["vlm_auth_failed", "vlm_model_unavailable", "vlm_rate_limited", "vlm_unreadable_response"],
)
def test_each_vlm_failure_keeps_its_own_code(catalog, settings, monkeypatch, failure_code):
    """A bad key, a retired model and a broken answer need three different fixes,
    so they must not collapse into one generic warning."""
    settings.VLM_DRY_RUN = False
    monkeypatch.setattr(
        pipeline_module,
        "extract_text_from_crop",
        lambda _crop: VlmResult(failure_code=failure_code),
    )

    result = run_scan_pipeline(make_image_bytes())

    assert result["high_confidence"] == []
    assert failure_code in result["needs_review"][0]["warnings"]


def test_key_level_failures_are_promoted_to_scan_metrics(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = False
    monkeypatch.setattr(
        pipeline_module,
        "extract_text_from_crop",
        lambda _crop: VlmResult(failure_code="vlm_auth_failed"),
    )

    result = run_scan_pipeline(make_image_bytes())

    assert "vlm_auth_failed" in result["metrics"]["warnings"], (
        "a whole-scan problem belongs in one banner, not repeated on every row"
    )


def test_reported_tokens_drive_the_cost_estimate(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = False
    monkeypatch.setattr(
        pipeline_module,
        "extract_text_from_crop",
        lambda _crop: VlmResult(
            title="Beloved", author="Toni Morrison", input_tokens=1000, output_tokens=100
        ),
    )

    result = run_scan_pipeline(make_image_bytes())

    expected = (1000 * 0.10 + 100 * 0.40) / 1_000_000
    assert result["metrics"]["est_cost_usd"] == pytest.approx(expected, abs=1e-9)


def test_parallel_extraction_keeps_crops_in_order(catalog, settings, monkeypatch):
    """Crops are read on a thread pool, so results must be zipped back to the box
    they came from — otherwise a title lands on the wrong spine's thumbnail."""
    settings.VLM_DRY_RUN = False
    settings.VLM_CONCURRENCY = 4
    settings.MAX_VLM_CALLS_PER_SCAN = 6

    from scanner.detector import BoundingBox

    # Distinct widths so each crop is identifiable once it reaches the worker.
    boxes = [BoundingBox(0, 0, (i + 1) * 10, 100, 0.9) for i in range(6)]
    monkeypatch.setattr(pipeline_module, "detect_spines", lambda _bytes: boxes)

    # Stagger the sleeps so the pool deliberately finishes out of submission order.
    def extract(crop):
        index = crop.size[0] // 10 - 1
        time.sleep(0.02 * (6 - index))
        return VlmResult(title=f"Title {index}", author="A")

    monkeypatch.setattr(pipeline_module, "extract_text_from_crop", extract)

    result = run_scan_pipeline(make_image_bytes(width=120, height=100))
    items = sorted(
        [*result["high_confidence"], *result["needs_review"]], key=lambda i: i["crop_index"]
    )

    assert [item["extracted_title"] for item in items] == [f"Title {i}" for i in range(6)]


def test_calls_the_provider_never_served_are_not_billed(catalog, settings, monkeypatch):
    """A retired model returns 404 before inference. Charging for it would burn the
    daily spend cap on requests that cost nothing."""
    settings.VLM_DRY_RUN = False
    monkeypatch.setattr(
        pipeline_module,
        "extract_text_from_crop",
        lambda _crop: VlmResult(failure_code="vlm_model_unavailable"),
    )

    result = run_scan_pipeline(make_image_bytes())

    assert result["metrics"]["est_cost_usd"] == 0.0


def test_vlm_exception_does_not_crash_scan(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = False

    def boom(_crop):
        raise RuntimeError("provider 500")

    monkeypatch.setattr(pipeline_module, "extract_text_from_crop", boom)
    result = run_scan_pipeline(make_image_bytes())

    assert result["needs_review"]
    assert "vlm_error" in result["needs_review"][0]["warnings"]


def test_live_mode_without_key_is_reported_not_faked(catalog, settings):
    settings.VLM_DRY_RUN = False
    settings.VLM_PROVIDER = "gemini"
    settings.GEMINI_API_KEY = ""

    result = run_scan_pipeline(make_image_bytes())

    assert "vlm_not_configured" in result["metrics"]["warnings"]
    assert result["high_confidence"] == [], "a missing key must not produce confident matches"


def test_per_scan_vlm_call_cap_is_enforced(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = True
    settings.MAX_VLM_CALLS_PER_SCAN = 2

    from scanner.detector import BoundingBox

    boxes = [BoundingBox(i * 10, 0, 10, 100, 0.9) for i in range(8)]
    monkeypatch.setattr(pipeline_module, "detect_spines", lambda _bytes: boxes)

    result = run_scan_pipeline(make_image_bytes())

    assert result["metrics"]["spines_detected"] == 2
    assert any(w.startswith("vlm_calls_capped_at") for w in result["metrics"]["warnings"])


def test_scan_endpoint_rejects_non_image(api_client, catalog):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
    response = api_client.post(reverse("scan"), {"photo": upload}, format="multipart", **AUTH)

    assert response.status_code == 400


def test_scan_endpoint_requires_token(api_client, catalog):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("shelf.jpg", make_image_bytes(), content_type="image/jpeg")
    response = api_client.post(reverse("scan"), {"photo": upload}, format="multipart")

    assert response.status_code in {401, 403}


def test_scan_endpoint_returns_200_with_stub(api_client, catalog):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("shelf.jpg", make_image_bytes(), content_type="image/jpeg")
    response = api_client.post(
        f"{reverse('scan')}?stub=1", {"photo": upload}, format="multipart", **AUTH
    )

    assert response.status_code == 200
    body = response.json()
    assert "high_confidence" in body and "needs_review" in body
    assert "metrics" in body


def test_library_create_validates_title(api_client, catalog):
    response = api_client.post(
        reverse("library-list"),
        {"raw_title": "   ", "raw_author": "Someone", "confidence_score": 0.5},
        format="json",
        **AUTH,
    )

    assert response.status_code == 400
    assert LibraryEntry.objects.count() == 0
