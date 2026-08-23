import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(repo: Path, *arguments: str, expected: int = 0) -> str:
    result = subprocess.run(
        list(arguments),
        cwd=repo,
        env=environment(),
        capture_output=True,
        text=True,
    )
    output = "\n".join(
        item for item in (result.stdout.strip(), result.stderr.strip()) if item
    )
    if output:
        print(output)
    if result.returncode != expected:
        raise SystemExit(
            f"command exited {result.returncode}, expected {expected}: {' '.join(arguments)}"
        )
    return output


def environment() -> dict[str, str]:
    environment = os.environ.copy()
    source_path = str(ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_path, environment.get("PYTHONPATH")) if item
    )
    return environment


def git(repo: Path, *arguments: str) -> str:
    return run(repo, "git", *arguments)


def memvet(repo: Path, *arguments: str, expected: int = 0) -> str:
    return run(repo, sys.executable, "-m", "memvet.cli", *arguments, expected=expected)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="memvet-shopcart-") as directory:
        repo = Path(directory) / "shopcart"
        shutil.copytree(ROOT / "examples" / "shopcart", repo)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "demo@example.com")
        git(repo, "config", "user.name", "MemVet Demo")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "initial ShopCart service")

        memvet(repo, "init", "--repo", str(repo))
        memvet(
            repo,
            "remember",
            "--repo",
            str(repo),
            "--id",
            "order-validation-001",
            "--title",
            "Validate orders at the service boundary",
            "--content",
            "The order service rejects non-positive totals before checkout.",
            "--file",
            "shop/handlers.py",
            "--symbol",
            "validate_order",
            "--test",
            "tests/test_orders.py",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "record validation decision")

        handlers = repo / "shop" / "handlers.py"
        handlers.write_text(
            handlers.read_text().replace(
                'return f"{order[\'id\']}"',
                'return f"{order[\'id\']}:{order[\'total\']}"',
            )
        )
        git(repo, "add", "shop/handlers.py")
        git(repo, "commit", "-qm", "format order output")
        unrelated = memvet(repo, "check", "--repo", str(repo))
        if "active" not in unrelated:
            raise SystemExit("unrelated edit did not remain active")

        git(repo, "mv", "shop/handlers.py", "shop/validation.py")
        (repo / "shop" / "handlers.py").write_text(
            "def format_order(order: dict) -> str:\n"
            "    return f\"{order['id']}:{order['total']}\"\n"
        )
        (repo / "shop" / "validation.py").write_text(
            "def validate_order(order: dict) -> bool:\n"
            "    if order['total'] <= 0:\n"
            "        raise ValueError('order total must be positive')\n"
            "    return True\n"
        )
        test_path = repo / "tests" / "test_orders.py"
        test_path.write_text(test_path.read_text().replace("shop.handlers", "shop.validation"))
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "move validation into its own module")
        moved = memvet(repo, "check", "--repo", str(repo), expected=1)
        if "symbol moved" not in moved:
            raise SystemExit("symbol move was not reported")

        memvet(
            repo,
            "verify",
            "order-validation-001",
            "--repo",
            str(repo),
            "--run-tests",
        )
        print("ShopCart demo complete: unrelated edit stayed active; moved symbol was verified by tests.")


if __name__ == "__main__":
    main()
