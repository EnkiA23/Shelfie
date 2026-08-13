from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings


@dataclass
class MetricsTracker:
    stage1_ms: int = 0
    stage2_ms: int = 0
    est_cost_usd: float = 0.0
    spines_detected: int = 0
    spines_matched: int = 0
    detector_backend: str = "none"
    vlm_provider: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def latency_ms(self) -> int:
        return self.stage1_ms + self.stage2_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "stage1_ms": self.stage1_ms,
            "stage2_ms": self.stage2_ms,
            "est_cost_usd": round(self.est_cost_usd, 6),
            "spines_detected": self.spines_detected,
            "spines_matched": self.spines_matched,
            "detector_backend": self.detector_backend,
            "vlm_provider": self.vlm_provider,
            "warnings": self.warnings,
        }


class StageTimer:
    def __init__(self, metrics: MetricsTracker, attr: str):
        self.metrics = metrics
        self.attr = attr
        self.start = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed_ms = int((time.perf_counter() - self.start) * 1000)
        setattr(self.metrics, self.attr, elapsed_ms)


def estimate_vlm_cost(num_calls: int, *, input_tokens: int = 900, output_tokens: int = 60) -> float:
    provider = getattr(settings, "VLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        # Gemini Flash free/low tier — approximate paid rate for cap tracking
        input_rate = 0.10 / 1_000_000
        output_rate = 0.40 / 1_000_000
    elif provider == "anthropic":
        input_rate = 3.0 / 1_000_000
        output_rate = 15.0 / 1_000_000
    else:
        input_rate = 0.15 / 1_000_000
        output_rate = 0.60 / 1_000_000
    per_call = (input_tokens * input_rate) + (output_tokens * output_rate)
    return per_call * num_calls


def daily_vlm_calls_total() -> int:
    from django.db.models import Sum
    from django.utils import timezone

    from scanner.models import ScanLog

    today = timezone.now().date()
    total = ScanLog.objects.filter(created_at__date=today).aggregate(
        total=Sum("spines_detected")
    )["total"]
    return int(total or 0)


def daily_spend_total() -> float:
    from django.db.models import Sum
    from django.utils import timezone

    from scanner.models import ScanLog

    today = timezone.now().date()
    total = ScanLog.objects.filter(created_at__date=today).aggregate(
        total=Sum("est_cost_usd")
    )["total"]
    return float(total or 0.0)
