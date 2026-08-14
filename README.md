# Shelfie — Bookshelf → Library Inventory

[![CI](https://github.com/OWNER/shelfie/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/shelfie/actions/workflows/ci.yml)

Photograph a bookshelf, get a structured personal library. An Expo app sends the photo to a
Django REST API, which crops individual spines with a local CPU model, reads title/author off
each crop with a hosted vision-language model, fuzzy-matches every read against a deliberately
messy `catalog.csv`, and routes anything uncertain to a human review step before it is saved.

> Replace `OWNER` in the badge URL above with your GitHub account once the repo is pushed.

---

## 1. Setup from a clean clone

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
copy .env.example .env         # cp on macOS/Linux

python manage.py migrate
python manage.py load_catalog
python manage.py runserver 0.0.0.0:8000
```

`requirements.txt` is deliberately small and pure-wheel. The YOLO detector lives in
`requirements-detector.txt` because it pulls torch (~2 GB); install it only if you want the
YOLO path, since the detector falls back to OpenCV without it:

```bash
pip install -r requirements-detector.txt   # optional, adds YOLOv8n
pip install -r requirements-dev.txt        # pytest + ruff, what CI runs
```

The API is now on `http://127.0.0.1:8000`. **It runs out of the box with no API key** —
`VLM_DRY_RUN=True` returns canned spine reads so you can click through the whole product
without spending anything.

### Where to put your API key

Open `backend/.env` and fill in **one** provider. Gemini is the default because its Flash tier
is the cheapest practical option and has a free quota.

```ini
# backend/.env
VLM_PROVIDER=gemini                 # gemini | openai | anthropic
GEMINI_API_KEY=your-key-here        # <-- paste your key here
GEMINI_MODEL=gemini-3.1-flash-lite

VLM_DRY_RUN=False                   # <-- flip this to make real calls
```

| Provider | Env var | Where to get a key |
|---|---|---|
| Gemini (default) | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |

Restart `runserver` after editing `.env`, then confirm the key actually works:

```bash
python manage.py check_vlm
# provider:  gemini
# model:     gemini-3.1-flash-lite
# key:       set, ends ...Kd1w
# OK in 1148 ms — read 'DUNE' / 'Herbert' (1114 in, 24 out tokens)
```

This spends one crop's worth of tokens and names the exact problem if there is one. It is worth
running before any demo, because **hosted model names expire**: this project originally defaulted
to `gemini-2.0-flash`, which has since been retired, and every call began returning HTTP 404. Use
`check_vlm --list-models` to see what your key can currently call.

Nothing else needs to change — every module reads config from `settings.py`, never from
`os.environ` directly. `.env` is gitignored, `.env.example` is the committed template, and CI
fails if either rule is broken (see §9).

If you would rather not use a key at all, leave `VLM_DRY_RUN=True` and use the **"Demo without
API"** button in the app, which exercises the full review-and-save flow with canned data.

### Expo app

```bash
cd app
npm install
copy .env.example .env
npx expo start
```

Then press `a` for an Android emulator, `i` for an iOS simulator, or scan the QR code with
Expo Go on a physical phone.

`app/.env` controls where the app looks for the backend:

```ini
EXPO_PUBLIC_API_URL=http://192.168.1.42:8000   # your machine's LAN IP for a real phone
EXPO_PUBLIC_API_TOKEN=dev-token                 # must match APP_SHARED_TOKEN in backend/.env
```

Defaults if unset: `10.0.2.2:8000` on Android emulator, `127.0.0.1:8000` elsewhere. **A physical
phone cannot reach `127.0.0.1`** — it must be your machine's LAN IP, with the backend bound to
`0.0.0.0:8000` and both devices on the same Wi-Fi.

### Tests and checks

```bash
cd backend
python -m pytest scanner/tests -q     # 27 tests: 9 matching, 18 pipeline/API
ruff check . && ruff format --check .

cd ../app
npx tsc --noEmit
```

These are exactly what CI runs, so a green local run means a green pipeline.

### Repository layout

```
.github/workflows/ci.yml   Lint, tests, typecheck, secret scan
.cursor/skills/            The four build passes, checked in and reusable
app/                       Expo (React Native) client
  api/client.ts              Single place that talks to the backend
  components/                Shared UI: buttons, cards, banners
  lib/warnings.ts            Backend warning codes → human messages
  screens/                   Capture, Review, Library
backend/                   Django + DRF API
  scanner/
    views.py                 Thin controllers: parse, validate, delegate
    pipeline.py              Composes the three stages, owns the try/except
    detector.py              Stage 1: YOLOv8n, OpenCV fallback
    vlm.py                   Stage 2: hosted vision model clients
    matching.py              Stage 3: fuzzy match + confidence score
    metrics.py               Latency, token accounting, spend caps
  catalog.csv                The messy catalog, reviewable in version control
docs/                      Architecture decisions and troubleshooting
scripts/check_no_secrets.sh  Fails the build if a credential is ever tracked
test_photos/               Committed images reproducing each failure mode
```

Two top-level components rather than an `apps/`+`packages/` workspace: with exactly one API and
one client, the extra nesting would add a directory level and a build tool without removing any
actual problem. The reasoning is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Further reading

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Monorepo, controller/service layering, monolith-vs-microservices |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Every environment failure we hit, and the fix |
| [`AGENTS.md`](AGENTS.md) | Conventions any change must follow |
| [`AI_USAGE.md`](AI_USAGE.md) | Which AI pass wrote which file |

---

## 2. Architecture

```
Expo app ──multipart photo──▶ POST /api/scan/         [Django + DRF]
                                    │
   Stage 1  local, CPU              ▼
   YOLOv8n (COCO "book" class) ──▶ spine bounding boxes
     └─ 0 boxes or crash ──▶ OpenCV vertical-edge projection
          └─ still 0 ──▶ send the FULL image on as one crop, warn, continue
                                    │
   Stage 2  hosted VLM              ▼
   one call per crop ──▶ {extracted_title, extracted_author}
     └─ timeout / bad JSON / HTTP error ──▶ 1 retry, then flag that crop
        and keep going with the rest (never a 500)
                                    │
   Stage 3  local                   ▼
   rapidfuzz match vs catalog.csv in SQLite ──▶ score 0.0–1.0 + top-N alternatives
                                    │
                                    ▼
        { high_confidence: [...],    # score >= 0.85
          needs_review:    [...],    # below threshold, unmatched, or failed read
          metrics: { latency_ms, stage1_ms, stage2_ms, est_cost_usd,
                     spines_detected, detector_backend, vlm_provider, warnings } }
                                    │
   Review screen (confirm / edit / discard) ──▶ POST /api/library/ ──▶ Library screen
```

**Why crop locally first.** This is the core design decision. Sending the whole shelf photo to a
VLM asks it to *find* text anywhere in a cluttered image and guess which words belong to which
book. Cropping first changes the question to "read the text on this one spine," which is both
cheaper (a 512px crop is far fewer image tokens than a full-resolution shelf) and more accurate
(less surface area to hallucinate across). The local model does the cheap spatial work; the
expensive model only does the part that actually needs language understanding.

**Layering.** `views.py` is a thin controller: parse, validate, delegate, shape the response.
`detector.py`, `vlm.py`, `matching.py`, `metrics.py` are single-purpose service modules, and
`pipeline.py` composes them and owns the per-stage try/except. That is why `test_matching.py`
can import and test the scoring logic without touching Django's request cycle. Full reasoning,
including why not microservices and why not a repository pattern, is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**Single call per crop, not one batched call.** Batching all crops into one request would be
marginally cheaper, but one malformed response would poison every book in the photo. Per-crop
calls mean a single unreadable spine degrades to one review item instead of losing the scan.
The per-scan cap keeps the call count bounded.

### API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/scan/` | multipart `photo`; add `?stub=1` for canned results |
| `GET/POST /api/library/` | list and persist confirmed books |
| `GET /api/catalog/search/?q=` | autocomplete for the review screen |

All endpoints require `Authorization: Bearer <APP_SHARED_TOKEN>`.

---

## 3. Measured numbers

All figures below are from live runs against Gemini 3.1 Flash-Lite, not estimates. Machine:
Windows 11, Python 3.11, CPU inference only, home broadband. Reproduce with:

```bash
python manage.py benchmark_scan --runs 2
```

**End to end**, over the three committed test photos:

| Photo | Spines | Stage 1 (local) | Stage 2 (hosted) | Total | Cost |
|---|---|---|---|---|---|
| `shelf_readable.jpg` | 10 | 29 ms | 1.9 s | **1.9 s** | $0.00116 |
| `shelf_low_confidence.jpg` | 10 | 31 ms | 2.5 s | **2.5 s** | $0.00114 |
| `shelf_zero_detections.jpg` | 1 (fallback) | 29 ms | 0.8 s | **0.8 s** | $0.00012 |

**Accuracy on the readable shelf: 8 of 10 spines matched at 1.00 confidence** (Beloved, Dune,
The Hobbit, The Road, Sapiens, The Martian, 1984, The Great Gatsby). The other two crops were
blank shelf edges, read as empty, and correctly routed to review rather than guessed at. On the
deliberately blurred photo only 1 of 10 was confident and 9 went to review — which is the
intended behaviour, not a regression.

**Stage 2 was the whole latency budget, so it runs in parallel.** Measured sequentially, ten
crops took **~16 s**, because each ~1.4 s round trip waited for the one before it. Reading the
crops on a bounded thread pool (`VLM_CONCURRENCY=5`) brought the same work down to **~2 s**, an
8× improvement on the dominant stage for no change in cost. The pool is bounded rather than
unbounded so a wide shelf cannot open thirty sockets at once and trigger rate limiting.

**Stage 1 — local detection.** OpenCV projection costs ~30 ms per image. With
`DETECTOR_BACKEND=auto`, the first scan in a process also pays ~2.3 s of YOLO weight loading,
then ~300 ms warm. YOLOv8n found **0 book-class detections** on these synthetic photos and fell
through to OpenCV every time. That is the honest result and the reason the fallback exists rather
than being decorative: COCO's `book` class is trained on books lying flat and face-out, not on
tightly packed vertical spines.

**Cost.** A 512px crop costs ~1070 input tokens and ~16–24 output tokens. At Flash-Lite rates
($0.10/M input, $0.40/M output):

| Unit | Measured cost |
|---|---|
| One spine crop | **$0.000115** |
| One photo at the 10-crop cap | **$0.00116** |
| 100 photos | **$0.116** |

Cost is billed from the token counts the provider reports back, not from a hardcoded assumption,
and calls the provider never served — a rejected key, a retired model — are not charged at all.
Each scan's cost is written to `ScanLog` and accumulates against the daily cap, so the number
above is arithmetic the code performs rather than a figure typed into this file.

---

## 4. The catalog

`backend/catalog.csv` — 130 entries, columns: `id, title, author, alternate_titles, edition_info`.
Load it with `python manage.py load_catalog`. It was first-drafted with an LLM and then hand-edited
so that each required ambiguity is actually present and actually breaks naive matching.

| Ambiguity | Rows | Why it is hard |
|---|---|---|
| Two editions of one book | `Pride and Prejudice` ×2 (1813 first edition, Norton Critical) | Identical title *and* author; only `edition_info` separates them, so a matcher must return both rather than silently picking one |
| US/UK regional titles | `Sorcerer's Stone` / `Philosopher's Stone` | Cross-referenced through `alternate_titles`, so either spine resolves to either row |
| Same title, different authors | `The Road` — Cormac McCarthy vs Jack London | Title score is 1.00 for both; **only the author signal can separate them** |
| Omnibus + volumes | `The Lord of the Rings` plus Fellowship / Two Towers / Return of the King | Substring overlap pulls the omnibus into every volume's candidate list |
| Substring titles | `Great` (Sara Benincasa) vs `The Great Gatsby` | `partial_ratio` alone scores this ~1.0 — a textbook false positive |
| Author name variants | Tolkien as `J.R.R. Tolkien`, `Tolkien, J.R.R.`, `John Ronald Reuel Tolkien` | Exact author comparison fails on all three forms |

The list is weighted toward books people actually own — bestsellers, classics, popular SF/fantasy —
because a catalog of obscure titles would match nothing against a real shelf and prove nothing.

Regenerate with `python scripts/generate_catalog.py`.

---

## 5. Matching, and how the confidence score is built

`scanner/matching.py`. Exact string comparison fails on every row in the table above, so:

**Normalisation** (both sides): lowercase, strip punctuation, drop the subtitle after a colon
(`The Great Gatsby: A Novel` → `great gatsby`), strip leading articles (`The`, `A`, `An`).

**Title score** — the best result across the canonical title *and* every alternate title:

```
0.55 · token_sort_ratio   # word order and reordering
0.35 · ratio              # overall string similarity
0.10 · partial_ratio      # substring hint, deliberately weighted down
```

`partial_ratio` is the trap. It scores `Great` against `The Great Gatsby` near 1.0, so it is a
10% tiebreaker rather than a primary signal.

**Author modifier** — added to the title score, not used as a hard filter:

| Situation | Modifier |
|---|---|
| Exact normalised match | +0.12 |
| Shared name token (handles `J.R.R. Tolkien` ↔ `Tolkien, J.R.R.`) | +0.08 |
| Surname-only match | +0.06 |
| No token overlap at all | **−0.20** |

That −0.20 is what makes `The Road` work. Both rows score 1.00 on title; McCarthy's row ends at
1.00 and London's at 0.80, which drops it below the 0.85 auto-accept line and into review instead
of being silently accepted. It is a modifier rather than a filter because spine OCR frequently
returns no author at all, and a missing author should mean "less certain," not "no match."

**Output:** top-N scored candidates, not just the winner, so the review screen can offer
"did you mean" alternatives. `>= 0.85` is auto-accepted; everything else goes to review.

Every row in that table has a test in `scanner/tests/test_matching.py`.

---

## 6. Human in the loop

The review screen is a product screen, not a debug dump:

- **High confidence** (≥ 0.85): listed with the spine crop thumbnail and an "Add all" action.
- **Needs review**: everything else — low score, no match, or a spine the VLM could not read.
  Each card shows the actual crop the model looked at, editable title and author fields, catalog
  autocomplete backed by `/api/catalog/search/`, "did you mean" alternatives, and Discard.

Nothing is auto-accepted below the threshold, and nothing is dropped silently: a failed read
still becomes a review card, carrying the crop image and a plain-language explanation, so the
user can type the title themselves rather than wondering why a book vanished.

---

## 7. Graceful failure

Every failure mode returns HTTP 200 with a usable payload and a machine-readable warning:

| Failure | Behaviour | Warning |
|---|---|---|
| Detector finds nothing | Whole image sent on as a single crop | `zero_detections_fallback_full_image` |
| Detector raises | Caught, falls through to the same path | `detector_error` |
| No API key in live mode | Reported as misconfiguration, never faked | `vlm_not_configured` |
| Key rejected by provider | No retry, promoted to a scan-level banner | `vlm_auth_failed` |
| Model name retired | No retry, banner names the setting to change | `vlm_model_unavailable` |
| Provider rate limits us | Retried, then that crop becomes a review card | `vlm_rate_limited` |
| Provider times out | Retried, then that crop becomes a review card | `vlm_timeout` |
| Model replies with broken JSON | Retried, then that crop becomes a review card | `vlm_unreadable_response` |
| VLM raises anything else | Scan continues with the remaining crops | `vlm_error` |
| Too many spines | Top-N by box confidence, rest reported as not scanned | `vlm_calls_capped_at_N` |
| Daily quota exhausted | 429 before any billed call | `daily_vlm_cap_reached` |
| Anything unexpected | View-level catch returns empty lists + warning | `unexpected_pipeline_error` |

**Why these are separate codes rather than one `vlm_failed`.** They were one code originally, and
that cost real time: when Gemini retired `gemini-2.0-flash`, every crop returned a bare `None`
that looked exactly like a bad key, a network blip, or an unreadable spine. Diagnosing it needed
a throwaway script. A bad key, a retired model and a garbled answer need three different fixes,
so they now carry three different codes. Failures that will repeat identically on every crop —
anything about the key or the model — are promoted once to scan level so the app shows one
actionable banner instead of ten identical row warnings, and are never retried, because retrying
a 404 only burns latency.

`app/lib/warnings.ts` is the single place that turns a code into a message and decides whether it
is the user's problem ("retake the photo") or the operator's ("fix the key"). Every path here is
covered by `scanner/tests/test_pipeline.py`.

Test photos in `test_photos/` reproduce these on demand:

| File | Exercises |
|---|---|
| `shelf_readable.jpg` | Normal path, 10 spines detected |
| `shelf_low_confidence.jpg` | Blurred spines → low scores → review queue |
| `shelf_zero_detections.jpg` | Empty wall → zero-detection fallback |

Regenerate with `python scripts/generate_test_photos.py`.

---

## 8. Cost and abuse controls

An unauthenticated endpoint that triggers billed API calls is a real risk on conference Wi-Fi,
so there are two layers: stop the request volume, and cap what any single scan can spend.

| Control | Default | Enforced in |
|---|---|---|
| Shared bearer token on every endpoint | `dev-token` | `permissions.py` |
| Scan throttle | 10/min | DRF `ScopedRateThrottle` |
| Library write / catalog search throttle | 30/min, 60/min | DRF |
| Max VLM calls per scan | 10 | `pipeline.py` |
| Max VLM calls per day | 50 | `pipeline.py` + `views.py` |
| Daily spend cap | $5.00 | `views.py`, summed from `ScanLog` |
| Per-call timeout / retries | 15 s, 1 retry, no retry on auth/model errors | `vlm.py` |
| Concurrent calls per scan | 5 | `pipeline.py` |
| Crop downscale before upload | 512 px longest edge | `vlm.py` |
| Upload size / content-type validation | 8 MB, `image/*` | `views.py` |
| CORS allowlist | Expo dev origins only | `settings.py` |

No secrets in the repo, no image bytes or prompt bodies in logs. There is deliberately **no user
auth** — the brief says it is out of scope, and a single shared token is enough to stop the
endpoint being open to the network.

---

## 9. CI

`.github/workflows/ci.yml` runs on every push and pull request:

| Job | What it does |
|---|---|
| **backend** (Python 3.11 and 3.12) | `ruff check`, `ruff format --check`, Django system checks, `makemigrations --check` so a model edit cannot land without its migration, then pytest |
| **app** | `npm ci` and `tsc --noEmit` |
| **secrets** | `scripts/check_no_secrets.sh`, then gitleaks over full history |

**CI runs with no API key at all**, and with `VLM_DRY_RUN=True`. Every test either mocks the
provider or runs dry, so the pipeline cannot leak a key it never had, and a live call from CI
would be a bug rather than a bill. It also installs `requirements-dev.txt` rather than the
detector extra, which means CI exercises the OpenCV fallback path on every run.

`scripts/check_no_secrets.sh` is deliberately small and dependency-free, so it cannot fail for
reasons unrelated to secrets. It fails the build if a `.env` is ever tracked, if a
Gemini/OpenAI/Anthropic key shape appears in tracked content, or if `.env.example` ships with a
real key filled in. Run it locally the same way CI does:

```bash
./scripts/check_no_secrets.sh
```

`.gitattributes` pins shell scripts to LF so a Windows checkout cannot commit a CRLF shebang that
Linux refuses to execute, and Dependabot opens grouped weekly dependency PRs.

---

## 10. Key decisions and tradeoffs

- **Monolith, not microservices.** One consumer, one machine, no deployment requirement. Splitting
  detect/VLM/match into services would mean three sets of error handling to keep in sync with the
  "never crash" requirement, for none of the benefits. The service-layer split already gives the
  isolation and testability people reach for microservices to get.
- **YOLOv8n with an OpenCV fallback, rather than picking one.** The brief requires a pretrained
  local model; the measurements above show COCO's `book` class is unreliable on vertical spines.
  Keeping both means the requirement is genuinely met while the app still works when the model
  finds nothing. Set `DETECTOR_BACKEND=opencv` to skip YOLO and save ~300 ms per image.
- **Per-crop VLM calls over one batched call** — blast radius, as described above. The latency
  cost of that choice is paid back with a bounded thread pool rather than by batching, which keeps
  one bad spine from poisoning the other nine.
- **0.85 threshold**, chosen so that a title-perfect match with a *wrong* author (score 0.80)
  lands in review rather than being auto-accepted. It is a setting, not a literal, so every
  threshold and cap lives in one file.
- **Typed failure codes instead of a nullable return.** A `dict | None` from the VLM layer made
  four unrelated problems look identical and cost an afternoon of debugging. Naming each failure
  is what let the app tell the user whether to retake the photo or fix the key.
- **SQLite and a management command to load the catalog**, so the catalog stays a reviewable CSV
  in version control rather than hand-maintained database rows.
- **Cropping locally is the whole cost story** — it is what makes per-photo cost a tenth of a cent.

---

## 11. What is unfinished, and what I would do next

**Unfinished, honestly:**

1. **Test photos are synthetic.** They reproduce every failure mode deterministically on any
   machine, which is why they are committed, but they are rendered rectangles rather than
   photographs — and that is part of why YOLO scores zero on them. Accuracy on a real shelf, with
   real lighting and tilted spines, is unmeasured. Real photos should be committed alongside.
2. **YOLO detection quality is not good enough to lead with.** In practice the OpenCV projection
   does the work on these images, and the YOLO attempt costs weight-loading time for nothing.
3. **No crop caching**, so re-scanning the same photo pays the full VLM cost again.
4. **No end-to-end test through the Expo app.** The backend is well covered and the client is
   typechecked, but nothing exercises capture → review → save as one flow.
5. **Deployment is not addressed.** CI proves the code is sound; there is no CD, no container,
   and SQLite with `DEBUG` off has not been validated for anything beyond local use.

**With another day:**

1. Swap the COCO checkpoint for a book-spine-specific community checkpoint, and measure
   precision/recall against hand-labelled boxes instead of eyeballing box counts.
2. Deskew each crop before Stage 2 — spines are often tilted, and rotating to vertical should
   lift read accuracy for free.
3. Cache VLM results keyed by a crop hash so repeated demos cost nothing.
4. Let the review screen merge duplicates when the same book is detected twice in one photo.
5. Persist `source_image` per library entry so the library can show the original crop.

See [`AI_USAGE.md`](AI_USAGE.md) for how AI tools were used to build this.
