import unittest
from unittest.mock import patch

from memvet.integrations.langgraph import LangGraphError, build_review_graph


class LangGraphTests(unittest.TestCase):
    def test_missing_optional_dependency_is_explained(self) -> None:
        with patch.dict("sys.modules", {"langgraph": None, "langgraph.graph": None}):
            with self.assertRaises(LangGraphError):
                build_review_graph()


if __name__ == "__main__":
    unittest.main()
