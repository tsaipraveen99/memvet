# Claude-Mem integration

MemVet treats Claude-Mem as a historical retrieval source. Results returned by Claude-Mem are labeled `external_unverified`; MemVet does not promote them to current truth until they are attached to a Git commit and checked locally.

Install and start Claude-Mem using its official instructions, then query it through MemVet:

```bash
memvet context \
  --provider claude-mem \
  --query "why does the payment retry policy work this way" \
  --json
```

The adapter defaults to the local worker at `http://127.0.0.1:37700`. Configure it with environment variables when needed:

```bash
export MEMVET_CLAUDE_MEM_URL="http://127.0.0.1:37700"
export MEMVET_CLAUDE_MEM_API_KEY="..."
export MEMVET_CLAUDE_MEM_PROJECT="my-project"
```

`MEMVET_CLAUDE_MEM_API_KEY` is optional for a local worker and should be provided through a secret manager or environment, never committed to the repository.

The adapter is intentionally read-only in this first integration. MemVet owns Git binding and freshness; Claude-Mem owns historical observations and retrieval.
