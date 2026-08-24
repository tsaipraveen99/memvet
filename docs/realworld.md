# Real-world validation

The repository includes a networked smoke harness for exercising MemVet against public projects rather than only synthetic fixtures:

```bash
python scripts/realworld_smoke.py
```

The default run uses Requests, Flask, and Black. For one project:

```bash
python scripts/realworld_smoke.py --project requests
```

For each project the harness clones a shallow copy, captures a real Python definition, commits an unrelated edit, and then commits a body edit. It expects the first change to remain `active` and the second to become `needs_revalidation`. The clones are temporary and no credentials are required.

## SessionStart context

Claude Code can inject fresh context before the first prompt with the project hook in `.claude/settings.json`. The hook prints the current branch, commit, and only fresh local memories. It does not call external providers or fail the session when a ledger is absent.

Claude Code documents that `SessionStart` command-hook stdout is added to the session context. Keep the hook fast and review the command before enabling it in a shared repository.
