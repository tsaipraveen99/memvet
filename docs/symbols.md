# Symbol-aware freshness

MemVet uses tracked files as a cheap Tier 0 pre-filter, then resolves Python symbols before changing a memory’s status.

- Unrelated edits in a tracked file leave a symbol-keyed memory `active`.
- A changed symbol body becomes `needs_revalidation`.
- A symbol found in another module becomes `needs_revalidation` with a `symbol moved` reason.
- A missing symbol becomes `stale`.

When a memory is recorded with `--symbol`, MemVet captures a normalized AST body hash in `symbol_hashes`. Older records without hashes remain supported but request revalidation when their tracked Python files change because there is no baseline for body comparison.

The current resolver supports Python definitions, including top-level functions, async functions, class methods, and qualified names. JavaScript and TypeScript files use the built-in adapter for functions, classes, and arrow-function declarations. Ambiguous or unsupported syntax retains the language-agnostic file-level fallback.
