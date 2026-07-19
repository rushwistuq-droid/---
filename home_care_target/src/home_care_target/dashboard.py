"""経営ダッシュボード: 獲得KPI / 能力上限 / 実績達成率の3本柱。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .actuals_compare import load_actuals
from .pipeline import ClinicAnalysis, analyze_all_wakasa


def build_dashboard(
    analyses: Optional[List[ClinicAnalysis]] = None,
    *,
    actuals_path: Optional[Path] = None,
    include_actuals: bool = True,
) -> Dict[str, Any]:
    analyses = analyses or analyze_all_wakasa()
    actuals = {}
    if include_actuals:
        try:
            actuals = load_actuals(actuals_path)
        except FileNotFoundError:
            actuals = {}

    rows = []
    for a in analyses:
        row = a.management_row()
        act = actuals.get(a.clinic)
        if act:
            home = int(act["home"])
            target = a.kpi_target_home or 1
            row["actual_home"] = home
            row["actual_facility"] = int(act["facility"])
            row["attainment_vs_kpi"] = round(home / target, 3)
            row["gap_vs_kpi"] = home - target
            if home >= a.acquisition.acquisition_stretch_home:
                row["status"] = "stretch以上"
            elif home >= target:
                row["status"] = "目標達成"
            elif home >= a.acquisition.acquisition_floor_home:
                row["status"] = "フロア以上・目標未達"
            else:
                row["status"] = "フロア未達"
        else:
            row["status"] = "実績未登録"
        rows.append(row)

    # 経営固定指標の説明
    meta = {
        "columns": {
            "acquisition_kpi_home": "短期目標＝獲得KPI（競合加味・本命）",
            "capacity_cap_home": "能力上限（specialty/地域平均×戦略居宅比）",
            "attainment_vs_kpi": "実績居宅 ÷ 獲得KPI",
            "acquisition_stretch_home": "伸長目標",
        },
        "policy": "短期=獲得KPI / 伸長=stretch / 能力のみの旧短期は参考",
    }
    return {"meta": meta, "n_clinics": len(rows), "rows": rows}


def public_dashboard(dash: Dict[str, Any]) -> Dict[str, Any]:
    """生実績人数を除いた公開用ダッシュボード。"""
    rows = []
    for r in dash["rows"]:
        pub = {
            "clinic": r["clinic"],
            "alias": r["alias"],
            "acquisition_kpi_home": r["acquisition_kpi_home"],
            "acquisition_floor_home": r["acquisition_floor_home"],
            "acquisition_stretch_home": r["acquisition_stretch_home"],
            "capacity_cap_home": r["capacity_cap_home"],
            "capacity_specialty_home": r["capacity_specialty_home"],
            "fte_cap_home": r["fte_cap_home"],
            "competition_label": r["competition_label"],
            "status": r.get("status"),
        }
        if "attainment_vs_kpi" in r:
            pub["attainment_vs_kpi"] = r["attainment_vs_kpi"]
            pub["gap_vs_kpi_sign"] = (
                "over" if r["gap_vs_kpi"] > 0 else "at" if r["gap_vs_kpi"] == 0 else "under"
            )
        rows.append(pub)
    return {"meta": dash["meta"], "n_clinics": len(rows), "rows": rows}


def write_dashboard(
    path: Path,
    *,
    public_path: Optional[Path] = None,
) -> Dict[str, Any]:
    dash = build_dashboard()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
    if public_path:
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_text(
            json.dumps(public_dashboard(dash), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return dash
