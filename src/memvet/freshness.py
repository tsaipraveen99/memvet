from dataclasses import dataclass
from pathlib import Path

from .git import changed_since, commit_exists, current_commit, file_exists_at
from .models import MemoryRecord
from .symbols import SymbolIndex, index_repository


@dataclass
class FreshnessResult:
    record: MemoryRecord
    status: str
    reasons: list[str]


def check_record(
    repo: Path,
    record: MemoryRecord,
    symbol_index: SymbolIndex | None = None,
) -> FreshnessResult:
    head = current_commit(repo)

    if not commit_exists(repo, record.introduced_commit):
        return FreshnessResult(record, "stale", ["introduced commit is not available"])

    if record.status == "superseded":
        return FreshnessResult(
            record,
            "superseded",
            ["record was superseded by a newer decision"],
        )

    historical_missing_files = [
        path
        for path in record.files
        if not file_exists_at(repo, record.introduced_commit, path)
    ]
    changed_files = [
        path
        for path in record.files
        if changed_since(repo, record.introduced_commit, path)
    ]

    if historical_missing_files:
        return FreshnessResult(
            record,
            "stale",
            [
                "files were not present at the introduction commit: "
                f"{', '.join(historical_missing_files)}"
            ],
        )

    if not changed_files:
        status = "verified" if record.verified_commit == head else "active"
        return FreshnessResult(
            record,
            status,
            ["tracked files are unchanged since the introduction commit"],
        )

    if record.symbols and any(path.endswith(".py") for path in record.files):
        return _check_symbol_freshness(
            repo,
            record,
            head,
            changed_files,
            symbol_index,
        )

    current_missing_files = [
        path for path in record.files if not file_exists_at(repo, head, path)
    ]
    reasons = [f"tracked files changed: {', '.join(changed_files)}"]
    if current_missing_files:
        reasons.append(
            f"tracked files are missing at HEAD: {', '.join(current_missing_files)}"
        )
        return FreshnessResult(record, "stale", reasons)
    status = "verified" if record.verified_commit == head else "needs_revalidation"
    return FreshnessResult(record, status, reasons)


def _check_symbol_freshness(
    repo: Path,
    record: MemoryRecord,
    head: str,
    changed_files: list[str],
    symbol_index: SymbolIndex | None,
) -> FreshnessResult:
    index = symbol_index or index_repository(repo, head)
    baseline_index = index_repository(repo, record.introduced_commit)
    reasons: list[str] = []
    missing_symbols: list[str] = []
    baseline_missing: list[str] = []
    symbol_paths: set[str] = set()

    for symbol in record.symbols:
        baseline = baseline_index.resolve(symbol, record.files)
        if baseline:
            symbol_paths.add(baseline.path)
        current = index.resolve(symbol, record.files)
        if current:
            symbol_paths.add(current.path)

    fallback_changed_files = [
        path for path in changed_files if path not in symbol_paths
    ]
    fallback_missing_files = [
        path
        for path in record.files
        if path not in symbol_paths and not file_exists_at(repo, head, path)
    ]

    if fallback_changed_files:
        reasons.append(
            "non-symbol tracked files changed: "
            f"{', '.join(fallback_changed_files)}"
        )
    if fallback_missing_files:
        reasons.append(
            "non-symbol tracked files are missing at HEAD: "
            f"{', '.join(fallback_missing_files)}"
        )

    for symbol in record.symbols:
        definition = index.resolve(symbol, record.files)
        if definition is None:
            missing_symbols.append(symbol)
            continue
        if definition.path not in record.files:
            reasons.append(
                f"symbol moved: {symbol} from {', '.join(record.files)} to {definition.path}"
            )
        baseline = record.symbol_hashes.get(symbol)
        if baseline is None:
            baseline_missing.append(symbol)
        elif baseline != definition.body_hash:
            reasons.append(f"symbol body changed: {symbol}")

    if missing_symbols:
        reasons.append(f"symbols missing at HEAD: {', '.join(missing_symbols)}")
        return FreshnessResult(record, "stale", reasons)
    if fallback_missing_files:
        return FreshnessResult(record, "stale", reasons)
    if baseline_missing:
        reasons.append(
            "symbol body hashes unavailable: "
            f"{', '.join(baseline_missing)}"
        )
    if not reasons:
        reasons.append("tracked symbols are unchanged despite file changes")

    symbols_unchanged = reasons == [
        "tracked symbols are unchanged despite file changes"
    ]
    if symbols_unchanged:
        status = "verified" if record.verified_commit == head else "active"
    else:
        status = "needs_revalidation"
    return FreshnessResult(record, status, reasons)
