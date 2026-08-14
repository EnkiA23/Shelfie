import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from scanner.models import CatalogBook


class Command(BaseCommand):
    help = "Load catalog.csv into CatalogBook rows (upsert by external_id)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(__file__).resolve().parents[3] / "catalog.csv"),
            help="Path to catalog.csv",
        )

    def handle(self, *args, **options):
        catalog_path = Path(options["path"])
        if not catalog_path.exists():
            self.stderr.write(self.style.ERROR(f"Catalog file not found: {catalog_path}"))
            return

        created = 0
        updated = 0
        with catalog_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                alternates = [
                    part.strip()
                    for part in (row.get("alternate_titles") or "").split("|")
                    if part.strip()
                ]
                defaults = {
                    "title": row["title"],
                    "author": row["author"],
                    "alternate_titles": alternates,
                    "edition_info": row.get("edition_info") or "",
                }
                _, was_created = CatalogBook.objects.update_or_create(
                    external_id=int(row["id"]),
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Catalog loaded: {created} created, {updated} updated.")
        )
