from dataclasses import dataclass
from pathlib import Path

from .git import changed_since, commit_exists, current_commit, file_exists_at
from .models import MemoryRecord


@dataclass
class FreshnessResult:
    record: MemoryRecord
    status: str
    reasons: list[str]


def check_record(repo: Path, record: MemoryRecord) -> FreshnessResult:
    reasons: list[str] = []
    head = current_commit(repo)

    if not commit_exists(repo, record.introduced_commit):
        return FreshnessResult(record, "stale", ["introduced commit is not available"])

    if record.status == "superseded":
        return FreshnessResult(record, "superseded", ["record was superseded by a newer decision"])

    historical_missing_files = [
        path for path in record.files if not file_exists_at(repo, record.introduced_commit, path)
    ]
    current_missing_files = [path for path in record.files if not file_exists_at(repo, head, path)]
    if historical_missing_files:
        reasons.append(
            "files were not present at the introduction commit: "
            f"{', '.join(historical_missing_files)}"
        )
    if current_missing_files:
        reasons.append(f"tracked files are missing at HEAD: {', '.join(current_missing_files)}")

    changed_files = [
        path for path in record.files if changed_since(repo, record.introduced_commit, path)
    ]
    if changed_files:
        reasons.append(f"tracked files changed: {', '.join(changed_files)}")

    if historical_missing_files or current_missing_files:
        status = "stale"
    elif record.verified_commit == head:
        status = "verified"
    elif changed_files:
        status = "needs_revalidation"
    else:
        status = "active"

    if not reasons:
        reasons.append("tracked files are unchanged since the introduction commit")
    return FreshnessResult(record, status, reasons)
