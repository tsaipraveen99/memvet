"""Install MemVet as a SessionStart hook for a coding agent.

`memvet context` already computes which recorded decisions still hold. Without a
hook nothing consumes that output, so an agent working in the repository never
sees it. Installing the hook means fresh memories reach the agent automatically
and stale ones never do.

The settings file belongs to the developer and may already carry hooks from
other tools, so every write here merges rather than replaces, and every MemVet
entry is tagged so it can be removed again without touching anything else.
"""

import json
from pathlib import Path

MARKER = "memvet-session-start"
HOOK_COMMAND = "memvet context"
EVENT = "SessionStart"


class HookError(RuntimeError):
    """Raised when the agent settings file cannot be read or written."""


def settings_path(repo: Path) -> Path:
    return repo / ".claude" / "settings.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as error:
        raise HookError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise HookError(f"{path} must contain a JSON object")
    return data


def _save(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _entries(settings: dict) -> list:
    hooks = settings.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        raise HookError("The 'hooks' key must be an object")
    entries = hooks.get(EVENT, [])
    if not isinstance(entries, list):
        raise HookError(f"The '{EVENT}' key must be a list")
    return entries


def _is_ours(entry) -> bool:
    return isinstance(entry, dict) and entry.get("memvet") == MARKER


def _new_entry(command: str) -> dict:
    # `memvet` is our own tag, not part of the agent hook schema. It is what
    # lets uninstall find this entry again without guessing at the command.
    return {
        "memvet": MARKER,
        "hooks": [{"type": "command", "command": command}],
    }


def install(repo: Path, command: str = HOOK_COMMAND) -> tuple[bool, Path]:
    """Add the SessionStart hook. Returns (changed, path).

    Existing settings and existing SessionStart entries are preserved. Running
    this twice is a no-op.
    """
    path = settings_path(repo)
    settings = _load(path)
    entries = _entries(settings)

    for entry in entries:
        if _is_ours(entry):
            return False, path

    entries = entries + [_new_entry(command)]
    hooks = dict(settings.get("hooks") or {})
    hooks[EVENT] = entries
    settings["hooks"] = hooks
    _save(path, settings)
    return True, path


def uninstall(repo: Path) -> tuple[bool, Path]:
    """Remove only MemVet's entry. Returns (changed, path)."""
    path = settings_path(repo)
    if not path.exists():
        return False, path
    settings = _load(path)
    entries = _entries(settings)
    remaining = [entry for entry in entries if not _is_ours(entry)]
    if len(remaining) == len(entries):
        return False, path

    hooks = dict(settings.get("hooks") or {})
    if remaining:
        hooks[EVENT] = remaining
    else:
        hooks.pop(EVENT, None)
    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)
    _save(path, settings)
    return True, path


def status(repo: Path) -> bool:
    """True when the MemVet hook is installed."""
    path = settings_path(repo)
    if not path.exists():
        return False
    return any(_is_ours(entry) for entry in _entries(_load(path)))
