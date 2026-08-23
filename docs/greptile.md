# Greptile integration

Greptile supplies codebase references. MemVet keeps the trust boundary separate: Greptile results are labeled `external_unverified` until the returned paths are checked against the local Git state.

Configure credentials through the environment:

```bash
export MEMVET_GREPTILE_API_KEY="..."
export MEMVET_GITHUB_TOKEN="..."
export MEMVET_GREPTILE_REPOSITORY="owner/repository"
export MEMVET_GREPTILE_BRANCH="main"
```

Search the indexed repository:

```bash
memvet context \
  --provider greptile \
  --query "Where is payment retry behavior implemented?" \
  --json
```

You can override the repository at invocation time:

```bash
memvet context \
  --provider greptile \
  --repository owner/repository \
  --branch main \
  --query "Which callers depend on coupon validation?"
```

Greptile must index the repository before search requests can return useful references. Keep both tokens in a secret manager or local environment; never commit them to `.memvet`, source files, or CI logs.

Submit the repository for indexing from MemVet:

```bash
memvet greptile-index \
  --repository owner/repository \
  --branch main
```

Indexing is asynchronous. Wait for Greptile to report the repository ready before running context searches.
