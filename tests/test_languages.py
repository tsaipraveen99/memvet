import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.freshness import check_record
from memvet.languages import JavaScriptAdapter
from memvet.models import MemoryRecord
from memvet.symbols import capture_symbol_hashes


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class LanguageAdapterTests(unittest.TestCase):
    def test_javascript_adapter_indexes_function_and_arrow_definition(self) -> None:
        definitions = JavaScriptAdapter().index_source(
            "function validateOrder(order) { return order.total > 0; }\n"
            "const formatOrder = (order) => `${order.id}`;\n",
            "src/orders.js",
        )

        self.assertEqual(
            {definition.name for definition in definitions},
            {"validateOrder", "formatOrder"},
        )
        self.assertTrue(all(definition.body_hash for definition in definitions))

    def test_javascript_body_change_needs_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            source = repo / "orders.js"
            source.write_text("export function validateOrder(order) { return order.total > 0; }\n")
            run_git(repo, "add", "orders.js")
            run_git(repo, "commit", "-qm", "initial orders")
            commit = run_git(repo, "rev-parse", "HEAD")
            record = MemoryRecord(
                id="decision-1",
                title="Order validation",
                content="Orders need a positive total.",
                introduced_commit=commit,
                files=["orders.js"],
                symbols=["validateOrder"],
                symbol_hashes=capture_symbol_hashes(
                    repo,
                    ["orders.js"],
                    ["validateOrder"],
                    commit,
                ),
            )
            source.write_text("export function validateOrder(order) { return order.total >= 0; }\n")
            run_git(repo, "add", "orders.js")
            run_git(repo, "commit", "-qm", "change validation")

            result = check_record(repo, record)

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn("symbol body changed: validateOrder", result.reasons)


if __name__ == "__main__":
    unittest.main()
