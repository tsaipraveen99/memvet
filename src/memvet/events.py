import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class MemoryEvent:
    event_type: str
    memory_id: str
    commit: str
    event_id: str = field(default_factory=lambda: f"event-{uuid4().hex[:12]}")
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "recorded_at": self.recorded_at,
            "event_type": self.event_type,
            "memory_id": self.memory_id,
            "commit": self.commit,
            "data": self.data,
        }


def events_path(repo: Path) -> Path:
    return repo / ".memvet" / "events.jsonl"


def append_event(
    repo: Path,
    event_type: str,
    memory_id: str,
    commit: str,
    **data: object,
) -> MemoryEvent:
    event = MemoryEvent(
        event_type=event_type,
        memory_id=memory_id,
        commit=commit,
        data=data,
    )
    path = events_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(event.to_dict()) + "\n")
    return event


def load_events(repo: Path) -> list[MemoryEvent]:
    path = events_path(repo)
    if not path.exists():
        return []
    events: list[MemoryEvent] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        events.append(
            MemoryEvent(
                event_id=str(value["event_id"]),
                recorded_at=str(value["recorded_at"]),
                event_type=str(value["event_type"]),
                memory_id=str(value["memory_id"]),
                commit=str(value["commit"]),
                data=dict(value.get("data", {})),
            )
        )
    return events
