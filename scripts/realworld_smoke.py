import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Project:
    name: str
    url: str


DEFAULT_PROJECTS = (
    Project("requests", "https://github.com/psf/requests.git"),
    Project("flask", "https://github.com/pallets/flask.git"),
    Project("black", "https://github.com/psf/black.git"),
)


def run(command: list[str], cwd: Path, *, expected: int = 0) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != expected:
        detail = "\n".join(item for item in (result.stdout, result.stderr) if item)
        raise RuntimeError(
            f"{' '.join(command)} exited {result.returncode}, expected {expected}\n{detail}"
        )
    return result.stdout.strip()


def environment() -> dict[str, str]:
    values = os.environ.copy()
    values["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(ROOT / "src"), values.get("PYTHONPATH")) if item
    )
    return values


def git(repo: Path, *arguments: str) -> str:
    return run(["git", *arguments], repo)


def memvet(repo: Path, *arguments: str, expected: int = 0) -> str:
    return run([sys.executable, "-m", "memvet.cli", *arguments], repo, expected=expected)


def choose_definition(repo: Path):
    from memvet.symbols import index_repository

    definitions = index_repository(repo).definitions
    candidates = [
        definition
        for definition in definitions
        if definition.path.endswith(".py")
        and definition.line_end > definition.line_start
        and "/__" not in definition.path
    ]
    if not candidates:
        raise RuntimeError("repository has no multiline Python definition to exercise")
    return sorted(candidates, key=lambda item: (item.path, item.line_start))[0]


def add_body_change(repo: Path, definition) -> None:
    path = repo / definition.path
    lines = path.read_text().splitlines(keepends=True)
    body_start = definition.line_start
    body_end = definition.line_end
    body_indent = None
    for line in lines[body_start:body_end]:
        stripped = line.lstrip()
        if stripped and not stripped.startswith(("@", "def ", "async def ")):
            body_indent = line[: len(line) - len(stripped)]
            break
    if body_indent is None:
        raise RuntimeError(f"could not determine body indentation for {definition.path}")
    lines.insert(body_end - 1, f"{body_indent}pass  # MemVet real-world smoke change\n")
    path.write_text("".join(lines))


def exercise(project: Project, destination: Path) -> dict:
    repo = destination / project.name
    run(["git", "clone", "--depth", "1", project.url, str(repo)], destination)
    git(repo, "config", "user.email", "memvet-smoke@example.com")
    git(repo, "config", "user.name", "MemVet Smoke")
    definition = choose_definition(repo)
    base = git(repo, "rev-parse", "HEAD")
    memvet(repo, "init", "--repo", str(repo))
    memvet(
        repo,
        "remember",
        "--repo",
        str(repo),
        "--id",
        f"{project.name}-realworld",
        "--title",
        f"Real-world symbol: {definition.qualified_name}",
        "--content",
        "MemVet captured this definition from a public repository.",
        "--file",
        definition.path,
        "--symbol",
        definition.qualified_name,
    )
    path = repo / definition.path
    path.write_text(
        path.read_text()
        + "\n\ndef memvet_unrelated_smoke_function():\n"
        + "    return None\n"
    )
    git(repo, "add", definition.path)
    git(repo, "commit", "-qm", "unrelated smoke edit")
    active = json.loads(
        memvet(repo, "check", "--repo", str(repo), "--json")
    )[0]
    if active["status"] != "active":
        from memvet.ledger import load_records
        from memvet.symbols import index_repository

        record = load_records(repo / ".memvet" / "memories.json")[0]
        resolved = index_repository(repo).resolve(record.symbols[0], record.files)
        raise RuntimeError(
            f"unrelated edit was not active: {active}; "
            f"baseline={record.symbol_hashes.get(record.symbols[0])}; "
            f"current={resolved.body_hash if resolved else None}"
        )

    add_body_change(repo, definition)
    git(repo, "add", definition.path)
    git(repo, "commit", "-qm", "body smoke edit")
    changed = json.loads(
        memvet(repo, "check", "--repo", str(repo), "--json", expected=1),
    )[0]
    if changed["status"] != "needs_revalidation":
        raise RuntimeError(f"body edit was not revalidation: {changed}")
    return {
        "project": project.name,
        "base": base,
        "file": definition.path,
        "symbol": definition.qualified_name,
        "unrelated_status": active["status"],
        "body_change_status": changed["status"],
        "reasons": changed["reasons"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise MemVet on public repositories")
    parser.add_argument("--project", action="append", choices=[item.name for item in DEFAULT_PROJECTS])
    args = parser.parse_args()
    selected = args.project or [item.name for item in DEFAULT_PROJECTS]
    projects = [item for item in DEFAULT_PROJECTS if item.name in selected]
    with tempfile.TemporaryDirectory(prefix="memvet-realworld-") as directory:
        destination = Path(directory)
        results = [exercise(project, destination) for project in projects]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
