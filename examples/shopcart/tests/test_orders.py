import unittest

from shop.handlers import validate_order


class OrderValidationTests(unittest.TestCase):
    def test_positive_order_is_valid(self) -> None:
        self.assertTrue(validate_order({"id": "order-1", "total": 25}))

    def test_zero_total_is_invalid(self) -> None:
        with self.assertRaises(ValueError):
            validate_order({"id": "order-2", "total": 0})


if __name__ == "__main__":
    unittest.main()
