#!/usr/bin/env bash
set -euo pipefail

input="$(cat || true)"
python_command="${PYTHON:-python3}"
repo="$($python_command -c 'import json,sys; data=json.loads(sys.stdin.read() or "{}"); print(data.get("cwd") or "")' <<<"$input" 2>/dev/null || true)"
repo="${repo:-$PWD}"

if [[ ! -d "$repo/.memvet" ]]; then
  printf 'MemVet: no .memvet ledger found in %s\n' "$repo"
  exit 0
fi

branch="$(git -C "$repo" branch --show-current 2>/dev/null || true)"
commit="$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || true)"
printf 'MemVet SessionStart: branch %s at %s\n' "${branch:-detached}" "${commit:-unknown}"

if [[ -f "$repo/src/memvet/cli.py" ]]; then
  context="$(PYTHONPATH="$repo/src${PYTHONPATH:+:$PYTHONPATH}" "$python_command" -m memvet.cli context --repo "$repo" --json 2>/dev/null || true)"
else
  context="$(memvet context --repo "$repo" --json 2>/dev/null || true)"
fi

if [[ -n "$context" && "$context" != "[]" ]]; then
  printf 'Fresh MemVet context:\n%s\n' "$context"
else
  printf 'No fresh MemVet context is available for this repository.\n'
fi
