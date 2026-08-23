from pathlib import Path
from typing import Any, TypedDict

from ..audit import AuditReport, audit_repository
from ..ledger import load_records
from ..providers import CodeContextProvider, CodeReference
from ..review import ReviewReport


class LangGraphError(RuntimeError):
    pass


class ReviewState(TypedDict, total=False):
    repo: str
    base: str
    greptile_provider: CodeContextProvider | None
    query: str | None
    limit: int
    audit: AuditReport
    external_findings: list[CodeReference]
    provider_errors: list[str]
    review: ReviewReport


def build_review_graph():
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as error:
        raise LangGraphError(
            "LangGraph orchestration requires the optional `langgraph` package"
        ) from error

    graph = StateGraph(ReviewState)
    graph.add_node("audit", _audit_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("synthesize", _synthesize_node)
    graph.add_edge(START, "audit")
    graph.add_edge("audit", "retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def run_langgraph_review(
    repo: Path,
    base: str,
    *,
    greptile_provider: CodeContextProvider | None = None,
    query: str | None = None,
    limit: int = 10,
) -> ReviewReport:
    graph = build_review_graph()
    state = graph.invoke(
        {
            "repo": str(repo),
            "base": base,
            "greptile_provider": greptile_provider,
            "query": query,
            "limit": limit,
        }
    )
    return state["review"]


def _audit_node(state: ReviewState) -> dict[str, Any]:
    repo = Path(state["repo"])
    records = load_records(repo / ".memvet" / "memories.json")
    return {"audit": audit_repository(repo, state["base"], records)}


def _retrieve_node(state: ReviewState) -> dict[str, Any]:
    provider = state.get("greptile_provider")
    if provider is None:
        return {"external_findings": [], "provider_errors": []}
    try:
        findings = list(
            provider.search(
                state.get("query")
                or "Review changed code for risks and downstream consumers",
                limit=state.get("limit", 10),
            )
        )
        return {"external_findings": findings, "provider_errors": []}
    except Exception as error:
        return {
            "external_findings": [],
            "provider_errors": [f"Greptile unavailable: {error}"],
        }


def _synthesize_node(state: ReviewState) -> dict[str, Any]:
    return {
        "review": ReviewReport(
            state["audit"],
            state.get("external_findings", []),
            state.get("provider_errors", []),
        )
    }
