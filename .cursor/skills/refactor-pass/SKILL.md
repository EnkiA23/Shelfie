---
name: refactor-pass
description: Runs a behaviour-preserving cleanup of Shelfie after features work, tightening error handling, removing dead code and aligning naming across views and service modules. Use only after the pipeline and screens work end to end.
disable-model-invocation: true
---

# Refactor Pass

Run this **after** correctness, never blended into feature work, so the diff is reviewable as
"the refactor commit" rather than hidden inside a feature.

## Precondition

```bash
nx run backend:test
```

All green before you start. If anything fails, that is a `bugfix-pass`, not this.

## Rule: no behaviour changes

Same inputs, same outputs, same warning codes, same scores. If the test suite would need
editing, you have gone too far. The one exception is deleting a code path that nothing reaches.

## Checklist

- [ ] **Dead code** — unused imports, helpers nothing calls, leftover stub branches. Keep the
      `?stub=1` path: the app's "Demo without API" button depends on it.
- [ ] **Naming alignment** — the same concept has the same name in `views.py`, `pipeline.py`
      and the service modules. `crop`, `bbox`, `candidate`, `warning` are the established terms.
- [ ] **Error handling** — every `except` is narrow enough to be meaningful, and every caught
      failure appends a warning code rather than passing silently.
- [ ] **Layer leaks** — no scoring math or image processing in `views.py`, no Django
      request objects inside service modules.
- [ ] **Magic numbers** — thresholds and caps read from `settings`, not inline literals.
- [ ] **Comments** — delete comments that narrate the code. Keep only ones stating a constraint
      the code cannot show, such as why the author penalty is exactly −0.20.

## Verify and commit

```bash
nx run backend:test && python manage.py check
```

One commit, `refactor: ...`, covering the whole pass.
