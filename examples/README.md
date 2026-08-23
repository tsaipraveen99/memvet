# MemVet examples

## ShopCart

`shopcart` is a small Python service used by the executable demo. It shows an unrelated edit staying active, a symbol move becoming `needs_revalidation`, and recorded tests verifying the new state.

Run it from the repository root:

```bash
python scripts/demo_shopcart.py
./demo.sh --fast
```

## Team adoption

1. Install MemVet in the repository with `python -m pip install -e .`.
2. Run `memvet init` and record decisions with `memvet remember`.
3. Add `.github/workflows/memvet-audit.yml` or call the reusable workflow from `docs/ci.md`.
4. Commit `.memvet/memories.json` and review the generated PR comment.
