# MemVet

MemVet keeps engineering knowledge tied to the codebase.

AI coding agents can retrieve an old decision, workaround, or failed approach and treat it as current even after the repository has changed. MemVet binds memories to Git commits and tracked files, detects drift, and generates a human-readable `memory.md` view.

## Status

Early open-source prototype. The first release provides a local Git freshness checker. Claude-Mem, Supermemory, Greptile, Modal, and LangGraph adapters will build on this core without making them required dependencies.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
memvet init
memvet remember \
  --id decision-001 \
  --title "Keep coupon validation at the API boundary" \
  --content "Mobile clients do not validate coupons, so the API must remain authoritative." \
  --file src/api/discounts.py \
  --symbol validate_coupon \
  --test tests/test_expired_coupon.py
memvet check
```

Create `.memvet/memories.json` entries like:

```json
{
  "version": 1,
  "memories": [
    {
      "id": "decision-001",
      "title": "Keep coupon validation at the API boundary",
      "content": "Mobile clients do not validate coupons, so the API must remain authoritative.",
      "introduced_commit": "<commit-sha>",
      "files": ["src/api/discounts.py"],
      "symbols": ["validate_coupon"],
      "tests": ["tests/test_expired_coupon.py"],
      "status": "active"
    }
  ]
}
```

When a tracked file changes, `memvet check` reports `needs_revalidation`. It reports `stale` when the introduction commit or tracked file is no longer available. Existing records are preserved; MemVet does not silently rewrite history.

After reviewing the change and running the relevant tests, verify the memory at the current commit:

```bash
memvet verify decision-001
```

To make verification test-backed, record test paths with `--test` and run them before the memory is marked verified:

```bash
memvet verify decision-001 --run-tests
```

MemVet runs the recorded paths with Python `unittest`, stores the command and verification commit, and leaves the memory unverified when the tests fail.

`memory.md` is a generated projection. `.memvet/memories.json` remains the local source of truth, while Git provides the version boundary used for freshness checks.

For a pull request, limit the check to memories attached to files changed from the base branch:

```bash
memvet check --base origin/main --changed-only
```

For a PR-level evidence report with explicit actions:

```bash
memvet audit --base origin/main --json
```

See `docs/audit.md` for the report semantics and CI exit codes.

MemVet also includes a GitHub Actions workflow that publishes the audit in the job summary and fails the pull-request check when affected memory needs review. See `docs/ci.md` for setup.

To give a coding agent only fresh, relevant context, export memories for a file:

```bash
memvet context --file src/api/discounts.py --json
```

To search Claude-Mem without treating its historical results as verified current context:

```bash
memvet context --provider claude-mem --query "payment retry policy" --json
```

See `docs/claude-mem.md` for configuration.

Greptile can provide code references for a natural-language query:

```bash
memvet context \
  --provider greptile \
  --repository owner/repository \
  --branch main \
  --query "Where is payment retry behavior implemented?" \
  --json
```

See `docs/greptile.md` for credentials and indexing setup.

## Design principles

- Memory is historical evidence, not current truth.
- Git and test results are authoritative for freshness.
- Old decisions are preserved and explicitly superseded.
- Provider integrations are adapters, not hard dependencies.
- The default action is a warning or review artifact, not an automatic merge.

## Roadmap

- Add append-only memory events and generated memory updates.
- Add Claude-Mem and Supermemory adapters.
- Add LangGraph orchestration for retrieval and verification.
- Add optional Greptile context and Modal test verification.
- Add pull-request comments and reusable workflow support.
