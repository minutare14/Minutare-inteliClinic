"""Feature extraction for glosa and financial anomaly detection.

Transforms raw clinic data (appointments, billing records, procedures)
into numeric feature vectors suitable for PyOD models.

Feature sets:
- GlosaFeatures: for insurance claim rejection prediction
- FinancialFeatures: for billing amount anomalies
- OperationalFeatures: for scheduling pattern analysis
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class GlosaFeatures:
    """Feature vector for a single insurance claim (guia).

    All features are normalized to [0, 1] or z-scored before model input.
    """

    # Claim characteristics
    procedure_value: float          # Claim value in BRL
    procedure_code: str             # TUSS code
    cid_code: str                   # CID-10 diagnosis code
    days_since_appointment: int     # Days between service and submission

    # Professional profile
    professional_glosa_rate: float  # Historical glosa rate for this professional
    professional_claim_count: int   # Total claims submitted by this professional

    # Insurance profile
    insurer_rejection_rate: float   # Historical rejection rate for this insurer
    plan_code: str                  # Health plan code

    # Procedure context
    is_elective: bool
    requires_pre_authorization: bool
    pre_authorization_present: bool

    def to_vector(self) -> np.ndarray:
        """Convert to numeric feature vector."""
        return np.array([
            self.procedure_value / 10_000.0,            # Normalize to ~[0,1] for typical clinic
            self.days_since_appointment / 30.0,          # Normalize to months
            self.professional_glosa_rate,
            self.professional_claim_count / 1000.0,
            self.insurer_rejection_rate,
            float(self.is_elective),
            float(self.requires_pre_authorization),
            float(self.pre_authorization_present),
            float(self.requires_pre_authorization and not self.pre_authorization_present),
        ], dtype=float)

    @classmethod
    def feature_names(cls) -> list[str]:
        return [
            "procedure_value_normalized",
            "days_since_appointment_normalized",
            "professional_glosa_rate",
            "professional_claim_count_normalized",
            "insurer_rejection_rate",
            "is_elective",
            "requires_pre_auth",
            "pre_auth_present",
            "missing_pre_auth",
        ]


class FeatureExtractor:
    """Transforms raw clinic records into feature vectors for anomaly detection."""

    def extract_glosa_features(self, claim: dict) -> GlosaFeatures:
        """Extract GlosaFeatures from a raw claim dict."""
        return GlosaFeatures(
            procedure_value=float(claim.get("value", 0)),
            procedure_code=claim.get("tuss_code", ""),
            cid_code=claim.get("cid_code", ""),
            days_since_appointment=int(claim.get("days_since_appointment", 0)),
            professional_glosa_rate=float(claim.get("professional_glosa_rate", 0)),
            professional_claim_count=int(claim.get("professional_claim_count", 0)),
            insurer_rejection_rate=float(claim.get("insurer_rejection_rate", 0)),
            plan_code=claim.get("plan_code", ""),
            is_elective=bool(claim.get("is_elective", True)),
            requires_pre_authorization=bool(claim.get("requires_pre_auth", False)),
            pre_authorization_present=bool(claim.get("pre_auth_present", False)),
        )

    def extract_batch(self, claims: list[dict]) -> np.ndarray:
        """Extract feature matrix from a list of claim dicts."""
        vectors = [self.extract_glosa_features(c).to_vector() for c in claims]
        return np.vstack(vectors) if vectors else np.empty((0, 9))

    @staticmethod
    def feature_names() -> list[str]:
        return GlosaFeatures.feature_names()
