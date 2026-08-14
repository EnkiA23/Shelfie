#!/usr/bin/env bash
#
# Fail if anything that looks like a credential is tracked by git.
#
# gitleaks covers the general case, but this guard is deliberately small,
# dependency-free and specific to the two mistakes that would actually matter
# here: committing a .env, or pasting a provider key into a tracked file.
#
# Usage: ./scripts/check_no_secrets.sh

set -euo pipefail

status=0

fail() {
  echo "FAIL: $1" >&2
  status=1
}

# 1. No .env file may ever be tracked. .env.example is the documented template
#    and is expected to be present.
tracked_env=$(git ls-files | grep -E '(^|/)\.env$|(^|/)\.env\.[a-z]+$' | grep -v '\.env\.example$' || true)
if [ -n "$tracked_env" ]; then
  fail "environment file(s) are tracked by git:"$'\n'"$tracked_env"
fi

# 2. No provider key shapes in tracked content. Patterns match the prefixes used
#    by the three providers this project can talk to.
patterns=(
  'AIza[0-9A-Za-z_-]{35}'         # Google API key
  'sk-[A-Za-z0-9]{32,}'           # OpenAI
  'sk-ant-[A-Za-z0-9_-]{32,}'     # Anthropic
  'AQ\.[A-Za-z0-9_-]{40,}'        # Google short-lived / OAuth-style token
)

for pattern in "${patterns[@]}"; do
  # Exclude this script, which necessarily contains the patterns themselves.
  matches=$(git grep -nIE "$pattern" -- ':!scripts/check_no_secrets.sh' || true)
  if [ -n "$matches" ]; then
    fail "possible credential matching /$pattern/:"$'\n'"$matches"
  fi
done

# 3. The example env must ship with empty values, or it stops being an example.
if git ls-files --error-unmatch backend/.env.example >/dev/null 2>&1; then
  filled=$(grep -E '^(GEMINI|OPENAI|ANTHROPIC)_API_KEY=.+' backend/.env.example || true)
  if [ -n "$filled" ]; then
    fail "backend/.env.example has a non-empty API key:"$'\n'"$filled"
  fi
fi

if [ "$status" -eq 0 ]; then
  echo "OK: no tracked secrets found."
fi

exit "$status"
