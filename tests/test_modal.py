import unittest

from memvet.integrations.modal import modal_test_command


class ModalTests(unittest.TestCase):
    def test_modal_test_command_is_shell_safe(self) -> None:
        command = modal_test_command(["tests/test_orders.py", "tests/test space.py"])
        self.assertEqual(
            command,
            "python -m unittest tests/test_orders.py 'tests/test space.py'",
        )


if __name__ == "__main__":
    unittest.main()
