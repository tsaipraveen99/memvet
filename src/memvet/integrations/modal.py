import asyncio
import importlib
import os
import shlex
from pathlib import Path

from ..git import current_commit
from ..providers import VerificationResult


class ModalError(RuntimeError):
    pass


def modal_test_command(tests: list[str]) -> str:
    return shlex.join(["python", "-m", "unittest", *tests])


def run_modal_tests(
    repo: Path,
    tests: list[str],
    timeout: float = 300.0,
) -> VerificationResult:
    try:
        modal = importlib.import_module("modal")
    except ImportError as error:
        raise ModalError(
            "Modal verification requires the optional `modal` package"
        ) from error

    return asyncio.run(_run_modal_tests(modal, repo, tests, timeout))


async def _run_modal_tests(modal, repo: Path, tests: list[str], timeout: float):
    app_name = os.getenv("MEMVET_MODAL_APP", "memvet-review")
    app = modal.App.lookup(app_name, create_if_missing=True)
    image = modal.Image.debian_slim().add_local_dir(
        str(repo),
        remote_path="/workspace",
    )
    sandbox = None
    command = modal_test_command(tests)
    try:
        sandbox = await modal.Sandbox.create.aio(
            app=app,
            image=image,
            timeout=timeout,
        )
        process = await sandbox.exec.aio(
            "bash",
            "-lc",
            f"cd /workspace && PYTHONPATH=src {command}",
            timeout=timeout,
        )
        stdout = await process.stdout.read.aio()
        stderr = await process.stderr.read.aio()
        returncode = await process.wait.aio()
    except Exception as error:
        raise ModalError(f"Modal sandbox verification failed: {error}") from error
    finally:
        if sandbox is not None:
            await sandbox.terminate.aio()
            await sandbox.detach.aio()

    output = "\n".join(item for item in (stdout, stderr) if item).strip()
    failures = () if returncode == 0 else (
        f"Modal test command exited with status {returncode}",
    )
    return VerificationResult(
        passed=returncode == 0,
        command=f"modal sandbox: {command}",
        output=output,
        failures=failures,
        provider="modal",
        evidence={
            "commit": current_commit(repo),
            "tests": list(tests),
            "timeout_seconds": timeout,
            "return_code": returncode,
            "outcome": "passed" if returncode == 0 else "failed",
            "app": app_name,
            "image": "debian_slim",
        },
    )
