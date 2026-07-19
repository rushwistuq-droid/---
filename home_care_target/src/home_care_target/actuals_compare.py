"""実績患者数と取得KPIの差分比較。

機密実績は analysis/confidential/ または環境変数 ACTUALS_PATH から読む。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .pipeline import analyze_all_wakasa
from .wakasa_demo_data import CLINIC_ALIASES

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
    gap_vs_target: int
    gap_vs_floor: int
    attainment_vs_target: float
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
    rows: List[ActualVsKpiRow] = []
    for a in analyze_all_wakasa(prefer_points=prefer_points):
        if a.clinic not in actuals:
            continue
        act = actuals[a.clinic]
        home = act["home"]
        fac = act["facility"]
        total = home + fac
        target = a.kpi_target_home
        if home >= a.acquisition.acquisition_stretch_home:
            note = "stretch以上（既に高実績）"
        elif home >= target:
            note = "目標達成"
        elif home >= a.acquisition.acquisition_floor_home:
            note = "フロア以上・目標未達"
        else:
            note = "フロア未達（優先獲得）"

        rows.append(
            ActualVsKpiRow(
                clinic=a.clinic,
                alias=act["alias"],
                actual_facility=fac,
                actual_home=home,
                actual_total=total,
                actual_home_share=round(home / total, 3) if total else 0.0,
                acquisition_floor_home=a.acquisition.acquisition_floor_home,
                acquisition_target_home=target,
                acquisition_stretch_home=a.acquisition.acquisition_stretch_home,
                competitive_home=round(a.acquisition.competitive_home, 1),
                gap_vs_target=home - target,
                gap_vs_floor=home - a.acquisition.acquisition_floor_home,
                attainment_vs_target=round(home / target, 3) if target else 0.0,
                competition_label=a.acquisition.competition_label,
                competitors_clinics=a.competitors_clinics,
                competitors_hospitals=a.competitors_hospitals,
                demand_home_adjusted=a.demand_home_adjusted,
                physician_fte=a.physician_fte,
                note=note,
            )
        )
    return rows


def rows_to_public_summary(rows: List[ActualVsKpiRow]) -> dict:
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
