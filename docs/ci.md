# CI integration

MemVet can run as a pull-request gate without provider credentials. Commit `.memvet/memories.json` to the project so the CI runner receives the memory ledger; `memory.md` can be committed as its generated human-readable view. The repository includes a workflow at `.github/workflows/memvet-audit.yml` that:

- checks out the complete Git history;
- installs MemVet from the repository;
- audits memories attached to files changed by the pull request;
- writes the report to the GitHub Actions job summary; and
- updates one sticky audit comment on the pull request;
- fails when an affected memory is stale, superseded, or needs revalidation.

For another repository, use the reusable workflow from a small caller workflow. The caller must grant `contents: read` and `pull-requests: write` so the audit comment can be published:

```yaml
name: MemVet audit

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  memvet:
    uses: tsaipraveen99/memvet/.github/workflows/memvet-audit.yml@main
```

The reusable workflow installs MemVet from its `memvet_ref` input (defaulting to `main`), preserves the audit exit code, and publishes its text output in both the job summary and a sticky pull-request comment. Comment publishing is best-effort; forked pull requests may not grant the workflow write permission, but the audit check still runs.

The audit exits with status `1` when an affected memory is `needs_revalidation`, `stale`, or `superseded`. It exits with status `0` when all affected memories are usable or when the pull request touches no tracked memory files.
