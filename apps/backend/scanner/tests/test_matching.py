"""Tests for catalog fuzzy matching edge cases."""

import pytest

from scanner.matching import (
    CatalogBook,
    match_against_catalog,
    normalize_text,
    score_match,
)


@pytest.fixture
def catalog() -> list[CatalogBook]:
    return [
        CatalogBook(1, "Pride and Prejudice", "Jane Austen", edition_info="1813 first edition"),
        CatalogBook(
            2,
            "Pride and Prejudice",
            "Jane Austen",
            edition_info="Annotated Norton Critical Edition",
        ),
        CatalogBook(
            3,
            "Harry Potter and the Sorcerer's Stone",
            "J.K. Rowling",
            ("Harry Potter and the Philosopher's Stone",),
            "US edition",
        ),
        CatalogBook(
            4,
            "Harry Potter and the Philosopher's Stone",
            "Joanne Rowling",
            ("Harry Potter and the Sorcerer's Stone",),
            "UK edition",
        ),
        CatalogBook(5, "The Road", "Cormac McCarthy"),
        CatalogBook(6, "The Road", "Jack London"),
        CatalogBook(
            7, "The Lord of the Rings", "J.R.R. Tolkien", ("LOTR omnibus",), "Omnibus one-volume"
        ),
        CatalogBook(8, "The Fellowship of the Ring", "J.R.R. Tolkien", edition_info="Volume 1"),
        CatalogBook(9, "The Two Towers", "J.R.R. Tolkien", edition_info="Volume 2"),
        CatalogBook(10, "The Return of the King", "J.R.R. Tolkien", edition_info="Volume 3"),
        CatalogBook(11, "The Great Gatsby", "F. Scott Fitzgerald"),
        CatalogBook(12, "Great", "Sara Benincasa"),
        CatalogBook(13, "The Hobbit", "J.R.R. Tolkien"),
        CatalogBook(14, "The Hobbit", "Tolkien, J.R.R.", edition_info="Deluxe reprint"),
        CatalogBook(
            15, "The Hobbit", "John Ronald Reuel Tolkien", edition_info="Illustrated edition"
        ),
    ]


def test_two_editions_same_book(catalog):
    results = match_against_catalog("Pride and Prejudice", "Jane Austen", catalog, top_n=3)
    assert len(results) >= 2
    assert all(r.catalog_book.title == "Pride and Prejudice" for r in results[:2])
    editions = {r.catalog_book.edition_info for r in results[:2]}
    assert "1813 first edition" in editions
    assert "Annotated Norton Critical Edition" in editions


def test_us_uk_regional_titles(catalog):
    us = match_against_catalog("Harry Potter Sorcerer's Stone", "J.K. Rowling", catalog, top_n=1)[0]
    uk = match_against_catalog(
        "Harry Potter Philosopher's Stone", "Joanne Rowling", catalog, top_n=1
    )[0]
    assert us.score >= 0.85
    assert uk.score >= 0.85
    assert (
        "Sorcerer" in us.catalog_book.title or "Philosopher" in us.catalog_book.alternate_titles[0]
    )
    assert "Philosopher" in uk.catalog_book.title


def test_same_title_different_authors(catalog):
    mccarthy = score_match("The Road", "Cormac McCarthy", catalog[4])
    london = score_match("The Road", "Jack London", catalog[5])
    wrong = score_match("The Road", "Cormac McCarthy", catalog[5])
    assert mccarthy.score >= 0.85
    assert london.score >= 0.85
    assert wrong.score < mccarthy.score
    assert wrong.score < 0.85


def test_omnibus_and_volume_rows(catalog):
    omnibus = match_against_catalog("Lord of the Rings", "Tolkien", catalog, top_n=5)
    fellowship = match_against_catalog("Fellowship of the Ring", "JRR Tolkien", catalog, top_n=1)[0]
    assert any(r.catalog_book.id == 7 for r in omnibus)
    assert fellowship.catalog_book.id == 8
    assert fellowship.score >= 0.80


def test_substring_title_does_not_false_match(catalog):
    great = score_match("Great Gatsby", "Fitzgerald", catalog[10])
    substring = score_match("Great", "Sara Benincasa", catalog[11])
    false_positive = score_match("Great", "F. Scott Fitzgerald", catalog[10])
    assert great.score >= 0.85
    assert substring.score >= 0.85
    assert false_positive.score < 0.85


def test_author_name_variants(catalog):
    variants = [
        ("The Hobbit", "J.R.R. Tolkien"),
        ("The Hobbit", "Tolkien, J.R.R."),
        ("The Hobbit", "John Ronald Reuel Tolkien"),
    ]
    scores = []
    for title, author in variants:
        top = match_against_catalog(title, author, catalog, top_n=1)[0]
        scores.append(top.score)
        assert top.catalog_book.title == "The Hobbit"
    assert all(s >= 0.85 for s in scores)


def test_normalize_strips_articles_and_subtitles():
    assert normalize_text("The Great Gatsby: A Novel") == "great gatsby"
    assert normalize_text("  A Tale of Two Cities  ") == "tale of two cities"


def test_empty_input_returns_no_candidates(catalog):
    assert match_against_catalog("", "", catalog) == []


def test_malformed_partial_title_still_ranks(catalog):
    results = match_against_catalog("Gatsby", "Scott Fitzgerald", catalog, top_n=3)
    assert results
    assert results[0].catalog_book.title == "The Great Gatsby"
