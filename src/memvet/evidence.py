from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .freshness import check_record
from .git import current_commit, file_exists_at
from .models import MemoryRecord
from .providers import CodeContextProvider, MemorySearchProvider


@dataclass(frozen=True)
class EvidenceItem:
    kind: str
    source: str
    trust: str
    status: str
    title: str
    content: str
    files: list[str]
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    path_status: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source": self.source,
            "trust": self.trust,
            "status": self.status,
            "title": self.title,
            "content": self.content,
            "files": self.files,
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "path_status": self.path_status,
        }


def collect_evidence(
    repo: Path,
    records: Sequence[MemoryRecord],
    files: Sequence[str],
    query: str | None,
    sources: Sequence[str],
    limit: int = 5,
    claude_mem_provider: MemorySearchProvider | None = None,
    greptile_provider: CodeContextProvider | None = None,
) -> list[EvidenceItem]:
    selected_files = set(files)
    evidence: list[EvidenceItem] = []
    for source in sources:
        if source == "local":
            evidence.extend(_local_evidence(repo, records, selected_files))
        elif source == "claude-mem":
            if not query:
                raise ValueError("Claude-Mem evidence requires --query or --file")
            if claude_mem_provider is None:
                raise ValueError("Claude-Mem provider is not configured")
            for hit in claude_mem_provider.search(query, limit=limit):
                evidence.append(
                    EvidenceItem(
                        kind="memory",
                        source=hit.source,
                        trust="external_unverified",
                        status="external_unverified",
                        title=hit.title,
                        content=hit.content,
                        files=[],
                    )
                )
        elif source == "greptile":
            if not query:
                raise ValueError("Greptile evidence requires --query or --file")
            if greptile_provider is None:
                raise ValueError("Greptile provider is not configured")
            head = current_commit(repo)
            for reference in greptile_provider.search(query, limit=limit):
                path_status = _path_status(repo, head, reference.path)
                evidence.append(
                    EvidenceItem(
                        kind="code_reference",
                        source=reference.source,
                        trust="external_unverified",
                        status="external_unverified",
                        title=reference.path or "Greptile reference",
                        content=reference.excerpt,
                        files=[reference.path] if reference.path else [],
                        path=reference.path or None,
                        line_start=reference.line_start,
                        line_end=reference.line_end,
                        path_status=path_status,
                    )
                )
        else:
            raise ValueError(f"Unsupported evidence source: {source}")
    return evidence


def _local_evidence(
    repo: Path,
    records: Sequence[MemoryRecord],
    selected_files: set[str],
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for record in records:
        if selected_files and not selected_files.intersection(record.files):
            continue
        result = check_record(repo, record)
        if result.status not in {"active", "verified"}:
            continue
        evidence.append(
            EvidenceItem(
                kind="memory",
                source="memvet:local",
                trust="fresh",
                status=result.status,
                title=record.title,
                content=record.content,
                files=record.files,
            )
        )
    return evidence


def _path_status(repo: Path, commit: str, path: str) -> str:
    if not path:
        return "not_provided"
    return "present" if file_exists_at(repo, commit, path) else "missing"
