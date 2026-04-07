"""Analytics module — operational intelligence for clinic management.

Modules:
    anomaly/  PyOD-based anomaly detection for glosas, financial fraud,
              billing inconsistencies, and operational patterns.

Data isolation:
    All analytics operate on LOCAL data for the current clinic deploy.
    No cross-clinic data is ever used. Each clinic trains its own models
    on its own historical data.
"""
