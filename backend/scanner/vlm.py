"""Stage 2: hosted vision-language extraction of title/author from a spine crop.

Every call returns a `VlmResult` rather than a bare dict-or-None. A silent `None`
hides the difference between "the key is wrong", "the model was retired" and "the
model answered but the JSON was broken" — three failures with three different
fixes, all of which we hit during development.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from PIL import Image

EXTRACTION_PROMPT = (
    "Read the book title and author from this book spine crop. "
    'Return JSON only: {"extracted_title":"...","extracted_author":"..."}. '
    "Use empty strings if unreadable."
)

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

# Retrying these is pointless: the request is malformed or the account is wrong,
# and a second identical call just burns latency and quota.
NON_RETRYABLE = frozenset({"vlm_not_configured", "vlm_auth_failed", "vlm_model_unavailable"})

# Failures where the provider never ran the model, so nothing was charged.
# Counting these would inflate the daily spend cap and lock us out for free.
UNBILLED_FAILURES = frozenset(
    {
        "vlm_not_configured",
        "vlm_auth_failed",
        "vlm_model_unavailable",
        "vlm_rate_limited",
        "vlm_timeout",
    }
)


@dataclass(frozen=True)
class VlmResult:
    """Outcome of one crop extraction, successful or not.

    `input_tokens`/`output_tokens` come from the provider's own usage accounting
    when it reports them, so the daily spend cap tracks real billing rather than
    a hardcoded guess.
    """

    title: str = ""
    author: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    failure_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_code is None


def _dry_run_result() -> VlmResult:
    return VlmResult(title="The Great Gatsby", author="F. Scott Fitzgerald")


def _prepare_crop(crop: Image.Image) -> Image.Image:
    max_edge = getattr(settings, "VLM_MAX_IMAGE_EDGE", 512)
    crop = crop.convert("RGB")
    w, h = crop.size
    if max(w, h) <= max_edge:
        return crop
    scale = max_edge / max(w, h)
    return crop.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def _image_to_base64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _result_from_payload(raw: str, input_tokens: int, output_tokens: int) -> VlmResult:
    """Turn the model's text answer into a result, tolerating markdown fences.

    Tokens are attached even on a parse failure — the provider bills for a bad
    answer exactly like a good one, so the cap has to see it either way.
    """
    unreadable = VlmResult(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        failure_code="vlm_unreadable_response",
    )

    text = raw.strip()
    if not text:
        return unreadable
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return unreadable
    if not isinstance(parsed, dict):
        return unreadable

    return VlmResult(
        title=str(parsed.get("extracted_title", "")).strip(),
        author=str(parsed.get("extracted_author", "")).strip(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def api_key_for_provider() -> str:
    provider = getattr(settings, "VLM_PROVIDER", "gemini").lower()
    key_setting = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(provider, "GEMINI_API_KEY")
    return getattr(settings, key_setting, "")


def is_configured() -> bool:
    """True when a live call can actually be made, i.e. dry run off and a key present."""
    if getattr(settings, "VLM_DRY_RUN", False):
        return True
    return bool(api_key_for_provider())


def _http_failure_code(status: int) -> str:
    if status in (401, 403):
        return "vlm_auth_failed"
    if status == 404:
        return "vlm_model_unavailable"
    if status == 429:
        return "vlm_rate_limited"
    return "vlm_provider_error"


def _call_provider(crop: Image.Image, timeout: int) -> VlmResult:
    provider = getattr(settings, "VLM_PROVIDER", "gemini").lower()
    prepared = _prepare_crop(crop)

    if provider == "anthropic":
        return _call_anthropic(prepared, timeout)
    if provider == "openai":
        return _call_openai(prepared, timeout)
    return _call_gemini(prepared, timeout)


def extract_text_from_crop(crop: Image.Image) -> VlmResult:
    if getattr(settings, "VLM_DRY_RUN", False):
        return _dry_run_result()
    if not api_key_for_provider():
        return VlmResult(failure_code="vlm_not_configured")

    timeout = getattr(settings, "VLM_TIMEOUT_SECONDS", 15)
    max_retries = max(0, getattr(settings, "VLM_MAX_RETRIES", 1))

    result = VlmResult(failure_code="vlm_provider_error")
    for _attempt in range(max_retries + 1):
        try:
            result = _call_provider(crop, timeout)
        except (TimeoutError, OSError):
            result = VlmResult(failure_code="vlm_timeout")
        except Exception:  # noqa: BLE001 - a provider bug must not kill the scan
            result = VlmResult(failure_code="vlm_provider_error")
        if result.ok or result.failure_code in NON_RETRYABLE:
            return result
    return result


def _call_gemini(crop: Image.Image, timeout: int) -> VlmResult:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return VlmResult(failure_code="vlm_not_configured")

    model = getattr(settings, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": EXTRACTION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": _image_to_base64(crop),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 120,
            "responseMimeType": "application/json",
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return VlmResult(failure_code=_http_failure_code(exc.code))
    except (urllib.error.URLError, TimeoutError):
        return VlmResult(failure_code="vlm_timeout")
    except json.JSONDecodeError:
        return VlmResult(failure_code="vlm_unreadable_response")

    usage = body.get("usageMetadata") or {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)

    candidates = body.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts") or [] if candidates else []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    return _result_from_payload(text, input_tokens, output_tokens)


def _call_openai(crop: Image.Image, timeout: int) -> VlmResult:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return VlmResult(failure_code="vlm_not_configured")

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{_image_to_base64(crop)}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 120,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return VlmResult(failure_code=_http_failure_code(exc.code))
    except (urllib.error.URLError, TimeoutError):
        return VlmResult(failure_code="vlm_timeout")
    except json.JSONDecodeError:
        return VlmResult(failure_code="vlm_unreadable_response")

    usage = body.get("usage") or {}
    choices = body.get("choices") or []
    if not choices:
        return VlmResult(failure_code="vlm_unreadable_response")
    content = choices[0].get("message", {}).get("content", "")
    return _result_from_payload(
        content,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
    )


def _call_anthropic(crop: Image.Image, timeout: int) -> VlmResult:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return VlmResult(failure_code="vlm_not_configured")

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 120,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": _image_to_base64(crop),
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return VlmResult(failure_code=_http_failure_code(exc.code))
    except (urllib.error.URLError, TimeoutError):
        return VlmResult(failure_code="vlm_timeout")
    except json.JSONDecodeError:
        return VlmResult(failure_code="vlm_unreadable_response")

    usage = body.get("usage") or {}
    text_blocks = [
        block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"
    ]
    if not text_blocks:
        return VlmResult(failure_code="vlm_unreadable_response")
    return _result_from_payload(
        text_blocks[0],
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
    )
