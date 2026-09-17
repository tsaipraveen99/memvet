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
            (
                re.compile(
                    r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("
                ),
                "{",
            ),
            (
                re.compile(
                    r"(?m)^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)\b"
                ),
                "{",
            ),
            (
                re.compile(
                    r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^\n]*\)|[A-Za-z_$][\w$]*)\s*=>"
                ),
                "{",
            ),
            # Data modules export const objects and arrays rather than functions.
            # Without this pattern a file like content/site.ts has no symbols at
            # all, so every edit to it invalidates the memories that point there.
            (
                re.compile(
                    r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?=[{\[])"
                ),
                "{[",
            ),
        )
        for pattern, openers in patterns:
            for match in pattern.finditer(source):
                start = match.start()
                end = _definition_end(source, match.end(), openers)
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


_CLOSERS = {"{": "}", "[": "]"}

# After one of these, a slash opens a regular expression rather than dividing.
_REGEX_KEYWORDS = frozenset(
    {
        "return",
        "typeof",
        "instanceof",
        "in",
        "of",
        "new",
        "delete",
        "void",
        "case",
        "do",
        "else",
        "yield",
        "await",
        "throw",
    }
)


def _definition_end(source: str, start: int, openers: str = "{") -> int:
    """Return the index just past the end of a definition body.

    The scan has to understand comments, string literals and regular expression
    literals, because a brace or a quote inside any of them is not structure. A
    regex such as /[^\\s)"'<>,]*/ desynchronizes a naive brace counter and makes
    the body run to the end of the file, which then reports every unrelated edit
    in that file as a change to this symbol.
    """
    length = len(source)
    position = start
    previous = ""
    opener: str | None = None
    closer = ""
    depth = 0

    while position < length:
        character = source[position]
        following = source[position + 1] if position + 1 < length else ""

        if character == "/" and following == "/":
            newline = source.find("\n", position)
            position = length if newline == -1 else newline
            continue
        if character == "/" and following == "*":
            closing = source.find("*/", position + 2)
            position = length if closing == -1 else closing + 2
            continue
        if character in "'\"`":
            position = _string_end(source, position)
            previous = "x"
            continue
        if character == "/" and _regex_can_open(source, position, previous):
            position = _regex_end(source, position)
            previous = "x"
            continue

        if opener is None:
            if character in openers:
                opener = character
                closer = _CLOSERS[character]
                depth = 1
            elif character == ";":
                return position + 1
            elif character == "\n" and previous in {";", "", ","}:
                return position
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return position + 1

        if not character.isspace():
            previous = character
        position += 1

    return length


def _string_end(source: str, start: int) -> int:
    """Return the index just past a string or template literal opened at start."""
    quote = source[start]
    position = start + 1
    length = len(source)
    while position < length:
        character = source[position]
        if character == "\\":
            position += 2
            continue
        if quote == "`" and character == "$" and source[position : position + 2] == "${":
            # A template expression holds real code, braces included.
            position = _definition_end(source, position + 1, "{")
            continue
        if character == quote:
            return position + 1
        if quote != "`" and character == "\n":
            # An unterminated single-line string, most likely a parse we cannot
            # trust. Stop here rather than swallowing the rest of the file.
            return position
        position += 1
    return length


def _regex_end(source: str, start: int) -> int:
    """Return the index just past a regex literal opened at start."""
    position = start + 1
    length = len(source)
    in_character_class = False
    while position < length:
        character = source[position]
        if character == "\\":
            position += 2
            continue
        if character == "\n":
            return position
        if in_character_class:
            if character == "]":
                in_character_class = False
        elif character == "[":
            in_character_class = True
        elif character == "/":
            position += 1
            while position < length and source[position].isalpha():
                position += 1
            return position
        position += 1
    return length


def _regex_can_open(source: str, position: int, previous: str) -> bool:
    """Decide whether a slash starts a regex literal or divides two values."""
    if previous == "":
        return True
    if previous in "(,=:[!&|?{};+-*%^~<>":
        return True
    if previous.isalnum() or previous in "_$)]":
        # Could be division. It is only a regex when a keyword precedes it,
        # as in `return /ab+c/.test(value)`.
        word = re.search(r"([A-Za-z_$][\w$]*)\s*$", source[:position])
        return bool(word and word.group(1) in _REGEX_KEYWORDS)
    return False


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
