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


# Fallback token counts, used only when a provider does not report usage.
# Measured against Gemini Flash-Lite on a 512px spine crop: ~1070 in, ~16 out.
ASSUMED_INPUT_TOKENS_PER_CALL = 1070
ASSUMED_OUTPUT_TOKENS_PER_CALL = 20


def estimate_vlm_cost(
    unmetered_calls: int = 0,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    """Cost of a scan in USD.

    `input_tokens`/`output_tokens` are the provider's own reported totals and are
    billed exactly. `unmetered_calls` covers billable calls where the provider did
    not report usage, and is priced with the measured per-call assumptions above.
    Calls the provider never served — a rejected key, a retired model — are
    neither, and must not be passed here at all.
    """
    provider = getattr(settings, "VLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        input_rate = 0.10 / 1_000_000
        output_rate = 0.40 / 1_000_000
    elif provider == "anthropic":
        input_rate = 3.0 / 1_000_000
        output_rate = 15.0 / 1_000_000
    else:
        input_rate = 0.15 / 1_000_000
        output_rate = 0.60 / 1_000_000

    total_input = input_tokens + (unmetered_calls * ASSUMED_INPUT_TOKENS_PER_CALL)
    total_output = output_tokens + (unmetered_calls * ASSUMED_OUTPUT_TOKENS_PER_CALL)
    return (total_input * input_rate) + (total_output * output_rate)


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
