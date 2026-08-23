import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.freshness import check_record
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


def create_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")
    (repo / "handlers.py").write_text(
        "def validate_order(order):\n"
        "    return order['id']\n\n"
        "def format_order(order):\n"
        "    return str(order)\n"
    )
    run_git(repo, "add", "handlers.py")
    run_git(repo, "commit", "-qm", "initial handlers")
    return repo, run_git(repo, "rev-parse", "HEAD")


def make_record(repo: Path, commit: str) -> MemoryRecord:
    return MemoryRecord(
        id="decision-1",
        title="Order validation",
        content="Validation stays at the order boundary.",
        introduced_commit=commit,
        files=["handlers.py"],
        symbols=["validate_order"],
        symbol_hashes=capture_symbol_hashes(
            repo,
            ["handlers.py"],
            ["validate_order"],
            commit,
        ),
    )


class SymbolFreshnessTests(unittest.TestCase):
    def test_unrelated_function_change_stays_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            (repo / "handlers.py").write_text(
                "def validate_order(order):\n"
                "    return order['id']\n\n"
                "def format_order(order):\n"
                "    return order['id']\n"
            )
            run_git(repo, "add", "handlers.py")
            run_git(repo, "commit", "-qm", "change formatter")

            result = check_record(repo, make_record(repo, commit))

            self.assertEqual(result.status, "active", result.reasons)
            self.assertEqual(
                result.reasons,
                ["tracked symbols are unchanged despite file changes"],
            )

    def test_symbol_body_change_needs_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            (repo / "handlers.py").write_text(
                "def validate_order(order):\n"
                "    return order['total']\n\n"
                "def format_order(order):\n"
                "    return str(order)\n"
            )
            run_git(repo, "add", "handlers.py")
            run_git(repo, "commit", "-qm", "change validation")

            result = check_record(repo, make_record(repo, commit))

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn("symbol body changed: validate_order", result.reasons)

    def test_symbol_move_needs_revalidation_instead_of_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            run_git(repo, "mv", "handlers.py", "validation.py")
            run_git(repo, "commit", "-qm", "move validation")

            result = check_record(repo, make_record(repo, commit))

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn(
                "symbol moved: validate_order from handlers.py to validation.py",
                result.reasons,
            )

    def test_missing_symbol_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            (repo / "handlers.py").write_text(
                "def format_order(order):\n    return str(order)\n"
            )
            run_git(repo, "add", "handlers.py")
            run_git(repo, "commit", "-qm", "remove validation")

            result = check_record(repo, make_record(repo, commit))

            self.assertEqual(result.status, "stale")
            self.assertIn("symbols missing at HEAD: validate_order", result.reasons)


if __name__ == "__main__":
    unittest.main()
