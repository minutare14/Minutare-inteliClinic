"""
AI Engine Evaluation Runner — FULL PIPELINE v2

Executa o pipeline COMPLETO da IA e avalia cada caso.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.ai_engine.orchestrator import AIOrchestrator
from app.ai_engine.intent_router import Intent
from app.models.patient import Patient
from app.models.conversation import Conversation


# 50 PERGUNTAS COM COMPORTAMENTO ESPERADO
TEST_CASES = [
    # PROFISSIONAIS (8)
    {"id": 1, "category": "PROFISSIONAIS", "input": "quais médicos vocês têm?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra", "Profissionais"]}},
    {"id": 2, "category": "PROFISSIONAIS", "input": "quais profissionais a clínica tem?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 3, "category": "PROFISSIONAIS", "input": "quem trabalha aí?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 4, "category": "PROFISSIONAIS", "input": "me liste os médicos",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 5, "category": "PROFISSIONAIS", "input": "relação de profissionais",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 6, "category": "PROFISSIONAIS", "input": "já estão cadastrados",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 7, "category": "PROFISSIONAIS", "input": "a equipe da clínica",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 8, "category": "PROFISSIONAIS", "input": "time de médicos",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},

    # ESPECIALIDADES (6)
    {"id": 9, "category": "ESPECIALIDADES", "input": "quais especialidades vocês têm?",
     "expected": {"intent_any": ["listar_especialidades"], "contains_any": ["Cardiologia", "Clínica Geral", "Dermatologia", "Neurologia"]}},
    {"id": 10, "category": "ESPECIALIDADES", "input": "vocês atendem neurologia?",
     "expected": {"intent_any": ["listar_profissionais", "listar_especialidades"], "contains_any": ["Neurologia", "Marcos Nunes"]}},
    {"id": 11, "category": "ESPECIALIDADES", "input": "tem cardiologia?",
     "expected": {"intent_any": ["listar_profissionais", "listar_especialidades"], "contains_any": ["Cardiologia", "João Santos"]}},
    {"id": 12, "category": "ESPECIALIDADES", "input": "quais áreas vocês atendem?",
     "expected": {"intent_any": ["listar_especialidades"], "contains_any": ["Cardiologia", "Clínica Geral", "Dermatologia"]}},
    {"id": 13, "category": "ESPECIALIDADES", "input": "vocês têm ortopedia?",
     "expected": {"intent_any": ["listar_profissionais", "listar_especialidades"], "contains_any": ["Ortopedia", "Pedro Costa"]}},
    {"id": 14, "category": "ESPECIALIDADES", "input": "quais as especialidades disponíveis?",
     "expected": {"intent_any": ["listar_especialidades"], "contains_any": ["Cardiologia", "Clínica Geral", "Dermatologia"]}},

    # PROFISSIONAIS POR ESPECIALIDADE (6)
    {"id": 15, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "quem atende neurologia?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["Marcos Nunes", "Neurologia"]}},
    {"id": 16, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "tem neurologista?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["Marcos Nunes", "Neurologia"]}},
    {"id": 17, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "quais médicos são ortopedistas?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["Pedro Costa", "Ortopedia"]}},
    {"id": 18, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "quem é da ortopedia?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["Pedro Costa", "Ortopedia"]}},
    {"id": 19, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "quais profissionais atendem dermatologia?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["Ana Oliveira", "Dermatologia"]}},
    {"id": 20, "category": "PROFISSIONAIS_POR_ESPECIALIDADE", "input": "existe algum médico de cardiologia?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Cardiologia"]}},

    # AGENDA (6)
    {"id": 21, "category": "AGENDA", "input": "tem horário com neurologista amanhã?",
     "expected": {"intent_any": ["agendar", "duvida_operacional"], "contains_any": ["Marcos Nunes", "Neurologia", "horário", "disponível", "20/04"]}},
    {"id": 22, "category": "AGENDA", "input": "tem consulta hoje?",
     "expected": {"intent_any": ["agendar", "duvida_operacional"], "route_any": ["schedule_flow", "structured_data_lookup"]}},
    {"id": 23, "category": "AGENDA", "input": "tem vaga para ortopedia?",
     "expected": {"intent_any": ["agendar"], "route_any": ["schedule_flow", "structured_data_lookup"]}},
    {"id": 24, "category": "AGENDA", "input": "qual horário disponível com dermatologista?",
     "expected": {"intent_any": ["agendar", "duvida_operacional"], "contains_any": ["Ana Oliveira", "Dermatologia"]}},
    {"id": 25, "category": "AGENDA", "input": "tem agenda amanhã de manhã?",
     "expected": {"intent_any": ["agendar", "duvida_operacional"], "contains_any": ["20/04", "08:", "disponível"]}},
    {"id": 26, "category": "AGENDA", "input": "quais horários disponíveis?",
     "expected": {"route_any": ["schedule_flow", "structured_data_lookup", "response_composer"]}},

    # CLÍNICA INFO (6)
    {"id": 27, "category": "CLINICA_INFO", "input": "qual o nome da clínica?",
     "expected": {"intent_any": ["duvida_operacional"], "contains_any": ["climesa", "Clínica", "Climesa"]}},
    {"id": 28, "category": "CLINICA_INFO", "input": "qual horário de funcionamento?",
     "expected": {"intent_any": ["duvida_operacional"], "contains_any": ["funcionamento", "horário", "7h", "20h", "8h", "18h"]}},
    {"id": 29, "category": "CLINICA_INFO", "input": "onde fica?",
     "expected": {"intent_any": ["duvida_operacional"], "route_any": ["structured_data_lookup"]}},
    {"id": 30, "category": "CLINICA_INFO", "input": "vocês atendem sábado?",
     "expected": {"intent_any": ["duvida_operacional"], "contains_any": ["sábado", "sabado", "atendimento"]}},
    {"id": 31, "category": "CLINICA_INFO", "input": "qual o endereço de vocês?",
     "expected": {"intent_any": ["duvida_operacional"], "route_any": ["structured_data_lookup"]}},
    {"id": 32, "category": "CLINICA_INFO", "input": "qual o telefone de vocês?",
     "expected": {"intent_any": ["duvida_operacional"], "route_any": ["structured_data_lookup"]}},

    # SAUDAÇÃO (6)
    {"id": 33, "category": "SAUDACAO", "input": "oi",
     "expected": {"intent_any": ["saudacao"], "contains_any": ["Olá", "oi", "bem-vindo", "Bom dia"]}},
    {"id": 34, "category": "SAUDACAO", "input": "olá",
     "expected": {"intent_any": ["saudacao"], "contains_any": ["Olá", "olá", "bem-vindo"]}},
    {"id": 35, "category": "SAUDACAO", "input": "bom dia",
     "expected": {"intent_any": ["saudacao"], "contains_any": ["Olá", "bom dia", "bem-vindo"]}},
    {"id": 36, "category": "SAUDACAO", "input": "preciso marcar consulta",
     "expected": {"intent_any": ["agendar"], "contains_any": ["agendar", "consulta", "especialidade"]}},
    {"id": 37, "category": "SAUDACAO", "input": "quero atendimento",
     "expected": {"intent_any": ["agendar", "listar_profissionais", "duvida_operacional"]}},
    {"id": 38, "category": "SAUDACAO", "input": "tudo bem?",
     "expected": {"intent_any": ["saudacao", "desconhecida"]}},

    # AMBÍGUAS (8)
    {"id": 39, "category": "AMBIGUAS", "input": "neuro tem?",
     "expected": {"contains_any": ["Marcos Nunes", "Neurologia", "temos"]}},
    {"id": 40, "category": "AMBIGUAS", "input": "medico cabeça",
     "expected": {"intent_any": ["desconhecida", "listar_profissionais"], "route_any": ["clarification_flow", "structured_data_lookup"]}},
    {"id": 41, "category": "AMBIGUAS", "input": "consulta urgente hj",
     "expected": {"intent_any": ["agendar", "desconhecida"]}},
    {"id": 42, "category": "AMBIGUAS", "input": "vcs tem dr?",
     "expected": {"intent_any": ["listar_profissionais"], "contains_any": ["João Santos", "Maria Silva", "Dr", "Dra"]}},
    {"id": 43, "category": "AMBIGUAS", "input": "orto amanha",
     "expected": {"intent_any": ["agendar", "desconhecida"]}},
    {"id": 44, "category": "AMBIGUAS", "input": "não sei",
     "expected": {"intent_any": ["desconhecida"]}},
    {"id": 45, "category": "AMBIGUAS", "input": "tanto faz",
     "expected": {"intent_any": ["desconhecida"]}},
    {"id": 46, "category": "AMBIGUAS", "input": "dgksndgl",
     "expected": {"intent_any": ["desconhecida"]}},

    # LONGAS (4)
    {"id": 47, "category": "LONGAS", "input": "quais profissionais a clínica tem e qual a especialidade de cada?",
     "expected": {"contains_any": ["João Santos", "Maria Silva", "Dr", "Dra", "Cardiologia", "Clínica Geral"]}},
    {"id": 48, "category": "LONGAS", "input": "vocês têm neurologista disponível amanhã à tarde?",
     "expected": {"contains_any": ["Marcos Nunes", "Neurologia", "20/04"]}},
    {"id": 49, "category": "LONGAS", "input": "eu queria saber quais médicos atendem aí e se algum deles atende neurologia",
     "expected": {"contains_any": ["Marcos Nunes", "Neurologia"]}},
    {"id": 50, "category": "LONGAS", "input": "quais especialidades vocês têm cadastradas no sistema?",
     "expected": {"intent_any": ["listar_especialidades"], "contains_any": ["Cardiologia", "Clínica Geral"]}},
]


@dataclass
class EvaluationResult:
    id: int
    category: str
    input: str
    faro_intent: str = ""
    route: str = ""
    source_of_truth: str = ""
    tool_used: str = ""
    output_text: str = ""
    correct: bool = False
    partially_correct: bool = False
    observation: str = ""
    # Instrumentation fields
    groq_called: bool = False
    llm_provider: str = ""
    llm_model: str = ""
    llm_stage: str = ""
    response_mode: str = ""


def evaluate_case(output_text: str, faro_intent: str, route: str, expected: dict) -> tuple[bool, bool, str]:
    """Evaluate if the output matches expected criteria."""
    output_lower = output_text.lower()

    # Check intent
    if "intent_any" in expected:
        if faro_intent not in expected["intent_any"]:
            return False, False, f"Intent mismatch: got {faro_intent}, expected any of {expected['intent_any']}"

    # Check route
    if "route_any" in expected:
        if route not in expected["route_any"]:
            return False, False, f"Route mismatch: got {route}, expected any of {expected['route_any']}"

    # Check content
    if "contains_any" in expected:
        matches = [kw for kw in expected["contains_any"] if kw.lower() in output_lower]
        if not matches:
            return False, False, f"Content mismatch: output does not contain any of {expected['contains_any']}"
        return True, True, f"OK (matched: {matches[:3]})"

    return True, True, "OK"


async def create_test_patient(session: AsyncSession) -> Patient:
    patient = Patient(
        id=uuid.uuid4(),
        full_name="Avaliador AI",
        telegram_user_id=f"eval_{uuid.uuid4().hex[:8]}",
        consented_ai=True,
    )
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient


async def create_test_conversation(session: AsyncSession, patient: Patient) -> Conversation:
    conversation = Conversation(
        id=uuid.uuid4(),
        patient_id=patient.id,
        channel="telegram",
        status="active",
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def run_evaluation_for_case(session_factory, case: dict):
    result = EvaluationResult(id=case["id"], category=case["category"], input=case["input"])

    async with session_factory() as session:
        try:
            patient = await create_test_patient(session)
            conversation = await create_test_conversation(session, patient)
            orchestrator = AIOrchestrator(session)

            response = await orchestrator.process_message(
                patient=patient,
                conversation=conversation,
                user_text=case["input"],
            )

            result.faro_intent = response.intent.value if response.intent else "NONE"
            result.route = getattr(response, 'route', 'unknown')
            result.source_of_truth = getattr(response, 'source_of_truth', 'unknown')
            result.output_text = response.text[:300] if response.text else ""

            # Instrumentation fields
            result.groq_called = getattr(response, 'groq_called', False)
            result.llm_provider = getattr(response, 'llm_provider', '')
            result.llm_model = getattr(response, 'llm_model', '')
            result.llm_stage = getattr(response, 'llm_stage', '')
            result.response_mode = getattr(response, 'response_mode', '')

            # Evaluate
            correct, partial, obs = evaluate_case(
                result.output_text,
                result.faro_intent,
                result.route,
                case["expected"]
            )
            result.correct = correct
            result.partially_correct = partial
            result.observation = obs

        except Exception as e:
            result.observation = f"ERRO: {str(e)[:150]}"

    return result


async def run_full_evaluation():
    print("=" * 80)
    print("AI ENGINE EVALUATION — FULL PIPELINE v3 (INSTRUMENTED)")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results = []

    for i, case in enumerate(TEST_CASES, 1):
        result = await run_evaluation_for_case(session_factory, case)
        results.append(result)

        status = "✅" if result.correct else ("⚠️" if result.partially_correct else "❌")
        groq = "🔵 Groq" if result.groq_called else "⚪ local"
        print(f"{status} [{case['id']:2d}] {case['input'][:45]} [{groq}]")
        if result.observation and not result.correct:
            print(f"       → {result.observation[:100]}")
            print(f"       → intent={result.faro_intent} route={result.route}")

    # Summary
    correct = sum(1 for r in results if r.correct)
    partial = sum(1 for r in results if r.partially_correct and not r.correct)
    incorrect = len(results) - correct - partial
    groq_total = sum(1 for r in results if r.groq_called)
    local_total = len(results) - groq_total

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total:     {len(results)}")
    print(f"Correct:   {correct} ({100*correct/len(results):.1f}%)")
    print(f"Partial:   {partial} ({100*partial/len(results):.1f}%)")
    print(f"Incorrect: {incorrect} ({100*incorrect/len(results):.1f}%)")
    print(f"\nTotal positivo: {correct + partial} ({100*(correct+partial)/len(results):.1f}%)")
    print(f"\nGroq calls:     {groq_total} ({100*groq_total/len(results):.1f}%)")
    print(f"Local (no LLM): {local_total} ({100*local_total/len(results):.1f}%)")

    # By category
    print(f"\n{'='*80}")
    print("BY CATEGORY")
    print(f"{'='*80}")
    cats = {}
    for r in results:
        cats.setdefault(r.category, {"correct": 0, "partial": 0, "incorrect": 0})
        if r.correct:
            cats[r.category]["correct"] += 1
        elif r.partially_correct:
            cats[r.category]["partial"] += 1
        else:
            cats[r.category]["incorrect"] += 1

    for cat, c in sorted(cats.items()):
        total = c["correct"] + c["partial"] + c["incorrect"]
        ok = c["correct"] + c["partial"]
        print(f"  {cat:40s} {ok:2d}/{total:2d} ({100*ok/total:.0f}%)")

    # Groq calls by category
    print(f"\n{'='*80}")
    print("GROQ CALLS BY CATEGORY")
    print(f"{'='*80}")
    groq_cats = {}
    for r in results:
        if r.groq_called:
            groq_cats.setdefault(r.category, 0)
            groq_cats[r.category] += 1
    for cat, count in sorted(groq_cats.items()):
        total_in_cat = sum(1 for r in results if r.category == cat)
        print(f"  {cat:40s} {count:2d}/{total_in_cat} Groq calls")

    # Save results
    results_data = [asdict(r) for r in results]
    with open("/tmp/evaluation_final.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults: /tmp/evaluation_final.json")

    await engine.dispose()
    return results


def main():
    asyncio.run(run_full_evaluation())

if __name__ == "__main__":
    main()
