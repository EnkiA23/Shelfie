"""Verify that the configured vision provider, key and model actually work.

Run this before a demo. It answers the three questions that cost us the most time
during development, without spending more than one crop's worth of tokens:

    python manage.py check_vlm
    python manage.py check_vlm --list-models

Hosted model names are retired on a rolling basis, so a config that worked last
month can fail with a 404 that looks nothing like "your model is gone".
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from scanner.vlm import api_key_for_provider, extract_text_from_crop

REMEDIES = {
    "vlm_not_configured": "Set the API key for VLM_PROVIDER in apps/backend/.env.",
    "vlm_auth_failed": "The key was rejected. Check for typos or a revoked key.",
    "vlm_model_unavailable": (
        "The model name no longer exists. Run with --list-models and set GEMINI_MODEL."
    ),
    "vlm_rate_limited": "You are being rate limited. Wait and retry.",
    "vlm_timeout": "The provider did not respond in VLM_TIMEOUT_SECONDS.",
    "vlm_unreadable_response": "The model replied, but not with the JSON we asked for.",
    "vlm_provider_error": "The provider returned an unexpected error.",
}


def _sample_spine() -> Image.Image:
    """A synthetic spine, so the check costs one small crop and needs no fixtures."""
    image = Image.new("RGB", (90, 480), "#2b3a55")
    draw = ImageDraw.Draw(image)
    draw.text((10, 220), "DUNE", fill="#f5f0e6")
    draw.text((10, 250), "Herbert", fill="#f5f0e6")
    return image


class Command(BaseCommand):
    help = "Check that the configured VLM provider, key and model can read a spine crop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-models",
            action="store_true",
            help="List Gemini models this key can call, then exit.",
        )

    def handle(self, *args, **options):
        provider = getattr(settings, "VLM_PROVIDER", "gemini")
        key = api_key_for_provider()

        self.stdout.write(f"provider:  {provider}")
        self.stdout.write(f"model:     {getattr(settings, 'GEMINI_MODEL', '(n/a)')}")
        self.stdout.write(f"dry run:   {settings.VLM_DRY_RUN}")
        # Never print the key itself; enough to confirm which one is loaded.
        self.stdout.write(f"key:       {'set, ends ...' + key[-4:] if key else 'MISSING'}")
        self.stdout.write("")

        if options["list_models"]:
            self._list_models(key)
            return

        if settings.VLM_DRY_RUN:
            self.stdout.write(
                self.style.WARNING(
                    "VLM_DRY_RUN=True, so no live call was made. "
                    "Set it to False in apps/backend/.env to test the key."
                )
            )
            return

        started = time.perf_counter()
        result = extract_text_from_crop(_sample_spine())
        elapsed_ms = (time.perf_counter() - started) * 1000

        if result.ok:
            self.stdout.write(
                self.style.SUCCESS(
                    f"OK in {elapsed_ms:.0f} ms — read "
                    f"{result.title!r} / {result.author!r} "
                    f"({result.input_tokens} in, {result.output_tokens} out tokens)"
                )
            )
            return

        self.stdout.write(
            self.style.ERROR(f"FAILED after {elapsed_ms:.0f} ms: {result.failure_code}")
        )
        remedy = REMEDIES.get(result.failure_code)
        if remedy:
            self.stdout.write(f"  -> {remedy}")

    def _list_models(self, key: str) -> None:
        if not key:
            self.stdout.write(self.style.ERROR("No API key set, cannot list models."))
            return

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=200"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.stdout.write(self.style.ERROR(f"HTTP {exc.code}: {exc.read().decode()[:300]}"))
            return
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"{type(exc).__name__}: {exc}"))
            return

        self.stdout.write("Models callable with generateContent:")
        for model in body.get("models", []):
            methods = model.get("supportedGenerationMethods") or model.get("supportedActions") or []
            if "generateContent" in methods:
                self.stdout.write(f"  {model['name'].removeprefix('models/')}")
