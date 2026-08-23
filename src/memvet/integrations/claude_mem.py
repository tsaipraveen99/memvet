import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..providers import MemoryHit, MemorySearchProvider


class ClaudeMemError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaudeMemConfig:
    base_url: str = "http://127.0.0.1:37700"
    api_key: str | None = None
    search_path: str = "/api/search"
    project: str | None = None
    timeout: float = 5.0

    @classmethod
    def from_environment(cls) -> "ClaudeMemConfig":
        host = os.getenv("CLAUDE_MEM_WORKER_HOST", "127.0.0.1")
        port = os.getenv("CLAUDE_MEM_WORKER_PORT", "37700")
        base_url = os.getenv("MEMVET_CLAUDE_MEM_URL", f"http://{host}:{port}")
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=os.getenv("MEMVET_CLAUDE_MEM_API_KEY"),
            search_path=os.getenv("MEMVET_CLAUDE_MEM_SEARCH_PATH", "/api/search"),
            project=os.getenv("MEMVET_CLAUDE_MEM_PROJECT"),
            timeout=float(os.getenv("MEMVET_CLAUDE_MEM_TIMEOUT", "5")),
        )


class ClaudeMemSearchProvider(MemorySearchProvider):
    """Read-only adapter for a local Claude-Mem worker search endpoint."""

    def __init__(self, config: ClaudeMemConfig | None = None) -> None:
        self.config = config or ClaudeMemConfig.from_environment()

    def search(self, query: str, *, limit: int = 5) -> list[MemoryHit]:
        params = {"query": query, "limit": str(limit)}
        if self.config.project:
            params["project"] = self.config.project
        payload = self._get_json(f"{self.config.search_path}?{urlencode(params)}")
        return [self._to_hit(item) for item in self._items(payload)][:limit]

    def _get_json(self, path: str):
        request = Request(
            f"{self.config.base_url}{path}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise ClaudeMemError(
                f"Claude-Mem returned HTTP {error.code}: {detail or error.reason}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise ClaudeMemError(f"Unable to reach Claude-Mem: {error}") from error
        except json.JSONDecodeError as error:
            raise ClaudeMemError("Claude-Mem returned invalid JSON") from error

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    @staticmethod
    def _items(payload) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            raise ClaudeMemError("Claude-Mem search response must be an object or array")
        for key in ("results", "observations", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = value.get("results") or value.get("observations")
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
        return []

    @staticmethod
    def _to_hit(item: dict) -> MemoryHit:
        identifier = str(item.get("id", item.get("observation_id", "unknown")))
        title = str(item.get("title") or item.get("type") or f"Observation {identifier}")
        content = str(
            item.get("narrative")
            or item.get("content")
            or item.get("facts")
            or item.get("text")
            or ""
        )
        score = item.get("score")
        return MemoryHit(
            id=identifier,
            title=title,
            content=content,
            source=f"claude-mem:{identifier}",
            score=float(score) if isinstance(score, (int, float)) else None,
        )
