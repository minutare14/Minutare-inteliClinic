"""Graph builder with per-clinic configuration support.

Each clinic deploy can customize:
- Which nodes are enabled
- Confidence thresholds per node
- Timeout settings
- Interrupt points for human review

GraphConfig is loaded from clinic/config/ at startup (e.g., from a YAML or env vars)
and passed to build_graph_with_config() to produce a compiled graph tailored to
that clinic's specific requirements and compliance needs.

Example usage:
    from inteliclinic.core.ai_engine.langgraph.builder import GraphConfig, build_graph_with_config

    config = GraphConfig(
        confidence_threshold=0.70,
        supervisor_threshold=0.55,
        human_interrupt_nodes=["supervisor"],
        max_turns=15,
    )
    graph = build_graph_with_config(config)

    # Invoke for a single turn:
    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": conversation_id}},
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# All available node names in the clinic graph
_ALL_NODES = [
    "reception",
    "scheduling",
    "insurance",
    "financial",
    "glosa",
    "supervisor",
    "fallback",
    "response",
]


@dataclass
class GraphConfig:
    """Per-clinic graph configuration. Loaded from clinic/config/.

    Attributes:
        enabled_nodes:          List of node names active for this clinic.
                                Remove 'glosa' for patient-facing deploys.
        confidence_threshold:   Minimum NLU confidence to proceed to intent node.
                                Below this → routes to fallback.
        supervisor_threshold:   Minimum confidence to skip escalation in supervisor.
                                Below this → human handoff is triggered.
        human_interrupt_nodes:  Node names where the graph pauses for human review.
                                Typically ["supervisor"] for HITL deploys.
        max_turns:              Maximum conversation turns before proactive escalation.
        timeout_seconds:        Per-node execution timeout (enforced by the runner).
        use_memory_saver:       Whether to attach MemorySaver for multi-turn persistence.
        llm_provider:           LLM provider for response generation ("openai"|"anthropic"|"gemini").
        llm_model:              Model identifier (e.g., "gpt-4o-mini", "claude-3-haiku-20240307").
        clinic_id:              Unique identifier for this clinic deploy (used in logging/tracing).
    """

    enabled_nodes: list[str] = field(
        default_factory=lambda: [
            "reception",
            "scheduling",
            "insurance",
            "financial",
            "supervisor",
            "fallback",
            "response",
        ]
    )
    confidence_threshold: float = 0.65
    supervisor_threshold: float = 0.50
    human_interrupt_nodes: list[str] = field(default_factory=list)
    max_turns: int = 20
    timeout_seconds: int = 30
    use_memory_saver: bool = True
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    clinic_id: str = "default"

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        # Ensure required nodes are always present
        required = {"reception", "supervisor", "fallback", "response"}
        missing = required - set(self.enabled_nodes)
        if missing:
            raise ValueError(
                f"GraphConfig.enabled_nodes is missing required nodes: {missing}. "
                "These nodes cannot be disabled as they form the safety backbone of the graph."
            )

        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, got {self.confidence_threshold}"
            )
        if not 0.0 <= self.supervisor_threshold <= 1.0:
            raise ValueError(
                f"supervisor_threshold must be between 0.0 and 1.0, got {self.supervisor_threshold}"
            )
        if self.supervisor_threshold > self.confidence_threshold:
            logger.warning(
                "GraphConfig: supervisor_threshold (%.2f) > confidence_threshold (%.2f). "
                "This means the supervisor will escalate messages that the routing threshold already accepted. "
                "Consider setting supervisor_threshold <= confidence_threshold.",
                self.supervisor_threshold,
                self.confidence_threshold,
            )
        if self.max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {self.max_turns}")
        if self.timeout_seconds < 1:
            raise ValueError(f"timeout_seconds must be >= 1, got {self.timeout_seconds}")

        # Validate interrupt node names
        invalid_interrupts = set(self.human_interrupt_nodes) - set(_ALL_NODES)
        if invalid_interrupts:
            raise ValueError(
                f"human_interrupt_nodes contains unknown node names: {invalid_interrupts}. "
                f"Valid nodes: {_ALL_NODES}"
            )

    def to_graph_config_dict(self) -> dict[str, Any]:
        """Serialize to a dict for injection into ClinicState.context['_graph_config'].

        Nodes read this at runtime to apply per-clinic thresholds without
        requiring graph recompilation.
        """
        return {
            "confidence_threshold": self.confidence_threshold,
            "supervisor_threshold": self.supervisor_threshold,
            "max_turns": self.max_turns,
            "timeout_seconds": self.timeout_seconds,
            "clinic_id": self.clinic_id,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphConfig:
        """Construct a GraphConfig from a raw dictionary (e.g., loaded from YAML).

        Unknown keys are silently ignored to allow forward compatibility.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def for_patient_interface(cls, clinic_id: str = "default") -> GraphConfig:
        """Pre-configured profile for patient-facing clinic interfaces.

        Disables the internal 'glosa' node, sets conservative thresholds,
        and enables the supervisor interrupt for human review.
        """
        return cls(
            enabled_nodes=["reception", "scheduling", "insurance", "financial", "supervisor", "fallback", "response"],
            confidence_threshold=0.65,
            supervisor_threshold=0.50,
            human_interrupt_nodes=["supervisor"],
            max_turns=20,
            clinic_id=clinic_id,
        )

    @classmethod
    def for_internal_billing(cls, clinic_id: str = "default") -> GraphConfig:
        """Pre-configured profile for internal billing/glosa review workflows.

        Enables the 'glosa' node and lowers thresholds since users are staff
        with domain knowledge.
        """
        return cls(
            enabled_nodes=_ALL_NODES,
            confidence_threshold=0.50,
            supervisor_threshold=0.30,
            human_interrupt_nodes=[],
            max_turns=10,
            clinic_id=clinic_id,
        )


def build_graph_with_config(config: GraphConfig) -> Any:
    """Build and compile the clinic graph with the given per-clinic configuration.

    This is the primary entry point for clinic-specific deployments. It delegates
    to the main graph builder and applies the GraphConfig settings.

    Args:
        config: GraphConfig instance defining node selection, thresholds, and options.

    Returns:
        A compiled LangGraph StateGraph (CompiledStateGraph) ready for async invocation.

    Example:
        graph = build_graph_with_config(GraphConfig.for_patient_interface("clinica-abc"))
        state = make_initial_state(conversation_id="thread-123", patient_id="pat-456")

        result = await graph.ainvoke(
            {**state, "context": {"_graph_config": config.to_graph_config_dict()}},
            config={"configurable": {"thread_id": "thread-123"}},
        )
    """
    from inteliclinic.core.ai_engine.graphs.main_graph import build_clinic_graph

    logger.info(
        "build_graph_with_config: clinic_id=%s | nodes=%s | confidence=%.2f | supervisor=%.2f | "
        "interrupt=%s | memory=%s",
        config.clinic_id,
        config.enabled_nodes,
        config.confidence_threshold,
        config.supervisor_threshold,
        config.human_interrupt_nodes,
        config.use_memory_saver,
    )

    graph_build_config = {
        "interrupt_before_supervisor": "supervisor" in config.human_interrupt_nodes,
        "use_memory_saver": config.use_memory_saver,
        "enabled_nodes": config.enabled_nodes,
    }

    return build_clinic_graph(config=graph_build_config)


def get_default_graph() -> Any:
    """Return the default clinic graph with standard configuration.

    Convenience function for quick-start usage and testing.
    The graph uses patient-facing defaults: glosa disabled, supervisor interrupt enabled.
    """
    return build_graph_with_config(GraphConfig.for_patient_interface())
