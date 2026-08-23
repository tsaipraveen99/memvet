# ShopCart demo

This deliberately small order service demonstrates MemVet’s symbol-aware workflow. The important symbol is `validate_order` in `shop/handlers.py`; `format_order` is an unrelated function in the same file.

Run the complete scenario from the repository root:

```bash
python scripts/demo_shopcart.py
```

The script creates a temporary Git repository, records a decision, makes an unrelated edit that stays `active`, moves `validate_order` to another module, observes `needs_revalidation`, and verifies the refactor by running the recorded tests.
