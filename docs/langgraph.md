# LangGraph orchestration

The core CLI does not require LangGraph. Teams that already use LangGraph can route MemVet through an optional review graph:

```bash
python -m pip install -e '.[langgraph]'
memvet review \
  --base origin/main \
  --orchestrator langgraph \
  --json
```

The graph uses three deterministic nodes:

1. `audit` evaluates Git freshness and produces the normal `AuditReport`.
2. `retrieve` queries optional Greptile context and preserves provider failures as warnings.
3. `synthesize` emits the same `ReviewReport` used by direct CLI reviews and GitHub comments.

This keeps orchestration replaceable. LangGraph coordinates the workflow; it does not decide whether local memory is fresh.
