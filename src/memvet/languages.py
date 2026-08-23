import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from .symbols import SymbolDefinition


class LanguageAdapter(Protocol):
    name: str
    extensions: frozenset[str]

    def index_source(self, source: str, path: str) -> list[SymbolDefinition]:
        ...


def adapter_for_path(path: str) -> LanguageAdapter | None:
    suffix = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    if suffix in JavaScriptAdapter.extensions:
        return JavaScriptAdapter()
    return None


def supports_symbol_path(path: str) -> bool:
    return path.endswith(".py") or adapter_for_path(path) is not None


@dataclass(frozen=True)
class JavaScriptAdapter:
    name: str = "javascript"
    extensions: frozenset[str] = frozenset({".js", ".jsx", ".mjs", ".ts", ".tsx"})

    def index_source(self, source: str, path: str) -> list[SymbolDefinition]:
        module = _module_name(path)
        definitions: list[SymbolDefinition] = []
        patterns = (
            re.compile(
                r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("
            ),
            re.compile(
                r"(?m)^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)\b"
            ),
            re.compile(
                r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^\n]*\)|[A-Za-z_$][\w$]*)\s*=>"
            ),
        )
        for pattern in patterns:
            for match in pattern.finditer(source):
                start = match.start()
                end = _definition_end(source, match.end())
                body = source[start:end]
                line_start = source.count("\n", 0, start) + 1
                line_end = source.count("\n", 0, end) + 1
                name = match.group(1)
                definitions.append(
                    SymbolDefinition(
                        name=name,
                        qualified_name=f"{module}.{name}",
                        path=path,
                        line_start=line_start,
                        line_end=line_end,
                        body_hash=hashlib.sha256(
                            _normalize(body).encode("utf-8")
                        ).hexdigest(),
                    )
                )
        return _deduplicate(definitions)


def _module_name(path: str) -> str:
    module = re.sub(r"\.[^.]+$", "", path).replace("/", ".")
    if module.endswith(".index"):
        module = module[: -len(".index")]
    return module


def _definition_end(source: str, start: int) -> int:
    opening = source.find("{", start)
    if opening == -1:
        return source.find("\n", start) if "\n" in source[start:] else len(source)
    depth = 0
    quote: str | None = None
    escaped = False
    for position in range(opening, len(source)):
        character = source[position]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "'\"`":
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return position + 1
    return len(source)


def _normalize(source: str) -> str:
    return " ".join(source.split())


def _deduplicate(definitions: list[SymbolDefinition]) -> list[SymbolDefinition]:
    seen: set[tuple[str, int]] = set()
    unique: list[SymbolDefinition] = []
    for definition in definitions:
        key = (definition.qualified_name, definition.line_start)
        if key not in seen:
            seen.add(key)
            unique.append(definition)
    return unique
