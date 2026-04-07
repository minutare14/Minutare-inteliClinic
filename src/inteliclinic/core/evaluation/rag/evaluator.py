"""RAG quality evaluation using RAGAS.

Metrics evaluated:
- faithfulness:       Are the answers grounded in the retrieved context?
- answer_relevancy:   Is the answer relevant to the question?
- context_recall:     Is the relevant context being retrieved?
- context_precision:  Is the retrieved context accurate (no noise)?

Reference: https://github.com/explodinggradients/ragas

Usage:
    evaluator = RAGEvaluator.from_config(config)

    dataset = EvaluationDataset.from_jsonl("tests/rag/eval_dataset.jsonl")
    report = await evaluator.evaluate(dataset)

    print(report.summary())
    report.save("results/rag_eval_2024_01.json")

Comparing versions:
    # After changing prompts or indexing strategy
    report_v1 = await evaluator.evaluate(dataset, run_name="v1_baseline")
    report_v2 = await evaluator.evaluate(dataset, run_name="v2_new_chunking")
    print(RAGEvaluator.compare(report_v1, report_v2))
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvaluationSample:
    """A single Q&A sample for RAG evaluation."""

    question: str
    ground_truth: str                    # Expected answer (human-annotated)
    contexts: list[str] = field(default_factory=list)   # Retrieved chunks
    answer: str = ""                     # Generated answer (filled by evaluator)
    metadata: dict = field(default_factory=dict)


@dataclass
class EvaluationDataset:
    """Collection of evaluation samples."""

    samples: list[EvaluationSample]
    name: str = "eval_dataset"

    def __len__(self) -> int:
        return len(self.samples)

    @classmethod
    def from_jsonl(cls, path: str | Path, name: str | None = None) -> "EvaluationDataset":
        """Load evaluation dataset from a JSONL file.

        Each line should be JSON with keys: question, ground_truth, (optional) contexts.
        """
        path = Path(path)
        samples = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                samples.append(
                    EvaluationSample(
                        question=data["question"],
                        ground_truth=data["ground_truth"],
                        contexts=data.get("contexts", []),
                        answer=data.get("answer", ""),
                        metadata=data.get("metadata", {}),
                    )
                )
        return cls(samples=samples, name=name or path.stem)

    def to_ragas_dataset(self):
        """Convert to RAGAS Dataset format."""
        from datasets import Dataset

        data = {
            "question": [s.question for s in self.samples],
            "ground_truth": [s.ground_truth for s in self.samples],
            "contexts": [s.contexts for s in self.samples],
            "answer": [s.answer for s in self.samples],
        }
        return Dataset.from_dict(data)


@dataclass
class MetricScore:
    name: str
    score: float
    description: str


@dataclass
class EvaluationReport:
    """RAGAS evaluation results."""

    run_name: str
    dataset_name: str
    timestamp: str
    n_samples: int
    metrics: list[MetricScore]
    raw_results: dict = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"RAG Evaluation — {self.run_name} ({self.timestamp})",
            f"Dataset: {self.dataset_name} | Samples: {self.n_samples}",
            "-" * 50,
        ]
        for m in self.metrics:
            lines.append(f"  {m.name:<25} {m.score:.3f}   {m.description}")
        return "\n".join(lines)

    def overall_score(self) -> float:
        """Weighted average of all metrics."""
        if not self.metrics:
            return 0.0
        return sum(m.score for m in self.metrics) / len(self.metrics)

    def save(self, path: str | Path) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "run_name": self.run_name,
            "dataset_name": self.dataset_name,
            "timestamp": self.timestamp,
            "n_samples": self.n_samples,
            "overall_score": self.overall_score(),
            "metrics": {m.name: m.score for m in self.metrics},
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info("Evaluation report saved to %s", path)


class RAGEvaluator:
    """RAGAS-based RAG quality evaluator.

    Runs the full RAGAS evaluation pipeline:
    1. Generate answers using the clinic's query engine
    2. Evaluate faithfulness, relevancy, recall, precision
    3. Return a structured report
    """

    def __init__(
        self,
        query_engine,          # ClinicQueryEngine
        llm_model: str = "gpt-4o-mini",
        metrics: list[str] | None = None,
    ):
        self.query_engine = query_engine
        self.llm_model = llm_model
        self.metrics = metrics or ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]

    async def evaluate(
        self,
        dataset: EvaluationDataset,
        run_name: str | None = None,
    ) -> EvaluationReport:
        """Run RAGAS evaluation on the dataset.

        Args:
            dataset:  EvaluationDataset with questions and ground truths.
            run_name: Label for this evaluation run (e.g. "v2_semantic_chunking").
        """
        run_name = run_name or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info("Starting RAG evaluation '%s' on %d samples", run_name, len(dataset))

        # Step 1: Generate answers + collect contexts
        samples_with_answers = await self._generate_answers(dataset.samples)

        # Step 2: Build RAGAS dataset
        eval_dataset = EvaluationDataset(
            samples=samples_with_answers,
            name=dataset.name,
        ).to_ragas_dataset()

        # Step 3: Run RAGAS metrics
        raw_scores = self._run_ragas(eval_dataset)

        # Step 4: Build report
        metric_scores = [
            MetricScore(
                name=name,
                score=raw_scores.get(name, 0.0),
                description=self._metric_description(name),
            )
            for name in self.metrics
        ]

        return EvaluationReport(
            run_name=run_name,
            dataset_name=dataset.name,
            timestamp=datetime.now().isoformat(),
            n_samples=len(dataset),
            metrics=metric_scores,
            raw_results=raw_scores,
        )

    async def _generate_answers(
        self, samples: list[EvaluationSample]
    ) -> list[EvaluationSample]:
        """Query the RAG engine for each sample to get answers and contexts."""
        updated = []
        for sample in samples:
            results = await self.query_engine.query(sample.question)
            answer = results[0].content if results else ""
            contexts = [r.content for r in results]
            updated.append(
                EvaluationSample(
                    question=sample.question,
                    ground_truth=sample.ground_truth,
                    contexts=contexts,
                    answer=answer,
                    metadata=sample.metadata,
                )
            )
        return updated

    def _run_ragas(self, eval_dataset) -> dict[str, float]:
        """Run RAGAS metrics on the prepared dataset."""
        try:
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )

            metric_map = {
                "faithfulness": faithfulness,
                "answer_relevancy": answer_relevancy,
                "context_recall": context_recall,
                "context_precision": context_precision,
            }
            selected = [metric_map[m] for m in self.metrics if m in metric_map]
            result = evaluate(eval_dataset, metrics=selected)
            return dict(result)
        except ImportError:
            logger.warning("RAGAS not installed. Install with: pip install ragas")
            return {m: 0.0 for m in self.metrics}
        except Exception as exc:
            logger.exception("RAGAS evaluation failed: %s", exc)
            return {m: 0.0 for m in self.metrics}

    @staticmethod
    def _metric_description(name: str) -> str:
        descriptions = {
            "faithfulness": "Respostas fundamentadas no contexto recuperado",
            "answer_relevancy": "Relevância da resposta para a pergunta",
            "context_recall": "Contexto relevante sendo recuperado",
            "context_precision": "Precisão do contexto (sem ruído)",
        }
        return descriptions.get(name, "")

    @staticmethod
    def compare(report_a: EvaluationReport, report_b: EvaluationReport) -> str:
        """Compare two evaluation reports side by side."""
        lines = [
            f"Comparação: {report_a.run_name} vs {report_b.run_name}",
            f"{'Métrica':<25} {'A':>8} {'B':>8} {'Δ':>8}",
            "-" * 50,
        ]
        scores_a = {m.name: m.score for m in report_a.metrics}
        scores_b = {m.name: m.score for m in report_b.metrics}
        all_metrics = sorted(set(scores_a) | set(scores_b))
        for metric in all_metrics:
            a = scores_a.get(metric, 0.0)
            b = scores_b.get(metric, 0.0)
            delta = b - a
            sign = "+" if delta > 0 else ""
            lines.append(f"  {metric:<23} {a:>8.3f} {b:>8.3f} {sign}{delta:>7.3f}")
        return "\n".join(lines)

    @classmethod
    def from_config(cls, config: dict, query_engine) -> "RAGEvaluator":
        return cls(
            query_engine=query_engine,
            llm_model=config.get("eval_llm_model", "gpt-4o-mini"),
            metrics=config.get("eval_metrics", None),
        )
