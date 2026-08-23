import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise GitError(message)
    return result.stdout.strip()


def current_commit(repo: Path) -> str:
    return run_git(repo, "rev-parse", "HEAD")


def commit_exists(repo: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def file_exists_at(repo: Path, commit: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{path}"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def changed_since(repo: Path, commit: str, path: str) -> bool:
    for diff_range in (f"{commit}..HEAD", "HEAD"):
        result = subprocess.run(
            ["git", "diff", "--quiet", diff_range, "--", path],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 1:
            return True
        if result.returncode != 0:
            raise GitError(result.stderr.strip() or f"Unable to inspect {path}")
    return False


def changed_paths(repo: Path, base: str) -> set[str]:
    output = run_git(repo, "diff", "--name-only", f"{base}..HEAD")
    return {path for path in output.splitlines() if path}
