import json
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from memvet.cli import handle_check, handle_context, handle_remember, handle_verify, ledger_path


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")
    (repo / "service.py").write_text("def validate():\n    return True\n")
    run_git(repo, "add", "service.py")
    run_git(repo, "commit", "-qm", "initial")
    return repo


class CliTests(unittest.TestCase):
    def test_remember_and_verify_update_ledger_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                ["validate"],
                [],
            )

            payload = json.loads(ledger_path(repo).read_text())
            self.assertEqual(payload["memories"][0]["status"], "active")
            self.assertIn("Status: `active`", (repo / "memory.md").read_text())

            handle_verify(repo, "decision-1")

            payload = json.loads(ledger_path(repo).read_text())
            self.assertEqual(payload["memories"][0]["status"], "verified")
            self.assertIn("Status: `verified`", (repo / "memory.md").read_text())

    def test_changed_only_check_preserves_full_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                [],
            )
            base = run_git(repo, "rev-parse", "HEAD")
            (repo / "service.py").write_text("def validate():\n    return False\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "change validation")

            result = handle_check(repo, True, base, True)

            self.assertEqual(result, 1)
            self.assertIn("Validation boundary", (repo / "memory.md").read_text())

    def test_context_exports_only_fresh_memories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                [],
            )
            output = io.StringIO()
            with redirect_stdout(output):
                result = handle_context(repo, ["service.py"], True)

            self.assertEqual(result, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload[0]["id"], "decision-1")


if __name__ == "__main__":
    unittest.main()
