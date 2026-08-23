from dataclasses import dataclass
from pathlib import Path

from .freshness import check_record
from .git import changed_paths, current_commit
from .models import MemoryRecord


@dataclass(frozen=True)
class AuditItem:
    id: str
    title: str
    status: str
    action: str
    files: list[str]
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "action": self.action,
            "files": self.files,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class AuditReport:
    base: str
    head: str
    changed_files: list[str]
    items: list[AuditItem]

    @property
    def requires_review(self) -> bool:
        return any(
            item.status in {"needs_revalidation", "stale", "superseded"}
            for item in self.items
        )

    def to_dict(self) -> dict:
        return {
            "base": self.base,
            "head": self.head,
            "changed_files": self.changed_files,
            "requires_review": self.requires_review,
            "items": [item.to_dict() for item in self.items],
        }


def audit_repository(
    repo: Path,
    base: str,
    records: list[MemoryRecord],
) -> AuditReport:
    changed = sorted(changed_paths(repo, base))
    changed_set = set(changed)
    items: list[AuditItem] = []
    for record in records:
        if not changed_set.intersection(record.files):
            continue
        result = check_record(repo, record)
        items.append(
            AuditItem(
                id=record.id,
                title=record.title,
                status=result.status,
                action=_action_for_status(result.status),
                files=sorted(changed_set.intersection(record.files)),
                reasons=result.reasons,
            )
        )
    return AuditReport(
        base=base,
        head=current_commit(repo),
        changed_files=changed,
        items=items,
    )


def _action_for_status(status: str) -> str:
    if status in {"active", "verified"}:
        return "usable"
    if status == "needs_revalidation":
        return "revalidate"
    return "do_not_use"
