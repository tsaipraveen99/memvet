from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class MemoryHit:
    id: str
    title: str
    content: str
    source: str
    score: float | None = None


@dataclass(frozen=True)
class MemoryObservation:
    title: str
    content: str
    commit: str
    files: Sequence[str] = field(default_factory=tuple)
    symbols: Sequence[str] = field(default_factory=tuple)
    tests: Sequence[str] = field(default_factory=tuple)


class MemorySearchProvider(Protocol):
    def search(self, query: str, *, limit: int = 5) -> Sequence[MemoryHit]:
        ...


class MemoryRecorder(Protocol):
    def record(self, observation: MemoryObservation) -> None:
        ...


class MemoryProvider(MemorySearchProvider, MemoryRecorder, Protocol):
    pass


@dataclass(frozen=True)
class CodeReference:
    path: str
    symbol: str | None = None
    excerpt: str = ""
    source: str = ""
    line_start: int | None = None
    line_end: int | None = None


class CodeContextProvider(Protocol):
    def search(self, query: str, *, limit: int = 10) -> Sequence[CodeReference]:
        ...


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    command: str
    output: str = ""
    failures: Sequence[str] = field(default_factory=tuple)


class TestVerifier(Protocol):
    def run(self, tests: Sequence[str]) -> VerificationResult:
        ...
