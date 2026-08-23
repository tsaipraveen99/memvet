import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.cli import handle_remember
from memvet.review import review_repository
from memvet.providers import CodeReference


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class FakeGreptile:
    def search(self, query: str, *, limit: int = 10):
        return [
            CodeReference(
                path="service.py",
                line_start=1,
                line_end=2,
                excerpt="Validation implementation changed.",
                source="greptile:github:example/shop:main",
            )
        ]


class ReviewTests(unittest.TestCase):
    def test_markdown_contains_explainable_local_and_external_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            (repo / "service.py").write_text("def validate():\n    return True\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "initial")
            base = run_git(repo, "rev-parse", "HEAD")
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

            report = review_repository(
                repo,
                base,
                greptile_provider=FakeGreptile(),
            )

            self.assertTrue(report.requires_review)
            self.assertEqual(report.external_findings[0].path, "service.py")
            markdown = report.to_markdown()
            self.assertIn("REVIEW REQUIRED", markdown)
            self.assertIn("tracked files changed: service.py", markdown)
            self.assertIn("external_unverified", markdown)
            self.assertIn("Revalidate affected memories", markdown)


if __name__ == "__main__":
    unittest.main()
