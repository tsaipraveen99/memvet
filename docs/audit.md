# Pull-request audits

`memvet audit` is the core MemVet workflow. It checks only memories whose tracked files appear in a pull-request diff, then reports whether that historical context is usable.

```bash
memvet audit --base origin/main
```

Machine-readable output is available for CI and PR bots:

```bash
memvet audit --base origin/main --json
```

Audit actions are:

- `usable`: the memory is active or verified.
- `revalidate`: related code changed since the memory was introduced; run `memvet verify <id> --run-tests` after reviewing it.
- `do_not_use`: the memory is stale or superseded.

The command exits `0` when all affected memories are usable and `1` otherwise. It does not rewrite the ledger; `memory.md` remains a generated projection.
