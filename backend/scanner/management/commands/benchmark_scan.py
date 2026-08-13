"""Run the scan pipeline over the committed test photos and print measured numbers.

Usage:
    python manage.py benchmark_scan
    python manage.py benchmark_scan --photos ../test_photos --runs 3
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from scanner.pipeline import run_scan_pipeline

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class Command(BaseCommand):
    help = "Measure per-image latency and estimated VLM cost across test photos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--photos",
            default=str(Path(settings.BASE_DIR).parent / "test_photos"),
            help="Directory of images to benchmark.",
        )
        parser.add_argument("--runs", type=int, default=1, help="Repetitions per image.")

    def handle(self, *args, **options):
        photo_dir = Path(options["photos"])
        runs = max(1, options["runs"])

        images = sorted(p for p in photo_dir.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
        if not images:
            self.stderr.write(self.style.ERROR(f"No images found in {photo_dir}"))
            return

        mode = "DRY RUN (no API calls)" if settings.VLM_DRY_RUN else f"LIVE ({settings.VLM_PROVIDER})"
        self.stdout.write(f"Mode: {mode}")
        self.stdout.write(f"Detector backend setting: {settings.DETECTOR_BACKEND}")
        self.stdout.write("")
        header = f"{'image':<32}{'spines':>8}{'stage1':>9}{'stage2':>9}{'total':>9}{'cost $':>11}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        totals = {"latency": 0, "cost": 0.0, "count": 0}

        for image_path in images:
            image_bytes = image_path.read_bytes()
            for _ in range(runs):
                result = run_scan_pipeline(image_bytes)
                metrics = result["metrics"]
                totals["latency"] += metrics["latency_ms"]
                totals["cost"] += metrics["est_cost_usd"]
                totals["count"] += 1
                self.stdout.write(
                    f"{image_path.name:<32}"
                    f"{metrics['spines_detected']:>8}"
                    f"{metrics['stage1_ms']:>9}"
                    f"{metrics['stage2_ms']:>9}"
                    f"{metrics['latency_ms']:>9}"
                    f"{metrics['est_cost_usd']:>11.6f}"
                )
                if metrics["warnings"]:
                    self.stdout.write(f"{'':<32}warnings: {', '.join(metrics['warnings'])}")

        count = totals["count"]
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Average over {count} run(s): "
                f"{totals['latency'] / count:.0f} ms, ${totals['cost'] / count:.6f} per image"
            )
        )
