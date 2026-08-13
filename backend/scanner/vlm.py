from __future__ import annotations

import base64
import json
import re
from io import BytesIO

from django.conf import settings
from PIL import Image

EXTRACTION_PROMPT = (
    "Read the book title and author from this book spine crop. "
    'Return JSON only: {"extracted_title":"...","extracted_author":"..."}. '
    "Use empty strings if unreadable."
)


def _dry_run_response() -> dict[str, str]:
    return {"extracted_title": "The Great Gatsby", "extracted_author": "F. Scott Fitzgerald"}


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


def _parse_extraction_payload(raw: str) -> dict[str, str] | None:
    text = raw.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "extracted_title": str(parsed.get("extracted_title", "")).strip(),
        "extracted_author": str(parsed.get("extracted_author", "")).strip(),
    }


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


def _call_provider(crop: Image.Image, timeout: int) -> dict[str, str] | None:
    provider = getattr(settings, "VLM_PROVIDER", "gemini").lower()
    prepared = _prepare_crop(crop)

    if provider == "gemini":
        return _call_gemini(prepared, timeout)
    if provider == "anthropic":
        return _call_anthropic(prepared, timeout)
    if provider == "openai":
        return _call_openai(prepared, timeout)
    return _call_gemini(prepared, timeout)


def extract_text_from_crop(crop: Image.Image) -> dict[str, str] | None:
    if getattr(settings, "VLM_DRY_RUN", False):
        return _dry_run_response()

    timeout = getattr(settings, "VLM_TIMEOUT_SECONDS", 15)
    max_retries = max(0, getattr(settings, "VLM_MAX_RETRIES", 1))

    for _attempt in range(max_retries + 1):
        try:
            result = _call_provider(crop, timeout)
            if result is not None:
                return result
        except Exception:
            continue
    return None


def _call_gemini(crop: Image.Image, timeout: int) -> dict[str, str] | None:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return None

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
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
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    candidates = body.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    return _parse_extraction_payload(text)


def _call_openai(crop: Image.Image, timeout: int) -> dict[str, str] | None:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None

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
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    content = body["choices"][0]["message"]["content"]
    return _parse_extraction_payload(content)


def _call_anthropic(crop: Image.Image, timeout: int) -> dict[str, str] | None:
    import urllib.error
    import urllib.request

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

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
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    text_blocks = [
        block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"
    ]
    if not text_blocks:
        return None
    return _parse_extraction_payload(text_blocks[0])
