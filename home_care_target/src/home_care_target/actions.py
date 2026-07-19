"""院別アクション設計: KPIギャップ → 月次新規・紹介経路。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .actuals_compare import load_actuals
from .pipeline import ClinicAnalysis, analyze_all_wakasa


REFERRAL_PLAYBOOK = {
    "低（獲得しやすい）": [
        {"channel": "居宅介護支援（CM）", "share": 0.45, "note": "新規開拓の主戦場。未取引事業所のリスト化"},
        {"channel": "病院退院調整", "share": 0.35, "note": "近隣病院の地域連携室へ定期訪問"},
        {"channel": "訪問看護", "share": 0.20, "note": "看護→医師の紹介ルートを月次KPI化"},
    ],
    "中": [
        {"channel": "居宅介護支援（CM）", "share": 0.40, "note": "既存CMの深度＋新規の選択と集中"},
        {"channel": "病院退院調整", "share": 0.35, "note": "退院時許諾の獲得率を追跡"},
        {"channel": "訪問看護", "share": 0.25, "note": "グループ訪看との本院水準連携"},
    ],
    "高": [
        {"channel": "居宅介護支援（CM）", "share": 0.35, "note": "施設偏重から居宅CMへシフト"},
        {"channel": "病院退院調整", "share": 0.30, "note": "グループ内エリア分担を明確化"},
        {"channel": "訪問看護", "share": 0.25, "note": "紹介元の質を優先"},
        {"channel": "自院外来・施設転換", "share": 0.10, "note": "施設患者の居宅移行・外来からの在宅化"},
    ],
    "非常に高（シェア拡大が難しい）": [
        {"channel": "居宅介護支援（CM）", "share": 0.30, "note": "高単価・重症寄りに絞る"},
        {"channel": "病院退院調整", "share": 0.25, "note": "特定病院との固定ルート"},
        {"channel": "訪問看護", "share": 0.25, "note": "既存連携の維持"},
        {"channel": "自院外来・施設転換", "share": 0.20, "note": "奪い合いより自院パイプライン"},
    ],
}


@dataclass
class ClinicActionPlan:
    clinic: str
    alias: str
    priority: int
    competition_label: str
    actual_home: Optional[int]
    kpi_target: int
    kpi_floor: int
    kpi_stretch: int
    gap_to_target: Optional[int]
    gap_to_stretch: Optional[int]
    months: int
    monthly_new_to_target: Optional[float]
    monthly_new_to_stretch: Optional[float]
    status: str
    referral_mix: List[Dict[str, Any]]
    actions: List[str]


def _playbook_key(label: str) -> str:
    if label.startswith("低"):
        return "低（獲得しやすい）"
    if label.startswith("非常に高"):
        return "非常に高（シェア拡大が難しい）"
    if label.startswith("高"):
        return "高"
    return "中"


def _priority_score(home: Optional[int], floor: int, target: int, stretch: int) -> int:
    if home is None:
        return 50
    if home < floor:
        return 1000 + (floor - home)
    if home < target:
        return 500 + (target - home)
    if home < stretch:
        return 100
    return 10


def build_action_plans(
    *,
    analyses: Optional[List[ClinicAnalysis]] = None,
    months: int = 12,
    actuals_path: Optional[Path] = None,
) -> List[ClinicActionPlan]:
    analyses = analyses or analyze_all_wakasa()
    try:
        actuals = load_actuals(actuals_path)
    except FileNotFoundError:
        actuals = {}

    drafts: List[tuple[int, ClinicActionPlan]] = []
    for a in analyses:
        act = actuals.get(a.clinic)
        home = int(act["home"]) if act else None
        target = a.kpi_target_home
        floor = a.acquisition.acquisition_floor_home
        stretch = a.acquisition.acquisition_stretch_home
        gap_t = (home - target) if home is not None else None
        gap_s = (home - stretch) if home is not None else None

        if home is None:
            status = "実績未登録"
            monthly_t = monthly_s = None
        elif home >= stretch:
            status = "stretch以上（維持・質向上）"
            monthly_t = monthly_s = 0.0
        elif home >= target:
            status = "目標達成（伸長挑戦）"
            monthly_t = 0.0
            monthly_s = max(0.0, (stretch - home) / months)
        elif home >= floor:
            status = "フロア以上・目標未達"
            monthly_t = max(0.0, (target - home) / months)
            monthly_s = max(0.0, (stretch - home) / months)
        else:
            status = "フロア未達（優先獲得）"
            monthly_t = max(0.0, (target - home) / months)
            monthly_s = max(0.0, (stretch - home) / months)

        mix = REFERRAL_PLAYBOOK[_playbook_key(a.acquisition.competition_label)]
        actions: List[str] = []
        if status.startswith("フロア未達"):
            actions.append(f"今後{months}ヶ月で月平均{monthly_t:.1f}人の居宅新規が必要（目標到達）")
            actions.append("未取引CM事業所の開拓リストを週次で回す")
            actions.append("近隣病院の地域連携室へ定期訪問し退院時許諾をKPI化")
        elif status.startswith("フロア以上"):
            actions.append(f"月平均{monthly_t:.1f}人の新規で獲得KPI到達")
            actions.append("紹介経路の構成比をプレイブックに寄せる（施設偏重の是正）")
        elif status.startswith("目標達成"):
            actions.append(f"伸長まで月平均{monthly_s:.1f}人（任意）")
            actions.append("既存パイプラインの質（重症・継続）を優先")
        else:
            actions.append("獲得KPIは超過済み。維持と紹介元の質、グループ内重複の整理")

        if a.acquisition.competition_label.startswith("高"):
            actions.append("16km圏の自グループ院と退院調整・CMエリアを分担")

        plan = ClinicActionPlan(
            clinic=a.clinic,
            alias=a.alias,
            priority=0,
            competition_label=a.acquisition.competition_label,
            actual_home=home,
            kpi_target=target,
            kpi_floor=floor,
            kpi_stretch=stretch,
            gap_to_target=gap_t,
            gap_to_stretch=gap_s,
            months=months,
            monthly_new_to_target=round(monthly_t, 2) if monthly_t is not None else None,
            monthly_new_to_stretch=round(monthly_s, 2) if monthly_s is not None else None,
            status=status,
            referral_mix=mix,
            actions=actions,
        )
        drafts.append((_priority_score(home, floor, target, stretch), plan))

    drafts.sort(key=lambda x: -x[0])
    out: List[ClinicActionPlan] = []
    for i, (_, p) in enumerate(drafts, 1):
        p.priority = i
        out.append(p)
    return out


def public_action_summary(plans: List[ClinicActionPlan]) -> Dict[str, Any]:
    rows = []
    for p in plans:
        rows.append(
            {
                "priority": p.priority,
                "clinic": p.clinic,
                "alias": p.alias,
                "status": p.status,
                "competition_label": p.competition_label,
                "kpi_target": p.kpi_target,
                "monthly_new_to_target": p.monthly_new_to_target,
                "referral_channels": [c["channel"] for c in p.referral_mix],
                "actions": p.actions,
                "gap_sign": (
                    None
                    if p.gap_to_target is None
                    else "over"
                    if p.gap_to_target > 0
                    else "at"
                    if p.gap_to_target == 0
                    else "under"
                ),
            }
        )
    return {"months": plans[0].months if plans else 12, "plans": rows}


def write_action_plans(
    confidential_path: Path,
    public_path: Path,
    *,
    months: int = 12,
) -> List[ClinicActionPlan]:
    plans = build_action_plans(months=months)
    confidential_path.parent.mkdir(parents=True, exist_ok=True)
    confidential_path.write_text(
        json.dumps({"plans": [asdict(p) for p in plans]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(
        json.dumps(public_action_summary(plans), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plans
