"""Tests for RAG evaluation pipeline using RAGAS.

Run:
    pytest tests/rag/test_rag_evaluation.py -v

Or use the full evaluation script:
    python scripts/evaluate_rag.py --dataset tests/rag/eval_dataset.jsonl
"""
import json
from pathlib import Path

import pytest

from inteliclinic.core.evaluation.rag.evaluator import (
    EvaluationDataset,
    EvaluationSample,
    EvaluationReport,
    MetricScore,
    RAGEvaluator,
)


class TestEvaluationDataset:
    def test_load_from_jsonl(self):
        dataset = EvaluationDataset.from_jsonl(
            Path(__file__).parent / "eval_dataset.jsonl"
        )
        assert len(dataset) == 8
        assert dataset.samples[0].question == "Quais convênios são aceitos na clínica?"

    def test_sample_has_required_fields(self):
        dataset = EvaluationDataset.from_jsonl(
            Path(__file__).parent / "eval_dataset.jsonl"
        )
        sample = dataset.samples[0]
        assert sample.question
        assert sample.ground_truth
        assert isinstance(sample.contexts, list)
        assert isinstance(sample.metadata, dict)

    def test_empty_dataset(self, tmp_path):
        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")
        dataset = EvaluationDataset.from_jsonl(empty_file)
        assert len(dataset) == 0


class TestEvaluationReport:
    def _make_report(self) -> EvaluationReport:
        return EvaluationReport(
            run_name="test_run",
            dataset_name="test_dataset",
            timestamp="2024-01-01T00:00:00",
            n_samples=8,
            metrics=[
                MetricScore("faithfulness", 0.85, "desc"),
                MetricScore("answer_relevancy", 0.78, "desc"),
                MetricScore("context_recall", 0.72, "desc"),
                MetricScore("context_precision", 0.80, "desc"),
            ],
        )

    def test_overall_score(self):
        report = self._make_report()
        expected = (0.85 + 0.78 + 0.72 + 0.80) / 4
        assert abs(report.overall_score() - expected) < 0.001

    def test_summary_contains_metrics(self):
        report = self._make_report()
        summary = report.summary()
        assert "faithfulness" in summary
        assert "test_run" in summary

    def test_save_and_load(self, tmp_path):
        report = self._make_report()
        path = tmp_path / "report.json"
        report.save(path)
        data = json.loads(path.read_text())
        assert data["run_name"] == "test_run"
        assert data["n_samples"] == 8
        assert "faithfulness" in data["metrics"]

    def test_compare_reports(self):
        report_a = self._make_report()
        report_b = EvaluationReport(
            run_name="improved",
            dataset_name="test_dataset",
            timestamp="2024-01-02T00:00:00",
            n_samples=8,
            metrics=[
                MetricScore("faithfulness", 0.90, "desc"),
                MetricScore("answer_relevancy", 0.82, "desc"),
                MetricScore("context_recall", 0.75, "desc"),
                MetricScore("context_precision", 0.83, "desc"),
            ],
        )
        comparison = RAGEvaluator.compare(report_a, report_b)
        assert "faithfulness" in comparison
        assert "improved" in comparison
        assert "test_run" in comparison
