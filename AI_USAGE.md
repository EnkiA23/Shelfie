# AI Usage

I used AI tooling heavily on this task. This file records what it wrote, what I changed, and
what I would be able to defend line by line.

## Tools

| Tool | Role |
|---|---|
| Cursor (agent mode, Claude-family model) | Wrote most of the repository, driven in scoped passes |
| Gemini 3.1 Flash-Lite | The product's own Stage 2 VLM — reads title/author off spine crops at runtime |

The agent was driven in separate, single-purpose passes rather than one "build the whole thing"
prompt, so each pass maps to a reviewable diff.

## Pass 1 — Catalog and matching

- **`scripts/generate_catalog.py`, `catalog.csv`** — AI-generated the bulk of the 130 rows from a
  prompt asking for commonly-owned books. I specified all six ambiguity cases by hand
  (rows 1–15) rather than trusting the model to invent them, because those are the rows the
  matcher is actually judged on. I verified each one exists and is structured correctly.
- **`scanner/matching.py`** — AI drafted the normalisation helpers and the rapidfuzz scoring
  blend. I set the weights (0.55 / 0.35 / 0.10) and the author modifier values myself against
  the failing tests; the first draft used `partial_ratio` too heavily and matched
  `Great` to `The Great Gatsby`.
- **Threshold tuning was mine.** The author-mismatch penalty started at −0.15, which left the
  wrong-author `The Road` at exactly 0.85 — right on the auto-accept line. I moved it to −0.20
  so it lands at 0.80 and goes to review. That test failure is in the commit history.

## Pass 2 — Tests, written separately from the implementation

Run as its own pass with the instruction "write tests against the existing behaviour of
`matching.py`; do not modify `matching.py`", so the tests could not be quietly reshaped to
match a bug.

- **`scanner/tests/test_matching.py`** — one test per catalog ambiguity, plus empty and
  malformed input.
- **`scanner/tests/test_pipeline.py`** — the graceful-failure matrix: detector returning nothing,
  detector raising, VLM returning `None`, VLM raising, per-scan cap, auth, upload validation.

## Pass 3 — Backend pipeline

- **`models.py`, `serializers.py`, `views.py`, `urls.py`, `load_catalog`** — AI-written from the
  plan's spec, reviewed and kept largely as drafted; this is standard DRF shape.
- **`detector.py`** — AI wrote the first version as a Canny-contour loop. I replaced the core
  with a vertical Sobel edge-projection segmentation because contours fragment on book cover
  artwork, and added the YOLOv8n path so the "pretrained local model" requirement is genuinely
  met rather than nominally.
- **`vlm.py`** — AI wrote the three provider clients. I added the markdown-fence stripping in
  `_parse_extraction_payload` after Gemini returned ```json-wrapped output, and the crop
  downscale, which is the single biggest cost lever in the pipeline.
- **`metrics.py`** — provider pricing constants entered by hand from published rate cards.

## Pass 4 — Expo app

- **Screens, navigation, theme, components** — AI-written. The first version was three plain
  screens with default React Native buttons; I had it redone as a bottom-tab mobile layout with
  a shared theme, and specifically asked for the review screen to carry crop thumbnails and
  per-item explanations, since that screen is graded as product surface rather than a debug view.
- **`api/client.ts`** — the platform-split upload (`File` on web, `{uri,name,type}` on native)
  was a fix I directed after multipart uploads silently failed in the browser.

## Pass 5 — Docs and measurement

- **`benchmark_scan` management command** — AI-written so the README numbers come from a
  reproducible command rather than hand timing.
- **`README.md`** — structure and prose AI-assisted; every number in it was produced by running
  `benchmark_scan` on this machine against a live key. Nothing in §3 is an estimate.
- **`scripts/generate_test_photos.py`** — AI-written; synthetic on purpose so the three failure
  modes reproduce on any machine, and flagged as a limitation in the README.

## Pass 6 — Refactor (behaviour-preserving, run last)

Run only after the pipeline and both screens worked end to end, so it is one reviewable
`refactor:` commit rather than cleanup hidden inside feature diffs.

- Deleted `load_catalog_from_rows` from `matching.py` — dead since the management command does
  its own CSV parsing.
- `daily_spend_total` now aggregates in SQL instead of summing `ScanLog` rows in Python.
- `CONFIDENCE_THRESHOLD` moved from a module constant to a setting, so every threshold and cap
  lives in one place.
- Removed a dead `extraction = None` assignment in the pipeline's exception branch.

One behaviour change went in as a `fix` rather than part of the refactor: `vlm.py` used to
return canned dry-run data when live mode was on but no API key was set, which silently
produced fake matches from a misconfiguration. It now reports `vlm_not_configured` and the
pipeline surfaces it, with a test asserting no confident matches come back.

## Pass 7 — First live run, and what it broke

Everything up to here ran in dry-run. Pointing a real key at it surfaced problems no amount of
mocking would have:

- **The default model was dead.** `gemini-2.0-flash` had been retired; every call returned HTTP
  404. Because `vlm.py` collapsed all failures to `None`, this was indistinguishable from a bad
  key, and diagnosing it needed a throwaway script. That is the origin of the typed failure
  codes and of the `check_vlm` command — the fix was to make the system able to explain itself,
  not just to change a string.
- **A scan took 16 seconds.** Ten sequential round trips at ~1.4 s each. Reading crops on a
  bounded thread pool took it to ~2 s. This was invisible in dry-run, where stage 2 costs
  milliseconds.
- **Cost accounting was a guess, and wrong in both directions.** It assumed 900 input tokens;
  the real figure is ~1070. It also charged for calls that 404'd and were never billed, which
  would have burned the daily cap on free failures. Both now use the provider's reported usage.
- **Measured accuracy replaced assumed accuracy.** 8 of 10 spines on the readable photo, 1 of 10
  on the deliberately blurred one, with the rest correctly routed to review.

The `partial_ratio` weighting and the −0.20 author penalty, both tuned in dry-run against the
test suite, held up unchanged against real model output.

## The four passes as checked-in skills

The workflow above is not just described here — `.cursor/skills/` contains
`implementation-pass`, `test-pass`, `bugfix-pass` and `refactor-pass` so the same discipline is
reproducible by anyone working in the repo, and `AGENTS.md` holds the conventions that apply to
all of them.

## Things I rejected from AI output

- A first-draft matcher that used `partial_ratio` as the primary signal — false-positive machine.
- Batching all crops into one VLM call: cheaper, but one malformed response loses the whole scan.
- A suggested user auth system with a `User` model and JWT: the brief says auth is out of scope,
  so it is a single shared token instead.
- Silently dropping crops the VLM could not read, which is exactly the behaviour the brief
  prohibits. They surface as review cards with the crop attached.
