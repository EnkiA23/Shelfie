from __future__ import annotations

from django.conf import settings
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from scanner.metrics import daily_spend_total, daily_vlm_calls_total
from scanner.models import CatalogBook, LibraryEntry, ScanLog
from scanner.permissions import HasAppToken
from scanner.pipeline import run_scan_pipeline
from scanner.serializers import (
    CatalogBookSerializer,
    LibraryEntryCreateSerializer,
    LibraryEntrySerializer,
)


class ScanBookshelfView(APIView):
    permission_classes = [HasAppToken]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scan"
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        daily_cap = getattr(settings, "DAILY_SPEND_CAP_USD", 5.0)
        if daily_spend_total() >= daily_cap:
            return Response(
                {
                    "detail": (
                        "Daily demo budget reached. Try again tomorrow or raise the cap locally."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        daily_vlm_cap = getattr(settings, "DAILY_VLM_CALLS_CAP", 50)
        if daily_vlm_calls_total() >= daily_vlm_cap:
            return Response(
                {"detail": "Daily vision API call limit reached. Try again tomorrow."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        upload = request.FILES.get("photo")
        if not upload:
            return Response(
                {"detail": "photo file is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        max_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 8)
        if upload.size > max_mb * 1024 * 1024:
            return Response(
                {"detail": f"Upload exceeds {max_mb} MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (upload.content_type or "").lower()
        if not content_type.startswith("image/"):
            return Response(
                {"detail": "Upload must be an image."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image_bytes = upload.read()
            use_stub = request.query_params.get("stub") == "1" or getattr(
                settings, "SCAN_USE_STUB", False
            )
            result = run_scan_pipeline(image_bytes, use_stub=use_stub)
        except Exception:
            result = {
                "high_confidence": [],
                "needs_review": [],
                "metrics": {
                    "latency_ms": 0,
                    "est_cost_usd": 0.0,
                    "spines_detected": 0,
                    "spines_matched": 0,
                    "warnings": ["unexpected_pipeline_error"],
                },
            }

        metrics = result.get("metrics", {})
        try:
            ScanLog.objects.create(
                latency_ms=int(metrics.get("latency_ms", 0)),
                est_cost_usd=float(metrics.get("est_cost_usd", 0.0)),
                spines_detected=int(metrics.get("spines_detected", 0)),
                spines_matched=int(metrics.get("spines_matched", 0)),
            )
        except Exception:
            pass

        return Response(result, status=status.HTTP_200_OK)


class LibraryViewSet(viewsets.ModelViewSet):
    permission_classes = [HasAppToken]
    queryset = LibraryEntry.objects.select_related("catalog_book").all()

    def get_throttles(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            self.throttle_scope = "library_write"
        else:
            self.throttle_scope = None
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "create":
            return LibraryEntryCreateSerializer
        return LibraryEntrySerializer


class CatalogSearchView(APIView):
    permission_classes = [HasAppToken]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "catalog_search"

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([])

        books = CatalogBook.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        ).order_by("title")[:10]
        return Response(CatalogBookSerializer(books, many=True).data)
