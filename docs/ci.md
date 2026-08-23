# CI integration

MemVet can run as a pull-request gate without provider credentials. Install the package in the repository that owns `.memvet/memories.json`, fetch the base branch, and run:

```yaml
- name: Install MemVet
  run: python -m pip install memvet

- name: Check engineering memory
  run: memvet check --base origin/${{ github.base_ref }} --changed-only
```

Until MemVet is published to a package registry, replace the install step with an editable checkout or a Git URL for the project.

The check exits with status `1` when an affected memory is `needs_revalidation` or `stale`. It exits with status `0` when no affected memories need attention.
