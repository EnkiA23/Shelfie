# Architecture

Structural decisions, and the reasoning I would give if asked to defend them live.

---

## 1. One repository, not two

`backend/` and `app/` are top-level folders in one repository with one root `README.md`.

A split into `shelfie-backend` and `shelfie-app` would:

- **Break the commit history exactly where it is most readable.** Adding a field to the scan
  response and consuming it in the review screen is one coherent commit here; across two repos
  it becomes two disconnected commits that a reviewer has to correlate by timestamp.
- **Double the clean-clone setup cost.** Two clones and two READMEs to keep in sync, against a
  requirement that the project runs from a clean clone.
- **Buy nothing at this scale.** No independent deploy cadence, no separate teams, no second
  frontend client that would need the API versioned against it.
- **Split CI in half.** One workflow currently proves the API and the client that consumes it
  agree, on the same commit.

### Why not `apps/` + `packages/`

The obvious next step up is an Nx- or Turborepo-style workspace: `apps/api`, `apps/mobile`,
`packages/shared`, `infrastructure/`. That shape solves three problems, and this project has
none of them.

| That layout exists to | Shelfie's situation |
|---|---|
| Share code between several apps | Two components, nothing shared but the HTTP contract |
| Avoid rebuilding untouched projects | A test run is seconds; there is no build graph to prune |
| Give many teams clear ownership | One author |

It would cost a directory level on every path, a workspace tool to install and keep working, and
several folders that start empty. The organising work that layout is really doing — keep
generated artefacts out, keep docs somewhere findable, keep CI declarative — is done here by
`docs/`, `scripts/`, `.github/` and `.gitignore` instead.

**What would change my mind:** a second client (a web dashboard, say) that needed the response
types. At that point `packages/shared-types` earns its keep, and the move is a rename rather
than a rewrite, because the API boundary is already a single module on each side.

---

## 2. Thin controllers over a service layer

Standard Django monolith with a clear internal split. Not a fat controller, and not
DDD/hexagonal — that would be abstraction the task did not ask for and a reviewer cannot
observe in a 30-minute demo.

```
HTTP request
     │
     ▼
views.py                    CONTROLLER
  parse and validate the upload, enforce caps and throttles,
  delegate, shape the HTTP response, choose the status code
     │
     ▼
pipeline.py                 ORCHESTRATION
  compose the three stages in order, own the per-stage try/except,
  collect metrics and warning codes
     │
     ├──▶ detector.py       SERVICE   detect_spines(bytes) -> list[BoundingBox]
     ├──▶ vlm.py            SERVICE   extract_text_from_crop(Image) -> VlmResult
     ├──▶ matching.py       SERVICE   match_against_catalog(...) -> list[ScoredCandidate]
     └──▶ metrics.py        SERVICE   MetricsTracker, estimate_vlm_cost(...)
```

### The rules this implies

| Layer | May do | May not do |
|---|---|---|
| `views.py` | HTTP concerns, validation, status codes | Scoring math, image processing, provider calls |
| `pipeline.py` | Sequence stages, contain failures, aggregate metrics | Touch `request` or `Response` |
| Services | One public entry point, pure-ish Python | Import Django request objects, know about HTTP |

### Why it earns its keep

The grading explicitly asks whether the matching logic is "more than a string comparison." A
service module is something I can point at, run in isolation, and explain. The same logic
buried inside a DRF view method is testable only through the HTTP layer and much harder to
defend under questioning.

`scanner/tests/test_matching.py` imports `matching.py` directly and never spins up a request.
That is the property the split exists to buy.

### Deliberately not adopted

**Repository pattern** — the ORM is already the abstraction over storage, and there is one
storage backend. **DI container** — four modules with one entry point each; constructor
injection would add indirection without decoupling anything real. **DDD entities** — the domain
is a book with a title and an author.

### Service return values name their failures

`vlm.py` originally returned `dict | None`. That is the smallest possible contract, and it was
the wrong one: `None` meant "no key", "key rejected", "model retired", "timed out" and "the
model replied with broken JSON" all at once. Those need five different responses — three from
the operator, two from the user — and the caller had no way to tell them apart.

It now returns a `VlmResult` carrying either the extraction or a specific `failure_code`, plus
the provider's token usage. The pipeline maps the code to a warning, decides whether to retry,
and decides whether the call was billable. **A service may hide its implementation, but it may
not hide which of its failure modes occurred.**

---

## 3. One Django monolith, not microservices

Detection, VLM calls and matching run in one process behind one REST API.

Microservices exist to buy independent scaling, independent deployment and fault isolation.
None apply here: deployment is explicitly out of scope, there is exactly one consumer, and the
whole thing runs on one laptop for the demo.

Splitting the three stages into services would mean three processes, inter-service HTTP calls,
and **three separate sets of error handling to keep in sync** with the "never crash, always
return something" requirement. That directly enlarges the surface area of the graceful-failure
behaviour the task grades.

The §2 service-layer split already delivers what people actually reach for microservices to
get — isolated, independently testable, swappable components — at none of the operational cost.

**What would change my mind:** if VLM calls needed to scale independently of detection, the
first move is still not a service split. It is moving the `vlm.py` call site behind a task
queue and returning a job id from `/api/scan/`. Same repository, same process boundary,
one changed call site.

---

## 4. Request lifecycle

```
POST /api/scan/  (multipart photo)
  │
  ├─ HasAppToken            401/403 if the bearer token does not match
  ├─ ScopedRateThrottle     429 above 10 scans/min
  ├─ daily spend + call cap 429 before any billed call
  ├─ upload validation      400 above 8 MB or non-image content type
  │
  ├─ Stage 1  detect_spines()      YOLOv8n ─▶ OpenCV ─▶ full-image fallback
  ├─ Stage 2  extract_text_from_crop()   per crop, 5 at a time, timeout + 1 retry
  ├─ Stage 3  match_against_catalog()    score 0.0–1.0 + alternatives
  │
  ├─ ScanLog row written (latency, estimated cost, counts)
  └─ 200 { high_confidence, needs_review, metrics }
```

Only unauthenticated, throttled, malformed or over-quota requests get a non-200. Every
*model* failure returns 200 with a warning code, because the app always has something to show.

---

## 5. Frontend structure

```
App.tsx              bottom tabs (Scan, Library) + Review as a stack screen
screens/             one file per screen, no cross-screen imports
components/          AppButton, BookCard, ErrorBanner — presentational only
api/client.ts        the only module that knows the API exists
lib/warnings.ts      backend warning codes -> message + severity
theme.ts             colour, spacing and radius tokens
```

Scan state lives in `App.tsx` and is passed to Review, rather than in a global store. One piece
of shared state does not justify a state-management dependency.

`api/client.ts` is the single network boundary: every request goes through one `request()`
helper that attaches the bearer token and normalises error payloads into readable messages.
Platform differences — the web `File` upload versus the React Native `{uri, name, type}`
form — are handled there so no screen has to care.

`lib/warnings.ts` is the mirror of that boundary for the backend's warning codes. Keeping the
mapping in one module means a screen never invents its own wording for a failure, and adding a
warning code to the pipeline has exactly one place it must be handled on the client. It also
carries the severity, which is what decides whether the user sees "retake the photo" or the
operator sees "fix the key".

---

## 6. Agent workflow

The four passes used to build this are checked in as project skills so the workflow is
reproducible rather than described after the fact:

| Skill | Role |
|---|---|
| `.cursor/skills/implementation-pass` | One module or screen at a time, in build order |
| `.cursor/skills/test-pass` | Tests written against existing behaviour, code under test frozen |
| `.cursor/skills/bugfix-pass` | One failure, smallest possible diff |
| `.cursor/skills/refactor-pass` | Behaviour-preserving cleanup, only after features work |

`AGENTS.md` holds the conventions that apply to every pass. `AI_USAGE.md` records which pass
actually touched which files.
