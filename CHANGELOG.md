# Changelog

## 0.2.1

Found by running MemVet against a real TypeScript repository for the first time.

- Fixed symbol slicing in the JavaScript and TypeScript adapter. Regular expression literals, line comments and block comments were scanned as ordinary code, so a quote or a brace inside any of them desynchronized the brace counter and ran a symbol body to the end of the file. Every later edit to that file then reported the tracked symbol as changed.
- Added symbol indexing for exported const objects and arrays, so data modules are tracked at symbol level instead of falling back to the whole file.
- Added `hash_version` to memory records. Improving an adapter changes every body hash, which previously surfaced as "symbol body changed" for code nobody had touched. Records written by an older version now have their baseline recomputed from the introduction commit and say so.
- `memvet context` now exports drifted decisions with an explicit warning rather than withholding them. An agent could not previously tell a constraint that had moved from one that never existed. `--only-fresh` restores the old behavior.

## 0.2.0

- Added JavaScript and TypeScript symbol adapters.
- Added provenance-rich evidence output for local, Claude-Mem, and Greptile sources.
- Added optional LangGraph orchestration for review flows.
- Added optional Modal-backed recorded test verification.
- Added a static landing page and review viewer at `web/index.html`.
- Added a real-world smoke harness and Claude Code `SessionStart` hook example.

## 0.1.0

- Added the local memory ledger, generated `memory.md`, freshness checks, PR review output, and Python symbol-aware validation.
