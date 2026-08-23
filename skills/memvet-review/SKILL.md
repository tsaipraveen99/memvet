---
name: memvet-review
description: Use MemVet to retrieve and validate repository-bound engineering memory during coding and pull-request review.
---

# MemVet review

Use this skill when an agent is about to rely on an old engineering decision, investigate a changed area, or prepare a pull request.

1. Run `memvet evidence --file <path> --source local --json` before reusing local decisions.
2. Treat only `fresh` local evidence as current context. Treat `external_unverified` Claude-Mem or Greptile results as leads that still need local validation.
3. Before a pull request, run `memvet audit --base origin/<base> --json` and follow every `revalidate` or `do_not_use` action.
4. After reviewing the change, run `memvet verify <id> --run-tests` when the memory has recorded tests. Do not claim verification when the command fails.
5. When a decision changes, use `memvet supersede <old-id>` instead of editing or deleting the old decision.

Keep the generated `memory.md` projection and `.memvet/memories.json` source of truth in sync with the repository. Never promote provider output to trusted memory without a local Git and test-backed verification step.
