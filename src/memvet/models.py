from dataclasses import dataclass, field
from typing import Any


VALID_STATUSES = {"active", "verified", "needs_revalidation", "stale", "superseded"}


@dataclass
class MemoryRecord:
    id: str
    title: str
    content: str
    introduced_commit: str
    files: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    symbol_hashes: dict[str, str] = field(default_factory=dict)
    status: str = "active"
    verified_commit: str | None = None
    supersedes: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryRecord":
        record = cls(
            id=str(value["id"]),
            title=str(value["title"]),
            content=str(value["content"]),
            introduced_commit=str(value["introduced_commit"]),
            files=[str(item) for item in value.get("files", [])],
            symbols=[str(item) for item in value.get("symbols", [])],
            tests=[str(item) for item in value.get("tests", [])],
            symbol_hashes={
                str(key): str(item)
                for key, item in value.get("symbol_hashes", {}).items()
            },
            status=str(value.get("status", "active")),
            verified_commit=value.get("verified_commit"),
            supersedes=value.get("supersedes"),
        )
        if record.status not in VALID_STATUSES:
            raise ValueError(f"Unsupported memory status: {record.status}")
        return record

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "introduced_commit": self.introduced_commit,
            "files": self.files,
            "symbols": self.symbols,
            "tests": self.tests,
            "symbol_hashes": self.symbol_hashes,
            "status": self.status,
            "verified_commit": self.verified_commit,
            "supersedes": self.supersedes,
        }
