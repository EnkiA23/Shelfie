from rest_framework import serializers

from scanner.models import CatalogBook, LibraryEntry


class CatalogBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogBook
        fields = ["id", "external_id", "title", "author", "alternate_titles", "edition_info"]


class LibraryEntrySerializer(serializers.ModelSerializer):
    catalog_book_id = serializers.PrimaryKeyRelatedField(
        source="catalog_book",
        queryset=CatalogBook.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = LibraryEntry
        fields = [
            "id",
            "catalog_book_id",
            "raw_title",
            "raw_author",
            "confidence_score",
            "source_image",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LibraryEntryCreateSerializer(serializers.ModelSerializer):
    catalog_book_id = serializers.PrimaryKeyRelatedField(
        source="catalog_book",
        queryset=CatalogBook.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = LibraryEntry
        fields = ["catalog_book_id", "raw_title", "raw_author", "confidence_score", "source_image"]

    def validate_raw_title(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Title is required.")
        return cleaned
