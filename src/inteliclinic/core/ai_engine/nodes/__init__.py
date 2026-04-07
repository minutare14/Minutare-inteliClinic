"""LangGraph nodes for the clinic orchestration graph.

Each node is a pure async function (state: ClinicState) -> ClinicStateUpdate.
Nodes are registered in the graph builder and wired together via conditional edges.

Available nodes:
- reception     : Entry point — identifies patient, runs NLU extraction
- scheduling    : Handles appointment booking, cancellation, rescheduling
- insurance     : Answers insurance/convenio coverage queries via RAG
- financial     : Handles price, payment method, and billing queries
- glosa         : Detects billing anomalies (glosas) and returns risk scores
- supervisor    : Human-in-the-loop escalation gate
- fallback      : Safe conservative response when confidence is too low
- response      : Final LLM-backed response generation
"""
