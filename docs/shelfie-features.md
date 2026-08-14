# Shelfie feature map

Where each product capability lives. Use this before guessing file paths when adding work.

## Mobile (`apps/mobile`)

| Feature | Primary files |
| --- | --- |
| Tab navigation (Scan / Library) | `App.tsx` |
| Capture or pick photo, start scan | `screens/CaptureScreen.tsx` |
| Review high-confidence vs needs-review, edit, save | `screens/ReviewScreen.tsx` |
| Saved library, pull-to-refresh | `screens/LibraryScreen.tsx` |
| API client (only network boundary) | `api/client.ts` |
| Warning code → user message | `lib/warnings.ts` |
| Shared buttons, cards, banners | `components/AppButton.tsx`, `BookCard.tsx`, `ErrorBanner.tsx` |
| Colours, spacing, radius | `theme.ts` |
| Expo config, permissions | `app.json` |
| API URL and token | `.env` (`EXPO_PUBLIC_*`) |

## Backend API (`apps/backend`)

| Feature | Primary files |
| --- | --- |
| Scan upload endpoint | `scanner/views.py` (`ScanBookshelfView`) |
| Library CRUD | `scanner/views.py` (`LibraryViewSet`) |
| Catalog search (review autocomplete) | `scanner/views.py` |
| Three-stage orchestration | `scanner/pipeline.py` |
| Stage 1: spine detection (YOLO + OpenCV) | `scanner/detector.py` |
| Stage 2: VLM title/author extraction | `scanner/vlm.py` |
| Stage 3: fuzzy catalog match + score | `scanner/matching.py` |
| Latency, tokens, spend caps | `scanner/metrics.py` |
| Auth token, throttling | `scanner/permissions.py`, `shelfie/settings.py` |
| ORM models | `scanner/models.py` |
| Request/response shapes | `scanner/serializers.py` |
| URL routing | `scanner/urls.py`, `shelfie/urls.py` |
| All settings and env knobs | `shelfie/settings.py`, `.env.example` |

## Management commands

| Command | File | Purpose |
| --- | --- | --- |
| `load_catalog` | `scanner/management/commands/load_catalog.py` | Upsert `catalog.csv` |
| `benchmark_scan` | `scanner/management/commands/benchmark_scan.py` | Measured latency/cost |
| `check_vlm` | `scanner/management/commands/check_vlm.py` | Key + model health check |

## Data and fixtures

| Asset | Path |
| --- | --- |
| Catalog (130 messy rows) | `apps/backend/catalog.csv` |
| Test photos (readable / blurred / empty) | `test_photos/` |
| Generate synthetic photos | `apps/backend/scripts/generate_test_photos.py` |
| Regenerate catalog draft | `apps/backend/scripts/generate_catalog.py` |

## Tests

| Area | Path |
| --- | --- |
| Matching edge cases | `apps/backend/scanner/tests/test_matching.py` |
| Pipeline + API graceful failure | `apps/backend/scanner/tests/test_pipeline.py` |

## Monorepo and CI

| Concern | Path |
| --- | --- |
| Root scripts | `package.json` |
| Nx workspace config | `nx.json`, `apps/*/project.json` |
| PR CI | `.github/workflows/pr.yml` |
| Secret guard | `scripts/check_no_secrets.sh` |
| Agent conventions | `AGENTS.md`, `CLAUDE.md` |
| Cursor build passes | `.cursor/skills/*-pass/SKILL.md` |

## Adding something new — checklist

1. Pick the row above closest to your feature; add a file in that folder.
2. Backend failure? New code in `pipeline.py` or a service + warning in `warnings.ts`.
3. New setting? `settings.py` + `.env.example` + document in README.
4. New screen? `screens/` + route in `App.tsx`; API calls only through `api/client.ts`.
5. Tests in `scanner/tests/`; run `pnpm backend:test`.
6. Record the pass in `AI_USAGE.md`.
