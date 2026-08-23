import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.audit import audit_repository
from memvet.cli import handle_remember
from memvet.ledger import load_records, save_records


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
    (repo / "service.py").write_text("def validate():\n    return True\n")
    run_git(repo, "add", "service.py")
    run_git(repo, "commit", "-qm", "initial")
    return repo, run_git(repo, "rev-parse", "HEAD")


class AuditTests(unittest.TestCase):
    def test_audit_marks_changed_memory_for_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, base = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                [],
            )
            (repo / "service.py").write_text("def validate():\n    return False\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "change validation")

            report = audit_repository(repo, base, load_records(repo / ".memvet" / "memories.json"))

            self.assertTrue(report.requires_review)
            self.assertEqual(report.items[0].status, "needs_revalidation")
            self.assertEqual(report.items[0].action, "revalidate")
            self.assertEqual(report.items[0].files, ["service.py"])

    def test_unrelated_pull_request_passes_without_memory_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, base = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                [],
            )
            (repo / "README.md").write_text("Documentation update.\n")
            run_git(repo, "add", "README.md")
            run_git(repo, "commit", "-qm", "update docs")

            report = audit_repository(repo, base, load_records(repo / ".memvet" / "memories.json"))

            self.assertFalse(report.requires_review)
            self.assertEqual(report.items, [])

    def test_superseded_memory_cannot_pass_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, base = create_repo(Path(directory))
            handle_remember(
                repo,
                "decision-1",
                "Validation boundary",
                "Keep validation in the service layer.",
                ["service.py"],
                [],
                [],
            )
            records = load_records(repo / ".memvet" / "memories.json")
            records[0].status = "superseded"
            save_records(repo / ".memvet" / "memories.json", records)
            (repo / "service.py").write_text("def validate():\n    return False\n")
            run_git(repo, "add", "service.py", ".memvet/memories.json")
            run_git(repo, "commit", "-qm", "replace validation decision")

            report = audit_repository(
                repo,
                base,
                load_records(repo / ".memvet" / "memories.json"),
            )

            self.assertTrue(report.requires_review)
            self.assertEqual(report.items[0].action, "do_not_use")


if __name__ == "__main__":
    unittest.main()
