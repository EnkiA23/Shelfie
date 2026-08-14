## What changed

<!-- One or two sentences. Why, not just what. -->

## How it was verified

<!-- Commands run, or the manual path exercised. -->

- [ ] `nx run backend:test`
- [ ] `nx run backend:lint && nx run backend:format-check`
- [ ] `nx run mobile:typecheck`

## Checks specific to this project

- [ ] No API key, `.env`, or other credential is in the diff
- [ ] Any new way a stage can fail appends a warning code, returns HTTP 200, and
      has a message in `apps/mobile/lib/warnings.ts` — silent drops are a bug
- [ ] Layer boundaries in `docs/ARCHITECTURE.md` still hold: views parse and delegate,
      services hold the logic
- [ ] Cost-affecting changes keep the per-scan cap and daily cap intact
