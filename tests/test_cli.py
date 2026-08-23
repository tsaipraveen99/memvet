import json
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from memvet.cli import (
    handle_check,
    handle_context,
    handle_remember,
    handle_supersede,
    handle_verify,
    ledger_path,
)
from memvet.events import load_events


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
            self.assertIn("validate", payload["memories"][0]["symbol_hashes"])
            self.assertIn("Status: `active`", (repo / "memory.md").read_text())

            handle_verify(repo, "decision-1")

            payload = json.loads(ledger_path(repo).read_text())
            self.assertEqual(payload["memories"][0]["status"], "verified")
            self.assertIn("Status: `verified`", (repo / "memory.md").read_text())
            self.assertEqual(
                [event.event_type for event in load_events(repo)],
                ["remembered", "verified"],
            )

    def test_supersede_preserves_old_memory_and_appends_events(self) -> None:
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

            result = handle_supersede(
                repo,
                "decision-1",
                "decision-2",
                "Validation boundary v2",
                "Keep validation in the service layer after the policy update.",
                ["service.py"],
                [],
                [],
            )

            self.assertEqual(result, 0)
            payload = json.loads(ledger_path(repo).read_text())
            self.assertEqual(payload["memories"][0]["status"], "superseded")
            self.assertEqual(payload["memories"][1]["supersedes"], "decision-1")
            self.assertEqual(
                [event.event_type for event in load_events(repo)],
                ["remembered", "superseded"],
            )
            self.assertIn("Validation boundary v2", (repo / "memory.md").read_text())

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

    def test_verify_with_recorded_tests_persists_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_repo(Path(directory))
            (repo / "test_validation.py").write_text(
                "import unittest\n\n"
                "class ValidationTests(unittest.TestCase):\n"
                "    def test_boundary(self):\n"
                "        self.assertTrue(True)\n"
            )
            run_git(repo, "add", "test_validation.py")
            run_git(repo, "commit", "-qm", "add validation test")
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                ["test_validation.py"],
            )

            result = handle_verify(repo, "decision-1", run_tests=True)

            self.assertEqual(result, 0)
            payload = json.loads(ledger_path(repo).read_text())
            record = payload["memories"][0]
            self.assertEqual(record["status"], "verified")
            self.assertEqual(record["verified_tests"], ["test_validation.py"])
            self.assertEqual(record["verification_evidence"]["provider"], "local")
            self.assertEqual(record["verification_evidence"]["outcome"], "passed")
            self.assertEqual(
                record["verification_evidence"]["commit"],
                run_git(repo, "rev-parse", "HEAD"),
            )
            self.assertIn("Verification command:", (repo / "memory.md").read_text())
            self.assertIn("Verification evidence: `local` / `passed`", (repo / "memory.md").read_text())

    def test_failed_recorded_tests_do_not_verify_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_repo(Path(directory))
            (repo / "test_validation.py").write_text(
                "import unittest\n\n"
                "class ValidationTests(unittest.TestCase):\n"
                "    def test_boundary(self):\n"
                "        self.assertTrue(False)\n"
            )
            run_git(repo, "add", "test_validation.py")
            run_git(repo, "commit", "-qm", "add failing validation test")
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                ["test_validation.py"],
            )

            result = handle_verify(repo, "decision-1", run_tests=True)

            self.assertEqual(result, 1)
            payload = json.loads(ledger_path(repo).read_text())
            self.assertEqual(payload["memories"][0]["status"], "active")

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
