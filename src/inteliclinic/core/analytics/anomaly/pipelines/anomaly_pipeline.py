"""End-to-end anomaly detection pipeline for clinic billing and operations.

Pipeline stages:
    1. Feature extraction (FeatureExtractor)
    2. Normalization
    3. Anomaly scoring (AnomalyDetector / PyOD)
    4. Alert generation with explanations
    5. Report generation

Usage:
    pipeline = AnomalyPipeline.for_glosa()
    pipeline.fit(historical_claims)

    report = pipeline.analyze(new_claims)
    for alert in report.alerts:
        print(f"[{alert.risk_level.upper()}] Claim {alert.claim_id}: {alert.explanation}")

Data isolation:
    Each clinic trains its own models on its own data.
    Models are saved/loaded from the clinic's local data directory.
    No model sharing between deployments.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from ..features.extractor import FeatureExtractor
from ..models.detector import AnomalyDetector, AnomalyResult

logger = logging.getLogger(__name__)


@dataclass
class AnomalyAlert:
    """A single actionable anomaly alert."""

    claim_id: str
    risk_score: float
    risk_level: str        # "low" | "medium" | "high" | "critical"
    explanation: str
    recommended_action: str
    raw_result: AnomalyResult


@dataclass
class PipelineReport:
    """Summary report from an anomaly detection run."""

    total_analyzed: int
    anomalies_found: int
    alerts: list[AnomalyAlert]
    anomaly_rate: float
    run_metadata: dict = field(default_factory=dict)

    def critical_alerts(self) -> list[AnomalyAlert]:
        return [a for a in self.alerts if a.risk_level == "critical"]

    def high_alerts(self) -> list[AnomalyAlert]:
        return [a for a in self.alerts if a.risk_level in ("high", "critical")]

    def summary(self) -> str:
        return (
            f"Analisados: {self.total_analyzed} | "
            f"Anomalias: {self.anomalies_found} ({self.anomaly_rate:.1%}) | "
            f"Críticos: {len(self.critical_alerts())} | "
            f"Altos: {len([a for a in self.alerts if a.risk_level == 'high'])}"
        )


class AnomalyPipeline:
    """Full anomaly detection pipeline for clinic data.

    Combines feature extraction, model fitting, scoring, and alerting.
    Operates entirely on local clinic data — no external dependencies beyond PyOD.
    """

    def __init__(
        self,
        detector: AnomalyDetector,
        extractor: FeatureExtractor,
        pipeline_type: str = "glosa",
    ):
        self.detector = detector
        self.extractor = extractor
        self.pipeline_type = pipeline_type
        self._is_fitted = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(self, historical_records: list[dict]) -> "AnomalyPipeline":
        """Fit the detector on historical clinic records.

        Args:
            historical_records: List of raw claim/billing dicts.
                                Should include both normal and anomalous examples.
        """
        if not historical_records:
            logger.warning("No historical records provided — detector not fitted")
            return self

        X = self.extractor.extract_batch(historical_records)
        feature_names = self.extractor.feature_names()
        self.detector.fit(X, feature_names=feature_names)
        self._is_fitted = True
        logger.info(
            "Pipeline '%s' fitted on %d records", self.pipeline_type, len(historical_records)
        )
        return self

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze(self, records: list[dict], record_ids: list[str] | None = None) -> PipelineReport:
        """Score a batch of records and return a report with alerts.

        Args:
            records:    List of raw claim/billing dicts to analyze.
            record_ids: Optional IDs for each record (for alert correlation).
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before analyze()")

        ids = record_ids or [str(i) for i in range(len(records))]
        X = self.extractor.extract_batch(records)

        if X.shape[0] == 0:
            return PipelineReport(
                total_analyzed=0,
                anomalies_found=0,
                alerts=[],
                anomaly_rate=0.0,
            )

        results = self.detector.predict(X)
        alerts = [
            self._build_alert(record_id, result)
            for record_id, result in zip(ids, results)
            if result.is_anomaly
        ]

        return PipelineReport(
            total_analyzed=len(records),
            anomalies_found=len(alerts),
            alerts=alerts,
            anomaly_rate=len(alerts) / len(records) if records else 0.0,
            run_metadata={"pipeline_type": self.pipeline_type},
        )

    def score_one(self, record: dict, record_id: str = "unknown") -> AnomalyAlert | None:
        """Score a single record. Returns alert if anomaly, None if normal."""
        report = self.analyze([record], record_ids=[record_id])
        return report.alerts[0] if report.alerts else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_alert(self, record_id: str, result: AnomalyResult) -> AnomalyAlert:
        recommended = {
            "critical": "Revisão imediata obrigatória antes de submeter à operadora.",
            "high": "Revisão recomendada — alta probabilidade de glosa.",
            "medium": "Atenção: verificar documentação e codificação antes da submissão.",
            "low": "Monitorar — baixo risco de glosa.",
        }
        return AnomalyAlert(
            claim_id=record_id,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            explanation=result.explanation,
            recommended_action=recommended.get(result.risk_level, "Revisar"),
            raw_result=result,
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_glosa(cls) -> "AnomalyPipeline":
        """Pre-configured pipeline for glosa detection."""
        return cls(
            detector=AnomalyDetector.for_glosa(),
            extractor=FeatureExtractor(),
            pipeline_type="glosa",
        )

    @classmethod
    def for_financial(cls) -> "AnomalyPipeline":
        """Pre-configured pipeline for financial anomaly detection."""
        return cls(
            detector=AnomalyDetector.for_financial(),
            extractor=FeatureExtractor(),
            pipeline_type="financial",
        )
