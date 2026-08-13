"""
Fuzzy catalog matching for extracted spine text.

Scores are 0.0–1.0 blends of title similarity, alternate-title hits,
partial/substring signals, and author agreement modifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from rapidfuzz import fuzz

ARTICLES = {"a", "an", "the"}


@dataclass(frozen=True)
class CatalogBook:
    id: int
    title: str
    author: str
    alternate_titles: tuple[str, ...] = ()
    edition_info: str = ""


@dataclass(frozen=True)
class ScoredCandidate:
    catalog_book: CatalogBook
    score: float
    title_score: float
    author_modifier: float


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if ":" in value:
        text = normalize_text(value.split(":", 1)[0])
    words = text.split()
    while words and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def _author_tokens(author: str) -> set[str]:
    normalized = normalize_text(author.replace(",", " "))
    return {token for token in normalized.split() if len(token) > 1}


def _author_last_name(author: str) -> str:
    author = author.strip()
    if "," in author:
        return normalize_text(author.split(",", 1)[0])
    parts = author.split()
    return normalize_text(parts[-1]) if parts else ""


def author_match_modifier(raw_author: str, catalog_author: str) -> float:
    raw_norm = normalize_text(raw_author)
    cat_norm = normalize_text(catalog_author)
    if not raw_norm or not cat_norm:
        return 0.0
    if raw_norm == cat_norm:
        return 0.12
    raw_tokens = _author_tokens(raw_author)
    cat_tokens = _author_tokens(catalog_author)
    if not raw_tokens or not cat_tokens:
        return 0.0
    overlap = raw_tokens & cat_tokens
    if overlap:
        return 0.08
    if _author_last_name(raw_author) and _author_last_name(raw_author) == _author_last_name(catalog_author):
        return 0.06
    if raw_tokens.isdisjoint(cat_tokens):
        return -0.20
    return 0.0


def _title_variants(book: CatalogBook) -> list[str]:
    variants = [book.title, *book.alternate_titles]
    return [normalize_text(v) for v in variants if normalize_text(v)]


def _best_title_score(raw_title: str, book: CatalogBook) -> float:
    normalized_raw = normalize_text(raw_title)
    if not normalized_raw:
        return 0.0

    best = 0.0
    for variant in _title_variants(book):
        sort_score = fuzz.token_sort_ratio(normalized_raw, variant) / 100.0
        ratio_score = fuzz.ratio(normalized_raw, variant) / 100.0
        partial_score = fuzz.partial_ratio(normalized_raw, variant) / 100.0
        combined = (0.55 * sort_score) + (0.35 * ratio_score) + (0.10 * partial_score)
        best = max(best, combined)
    return best


def score_match(raw_title: str, raw_author: str, book: CatalogBook) -> ScoredCandidate:
    title_score = _best_title_score(raw_title, book)
    author_mod = author_match_modifier(raw_author, book.author)
    final = min(1.0, max(0.0, title_score + author_mod))
    return ScoredCandidate(
        catalog_book=book,
        score=round(final, 4),
        title_score=round(title_score, 4),
        author_modifier=round(author_mod, 4),
    )


def match_against_catalog(
    raw_title: str,
    raw_author: str,
    catalog: Sequence[CatalogBook],
    *,
    top_n: int = 5,
    min_score: float = 0.0,
) -> list[ScoredCandidate]:
    if not raw_title and not raw_author:
        return []
    scored = [score_match(raw_title, raw_author, book) for book in catalog]
    scored.sort(key=lambda item: item.score, reverse=True)
    filtered = [item for item in scored if item.score >= min_score]
    return filtered[:top_n]


