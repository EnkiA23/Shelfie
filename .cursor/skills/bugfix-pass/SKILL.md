---
name: bugfix-pass
description: Fixes one specific Shelfie failure from a failing test or stack trace with the smallest possible change, without rewriting surrounding code. Use when a test fails, the demo throws, or a fallback path does not trigger.
disable-model-invocation: true
---

# Bug-Fix Pass

Scope is **one** failure. A rewrite is not a fix — the surrounding code was reviewed and
committed deliberately, and a large diff is unreviewable before a deadline.

## Workflow

1. **Reproduce first.** Run the failing test or repro the request. Never fix from a description
   alone.

   ```bash
   cd backend && python -m pytest scanner/tests/test_pipeline.py::test_name -x -q
   ```

2. **Name the root cause in one sentence** before editing. If you cannot, keep investigating.

3. **Write a failing test first** if one does not exist yet, so the bug cannot come back.

4. **Make the smallest change** that turns it green. Do not rename, reformat, or restructure
   nearby code — that belongs in `refactor-pass`.

5. **Run the whole suite**, not just the one test:

   ```bash
   cd backend && python -m pytest scanner/tests -q
   ```

## Threshold bugs

When a matching test fails on a score boundary, adjust the weight or modifier in
`matching.py` — never the assertion. The thresholds encode product behaviour: a wrong-author
match landing at exactly 0.85 is a real bug, because 0.85 is the auto-accept line.

## Failure-path bugs

If a fallback did not trigger, check in order: does the exception actually reach the
`try`/`except` in `pipeline.py`; is a warning code appended to `metrics.warnings`; does the
item still reach `needs_review`; does the app map that warning to a message.

Commit as `fix(scope): ...` describing the cause, not the symptom.
