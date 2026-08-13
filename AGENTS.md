# Shelfie — agent conventions

Rules that apply to any change in this repository. Full reasoning is in `ARCHITECTURE.md`.

## Layering

| File | Responsibility | Never |
|---|---|---|
| `scanner/views.py` | HTTP: validate, delegate, status codes | Scoring math, image processing, provider calls |
| `scanner/pipeline.py` | Stage orchestration, failure containment, metrics | Touch `request` / `Response` |
| `scanner/detector.py` | `detect_spines(bytes) -> list[BoundingBox]` | Know about HTTP or the catalog |
| `scanner/vlm.py` | `extract_text_from_crop(Image) -> dict \| None` | Raise on provider failure — return `None` |
| `scanner/matching.py` | `match_against_catalog(...) -> list[ScoredCandidate]` | Import Django |
| `scanner/metrics.py` | Timing and cost estimation | Log image bytes or prompt bodies |
| `app/api/client.ts` | The only module that talks to the API | — |

## Non-negotiables

1. **A handled failure returns HTTP 200** with `high_confidence`, `needs_review` and `metrics`.
   Non-200 is reserved for auth, throttling, quota and malformed uploads.
2. **Every failure path appends a snake_case code** to `metrics.warnings` and stays visible to
   the user. Nothing is silently accepted or silently dropped.
3. **Anything scoring below 0.85 goes to `needs_review`**, including reads that failed entirely.
4. **No secrets in the repo.** Config comes from `settings.py`, which reads `.env`. Modules never
   read `os.environ` directly. `.env` is gitignored, `.env.example` is the committed template.
5. **New caps and thresholds are settings**, not inline literals, so every knob is visible in
   one place.

## Config

Add a new setting in three places: a default in the `environ.Env(...)` call, a module-level
assignment in `settings.py`, and a documented line in `backend/.env.example`.

## Commands

```bash
cd backend
python -m pytest scanner/tests -q       # 18 tests, all must pass
python manage.py check
python manage.py load_catalog           # after editing catalog.csv
python manage.py benchmark_scan --runs 3   # regenerate README numbers
```

## Commits

Scoped and incremental — `feat(matching):`, `fix(pipeline):`, `test(catalog):`, `refactor:`,
`docs:`. One logical unit per commit; a single large commit counts against this project.

## Working with AI passes

Use exactly one skill per run and stop when it is done:
`implementation-pass`, `test-pass`, `bugfix-pass`, `refactor-pass` in `.cursor/skills/`.
Record which pass touched which files in `AI_USAGE.md` as you go.
