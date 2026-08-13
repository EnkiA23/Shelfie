# Shelfie — Build Brief (hand this to a coding agent)

**How to use this document:** this is written to be pasted into a coding agent (Claude Code or similar) as its working brief, section by section, in the order given. Each section below is scoped so the agent can implement it, run it, and stop — don't hand over the whole document as one "build everything" prompt (see §12 on why). Sections 1–8 are the architecture/plan; sections 9–16 are the operational requirements (keys, auth, rate limits, security) that must exist before the agent wires up any real API calls.

This is scoped to the **actual assignment** (the take-home brief), not the maximal "generate everything" prompt. The grading rubric rewards good cutting, honest documentation, and a defensible matching algorithm over feature volume — so the plan below is deliberately smaller than the "non-negotiable" wishlist in the AI-prompt doc. Where they conflict, the real brief wins.

---

## 1. Time budget (8 hours target, 48-hour window)

| Block | Time | Output |
|---|---|---|
| 0. Setup & scaffolding | 0.5h | Django project, Expo project, repo structure, first commit |
| 1. Catalog (`catalog.csv`) | 0.5h | 100+ messy entries, LLM-generated + hand-checked |
| 2. Matching module + tests | 1.5h | `matching.py`, `test_matching.py`, confidence scoring |
| 3. Backend pipeline (detect → VLM → match) | 2h | `ScanBookshelfView`, spine detector wrapper, VLM client, error handling |
| 4. Expo app (3 screens) | 2h | Capture → Review → Library |
| 5. Metrics + graceful fallback wiring | 0.5h | Latency/cost logging, empty-array-on-failure paths |
| 6. README, AI_USAGE.md, test photos, polish | 1h | Docs + commit hygiene |

Buffer lives in the 48-hour window, not the 8-hour budget — plan to do this across 2–3 sittings with real incremental commits, not one marathon session (the brief explicitly penalizes a single giant commit).

**Cuts to make on purpose, and say so in the README:**
- No auth, no deployment (explicitly not graded).
- No fine-tuning (explicitly forbidden).
- One local detector, no ensemble.
- Review screen UI is functional, not polished.
- Only as many manual test photos as needed to demo the three failure modes (zero detections, low confidence, VLM error) — not a big test set.

---

## 2. Repo structure

```
shelfie/
├── backend/
│   ├── manage.py
│   ├── shelfie/                  # Django project (settings, urls)
│   ├── scanner/                  # app: pipeline + views
│   │   ├── views.py              # ScanBookshelfView
│   │   ├── detector.py           # Stage 1: local spine detection
│   │   ├── vlm.py                # Stage 2: hosted VLM client
│   │   ├── matching.py           # Stage 3: fuzzy match + scoring
│   │   ├── metrics.py            # latency/cost tracker
│   │   ├── models.py             # Book, LibraryEntry, ScanLog
│   │   ├── serializers.py
│   │   └── tests/
│   │       └── test_matching.py
│   ├── catalog.csv
│   └── requirements.txt
├── app/                           # Expo app
│   ├── screens/
│   │   ├── CaptureScreen.tsx
│   │   ├── ReviewScreen.tsx
│   │   └── LibraryScreen.tsx
│   ├── api/client.ts
│   └── App.tsx
├── test_photos/                  # bookshelf photos used for dev/demo
├── README.md
└── AI_USAGE.md
```

---

## 3. Pipeline architecture

```
Expo App
   │  photo (multipart POST)
   ▼
POST /api/scan/                       [Django DRF]
   │
   ├─ Stage 1: Local detection (CPU)
   │     YOLOv8n (pretrained COCO or a book-spine-tuned
   │     community checkpoint if one is easily available;
   │     otherwise plain OpenCV contour/line detection as a
   │     cheap fallback) → list of spine bounding boxes
   │     ├─ 0 boxes / detector error → fall back to sending
   │     │  the FULL image to Stage 2, log a warning, continue
   │     └─ N boxes → crop each spine, keep in memory
   │
   ├─ Stage 2: Hosted VLM (one call per crop, or a single
   │     batched call with all crops + a JSON-schema prompt —
   │     pick ONE strategy and justify it in README on cost/
   │     latency grounds)
   │     ├─ timeout / malformed JSON → catch, skip that crop,
   │     │  continue with the rest (never 500)
   │     └─ success → {extracted_title, extracted_author} per crop
   │
   ├─ Stage 3: Fuzzy match against catalog.csv (in SQLite)
   │     → confidence score 0.0–1.0 per book
   │
   └─ Response: {
        high_confidence: [...],   // score >= 0.85
        needs_review: [...],      // score < 0.85 or unmatched
        metrics: {latency_ms, est_cost_usd, spines_detected}
      }
   HTTP 200 always on a handled failure; only truly
   unexpected exceptions should ever surface as 5xx, and
   even those should be caught at the view level.
   │
   ▼
Expo App: Review screen (human-in-the-loop) → confirm/edit/discard
   │
   ▼
POST /api/library/  → persist confirmed entries to SQLite
   │
   ▼
Library screen: GET /api/library/
```

Key architectural point to lead with in the presentation: **cropping locally moves the model's job from "read text somewhere in a full shelf photo" to "read text in a tight spine crop,"** which is both what makes the VLM call cheap (smaller payload → fewer tokens) and what makes it accurate (less to search, less to hallucinate). That framing is the actual engineering justification — lead the demo with it rather than the cost number alone.

---

## 4. Backend design details

**Models (`scanner/models.py`)**
- `CatalogBook`: id, title, author, alternate_titles (comma/JSON), edition_info — loaded from `catalog.csv` via a management command (`load_catalog`), not hand-maintained in the DB.
- `LibraryEntry`: fk to CatalogBook (nullable, for "kept as unmatched custom entry"), raw_title, raw_author, confidence_score, source_image, created_at.
- `ScanLog` (optional, only if time allows): latency_ms, est_cost_usd, spines_detected, spines_matched — gives you the "measured benchmarks" the README needs without hand-timing.

**Matching (`scanner/matching.py`)**
- Normalize both sides: lowercase, strip punctuation/subtitle-after-colon, strip leading articles.
- Score = weighted blend, e.g.:
  - `token_sort_ratio(title, catalog_title)` — handles reordering
  - best of `token_sort_ratio` against each `alternate_titles` entry — handles US/UK titles, omnibus vs volume
  - `partial_ratio` — handles substring titles (catches false positives too, so weight it down or use it only as a tiebreaker, not the primary score)
  - author match (normalized "Last, First" ↔ "First Last" ↔ initials) as a **bonus/penalty modifier**, not a hard filter — this is what resolves "two different books with the same title" (Cormac McCarthy's *The Road* vs Jack London's) without author agreement, don't let title score alone hit 0.85.
- Return top-N candidates with scores, not just the top-1 — the Review screen should be able to show "did you mean" alternatives.
- This is the module to pytest hardest — write one test per catalog edge case (editions, US/UK, shared title, omnibus, substring, messy author names). That test file doubles as your proof-of-work for the "matching against a messy catalog" grading criterion.

**Views**
- `ScanBookshelfView`: orchestrates the three stages, each stage wrapped in its own try/except so one stage's failure doesn't take down the others' results.
- `LibraryViewSet` (list/create) for persistence.

**Metrics**
- Wrap Stage 1 and Stage 2 calls with `time.perf_counter()`; sum for total latency.
- Cost estimate: hosted VLM pricing × (input tokens ≈ image size + prompt, output tokens ≈ JSON response) — compute this per real call during your own test runs and put actual numbers in the README, not hypothetical ones. This is explicitly graded ("numbers, not adjectives").

---

## 5. Frontend design details

- **CaptureScreen**: `expo-image-picker` (camera + library), single "Scan" button, loading state, error banner component reused across screens.
- **ReviewScreen**: two sections — High Confidence (list with one-tap "Add All" / per-item accept) and Needs Review (card per item: crop thumbnail, editable title/author fields, a simple catalog search/autocomplete pulling from `/api/catalog/search/`, Discard button). This screen is the part graders said to treat "as part of the product, not a debug screen" — spend real UI time here relative to Capture/Library.
- **LibraryScreen**: simple flat list from `GET /api/library/`, pull-to-refresh.
- Shared `ErrorBanner` component triggered on network failure, zero-detections response, and VLM-timeout response — three distinct friendly messages, not one generic one.

---

## 6. Catalog build approach (30–45 min)

Generate ~100–120 entries with an LLM, then hand-verify the six required edge cases are actually present and correctly structured (don't trust the LLM's edge cases blindly — this is exactly what you'll be asked to defend):
1. Two editions of the same book as separate rows.
2. Same book, two regional titles (US/UK).
3. Two different books, identical title, different authors.
4. Omnibus row + its individual-volume rows.
5. A title that's a substring of another, unrelated title.
6. One author appearing in 3+ written forms across different rows (initials, full name, "Last, First").
Bias the list toward commonly-owned books (bestsellers, classics, popular sci-fi/fantasy) since the presentation uses the interviewers' real shelves.

---

## 7. Documentation deliverables

- **README.md**: setup (backend venv + `pip install`, `python manage.py migrate`, `load_catalog`, `runserver`; Expo `npm install` + `npx expo start`), architecture diagram (reuse §3), measured latency/cost table, tradeoffs (why YOLOv8n vs plain OpenCV, why this scoring blend, single vs batched VLM calls), catalog design rationale, what's unfinished + next-day plan.
- **AI_USAGE.md**: honest, specific — which tool for which file (e.g., "used Claude to draft matching.py scoring weights, then hand-tuned thresholds against test photos"; "catalog.csv first-drafted by an LLM, hand-edited for edge-case correctness"). Vague "AI helped throughout" answers are the thing they're explicitly screening against.
- **test_matching.py**: real pytest cases, one per catalog edge case, plus 1-2 for malformed/empty input.

---

## 8. Order of operations (so you always have something demoable)

1. Catalog + matching module + tests first — it's the part they check hardest and it has zero external dependencies (no camera, no API keys).
2. Django models + `load_catalog` command + `LibraryViewSet` — gets persistence working end to end with fake data.
3. Wire a **stub** `ScanBookshelfView` that skips real detection/VLM and returns canned matched results — unblocks frontend work immediately.
4. Build Expo screens against the stub.
5. Swap in real YOLOv8n detection, then real VLM calls, keeping the fallback paths from day one (don't bolt them on at the end).
6. Metrics, README, AI_USAGE.md, commit cleanup.

This ordering means that if you run out of time, what's cut is the *real* vision pipeline (falls back to the stub/degraded path) rather than the matching logic or the review UI — and that's a defensible, disclosed cut, not a silent one.

---

## 9. Repo strategy: monorepo vs polyrepo

**Monorepo.** The brief asks for "a GitHub repository" — singular — with real incremental commit history the interviewers can read end to end. A polyrepo (separate `shelfie-backend` / `shelfie-app` repos) would:
- split the commit history exactly where they want to see the pipeline evolve together (a commit that adds a field to the API response and the screen that consumes it is one meaningful commit in a monorepo, two disconnected ones in a polyrepo),
- add setup friction against "must run from a clean clone" — two clones, two READMEs to reconcile,
- buy you nothing at this scale — there's no independent deploy cadence, no separate team, no need to version the API against multiple frontend clients.

Use `backend/` and `app/` as top-level folders in one repo (already reflected in §2). Put a single root `README.md` that covers both, rather than a README per folder — one clean-clone story, not two.

---

## 10. Design pattern: controller vs service layer

Short answer: **thin views (controllers) + a separate service/pipeline layer underneath, inside a standard Django monolith.** Not a bare "fat controller" pattern, and not full DDD/hexagonal — that's over-engineering for 8 hours.

Concretely:
- `views.py` (`ScanBookshelfView`, `LibraryViewSet`) is the **controller layer**: parses the request, calls the pipeline, shapes the HTTP response, handles status codes. It should contain almost no business logic — no scoring math, no image processing inline.
- `detector.py`, `vlm.py`, `matching.py`, `metrics.py` are the **service layer**: each is a plain Python module/class with a clear single-purpose entry point (`detect_spines(image) -> list[BBox]`, `extract_text(crop) -> dict`, `match(raw_title, raw_author) -> list[ScoredCandidate]`). Each is independently unit-testable without spinning up Django's request/response cycle — which is exactly why `test_matching.py` can import `matching.py` directly and test it in isolation.
- A thin `pipeline.py` (or a method on the view, if you want to save a file) composes the three services in order and owns the per-stage try/except + fallback logic. That's the one piece of "orchestration" logic that's allowed to sit close to the controller.

Why this over a raw fat-controller approach: the grading explicitly checks whether the matching logic is "more than a string comparison" and whether you can defend every line — a service layer you can point to and unit-test in isolation is a much easier thing to defend live than logic buried inside a DRF view method.

Why not further (repository pattern, DI containers, DDD entities): none of that pays for itself at this scope — it would eat implementation hours on abstraction the interviewers didn't ask for and can't observe in a 30-minute demo.

---

## 11. Microservices vs a single API

**Single Django monolith exposing a REST API. Not microservices.**

Reasons, stated plainly for the README/defense:
- Microservices buy you independent scaling, independent deployment, and fault isolation between services — none of which apply here: deployment isn't even required, there's one consumer (the Expo app), and the whole thing runs on one machine for the demo.
- Splitting detection/VLM/matching into separate services would mean three processes, inter-service HTTP calls, and three sets of error handling to keep in sync with the "never crash, always return something" requirement — pure overhead that increases the surface area for the exact failure modes ("graceful failure") the brief is grading you on.
- The service-layer split in §10 already gives you the real benefit people reach for microservices for (isolated, independently testable, swappable components) without the operational cost. If in the future you genuinely needed to scale the VLM calls independently of the detector, that's a refactor of `vlm.py`'s call site into a task queue — not a reason to split repos or processes today.

State this explicitly in the README's tradeoffs section — "monolith, service-layer internally, here's why" is a stronger answer under questioning than silently defaulting to one API and never explaining the choice.

---

## 12. AI tooling & agent workflow

Be explicit and honest here, since AI_USAGE.md is graded on specificity, not just disclosure.

**Hosted VLM (product-facing, does the OCR in Stage 2):** either GPT-4o-mini or Claude 3.5 Sonnet is a reasonable default — both handle small-image OCR-style extraction cheaply. If you already have a spend-capped key from the interviewers, use whichever they issue; otherwise pick one and justify it in the README on cost (mini/flash-tier pricing) rather than accuracy, since accuracy differences at this task size are marginal and unmeasured.

**Coding assistant (build-facing, writes/edits the repo):** Claude Code is a good fit here specifically because the task rewards incremental, explainable commits — it can work directly in your repo, run the test suite, and commit as it goes, which naturally produces the "real commit history" the brief wants instead of one AI-generated mega-commit. Any comparable agentic coding tool (Cursor, etc.) works the same way; the important part is *how* you drive it, not the brand.

Use it in distinct, single-purpose passes rather than one open-ended "build the whole thing" prompt — this also makes AI_USAGE.md easy to write honestly, since each pass maps to a bullet point:

1. **Implementation pass** — scaffold and implement one module/screen at a time, in the order from §8 (matching → models → stub view → frontend → real pipeline). Review and understand every diff before committing; you have to defend all of it live.
2. **Test-writing agent (separate pass)** — after `matching.py` is implemented, run a dedicated pass whose only job is: "write pytest cases for every edge case listed in catalog.csv §6, plus malformed/empty input cases, against the existing `matching.py` — do not modify `matching.py` itself." Keeping this a separate pass (not bundled into the implementation pass) means the tests are written against the real behavior of the code rather than co-evolving with it, which is a more honest test suite.
3. **Bug-fix agent (separate pass, triggered by a failing test or a manual repro)** — when something breaks (a test fails, the demo throws, a fallback path doesn't trigger), give the agent the specific failing test or stack trace and ask only for a fix to make it pass — not a rewrite. Diff review still applies before commit.
4. **Refactor agent (final pass, after everything works)** — once the pipeline and screens work end to end, run one dedicated cleanup pass: tighten error handling, remove dead code from the stubbed pipeline, make sure naming is consistent between `views.py` and the service modules. Do this *after* correctness, not blended into feature work, so it's a clean, reviewable diff you can point to as "the refactor commit" rather than something invisible inside a feature commit.

Log which of these four passes touched which files as you go — that log is basically your AI_USAGE.md draft, and it's much more convincing than a retrospective summary written from memory the night before the deadline.

---

## 13. Required API keys & secrets

Nothing gets committed to the repo. All of this lives in `backend/.env`, which must be in `.gitignore` from the very first commit — the agent should create `.env.example` (committed, no real values) alongside it.

**Keys you need before Stage 2 can be wired up:**

| Key | Where it comes from | Required for |
|---|---|---|
| `VLM_PROVIDER` | you choose: `openai` or `anthropic` | selects which client `vlm.py` uses |
| `OPENAI_API_KEY` *or* `ANTHROPIC_API_KEY` | the spend-capped key the interviewers offered to issue, or your own | Stage 2 hosted VLM calls |
| `DJANGO_SECRET_KEY` | generate locally (`django-admin` does this, or `python -c "import secrets; print(secrets.token_urlsafe(50))"`) | Django itself |
| `APP_SHARED_TOKEN` | generate locally, same command as above | see §14 — the one piece of access control this app has |

**`.env.example` (commit this, it documents what's needed without leaking anything):**
```
VLM_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DJANGO_SECRET_KEY=
APP_SHARED_TOKEN=
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=http://localhost:8081
MAX_VLM_CALLS_PER_SCAN=25
MAX_UPLOAD_SIZE_MB=8
VLM_TIMEOUT_SECONDS=15
VLM_MAX_RETRIES=1
DAILY_SPEND_CAP_USD=5.00
SCAN_RATE_LIMIT=10/min
```
Load with `django-environ` or `python-decouple` (either is fine, pick one). The agent's first task in the backend setup pass should be creating this file and wiring `settings.py` to read from it — every other module (`vlm.py`, throttles, the CORS config) reads its config from `settings`, never from `os.environ` directly, so there's one place to see all the knobs.

**Getting the actual key:** ask the interviewers for the spend-capped key per the brief ("API keys: ask us and we will issue you a spend-capped key... neither is scored") — that's the lowest-risk option since it's pre-capped on their end regardless of what §15 enforces on yours.

---

## 14. Authentication

The brief explicitly says auth isn't graded and isn't required for the product. But "no auth" and "wide open to anyone on the network who finds the port" aren't the same thing, and an unauthenticated endpoint that triggers billed API calls is a real risk the moment your laptop is on shared wifi during the presentation. So: no user accounts, no login screen, but a minimal gate.

**What to build:** a single static shared-secret header, not a user auth system.
- Expo app sends `Authorization: Bearer <APP_SHARED_TOKEN>` on every request, read from an Expo env var (`EXPO_PUBLIC_API_TOKEN`) set locally, never committed.
- Django side: a small DRF `permission_classes = [HasAppToken]` custom permission checking the header against `settings.APP_SHARED_TOKEN`, applied to `ScanBookshelfView` and the library endpoints. A few lines, not a library.
- No user model, no sessions, no JWT — that would be solving a problem ("multiple users, per-user libraries") this app doesn't have, and the brief tells you not to grade it.

State this explicitly in the README as a deliberate, scoped decision: "no user auth (out of scope per brief); a single shared app token gates the API so it isn't billing-call-open on the network."

---

## 15. Rate limiting & AI usage caps

This is the part that actually protects your spend cap, and it needs to exist in two layers: **stopping abusive/accidental request volume**, and **stopping any single scan from being expensive**.

**Layer 1 — request-level throttling (DRF built-in):**
```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "scan": env("SCAN_RATE_LIMIT", default="10/min"),
        "library_write": "30/min",
    },
}
```
Apply `throttle_scope = "scan"` on `ScanBookshelfView`. This is what stops a retry loop or a UI bug from silently hammering the VLM.

**Layer 2 — per-scan cost ceiling, enforced in `vlm.py` / the pipeline, not just at the HTTP layer:**
- `MAX_VLM_CALLS_PER_SCAN` — hard cap on how many spine crops get sent per photo. If the detector finds more spines than the cap, send the top-N by bounding-box confidence/size and mark the rest as "not scanned" in the response rather than silently calling the VLM 40 times on one shelf photo.
- `VLM_TIMEOUT_SECONDS` and `VLM_MAX_RETRIES` — every VLM call gets a hard timeout and at most one retry on failure, then falls into the existing graceful-failure path (§3, Stage 2 fallback). No unbounded retry loops.
- `DAILY_SPEND_CAP_USD` — the metrics tracker (§4) sums `est_cost_usd` across `ScanLog` rows for the current day before each new scan starts; if the running total is over the cap, `ScanBookshelfView` returns a clear `429`-style response ("daily demo budget reached") instead of making the call at all. This is a soft, app-level guard — the real backstop is the spend-capped key itself (§13) — but it means you find out from your own UI, not from a billing alert.
- A `VLM_DRY_RUN` env flag (bonus, cheap to add) that makes `vlm.py` return canned fixture responses instead of calling the real API — lets the agent build and test the whole review-screen flow without spending anything, and lets you demo the fallback UI on command by flipping it on.

Put the measured numbers this produces (real per-image latency, real per-image cost against the cap) straight into the README's benchmarks section — that's the same data §15 is enforcing against.

---

## 16. Security checklist

Scoped to what a local-run, non-deployed, non-graded-on-auth demo app actually needs — not a production hardening pass:

- **Upload validation:** reject uploads over `MAX_UPLOAD_SIZE_MB`, reject non-image content types, before the file ever reaches the detector. This is also a cost control (§15) — a huge image is a slow, expensive Stage 2 call.
- **Secrets never in the repo:** `.env` gitignored from commit #1, `.env.example` committed instead, no key ever pasted into a prompt, log line, or test fixture. Grep the diff for the literal string `sk-` / `sk-ant-` before every commit if you want a cheap safety net.
- **CORS locked to the Expo dev origin**, not `*` — `CORS_ALLOWED_ORIGINS` from `.env`, read into `django-cors-headers` config.
- **No secrets or PII in logs:** the metrics/latency logger (§4) logs cost and timing, never the raw image bytes or the full VLM prompt/response body.
- **Input validation on the confirm/save endpoint:** whitelist the fields the review screen can write (title, author, catalog_book_id, discard flag) via the DRF serializer — don't accept an arbitrary JSON blob into `LibraryEntry`.
- **`DEBUG=False` reminder in README** for anyone who does try to run it beyond localhost, even though deployment itself is out of scope.

None of this is a "security audit" — it's the minimum so that handing over a spend-capped API key and demoing on shared wifi doesn't turn into an incident. Say that explicitly in the README's tradeoffs section so it reads as a scoped decision, not an oversight.
