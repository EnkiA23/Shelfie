# CLAUDE.md

This file provides guidance to Claude Code and Cursor when working with code in this
repository. It mirrors the FriendMap monorepo workflow: Nx projects under `apps/`, root
pnpm scripts, and specialist agents for large changes.

## Repository shape

Shelfie is an **Nx + pnpm monorepo** for a bookshelf-scanning product. Two deployable apps,
one shared catalog, one CI pipeline.

| Path | Runtime | Role |
| --- | --- | --- |
| `apps/backend` | Django 5 + DRF (Python 3.11+) | Scan API: detect spines locally, read titles with a hosted VLM, fuzzy-match against `catalog.csv`, return high-confidence + review buckets. Nx project: `backend`. |
| `apps/mobile` | Expo / React Native (TypeScript) | Mobile client: capture photo, review matches, save library. Nx project: `mobile`. |
| `test_photos/` | — | Committed images that reproduce readable, low-confidence, and zero-detection cases. |
| `docs/` | — | Architecture, troubleshooting, feature → file map. |
| `scripts/` | shell | Repo-wide guards (`check_no_secrets.sh`). |

**Layering (backend).** `views.py` is the HTTP controller. `pipeline.py` orchestrates stages
and owns try/except. `detector.py`, `vlm.py`, `matching.py`, `metrics.py` are services with
one public entry point each. Full rules in `AGENTS.md` and `docs/ARCHITECTURE.md`.

**Mobile boundary.** `apps/mobile/api/client.ts` is the only module that talks to the API.
`apps/mobile/lib/warnings.ts` maps backend warning codes to user-facing messages.

## Commands

Package manager: **pnpm 10.28.0** at the root. Nx wraps native tools — prefer root scripts when
the path is non-obvious.

### Backend (`apps/backend`, Nx project `backend`)

```sh
pnpm backend:dev              # Django on 0.0.0.0:8000
pnpm backend:test             # pytest scanner/tests -q
pnpm backend:lint             # ruff check
pnpm backend:check            # manage.py check
pnpm backend:check-vlm        # one-crop live VLM health check
pnpm backend:load-catalog     # load catalog.csv into SQLite
pnpm backend:benchmark        # measured latency + cost table

nx run backend:test           # same as above, with Nx cache
nx run backend:lint
nx run backend:check-vlm
```

Setup from a clean clone:

```sh
cd apps/backend
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py load_catalog
```

Optional YOLO detector (large download): `pip install -r requirements-detector.txt`.

### Mobile (`apps/mobile`, Nx project `mobile`)

```sh
pnpm mobile:dev               # npx expo start
pnpm mobile:typecheck         # tsc --noEmit
pnpm mobile:install           # npm ci

nx run mobile:dev
nx run mobile:typecheck
```

Copy `apps/mobile/.env.example` → `.env`. Set `EXPO_PUBLIC_API_URL` to your machine's LAN IP
for a physical phone; use `10.0.2.2:8000` on Android emulator.

### Cross-cutting

```sh
pnpm ci:secrets               # fail if a credential is tracked
./scripts/check_no_secrets.sh # same, from repo root

# Run what CI runs (after pnpm install + backend venv deps):
nx run backend:lint && nx run backend:format-check && nx run backend:test
nx run mobile:typecheck
```

## Where to add new work

| You want to… | Start here |
| --- | --- |
| New API endpoint or upload rule | `apps/backend/scanner/views.py` → delegate to `pipeline.py` or a service |
| New pipeline stage or failure mode | `apps/backend/scanner/pipeline.py` + warning in `apps/mobile/lib/warnings.ts` |
| New matcher edge case | `apps/backend/scanner/matching.py` + test in `scanner/tests/test_matching.py` |
| New screen or flow | `apps/mobile/screens/` + wire in `App.tsx` |
| New shared UI piece | `apps/mobile/components/` |
| New catalog ambiguity | `apps/backend/catalog.csv` → `load_catalog` |
| New agent workflow | `.cursor/skills/` or `.github/agents/` |

See `docs/shelfie-features.md` for a feature → file map.

## Agent workflow

Specialist agents (FriendMap pattern):

| Agent | When to use |
| --- | --- |
| **Shelfie Master** (`.github/agents/shelfie-master.agent.md`) | Multi-step work: plan + implement + validate |
| **Shelfie Architect** | New module, screen, or API surface — design before code |
| **Shelfie Bugfix** | One failure, smallest diff |
| **Shelfie Test** | Tests against frozen behaviour |

Cursor skills in `.cursor/skills/` (`implementation-pass`, `test-pass`, `bugfix-pass`,
`refactor-pass`) are the checked-in equivalents. Use **one skill per run**. Record touches in
`AI_USAGE.md`.

## Secrets and config

- **Never commit** `apps/backend/.env`, `apps/mobile/.env`, or API keys.
- Templates: `apps/backend/.env.example`, `apps/mobile/.env.example`.
- All backend config flows through `apps/backend/shelfie/settings.py` — modules never read
  `os.environ` directly.
- CI runs with `VLM_DRY_RUN=True` and no key. A live VLM call from CI is a bug.
- Before a demo: `pnpm backend:check-vlm` — model names expire (e.g. retired Gemini IDs).

## CI

`.github/workflows/pr.yml` on every push and PR:

1. pnpm install + Nx targets for backend lint, format, check, migrations, tests
2. mobile `npm ci` + typecheck
3. secret guard + gitleaks

PR template checklist lives in `.github/pull_request_template.md`.

## Branching

- `main` / `master` — stable; CI must pass before merge.
- Feature branches → PR → review → merge.

## Docs index

| File | Contents |
| --- | --- |
| `README.md` | Setup, architecture, measured numbers |
| `AGENTS.md` | Non-negotiable conventions for any change |
| `docs/ARCHITECTURE.md` | Monorepo, layering, monolith rationale |
| `docs/TROUBLESHOOTING.md` | Environment failures and fixes |
| `docs/shelfie-features.md` | Feature → file map |
| `AI_USAGE.md` | Which AI pass touched which files |
