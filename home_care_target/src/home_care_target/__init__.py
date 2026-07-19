"""在宅支援診療所・在宅支援病院の精密集計と居宅患者目標計算."""

from .catchment import CatchmentPoint, aggregate_catchment_supply, compute_regional_supply
from .targets import (
    HomePatientTargetResult,
    SupplySnapshot,
    compute_home_patient_targets,
)

__all__ = [
    "HomePatientTargetResult",
    "SupplySnapshot",
    "CatchmentPoint",
    "compute_home_patient_targets",
    "compute_regional_supply",
    "aggregate_catchment_supply",
]

__version__ = "0.1.0"
