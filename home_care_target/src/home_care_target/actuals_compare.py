"""実績患者数と取得KPIの差分比較。

機密実績は analysis/confidential/ または環境変数 ACTUALS_PATH から読む。
コミット対象外の数値は公開レポートに生値を書き出さない運用を想定。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .acquisition import compute_acquisition_indicator
from .catchment import aggregate_catchment_supply
from .demand import estimate_demand_for_catchment
from .facilities import (
    adjusted_demand,
    count_facilities_in_radius,
    hospital_weight_for_prefs,
    load_facility_points,
)
from .targets import SupplySnapshot, compute_home_patient_targets
from .wakasa_demo_data import CLINIC_ALIASES, CLINICS, MUNICIPALITIES, PHYSICIAN_FTE

DEFAULT_ACTUALS = (
    Path(__file__).resolve().parents[3]
    / "analysis"
    / "confidential"
    / "wakasa_patient_actuals.yaml"
)


@dataclass
class ActualVsKpiRow:
    clinic: str
    alias: str
    actual_facility: int
    actual_home: int
    actual_total: int
    actual_home_share: float
    acquisition_floor_home: int
    acquisition_target_home: int
    acquisition_stretch_home: int
    competitive_home: float
    gap_vs_target: int  # actual_home - target
    gap_vs_floor: int
    attainment_vs_target: float  # actual / target
    competition_label: str
    competitors_clinics: float
    competitors_hospitals: float
    demand_home_adjusted: float
    physician_fte: Optional[float]
    note: str


def _load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _parse_simple_actuals_yaml(text)


def _parse_simple_actuals_yaml(text: str) -> dict:
    """最小YAMLパーサ（PyYAML無し環境向け）。本実績ファイル形式専用。"""
    clinics: List[dict] = []
    current: Optional[dict] = None
    meta: Dict[str, Any] = {"clinics": clinics}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("clinics:"):
            continue
        if line.strip().startswith("- alias:"):
            if current:
                clinics.append(current)
            current = {"alias": line.split(":", 1)[1].strip()}
            continue
        if current is None:
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
            continue
        if ":" in line:
            k, v = line.strip().split(":", 1)
            k = k.strip()
            v = v.strip()
            if k in ("facility", "home"):
                current[k] = int(v)
            else:
                current[k] = v
    if current:
        clinics.append(current)
    return meta


def load_actuals(path: Optional[Path] = None) -> Dict[str, dict]:
    path = path or DEFAULT_ACTUALS
    if not path.exists():
        raise FileNotFoundError(f"actuals not found: {path}")
    raw = _load_yaml(path)
    out: Dict[str, dict] = {}
    for row in raw.get("clinics", []):
        alias = str(row["alias"])
        full = CLINIC_ALIASES.get(alias, alias)
        out[full] = {
            "alias": alias,
            "facility": int(row["facility"]),
            "home": int(row["home"]),
        }
    return out


def compare_actuals_to_kpi(
    actuals_path: Optional[Path] = None,
    *,
    prefer_points: bool = True,
) -> List[ActualVsKpiRow]:
    actuals = load_actuals(actuals_path)
    munis = list(MUNICIPALITIES.values())
    points = load_facility_points()
    clinic_xy = [(c.name, c.lat, c.lon) for c in CLINICS]
    rows: List[ActualVsKpiRow] = []

    for clinic in CLINICS:
        if clinic.name not in actuals:
            continue
        act = actuals[clinic.name]
        muni_supply = aggregate_catchment_supply(clinic, munis)
        prefs = {MUNICIPALITIES[n].pref for n in muni_supply.municipalities if n in MUNICIPALITIES}
        hw = hospital_weight_for_prefs(prefs)
        demand = estimate_demand_for_catchment(
            clinic.lat, clinic.lon, munis, radius_km=clinic.radius_km
        )

        if prefer_points and points:
            point_supply = count_facilities_in_radius(
                clinic.lat, clinic.lon, clinic.radius_km, points, hospital_weight=hw
            )
            snap = SupplySnapshot.from_point_supply(
                point_supply,
                elderly_65=demand.elderly_65,
                avg_patients=muni_supply.avg_patients_local_proxy,
                enhanced_clinics=muni_supply.clinic_enhanced,
            )
            if point_supply.clinics + point_supply.hospitals < 1:
                snap = SupplySnapshot.from_catchment(muni_supply, hospital_weight=hw)
                snap.elderly_65 = demand.elderly_65
        else:
            snap = SupplySnapshot.from_catchment(muni_supply, hospital_weight=hw)
            snap.elderly_65 = demand.elderly_65

        home_adj, total_adj, _overlap = adjusted_demand(
            demand.recommended_home_patients,
            demand.visit_patients_total,
            clinic.name,
            clinic_xy,
        )
        fte = PHYSICIAN_FTE.get(clinic.name)
        acq = compute_acquisition_indicator(
            regional_home_demand=home_adj,
            regional_visit_demand=total_adj,
            competitors_clinics=snap.home_support_clinics,
            competitors_hospitals=snap.home_support_hospitals,
            hospital_weight=snap.hospital_weight,
            physician_fte=fte,
            local_avg_total_patients=muni_supply.avg_patients_local_proxy,
        )
        # capacity reference (not primary KPI)
        _ = compute_home_patient_targets(
            snap,
            regional_visit_patients=total_adj,
            regional_home_patients=home_adj,
            home_share=demand.home_share_used,
            physician_fte=fte,
            clinic_tier="specialty",
        )

        home = act["home"]
        fac = act["facility"]
        total = home + fac
        target = acq.acquisition_target_home
        note = ""
        if home >= acq.acquisition_stretch_home:
            note = "stretch以上（既に高実績）"
        elif home >= target:
            note = "目標達成"
        elif home >= acq.acquisition_floor_home:
            note = "フロア以上・目標未達"
        else:
            note = "フロア未達（優先獲得）"

        rows.append(
            ActualVsKpiRow(
                clinic=clinic.name,
                alias=act["alias"],
                actual_facility=fac,
                actual_home=home,
                actual_total=total,
                actual_home_share=round(home / total, 3) if total else 0.0,
                acquisition_floor_home=acq.acquisition_floor_home,
                acquisition_target_home=target,
                acquisition_stretch_home=acq.acquisition_stretch_home,
                competitive_home=round(acq.competitive_home, 1),
                gap_vs_target=home - target,
                gap_vs_floor=home - acq.acquisition_floor_home,
                attainment_vs_target=round(home / target, 3) if target else 0.0,
                competition_label=acq.competition_label,
                competitors_clinics=snap.home_support_clinics,
                competitors_hospitals=snap.home_support_hospitals,
                demand_home_adjusted=round(home_adj, 1),
                physician_fte=fte,
                note=note,
            )
        )
    return rows


def rows_to_public_summary(rows: List[ActualVsKpiRow]) -> dict:
    """公開用: 生の実績人数を出さず、ギャップ符号と達成帯のみ。"""
    bands = {
        "stretch以上（既に高実績）": 0,
        "目標達成": 0,
        "フロア以上・目標未達": 0,
        "フロア未達（優先獲得）": 0,
    }
    gaps = []
    for r in rows:
        bands[r.note] = bands.get(r.note, 0) + 1
        gaps.append(
            {
                "clinic": r.clinic,
                "gap_vs_target_sign": (
                    "over" if r.gap_vs_target > 0 else "at" if r.gap_vs_target == 0 else "under"
                ),
                "attainment_band": r.note,
                "competition_label": r.competition_label,
                "acquisition_target_home": r.acquisition_target_home,
                "acquisition_floor_home": r.acquisition_floor_home,
                "acquisition_stretch_home": r.acquisition_stretch_home,
            }
        )
    return {
        "metric": "home_patients_vs_acquisition_target",
        "n_clinics": len(rows),
        "band_counts": bands,
        "clinics": gaps,
    }


def write_confidential_report(rows: List[ActualVsKpiRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metric": "actual patients vs acquisition KPI",
        "rows": [asdict(r) for r in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
