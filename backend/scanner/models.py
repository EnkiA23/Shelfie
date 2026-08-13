from django.db import models


class CatalogBook(models.Model):
    external_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=512)
    author = models.CharField(max_length=256)
    alternate_titles = models.JSONField(default=list, blank=True)
    edition_info = models.CharField(max_length=256, blank=True)

    class Meta:
        ordering = ["title", "author"]

    def __str__(self) -> str:
        return f"{self.title} — {self.author}"


class LibraryEntry(models.Model):
    catalog_book = models.ForeignKey(
        CatalogBook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_entries",
    )
    raw_title = models.CharField(max_length=512)
    raw_author = models.CharField(max_length=256, blank=True)
    confidence_score = models.FloatField(default=0.0)
    source_image = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.raw_title


class ScanLog(models.Model):
    latency_ms = models.IntegerField(default=0)
    est_cost_usd = models.FloatField(default=0.0)
    spines_detected = models.IntegerField(default=0)
    spines_matched = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
