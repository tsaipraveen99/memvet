# Test-backed verification

Attach test paths when recording a decision:

```bash
memvet remember \
  --title "Keep coupon validation at the API boundary" \
  --content "The API remains authoritative for all clients." \
  --file src/api/discounts.py \
  --test tests/test_expired_coupon.py
```

After a change triggers revalidation, run:

```bash
memvet verify decision-001 --run-tests
```

MemVet executes the recorded paths with Python `unittest`. A passing run records the test paths, command, current Git commit, provider, timeout, return code, and outcome, then marks the memory `verified`. A failing or timed-out run returns status `1` and does not update the ledger.

Use `--timeout` to change the default five-minute limit:

```bash
memvet verify decision-001 --run-tests --timeout 900
```

Use Modal as an optional remote verifier:

```bash
python -m pip install -e '.[modal]'
memvet verify decision-001 --run-tests --sandbox modal
```
