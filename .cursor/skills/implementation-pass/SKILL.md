---
name: implementation-pass
description: Implements one Shelfie module or screen at a time in the build order from the plan, stopping after each unit for diff review and a commit. Use when adding a feature to the Shelfie backend pipeline or Expo app.
disable-model-invocation: true
---

# Implementation Pass

Build **one** module or screen, then stop. Never bundle several units into one run —
every line has to be defensible live, and the commit history is graded.

## Build order

Work strictly in this order; each step is demoable on its own:

1. `matching.py` — no external dependencies, no camera, no API key
2. `models.py` + `load_catalog` + `LibraryViewSet` — persistence end to end
3. Stub `ScanBookshelfView` (`?stub=1`) — unblocks frontend work immediately
4. Expo screens against the stub
5. Real detection, then real VLM calls — keep the fallback paths from the start
6. Metrics, docs, commit cleanup

If time runs out, what gets cut is the real vision pipeline (which degrades to the stub),
never the matching logic or the review UI.

## Layer rules

Respect the boundaries in `docs/ARCHITECTURE.md`:

- `views.py` parses, validates, delegates, shapes the response. No scoring math, no image
  processing, no provider SDK calls.
- `detector.py`, `vlm.py`, `matching.py`, `metrics.py` are services: one public entry point
  each, importable and testable without Django's request cycle.
- `pipeline.py` composes services in order and owns the per-stage `try`/`except`.

## Every new failure path needs a warning code

Any new way a stage can fail must append a snake_case string to `metrics.warnings`, return
HTTP 200, and be mapped to a friendly message in the app. Silent drops are a grading failure.

## Before finishing

```bash
nx run backend:test
# or: cd apps/backend && python -m pytest scanner/tests -q
```

Then commit that single unit with a scoped message (`feat(matching): ...`). Do not start the
next unit in the same run.
