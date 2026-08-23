# Pull-request reviews

`memvet review` is the user-facing review surface. It combines the local freshness audit with optional external code context and emits Markdown or JSON.

```bash
memvet review --base origin/main
memvet review --base origin/main --json > web/review.json
```

Local memory findings are authoritative for MemVet’s status and exit code. A finding includes the memory ID, affected files, status, reasons, and recommended action:

- `usable`: the memory is active or verified;
- `revalidate`: the symbol body, location, or a non-symbol tracked file changed;
- `do_not_use`: the memory is stale or superseded.

Greptile is optional. When enabled, its code references are included as `external_unverified`; they help an agent investigate but never upgrade a memory to trusted status.

The GitHub Actions workflow writes this Markdown to the job summary and maintains one sticky pull-request comment. The static dashboard in `web/index.html` reads the same JSON report and needs no frontend dependencies.
