"""Anomaly detection for medical billing and operational data.

Uses PyOD (https://github.com/yzhao062/pyod) as the primary detection engine.

Use cases:
- Glosa prediction: identify claims likely to be rejected before submission
- Financial anomalies: unusual billing amounts, payment patterns
- Operational gaps: scheduling irregularities, cancellation spikes
- Behavioral outliers: professional productivity deviations

Each clinic deploy uses its OWN historical data to train models.
No model or data is shared between clinic deployments.
"""

from .models.detector import AnomalyDetector, AnomalyResult
from .pipelines.anomaly_pipeline import AnomalyPipeline

__all__ = ["AnomalyDetector", "AnomalyResult", "AnomalyPipeline"]
