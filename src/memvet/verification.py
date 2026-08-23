import shlex
import subprocess
import sys
from pathlib import Path

from .git import current_commit
from .providers import VerificationResult


def run_recorded_tests(
    repo: Path,
    tests: list[str],
    timeout: float = 300.0,
) -> VerificationResult:
    arguments = [sys.executable, "-m", "unittest", *tests]
    command = shlex.join(arguments)
    try:
        result = subprocess.run(
            arguments,
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = "\n".join(
            item for item in (error.stdout, error.stderr) if item
        ).strip()
        return VerificationResult(
            passed=False,
            command=command,
            output=output,
            failures=(f"test command timed out after {timeout:g} seconds",),
            provider="local",
            evidence={
                "commit": current_commit(repo),
                "tests": list(tests),
                "timeout_seconds": timeout,
                "outcome": "timeout",
            },
        )

    output = "\n".join(
        item for item in (result.stdout, result.stderr) if item
    ).strip()
    failures = () if result.returncode == 0 else (
        f"test command exited with status {result.returncode}",
    )
    return VerificationResult(
        passed=result.returncode == 0,
        command=command,
        output=output,
        failures=failures,
        provider="local",
        evidence={
            "commit": current_commit(repo),
            "tests": list(tests),
            "timeout_seconds": timeout,
            "return_code": result.returncode,
            "outcome": "passed" if result.returncode == 0 else "failed",
        },
    )
