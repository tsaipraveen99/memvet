# Evidence bundles

`memvet evidence` exports one envelope for an agent that needs both current repository memory and optional external context.

Local evidence is filtered through Git freshness first:

```bash
memvet evidence --file src/api/discounts.py --json
```

Provider sources are opt-in and can be combined by repeating `--source`:

```bash
memvet evidence \
  --source local \
  --source claude-mem \
  --source greptile \
  --repository owner/repository \
  --query "Where is coupon validation implemented?" \
  --json
```

Every result includes a trust label:

- `fresh`: local MemVet memory is `active` or `verified` at the current Git state.
- `external_unverified`: Claude-Mem or Greptile supplied the result; MemVet does not treat it as current truth.

Greptile code references also include `path_status`, which is `present`, `missing`, or `not_provided` after checking the current commit. A present path confirms only that the reference exists locally; it does not promote the external result to trusted memory.

If a local memory needs revalidation or is stale, it is omitted from the fresh local evidence set. Use `memvet audit` to get the complete PR safety report and required action.
