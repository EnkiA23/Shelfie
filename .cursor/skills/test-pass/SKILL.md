---
name: test-pass
description: Writes pytest cases for Shelfie against existing behaviour without modifying the code under test, covering catalog ambiguities and graceful-failure paths. Use when adding tests for matching.py or the scan pipeline.
disable-model-invocation: true
---

# Test-Writing Pass

**Hard constraint: do not modify the code under test in this pass.** Tests written while the
implementation is still moving end up asserting whatever the code happens to do. If a test
reveals a bug, report it and stop — fixing it is the `bugfix-pass`.

## Coverage targets

### Catalog ambiguities (`scanner/tests/test_matching.py`)

One test per row class in `catalog.csv`. A test is only meaningful if naive string comparison
would fail it:

| Case | Assert |
|---|---|
| Two editions of one book | Both rows come back; `edition_info` distinguishes them |
| US/UK regional titles | Either spelling resolves via `alternate_titles`, both ≥ 0.85 |
| Same title, different authors | Correct author ≥ 0.85, wrong author **< 0.85** |
| Omnibus + individual volumes | Volume query returns the volume, omnibus is a candidate |
| Substring titles | `Great` does not auto-match `The Great Gatsby` |
| Author name variants | All three Tolkien forms reach the same row ≥ 0.85 |

Plus empty input and partial/malformed titles.

### Graceful failure (`scanner/tests/test_pipeline.py`)

Monkeypatch the service module, never real network:

```python
monkeypatch.setattr(pipeline_module, "detect_spines", lambda _bytes: [])
monkeypatch.setattr(pipeline_module, "extract_text_from_crop", lambda _crop: None)
```

Assert on the warning code and on the item still reaching `needs_review` — a failed read must
surface to the user, not vanish.

## Conventions

- `pytest`, plain functions, `db` fixture for anything touching models.
- Never call a real provider. `settings.VLM_DRY_RUN` or monkeypatch.
- Assert behaviour and thresholds, not implementation details of the scoring blend.

```bash
nx run backend:test
```

Commit as `test(scope): ...`, separate from any implementation commit.
