"""Clinic branding — name, logo, colors, tone of voice.

Loaded from clinic/config/ClinicSettings at deploy startup.
Never referenced in core/ product code.
"""

from .brand import ClinicBrand

__all__ = ["ClinicBrand"]
