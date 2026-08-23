import tempfile
import unittest
import subprocess
from pathlib import Path

from memvet.freshness import check_record
from memvet.models import MemoryRecord


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


class FreshnessTests(unittest.TestCase):
    def make_record(self, commit: str) -> MemoryRecord:
        return MemoryRecord(
            id="decision-1",
            title="Validation boundary",
            content="Keep validation in the service layer.",
            introduced_commit=commit,
            files=["service.py"],
        )

    def test_unchanged_memory_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            result = check_record(repo, self.make_record(commit))

            self.assertEqual(result.status, "active")
            self.assertEqual(
                result.reasons,
                ["tracked files are unchanged since the introduction commit"],
            )

    def test_changed_memory_needs_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            (repo / "service.py").write_text("def validate():\n    return False\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "change validation")

            result = check_record(repo, self.make_record(commit))

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn("tracked files changed: service.py", result.reasons)

    def test_uncommitted_change_needs_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            (repo / "service.py").write_text("def validate():\n    return False\n")

            result = check_record(repo, self.make_record(commit))

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn("tracked files changed: service.py", result.reasons)

    def test_missing_tracked_file_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, commit = create_repo(Path(directory))
            run_git(repo, "rm", "-q", "service.py")
            run_git(repo, "commit", "-qm", "remove service")

            result = check_record(repo, self.make_record(commit))

            self.assertEqual(result.status, "stale")
            self.assertIn("tracked files are missing at HEAD: service.py", result.reasons)


if __name__ == "__main__":
    unittest.main()
