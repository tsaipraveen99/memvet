def validate_order(order: dict) -> bool:
    if order["total"] <= 0:
        raise ValueError("order total must be positive")
    return True


def format_order(order: dict) -> str:
    return f"{order['id']}"
