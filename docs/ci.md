# CI integration

MemVet can run as a pull-request gate without provider credentials. Commit `.memvet/memories.json` to the project so the CI runner receives the memory ledger; `memory.md` can be committed as its generated human-readable view. The repository includes a workflow at `.github/workflows/memvet-audit.yml` that:

- checks out the complete Git history;
- installs MemVet from the repository;
- audits memories attached to files changed by the pull request;
- writes the report to the GitHub Actions job summary; and
- updates one sticky audit comment on the pull request; and
- fails when an affected memory is stale, superseded, or needs revalidation.

Copy the workflow into a project that owns `.memvet/memories.json`, then change the install step to the published package or MemVet Git URL. The minimal workflow command is:

```yaml
- name: Install MemVet
  run: python -m pip install "git+https://github.com/tsaipraveen99/memvet.git"

- name: Audit engineering memory
  run: memvet audit --base origin/${{ github.base_ref }}
```

The full workflow preserves the audit exit code while publishing its text output in both the job summary and a sticky pull-request comment. Comment publishing is best-effort; forked pull requests may not grant the workflow write permission, but the audit check still runs.

The audit exits with status `1` when an affected memory is `needs_revalidation`, `stale`, or `superseded`. It exits with status `0` when all affected memories are usable or when the pull request touches no tracked memory files.
