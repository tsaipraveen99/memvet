import shlex
import subprocess
import sys
from pathlib import Path

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
    )
