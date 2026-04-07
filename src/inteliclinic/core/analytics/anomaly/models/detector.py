"""Anomaly detector wrapping PyOD algorithms for clinic billing/ops data.

Uses an ensemble of PyOD detectors for robust anomaly detection:
- IsolationForest: good for high-dimensional tabular data
- LOF (Local Outlier Factor): good for dense cluster detection
- HBOS (Histogram-based Outlier Score): fast, interpretable

Reference: https://github.com/yzhao062/pyod

Usage:
    detector = AnomalyDetector.for_glosa()
    detector.fit(historical_claims_df)

    # Score new claims
    results = detector.predict(new_claims_df)
    for result in results:
        if result.is_anomaly:
            print(f"Risk: {result.risk_score:.2f} — {result.explanation}")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class DetectorAlgorithm(str, Enum):
    ISOLATION_FOREST = "iforest"
    LOF = "lof"
    HBOS = "hbos"
    OCSVM = "ocsvm"
    ENSEMBLE = "ensemble"  # Weighted average of multiple detectors


@dataclass
class DetectorConfig:
    algorithm: DetectorAlgorithm = DetectorAlgorithm.ENSEMBLE
    contamination: float = 0.05  # Expected fraction of anomalies
    n_estimators: int = 100       # For IsolationForest
    n_neighbors: int = 20         # For LOF
    random_state: int = 42
    explain: bool = True          # Return feature-level explanations


@dataclass
class AnomalyResult:
    """Result for a single observation."""

    index: int
    risk_score: float           # 0.0 (normal) to 1.0 (highly anomalous)
    is_anomaly: bool
    confidence: float           # Detector confidence in this classification
    explanation: str            # Human-readable explanation
    feature_contributions: dict[str, float] = field(default_factory=dict)
    raw_scores: dict[str, float] = field(default_factory=dict)

    @property
    def risk_level(self) -> str:
        if self.risk_score >= 0.80:
            return "critical"
        if self.risk_score >= 0.60:
            return "high"
        if self.risk_score >= 0.40:
            return "medium"
        return "low"


class AnomalyDetector:
    """Ensemble anomaly detector for clinic operational data.

    Wraps PyOD detectors with a consistent interface.
    Supports fitting, prediction, and human-readable explanations.
    """

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        self._detectors: dict[str, Any] = {}
        self._is_fitted = False
        self._feature_names: list[str] = []

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, feature_names: list[str] | None = None) -> "AnomalyDetector":
        """Fit the detector on historical (normal + anomalous) data.

        Args:
            X:             Feature matrix, shape (n_samples, n_features).
            feature_names: Names for interpretability. Must match X columns.
        """
        from pyod.models.hbos import HBOS
        from pyod.models.iforest import IForest
        from pyod.models.lof import LOF

        self._feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        if self.config.algorithm in (DetectorAlgorithm.ISOLATION_FOREST, DetectorAlgorithm.ENSEMBLE):
            self._detectors["iforest"] = IForest(
                n_estimators=self.config.n_estimators,
                contamination=self.config.contamination,
                random_state=self.config.random_state,
            )
            self._detectors["iforest"].fit(X)

        if self.config.algorithm in (DetectorAlgorithm.LOF, DetectorAlgorithm.ENSEMBLE):
            self._detectors["lof"] = LOF(
                n_neighbors=self.config.n_neighbors,
                contamination=self.config.contamination,
            )
            self._detectors["lof"].fit(X)

        if self.config.algorithm in (DetectorAlgorithm.HBOS, DetectorAlgorithm.ENSEMBLE):
            self._detectors["hbos"] = HBOS(contamination=self.config.contamination)
            self._detectors["hbos"].fit(X)

        self._is_fitted = True
        logger.info(
            "AnomalyDetector fitted on %d samples with %d features — algorithm: %s",
            X.shape[0],
            X.shape[1],
            self.config.algorithm,
        )
        return self

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    def predict(self, X: np.ndarray) -> list[AnomalyResult]:
        """Score observations and return AnomalyResult for each row."""
        if not self._is_fitted:
            raise RuntimeError("Call fit() before predict()")

        ensemble_scores = self._compute_ensemble_scores(X)
        threshold = np.percentile(ensemble_scores, (1 - self.config.contamination) * 100)

        results = []
        for i, (score, row) in enumerate(zip(ensemble_scores, X)):
            is_anomaly = score >= threshold
            explanation = self._explain(row, score, is_anomaly)
            results.append(
                AnomalyResult(
                    index=i,
                    risk_score=float(np.clip(score, 0.0, 1.0)),
                    is_anomaly=is_anomaly,
                    confidence=0.75 if len(self._detectors) > 1 else 0.60,
                    explanation=explanation,
                )
            )
        return results

    def predict_one(self, x: np.ndarray) -> AnomalyResult:
        """Score a single observation."""
        results = self.predict(x.reshape(1, -1))
        return results[0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_ensemble_scores(self, X: np.ndarray) -> np.ndarray:
        """Compute normalized ensemble scores (0-1) for each row."""
        all_scores: list[np.ndarray] = []
        for name, det in self._detectors.items():
            raw = det.decision_function(X)
            # Normalize to [0, 1]
            mn, mx = raw.min(), raw.max()
            normalized = (raw - mn) / (mx - mn + 1e-9)
            all_scores.append(normalized)

        if not all_scores:
            return np.zeros(X.shape[0])
        return np.mean(all_scores, axis=0)

    def _explain(self, row: np.ndarray, score: float, is_anomaly: bool) -> str:
        """Generate a human-readable explanation for this prediction."""
        level = "ANOMALIA DETECTADA" if is_anomaly else "Normal"
        risk_pct = int(score * 100)
        base = f"{level} — Score de risco: {risk_pct}%."

        if is_anomaly and self._feature_names and len(row) == len(self._feature_names):
            # Identify the top contributing features (highest absolute value)
            top_idx = int(np.argmax(np.abs(row)))
            feat = self._feature_names[top_idx]
            val = row[top_idx]
            base += f" Principal fator: {feat} = {val:.2f}."

        return base

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def for_glosa(cls) -> "AnomalyDetector":
        """Pre-configured detector for insurance glosa prediction."""
        return cls(DetectorConfig(
            algorithm=DetectorAlgorithm.ENSEMBLE,
            contamination=0.08,  # ~8% glosa rate typical in Brazilian clinics
        ))

    @classmethod
    def for_financial(cls) -> "AnomalyDetector":
        """Pre-configured detector for financial transaction anomalies."""
        return cls(DetectorConfig(
            algorithm=DetectorAlgorithm.ISOLATION_FOREST,
            contamination=0.03,
        ))

    @classmethod
    def for_operations(cls) -> "AnomalyDetector":
        """Pre-configured detector for operational pattern anomalies."""
        return cls(DetectorConfig(
            algorithm=DetectorAlgorithm.LOF,
            contamination=0.05,
        ))
