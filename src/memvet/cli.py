import argparse
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .audit import AuditReport, audit_repository
from .events import append_event, events_path
from .evidence import EvidenceItem, collect_evidence
from .freshness import check_record
from .git import GitError, changed_paths, current_commit
from .integrations.claude_mem import ClaudeMemError, ClaudeMemSearchProvider
from .integrations.greptile import GreptileError, GreptileSearchProvider
from .integrations.modal import ModalError, run_modal_tests
from .ledger import load_records, render_markdown, save_records
from .models import MemoryRecord
from .review import review_repository
from .symbols import capture_symbol_hashes, index_repository
from .verification import run_recorded_tests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memvet")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--repo", type=Path, default=Path.cwd())

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--repo", type=Path, default=Path.cwd())
    check_parser.add_argument("--json", action="store_true", dest="as_json")
    check_parser.add_argument("--base", help="compare only changes from this Git ref")
    check_parser.add_argument(
        "--changed-only",
        action="store_true",
        help="check memories whose tracked files changed from --base",
    )

    audit_parser = subparsers.add_parser(
        "audit",
        help="audit memory safety for a pull-request diff",
    )
    audit_parser.add_argument("--repo", type=Path, default=Path.cwd())
    audit_parser.add_argument("--base", required=True)
    audit_parser.add_argument("--json", action="store_true", dest="as_json")

    review_parser = subparsers.add_parser(
        "review",
        help="build a human-readable pull-request memory review",
    )
    review_parser.add_argument("--repo", type=Path, default=Path.cwd())
    review_parser.add_argument("--base", required=True)
    review_parser.add_argument("--json", action="store_true", dest="as_json")
    review_parser.add_argument("--output", type=Path)
    review_parser.add_argument("--greptile", action="store_true")
    review_parser.add_argument("--query")
    review_parser.add_argument("--limit", type=int, default=10)
    review_parser.add_argument("--repository")
    review_parser.add_argument("--branch")
    review_parser.add_argument("--remote")
    review_parser.add_argument("--genius", action="store_true")

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--repo", type=Path, default=Path.cwd())

    remember_parser = subparsers.add_parser(
        "remember",
        help="record an engineering decision at the current Git commit",
    )
    remember_parser.add_argument("--repo", type=Path, default=Path.cwd())
    remember_parser.add_argument("--id")
    remember_parser.add_argument("--title", required=True)
    remember_parser.add_argument("--content", required=True)
    remember_parser.add_argument("--file", dest="files", action="append", default=[])
    remember_parser.add_argument("--symbol", dest="symbols", action="append", default=[])
    remember_parser.add_argument("--test", dest="tests", action="append", default=[])

    supersede_parser = subparsers.add_parser(
        "supersede",
        help="replace an existing engineering decision",
    )
    supersede_parser.add_argument("memory_id")
    supersede_parser.add_argument("--repo", type=Path, default=Path.cwd())
    supersede_parser.add_argument("--id")
    supersede_parser.add_argument("--title", required=True)
    supersede_parser.add_argument("--content", required=True)
    supersede_parser.add_argument("--file", dest="files", action="append", default=[])
    supersede_parser.add_argument("--symbol", dest="symbols", action="append", default=[])
    supersede_parser.add_argument("--test", dest="tests", action="append", default=[])

    verify_parser = subparsers.add_parser(
        "verify",
        help="mark a memory as verified at the current Git commit",
    )
    verify_parser.add_argument("memory_id")
    verify_parser.add_argument("--repo", type=Path, default=Path.cwd())
    verify_parser.add_argument("--run-tests", action="store_true")
    verify_parser.add_argument(
        "--sandbox",
        choices=("local", "modal"),
        default="local",
        help="run recorded tests locally or in an ephemeral Modal sandbox",
    )
    verify_parser.add_argument("--timeout", type=float, default=300.0)

    context_parser = subparsers.add_parser(
        "context",
        help="export fresh memories for an AI coding agent",
    )
    context_parser.add_argument("--repo", type=Path, default=Path.cwd())
    context_parser.add_argument("--file", dest="files", action="append", default=[])
    context_parser.add_argument("--json", action="store_true", dest="as_json")
    context_parser.add_argument(
        "--provider",
        choices=("local", "claude-mem", "greptile"),
        default="local",
    )
    context_parser.add_argument("--query")
    context_parser.add_argument("--limit", type=int, default=5)
    context_parser.add_argument("--repository")
    context_parser.add_argument("--branch")
    context_parser.add_argument("--remote")
    context_parser.add_argument("--genius", action="store_true")

    evidence_parser = subparsers.add_parser(
        "evidence",
        help="combine fresh local memory with optional provider evidence",
    )
    evidence_parser.add_argument("--repo", type=Path, default=Path.cwd())
    evidence_parser.add_argument("--file", dest="files", action="append", default=[])
    evidence_parser.add_argument("--query")
    evidence_parser.add_argument("--limit", type=int, default=5)
    evidence_parser.add_argument(
        "--source",
        choices=("local", "claude-mem", "greptile"),
        action="append",
        default=None,
    )
    evidence_parser.add_argument("--json", action="store_true", dest="as_json")
    evidence_parser.add_argument("--repository")
    evidence_parser.add_argument("--branch")
    evidence_parser.add_argument("--remote")
    evidence_parser.add_argument("--genius", action="store_true")

    index_parser = subparsers.add_parser(
        "greptile-index",
        help="submit a repository for Greptile indexing",
    )
    index_parser.add_argument("--repository", required=True)
    index_parser.add_argument("--branch", default="main")
    index_parser.add_argument("--remote", default="github")
    index_parser.add_argument("--reload", action="store_true")
    index_parser.add_argument("--notify", action="store_true")

    return parser


def ledger_path(repo: Path) -> Path:
    return repo / ".memvet" / "memories.json"


def handle_init(repo: Path) -> int:
    path = ledger_path(repo)
    if not path.exists():
        save_records(path, [])
    (repo / "memory.md").write_text(render_markdown(load_records(path)))
    events_path(repo).touch(exist_ok=True)
    print(f"Initialized {path}")
    return 0


def evaluated_records(repo: Path, records: list[MemoryRecord]):
    symbol_index = None
    if any(
        record.symbols and any(path.endswith(".py") for path in record.files)
        for record in records
    ):
        symbol_index = index_repository(repo)
    results = [check_record(repo, record, symbol_index) for record in records]
    evaluated = [replace(result.record, status=result.status) for result in results]
    return results, evaluated


def render_current_memory(repo: Path, records: list[MemoryRecord]) -> None:
    _, evaluated = evaluated_records(repo, records)
    (repo / "memory.md").write_text(render_markdown(evaluated))


def handle_remember(
    repo: Path,
    memory_id: str | None,
    title: str,
    content: str,
    files: list[str],
    symbols: list[str],
    tests: list[str],
) -> int:
    path = ledger_path(repo)
    records = load_records(path)
    record_id = memory_id or f"memory-{uuid4().hex[:12]}"
    if any(record.id == record_id for record in records):
        raise ValueError(f"memory ID already exists: {record_id}")
    record = MemoryRecord(
        id=record_id,
        title=title,
        content=content,
        introduced_commit=current_commit(repo),
        files=files,
        symbols=symbols,
        tests=tests,
        symbol_hashes=capture_symbol_hashes(repo, files, symbols) if symbols else {},
    )
    records.append(record)
    save_records(path, records)
    append_event(
        repo,
        "remembered",
        record.id,
        record.introduced_commit,
        title=record.title,
        files=record.files,
    )
    render_current_memory(repo, records)
    print(f"Recorded {record.id} at {record.introduced_commit}")
    return 0


def handle_check(
    repo: Path,
    as_json: bool,
    base: str | None = None,
    changed_only: bool = False,
) -> int:
    all_records = load_records(ledger_path(repo))
    records = all_records
    if changed_only:
        if not base:
            raise ValueError("--changed-only requires --base")
        affected_paths = changed_paths(repo, base)
        records = [
            record for record in records if affected_paths.intersection(record.files)
        ]
    results, evaluated = evaluated_records(repo, records)
    if changed_only:
        render_current_memory(repo, all_records)
    else:
        (repo / "memory.md").write_text(render_markdown(evaluated))
    if not records:
        print("No affected memories found." if changed_only else "No memories found.")
        return 0
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "id": result.record.id,
                        "title": result.record.title,
                        "status": result.status,
                        "reasons": result.reasons,
                    }
                    for result in results
                ],
                indent=2,
            )
        )
    else:
        print(f"HEAD: {current_commit(repo)}")
        for result in results:
            print(f"{result.status:18} {result.record.id}: {result.record.title}")
            for reason in result.reasons:
                print(f"  - {reason}")
    return 1 if any(result.status in {"stale", "needs_revalidation"} for result in results) else 0


def handle_audit(repo: Path, base: str, as_json: bool) -> int:
    records = load_records(ledger_path(repo))
    report = audit_repository(repo, base, records)
    render_current_memory(repo, records)
    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_audit_report(report)
    return 1 if report.requires_review else 0


def handle_review(
    repo: Path,
    base: str,
    as_json: bool,
    output: Path | None,
    greptile: bool,
    query: str | None,
    limit: int,
    repository: str | None,
    branch: str | None,
    remote: str | None,
    genius: bool,
) -> int:
    provider = None
    if greptile:
        config = GreptileSearchProvider().config
        if repository:
            config = replace(config, repository=repository)
        if branch:
            config = replace(config, branch=branch)
        if remote:
            config = replace(config, remote=remote)
        if genius:
            config = replace(config, genius=True)
        provider = GreptileSearchProvider(config)

    report = review_repository(
        repo,
        base,
        greptile_provider=provider,
        query=query,
        limit=limit,
    )
    rendered = (
        json.dumps(report.to_dict(), indent=2)
        if as_json
        else report.to_markdown()
    )
    if output:
        output = output if output.is_absolute() else repo / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n")
        print(f"Wrote {output}")
    else:
        print(rendered)
    return 1 if report.requires_review else 0


def _print_audit_report(report: AuditReport) -> None:
    print(f"Base: {report.base}")
    print(f"HEAD: {report.head}")
    print(f"Changed files: {len(report.changed_files)}")
    if not report.items:
        print("PASS: no tracked memories are affected by this diff")
        return
    for item in report.items:
        print(f"{item.action:12} {item.id}: {item.title} [{item.status}]")
        if item.files:
            print(f"  files: {', '.join(item.files)}")
        for reason in item.reasons:
            print(f"  - {reason}")
    if report.requires_review:
        print("REVIEW: affected memory requires verification before reuse")
    else:
        print("PASS: affected memories are currently usable")


def handle_render(repo: Path) -> int:
    path = ledger_path(repo)
    render_current_memory(repo, load_records(path))
    print(f"Rendered {repo / 'memory.md'}")
    return 0


def handle_verify(
    repo: Path,
    memory_id: str,
    run_tests: bool = False,
    timeout: float = 300.0,
    sandbox: str = "local",
) -> int:
    path = ledger_path(repo)
    records = load_records(path)
    record = next((item for item in records if item.id == memory_id), None)
    if record is None:
        raise ValueError(f"memory ID not found: {memory_id}")

    result = check_record(repo, record)
    if result.status == "stale":
        raise ValueError(f"cannot verify stale memory: {memory_id}")
    if result.status == "superseded":
        raise ValueError(f"cannot verify superseded memory: {memory_id}")

    verification = None
    if run_tests:
        if not record.tests:
            raise ValueError(f"memory has no recorded tests: {memory_id}")
        if sandbox == "modal":
            verification = run_modal_tests(repo, record.tests, timeout)
        else:
            verification = run_recorded_tests(repo, record.tests, timeout)
        if verification.output:
            print(verification.output)
        if not verification.passed:
            for failure in verification.failures:
                print(f"Verification blocked: {failure}")
            return 1

    record.status = "verified"
    record.verified_commit = current_commit(repo)
    if verification:
        record.verified_tests = list(record.tests)
        record.verification_command = verification.command
    else:
        record.verified_tests = []
        record.verification_command = None
    save_records(path, records)
    append_event(
        repo,
        "verified",
        record.id,
        record.verified_commit,
        tests=record.tests,
    )
    render_current_memory(repo, records)
    if verification:
        print(f"Verified {memory_id} with recorded tests at {record.verified_commit}")
    else:
        print(f"Verified {memory_id} at {record.verified_commit}")
    return 0


def handle_supersede(
    repo: Path,
    memory_id: str,
    new_memory_id: str | None,
    title: str,
    content: str,
    files: list[str],
    symbols: list[str],
    tests: list[str],
) -> int:
    path = ledger_path(repo)
    records = load_records(path)
    old_record = next((item for item in records if item.id == memory_id), None)
    if old_record is None:
        raise ValueError(f"memory ID not found: {memory_id}")
    if old_record.status == "superseded":
        raise ValueError(f"memory is already superseded: {memory_id}")

    record_id = new_memory_id or f"memory-{uuid4().hex[:12]}"
    if any(record.id == record_id for record in records):
        raise ValueError(f"memory ID already exists: {record_id}")

    commit = current_commit(repo)
    old_record.status = "superseded"
    new_record = MemoryRecord(
        id=record_id,
        title=title,
        content=content,
        introduced_commit=commit,
        files=files,
        symbols=symbols,
        tests=tests,
        supersedes=memory_id,
    )
    records.append(new_record)
    save_records(path, records)
    append_event(
        repo,
        "superseded",
        new_record.id,
        commit,
        supersedes=memory_id,
        title=new_record.title,
    )
    render_current_memory(repo, records)
    print(f"Superseded {memory_id} with {new_record.id} at {commit}")
    return 0


def handle_context(
    repo: Path,
    files: list[str],
    as_json: bool,
    provider: str = "local",
    query: str | None = None,
    limit: int = 5,
    repository: str | None = None,
    branch: str | None = None,
    remote: str | None = None,
    genius: bool = False,
) -> int:
    if provider == "claude-mem":
        search_query = query or " ".join(files)
        if not search_query:
            raise ValueError("Claude-Mem context requires --query or --file")
        hits = ClaudeMemSearchProvider().search(search_query, limit=limit)
        payload = [
            {
                "id": hit.id,
                "title": hit.title,
                "content": hit.content,
                "status": "external_unverified",
                "source": hit.source,
                "score": hit.score,
            }
            for hit in hits
        ]
        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            for item in payload:
                print(f"## {item['id']}: {item['title']}")
                print(f"Status: `{item['status']}`")
                print(f"Source: `{item['source']}`")
                print(f"\n{item['content']}\n")
        return 0

    if provider == "greptile":
        search_query = query or " ".join(files)
        if not search_query:
            raise ValueError("Greptile context requires --query or --file")
        config = GreptileSearchProvider().config
        if repository:
            config = replace(config, repository=repository)
        if branch:
            config = replace(config, branch=branch)
        if remote:
            config = replace(config, remote=remote)
        if genius:
            config = replace(config, genius=True)
        references = GreptileSearchProvider(config).search(search_query, limit=limit)
        payload = [
            {
                "path": reference.path,
                "line_start": reference.line_start,
                "line_end": reference.line_end,
                "excerpt": reference.excerpt,
                "status": "external_unverified",
                "source": reference.source,
            }
            for reference in references
        ]
        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            for item in payload:
                location = item["path"]
                if item["line_start"] is not None:
                    location += f":{item['line_start']}"
                    if item["line_end"] is not None:
                        location += f"-{item['line_end']}"
                print(f"## {location}")
                print(f"Status: `{item['status']}`")
                print(f"Source: `{item['source']}`")
                print(f"\n{item['excerpt']}\n")
        return 0

    records = load_records(ledger_path(repo))
    results, _ = evaluated_records(repo, records)
    fresh_results = [
        result
        for result in results
        if result.status in {"active", "verified"}
        and (not files or set(files).intersection(result.record.files))
    ]
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "id": result.record.id,
                        "title": result.record.title,
                        "content": result.record.content,
                        "status": result.status,
                        "files": result.record.files,
                        "symbols": result.record.symbols,
                        "tests": result.record.tests,
                    }
                    for result in fresh_results
                ],
                indent=2,
            )
        )
    else:
        for result in fresh_results:
            record = result.record
            print(f"## {record.id}: {record.title}")
            print(f"Status: `{result.status}`")
            if record.files:
                print(f"Files: {', '.join(record.files)}")
            if record.symbols:
                print(f"Symbols: {', '.join(record.symbols)}")
            print(f"\n{record.content}\n")
    return 0


def handle_evidence(
    repo: Path,
    files: list[str],
    query: str | None,
    limit: int,
    sources: list[str] | None,
    as_json: bool,
    repository: str | None,
    branch: str | None,
    remote: str | None,
    genius: bool,
) -> int:
    selected_sources = sources or ["local"]
    search_query = query or " ".join(files) or None
    claude_provider = (
        ClaudeMemSearchProvider() if "claude-mem" in selected_sources else None
    )
    greptile_provider = None
    if "greptile" in selected_sources:
        config = GreptileSearchProvider().config
        if repository:
            config = replace(config, repository=repository)
        if branch:
            config = replace(config, branch=branch)
        if remote:
            config = replace(config, remote=remote)
        if genius:
            config = replace(config, genius=True)
        greptile_provider = GreptileSearchProvider(config)

    evidence = collect_evidence(
        repo,
        load_records(ledger_path(repo)),
        files,
        search_query,
        selected_sources,
        limit=limit,
        claude_mem_provider=claude_provider,
        greptile_provider=greptile_provider,
    )
    if as_json:
        print(json.dumps([item.to_dict() for item in evidence], indent=2))
    else:
        _print_evidence(evidence)
    return 0


def _print_evidence(evidence: list[EvidenceItem]) -> None:
    if not evidence:
        print("No evidence found.")
        return
    for item in evidence:
        print(f"## {item.kind}: {item.title}")
        print(f"Trust: `{item.trust}`")
        print(f"Status: `{item.status}`")
        print(f"Source: `{item.source}`")
        if item.files:
            print(f"Files: {', '.join(item.files)}")
        if item.path_status:
            print(f"Local path: `{item.path_status}`")
        print(f"\n{item.content}\n")


def handle_greptile_index(
    repository: str,
    branch: str,
    remote: str,
    reload: bool,
    notify: bool,
) -> int:
    config = GreptileSearchProvider().config
    config = replace(config, repository=repository, branch=branch, remote=remote)
    result = GreptileSearchProvider(config).index_repository(
        reload=reload,
        notify=notify,
    )
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve() if hasattr(args, "repo") else Path.cwd()
    try:
        if args.command == "init":
            return handle_init(repo)
        if args.command == "check":
            return handle_check(repo, args.as_json, args.base, args.changed_only)
        if args.command == "audit":
            return handle_audit(repo, args.base, args.as_json)
        if args.command == "review":
            return handle_review(
                repo,
                args.base,
                args.as_json,
                args.output,
                args.greptile,
                args.query,
                args.limit,
                args.repository,
                args.branch,
                args.remote,
                args.genius,
            )
        if args.command == "render":
            return handle_render(repo)
        if args.command == "remember":
            return handle_remember(
                repo,
                args.id,
                args.title,
                args.content,
                args.files,
                args.symbols,
                args.tests,
            )
        if args.command == "supersede":
            return handle_supersede(
                repo,
                args.memory_id,
                args.id,
                args.title,
                args.content,
                args.files,
                args.symbols,
                args.tests,
            )
        if args.command == "context":
            return handle_context(
                repo,
                args.files,
                args.as_json,
                args.provider,
                args.query,
                args.limit,
                args.repository,
                args.branch,
                args.remote,
                args.genius,
            )
        if args.command == "evidence":
            return handle_evidence(
                repo,
                args.files,
                args.query,
                args.limit,
                args.source,
                args.as_json,
                args.repository,
                args.branch,
                args.remote,
                args.genius,
            )
        if args.command == "greptile-index":
            return handle_greptile_index(
                args.repository,
                args.branch,
                args.remote,
                args.reload,
                args.notify,
            )
        return handle_verify(
            repo,
            args.memory_id,
            args.run_tests,
            args.timeout,
            args.sandbox,
        )
    except (ClaudeMemError, GreptileError, GitError, ModalError, ValueError) as error:
        print(f"memvet: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
