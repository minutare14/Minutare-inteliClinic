#!/usr/bin/env python3
"""Script de avaliação de qualidade do RAG usando RAGAS.

Uso:
    python scripts/evaluate_rag.py

    # Com dataset personalizado
    python scripts/evaluate_rag.py --dataset tests/rag/eval_dataset.jsonl

    # Comparar duas configurações
    python scripts/evaluate_rag.py --run-name "v2_semantic_chunking" --output results/v2.json
    python scripts/evaluate_rag.py --run-name "v1_baseline" --output results/v1.json

    # Comparar resultados salvos
    python scripts/evaluate_rag.py --compare results/v1.json results/v2.json

Pré-requisitos:
    pip install "inteliclinic[evaluation]"
    # ou: pip install ragas datasets

Variáveis de ambiente necessárias:
    OPENAI_API_KEY ou ANTHROPIC_API_KEY
    CLINIC_QDRANT_URL (para consultar a knowledge base)
    CLINIC_ID
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Adicionar src/ ao path para imports locais
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Avalia qualidade do RAG usando RAGAS"
    )
    parser.add_argument(
        "--dataset",
        default="tests/rag/eval_dataset.jsonl",
        help="Caminho para o dataset de avaliação (JSONL)",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Nome desta execução (para comparação futura)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Arquivo JSON para salvar o relatório (ex: results/eval.json)",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["faithfulness", "answer_relevancy", "context_recall", "context_precision"],
        help="Métricas RAGAS a avaliar",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("REPORT_A", "REPORT_B"),
        help="Comparar dois relatórios JSON salvos anteriormente",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de chunks a recuperar por query",
    )
    return parser.parse_args()


async def run_evaluation(args: argparse.Namespace) -> None:
    from inteliclinic.core.evaluation.rag.evaluator import (
        EvaluationDataset,
        EvaluationReport,
        RAGEvaluator,
    )

    # Carregar dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"❌ Dataset não encontrado: {dataset_path}")
        sys.exit(1)

    print(f"📂 Carregando dataset: {dataset_path}")
    dataset = EvaluationDataset.from_jsonl(dataset_path)
    print(f"   {len(dataset)} amostras carregadas")

    # Configurar query engine
    query_engine = _build_query_engine(args)

    # Criar avaliador
    evaluator = RAGEvaluator(
        query_engine=query_engine,
        metrics=args.metrics,
    )

    # Executar avaliação
    print(f"\n🔬 Executando avaliação RAGAS...")
    print(f"   Métricas: {', '.join(args.metrics)}")
    report = await evaluator.evaluate(dataset, run_name=args.run_name)

    # Exibir resultado
    print("\n" + "=" * 60)
    print(report.summary())
    print(f"\n📊 Score geral: {report.overall_score():.3f}")
    print("=" * 60)

    # Salvar relatório
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.save(output_path)
        print(f"\n💾 Relatório salvo em: {output_path}")


def compare_reports(path_a: str, path_b: str) -> None:
    from inteliclinic.core.evaluation.rag.evaluator import EvaluationReport, MetricScore, RAGEvaluator

    def _load(path: str) -> EvaluationReport:
        data = json.loads(Path(path).read_text())
        return EvaluationReport(
            run_name=data["run_name"],
            dataset_name=data.get("dataset_name", ""),
            timestamp=data.get("timestamp", ""),
            n_samples=data.get("n_samples", 0),
            metrics=[
                MetricScore(name=k, score=v, description="")
                for k, v in data.get("metrics", {}).items()
            ],
        )

    report_a = _load(path_a)
    report_b = _load(path_b)
    print("\n" + RAGEvaluator.compare(report_a, report_b))


def _build_query_engine(args: argparse.Namespace):
    """Build a ClinicQueryEngine from environment configuration."""
    import os

    qdrant_url = os.getenv("CLINIC_QDRANT_URL", "http://localhost:6333")
    clinic_id = os.getenv("CLINIC_ID", "eval_test")

    try:
        from inteliclinic.core.rag.indexes.llamaindex_store import LlamaIndexStore
        from inteliclinic.core.rag.query.query_engine import ClinicQueryEngine

        store = LlamaIndexStore.from_config({
            "clinic_id": clinic_id,
            "qdrant_url": qdrant_url,
        })
        return ClinicQueryEngine(store=store, top_k=args.top_k)
    except Exception as exc:
        print(f"⚠️  Não foi possível conectar ao Qdrant: {exc}")
        print("   Usando query engine mock para avaliação estrutural.")
        return _MockQueryEngine()


class _MockQueryEngine:
    """Mock query engine para testes sem Qdrant."""

    async def query(self, question: str, **kwargs):
        return []


def main():
    args = parse_args()

    if args.compare:
        compare_reports(args.compare[0], args.compare[1])
        return

    asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    main()
