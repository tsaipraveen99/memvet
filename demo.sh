#!/usr/bin/env bash
# MemVet demo. Builds a throwaway repo, then walks the three beats.
# Usage: ./demo.sh          step through with Enter
#        ./demo.sh --fast   run straight through, for recording
set -euo pipefail

MEMVET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
DEMO_DIR="${TMPDIR:-/tmp}/memvet-demo"
FAST="${1:-}"

say()  { printf "\n\033[1;36m%s\033[0m\n" "$1"; }
line() { printf "\033[2m%s\033[0m\n" "-------------------------------------------------------"; }
# `memvet check` exits non-zero when a memory is stale, which is what CI wants.
# The demo narrates that state rather than failing on it.
run()  { printf "\033[1;32m$ %s\033[0m\n" "$*"; eval "$@" || true; }
pause() { [ "$FAST" = "--fast" ] || { printf "\n\033[2m[enter]\033[0m"; read -r _; }; }

mv_() {
  PYTHONPATH="$MEMVET_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON" -m memvet.cli "$@"
}

rm -rf "$DEMO_DIR"; mkdir -p "$DEMO_DIR/api"; cd "$DEMO_DIR"
git init -q
git config user.email demo@example.com
git config user.name  demo

cat > api/handlers.py <<'PY'
def validate_order(payload):
    if not payload.get("items"):
        raise ValueError("empty order")
    return payload
PY
git add -A && git commit -qm "validation lives in the API layer"
BASE_COMMIT="$(git rev-parse HEAD)"

say "1. A decision is made, and recorded against the code that makes it true."
line
run mv_ remember \
  --title '"Validation belongs in the API layer"' \
  --content '"Order payload validation lives in api/handlers.py, not in services."' \
  --file api/handlers.py \
  --symbol api.handlers.validate_order
pause

say "   This is what a coding agent receives today."
line
run mv_ context
pause

say "2. Someone adds an unrelated endpoint to that same file."
line
cat >> api/handlers.py <<'PY'


def health():
    return "ok"
PY
git add -A && git commit -qm "add health endpoint"
run mv_ check
say "   The file changed. The decision did not. No false alarm."
pause

say "3. Three months later, validation moves into a shared service."
line
mkdir -p services
cat > services/validation.py <<'PY'
def validate_order(payload):
    if not payload.get("items"):
        raise ValueError("empty order")
    return payload
PY
cat > api/handlers.py <<'PY'
from services.validation import validate_order


def handle_order(payload):
    return validate_order(payload)


def health():
    return "ok"
PY
git add -A && git commit -qm "move validation into shared service"
run mv_ check
pause

say "   And this is what the agent receives now."
line
run mv_ context
say "   Nothing. Nobody told it the decision was outdated. The code did."
pause

say "4. The pull-request review explains why the old decision needs attention."
line
run mv_ review --base "$BASE_COMMIT"
pause

say "5. The decision really did change, so it gets superseded, not patched."
line
ID="$(python3 -c "import json,pathlib;print(json.loads(pathlib.Path('.memvet/memories.json').read_text())['memories'][0]['id'])")"
run mv_ supersede "$ID" \
  --title '"Validation belongs in the shared service"' \
  --content '"Order payload validation moved to services/validation.py and is called from the API layer."' \
  --file services/validation.py \
  --symbol services.validation.validate_order
pause

say "   The agent now receives the current truth. The old decision stays queryable."
line
run mv_ context
run mv_ check
line
printf "\n\033[1mMemory is retrieved everywhere. MemVet is the layer that checks it still holds.\033[0m\n\n"
