import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.evidence import collect_evidence
from memvet.models import MemoryRecord
from memvet.providers import CodeReference, MemoryHit


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class FakeMemoryProvider:
    def search(self, query: str, *, limit: int = 5):
        return [
            MemoryHit(
                id="obs-1",
                title="Validation history",
                content=f"Historical result for {query}",
                source="claude-mem:obs-1",
            )
        ][:limit]


class FakeCodeProvider:
    def search(self, query: str, *, limit: int = 10):
        return [
            CodeReference(
                path="service.py",
                excerpt=f"Code result for {query}",
                source="greptile:github:owner/repo:main",
                line_start=1,
                line_end=3,
            )
        ][:limit]


class EvidenceTests(unittest.TestCase):
    def test_combines_fresh_local_and_external_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            (repo / "service.py").write_text("def validate():\n    return True\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "initial")
            commit = run_git(repo, "rev-parse", "HEAD")
            records = [
                MemoryRecord(
                    id="decision-1",
                    title="Validation boundary",
                    content="Keep validation in the service layer.",
                    introduced_commit=commit,
                    files=["service.py"],
                )
            ]

            evidence = collect_evidence(
                repo,
                records,
                ["service.py"],
                "validation",
                ["local", "claude-mem", "greptile"],
                claude_mem_provider=FakeMemoryProvider(),
                greptile_provider=FakeCodeProvider(),
            )

            self.assertEqual(len(evidence), 3)
            self.assertEqual(evidence[0].trust, "fresh")
            self.assertEqual(evidence[1].trust, "external_unverified")
            self.assertEqual(evidence[2].path_status, "present")

    def test_changed_local_memory_is_not_exported_as_fresh_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            (repo / "service.py").write_text("def validate():\n    return True\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "initial")
            commit = run_git(repo, "rev-parse", "HEAD")
            (repo / "service.py").write_text("def validate():\n    return False\n")
            run_git(repo, "add", "service.py")
            run_git(repo, "commit", "-qm", "change validation")

            evidence = collect_evidence(
                repo,
                [
                    MemoryRecord(
                        id="decision-1",
                        title="Validation boundary",
                        content="Keep validation in the service layer.",
                        introduced_commit=commit,
                        files=["service.py"],
                    )
                ],
                ["service.py"],
                None,
                ["local"],
            )

            self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
