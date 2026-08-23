# Memory events and supersession

MemVet keeps the current projection in `.memvet/memories.json` and appends lifecycle events to `.memvet/events.jsonl`. Commit both files when using the repository as a shared engineering record.

Record a new decision normally:

```bash
memvet remember \
  --id decision-001 \
  --title "Keep validation at the API boundary" \
  --content "The API remains authoritative for all clients." \
  --file src/api/discounts.py
```

When a decision changes, supersede it instead of editing its content:

```bash
memvet supersede decision-001 \
  --id decision-002 \
  --title "Validate coupons at the service boundary" \
  --content "The service owns validation after the client contract update." \
  --file src/api/discounts.py
```

The original record remains in the ledger with status `superseded`; the replacement points back to it through `supersedes`. MemVet appends `remembered`, `verified`, and `superseded` events without rewriting earlier events.
