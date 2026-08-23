import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..providers import CodeContextProvider, CodeReference


class GreptileError(RuntimeError):
    pass


@dataclass(frozen=True)
class GreptileConfig:
    api_key: str | None = None
    github_token: str | None = None
    repository: str | None = None
    branch: str = "main"
    remote: str = "github"
    base_url: str = "https://api.greptile.com/v2"
    timeout: float = 30.0
    genius: bool = False

    @classmethod
    def from_environment(cls) -> "GreptileConfig":
        return cls(
            api_key=os.getenv("MEMVET_GREPTILE_API_KEY") or os.getenv("GREPTILE_API_KEY"),
            github_token=os.getenv("MEMVET_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN"),
            repository=os.getenv("MEMVET_GREPTILE_REPOSITORY"),
            branch=os.getenv("MEMVET_GREPTILE_BRANCH", "main"),
            remote=os.getenv("MEMVET_GREPTILE_REMOTE", "github"),
            base_url=os.getenv("MEMVET_GREPTILE_URL", "https://api.greptile.com/v2").rstrip("/"),
            timeout=float(os.getenv("MEMVET_GREPTILE_TIMEOUT", "30")),
            genius=os.getenv("MEMVET_GREPTILE_GENIUS", "false").lower() == "true",
        )


class GreptileSearchProvider(CodeContextProvider):
    def __init__(self, config: GreptileConfig | None = None) -> None:
        self.config = config or GreptileConfig.from_environment()

    def search(self, query: str, *, limit: int = 10) -> list[CodeReference]:
        if not self.config.repository:
            raise GreptileError("Greptile search requires a repository in owner/name format")
        self._require_credentials("search")

        payload = self._request(
            "POST",
            "/search",
            {
                "query": query,
                "repositories": [
                    {
                        "remote": self.config.remote,
                        "repository": self.config.repository,
                        "branch": self.config.branch,
                    }
                ],
                "genius": self.config.genius,
            },
        )
        return [self._to_reference(item) for item in self._items(payload)][:limit]

    def index_repository(self, *, reload: bool = False, notify: bool = False):
        if not self.config.repository:
            raise GreptileError("Greptile indexing requires a repository in owner/name format")
        self._require_credentials("indexing")
        payload = self._request(
            "POST",
            "/repositories",
            {
                "remote": self.config.remote,
                "repository": self.config.repository,
                "branch": self.config.branch,
                "reload": reload,
                "notify": notify,
            },
        )
        return payload

    def _require_credentials(self, operation: str) -> None:
        if not self.config.api_key:
            raise GreptileError(
                f"Greptile {operation} requires MEMVET_GREPTILE_API_KEY or GREPTILE_API_KEY"
            )
        if not self.config.github_token:
            raise GreptileError(
                f"Greptile {operation} requires MEMVET_GITHUB_TOKEN or GITHUB_TOKEN"
            )

    def _request(self, method: str, path: str, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.config.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "X-GitHub-Token": self.config.github_token or "",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise GreptileError(
                f"Greptile returned HTTP {error.code}: {detail or error.reason}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise GreptileError(f"Unable to reach Greptile: {error}") from error
        except json.JSONDecodeError as error:
            raise GreptileError("Greptile returned invalid JSON") from error

    @staticmethod
    def _items(payload) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            raise GreptileError("Greptile search response must be an object or array")
        for key in ("sources", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _to_reference(item: dict) -> CodeReference:
        path = str(item.get("filepath") or item.get("path") or "")
        source = ":".join(
            str(value)
            for value in (
                item.get("remote", "github"),
                item.get("repository", ""),
                item.get("branch", "main"),
            )
            if value
        )
        return CodeReference(
            path=path,
            excerpt=str(item.get("summary") or item.get("excerpt") or ""),
            source=f"greptile:{source}",
            line_start=_integer_or_none(item.get("linestart", item.get("line_start"))),
            line_end=_integer_or_none(item.get("lineend", item.get("line_end"))),
        )


def _integer_or_none(value) -> int | None:
    return int(value) if isinstance(value, int) else None
