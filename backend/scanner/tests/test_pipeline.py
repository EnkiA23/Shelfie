"""Graceful-failure tests for the scan pipeline and the scan endpoint.

The brief requires that a detector crash, a VLM timeout, malformed model JSON,
or zero detections never crash the app or return an empty screen.
"""

from io import BytesIO

import pytest
from django.urls import reverse
from PIL import Image

from scanner import pipeline as pipeline_module
from scanner.models import CatalogBook, LibraryEntry
from scanner.pipeline import run_scan_pipeline

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
    monkeypatch.setattr(pipeline_module, "extract_text_from_crop", lambda _crop: None)

    result = run_scan_pipeline(make_image_bytes())

    assert result["high_confidence"] == []
    assert result["needs_review"], "a failed read must still surface to the user"
    assert "vlm_timeout_or_malformed" in result["needs_review"][0]["warnings"]


def test_vlm_exception_does_not_crash_scan(catalog, settings, monkeypatch):
    settings.VLM_DRY_RUN = False

    def boom(_crop):
        raise RuntimeError("provider 500")

    monkeypatch.setattr(pipeline_module, "extract_text_from_crop", boom)
    result = run_scan_pipeline(make_image_bytes())

    assert result["needs_review"]
    assert "vlm_error" in result["needs_review"][0]["warnings"]


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
