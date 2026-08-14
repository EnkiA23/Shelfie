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
    # Prefer the catalog match when we have one; raw_* is what the VLM actually read.
    title = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()

    class Meta:
        model = LibraryEntry
        fields = [
            "id",
            "catalog_book_id",
            "title",
            "author",
            "raw_title",
            "raw_author",
            "confidence_score",
            "source_image",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "title", "author"]

    def get_title(self, obj: LibraryEntry) -> str:
        if obj.catalog_book_id:
            return obj.catalog_book.title
        return obj.raw_title

    def get_author(self, obj: LibraryEntry) -> str:
        if obj.catalog_book_id:
            return obj.catalog_book.author
        return obj.raw_author


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
