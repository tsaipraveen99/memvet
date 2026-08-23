import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .git import run_git


@dataclass(frozen=True)
class SymbolDefinition:
    name: str
    qualified_name: str
    path: str
    line_start: int
    line_end: int
    body_hash: str


class SymbolIndex:
    def __init__(self, definitions: list[SymbolDefinition]) -> None:
        self.definitions = definitions

    def resolve(
        self,
        symbol: str,
        preferred_paths: list[str],
    ) -> SymbolDefinition | None:
        matches = [
            definition
            for definition in self.definitions
            if definition.name == symbol
            or definition.qualified_name == symbol
            or definition.qualified_name.endswith(f".{symbol}")
        ]
        preferred = [
            definition for definition in matches if definition.path in preferred_paths
        ]
        if len(preferred) == 1:
            return preferred[0]
        if len(matches) == 1:
            return matches[0]
        return None


def index_repository(repo: Path, commit: str = "HEAD") -> SymbolIndex:
    definitions: list[SymbolDefinition] = []
    paths = run_git(repo, "ls-tree", "-r", "--name-only", commit).splitlines()
    for path in paths:
        if not path.endswith(".py"):
            continue
        try:
            source = run_git(repo, "show", f"{commit}:{path}")
            tree = ast.parse(source, filename=path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        definitions.extend(_definitions_for_tree(tree, path, module))
    return SymbolIndex(definitions)


def capture_symbol_hashes(
    repo: Path,
    files: list[str],
    symbols: list[str],
    commit: str = "HEAD",
) -> dict[str, str]:
    index = index_repository(repo, commit)
    hashes: dict[str, str] = {}
    for symbol in symbols:
        definition = index.resolve(symbol, files)
        if definition:
            hashes[symbol] = definition.body_hash
    return hashes


def _definitions_for_tree(
    tree: ast.AST,
    path: str,
    module: str,
) -> list[SymbolDefinition]:
    definitions: list[SymbolDefinition] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._record(node)
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._record(node)
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def _record(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualified_name = ".".join([module, *self.scope, node.name])
            normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
            body_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            definitions.append(
                SymbolDefinition(
                    name=node.name,
                    qualified_name=qualified_name,
                    path=path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    body_hash=body_hash,
                )
            )

    Visitor().visit(tree)
    return definitions
