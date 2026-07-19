"""競合を本軸にした患者獲得指標。

背景
----
在支診・在支病の施設点数は供給ユニットとして既に集計している。
ただし「能力ティア目標」だけだと競合密度が目標に効かない。
本モジュールは需要÷実効競合を主軸に、能力・医師数で上限をかけた
獲得目標（attainable acquisition）を算出する。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from .data_loader import load_constants


@dataclass
class AcquisitionIndicator:
    """患者獲得の実務指標一式。"""

    # 市場
    regional_home_demand: float
    regional_visit_demand: float
    competitors_clinics: float
    competitors_hospitals: float
    hospital_weight: float
    raw_supply_units: float
    effective_supply_units: float
    active_competitor_rate: float

    # シェア系
    equilibrium_home: float  # 単純按分
    competitive_home: float  # 実効競合按分（本指標の中核）
    top_quartile_home: float  # 上位層想定（実効按分×倍率）
    market_share_equilibrium_pct: float
    market_share_competitive_pct: float

    # 制約
    capacity_cap_home: float
    fte_cap_home: Optional[float]

    # 獲得目標
    acquisition_floor_home: int  # 最低ライン（均衡按分と能力下限の高い方を抑制）
    acquisition_target_home: int  # 本命KPI
    acquisition_stretch_home: int  # 伸ばし目標
    competition_index: float  # 0-100 競合厳しさ
    competition_label: str

    notes: list[str] = field(default_factory=list)
    assumptions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _competition_label(index: float) -> str:
    if index < 30:
        return "低（獲得しやすい）"
    if index < 55:
        return "中"
    if index < 75:
        return "高"
    return "非常に高（シェア拡大が難しい）"


def compute_acquisition_indicator(
    *,
    regional_home_demand: float,
    regional_visit_demand: float,
    competitors_clinics: float,
    competitors_hospitals: float,
    hospital_weight: float = 1.0,
    physician_fte: Optional[float] = None,
    local_avg_total_patients: Optional[float] = None,
    strategic_home_ratio: float = 0.60,
    # 在支診のうち「実質的な訪問競合」とみなす割合
    # T168: 患者数判明かつ20人以上 ≈ 全在支診の約37%、判明分の活動層 ≈ 55%
    # ここでは「届出はあるが患者がごく少ない層」を除く既定 0.45
    active_competitor_rate: float = 0.45,
    # 訪問特化が実効按分に対して取りうる倍率（上位層）
    top_quartile_multiplier: float = 2.5,
    ambition_multiplier: float = 1.35,
) -> AcquisitionIndicator:
    """競合加味の獲得目標を計算する。

    核心式
    ------
    raw_units = clinics + hospitals * hospital_weight
    effective_units = clinics * active_rate + hospitals * hospital_weight
    competitive_home = regional_home_demand / effective_units

    acquisition_target = median帯 =
      clip(
        competitive_home * ambition_multiplier,
        lower=equilibrium,
        upper=min(capacity_cap, fte_cap, top_quartile)
      )
    """
    constants = load_constants()
    tiers = constants.get("capacity_tiers", {})
    cap = constants["capacity_benchmarks"]

    clinics = max(float(competitors_clinics), 0.0)
    hospitals = max(float(competitors_hospitals), 0.0)
    hw = float(hospital_weight)
    home = max(float(regional_home_demand), 0.0)
    visit = max(float(regional_visit_demand), home)

    raw_units = max(clinics + hospitals * hw, 1.0)
    effective_units = max(clinics * active_competitor_rate + hospitals * hw, 1.0)

    equilibrium = home / raw_units
    competitive = home / effective_units
    top_q = competitive * top_quartile_multiplier

    # 能力上限: 地域平均と specialty/enhanced の大きい方を居宅換算
    specialty_total = float(tiers.get("specialty_p90_total", 150.0))
    enhanced_total = float(tiers.get("enhanced_proxy_total", 200.0))
    local_total = float(local_avg_total_patients) if local_avg_total_patients else specialty_total
    capacity_cap = max(local_total, specialty_total) * strategic_home_ratio
    stretch_cap = enhanced_total * strategic_home_ratio

    per_fte = float(tiers.get("physician_home_per_fte", 100.0))
    fte_cap = physician_fte * per_fte if physician_fte and physician_fte > 0 else None

    # 競合指数: 実効供給密度（需要1000人あたりの実効競合）を0-100に正規化
    # 実効競合が需要に対して多いほど厳しい
    density = effective_units / max(home / 1000.0, 0.01)  # units per 1000 home patients
    # 経験的: 10未満=緩い, 40超=厳しい
    competition_index = max(0.0, min(100.0, (density - 5.0) / 45.0 * 100.0))

    # 獲得目標
    # floor: 均衡按分（これ未満は「市場平均以下」）
    # target: 実効按分×ambition を能力・FTEでキャップ
    # stretch: 上位倍率を能力伸長キャップで抑制
    uncapped_target = competitive * ambition_multiplier
    uncapped_stretch = top_q

    upper_target = capacity_cap
    upper_stretch = stretch_cap
    if fte_cap is not None:
        upper_target = min(upper_target, fte_cap)
        upper_stretch = min(upper_stretch, fte_cap * 1.25)

    # 競合が極めて厳しい場合、ambitionを抑える
    if competition_index >= 75:
        uncapped_target = competitive * min(ambition_multiplier, 1.15)
        uncapped_stretch = competitive * min(top_quartile_multiplier, 1.8)

    floor = min(equilibrium, competitive)  # 通常 equilibrium < competitive
    # floor は「最低でも均衡は取りに行く」だが、能力上限は超えない
    floor = min(floor, upper_target)
    target = max(floor, min(uncapped_target, upper_target))
    stretch = max(target, min(uncapped_stretch, upper_stretch))

    notes = [
        f"単純按分 = 居宅需要 {home:.0f} ÷ 生供給 {raw_units:.1f} = {equilibrium:.1f}",
        f"実効按分 = 居宅需要 {home:.0f} ÷ 実効競合 {effective_units:.1f} "
        f"(在支診×{active_competitor_rate:.0%}+在支病×{hw:.2f}) = {competitive:.1f}",
        f"獲得目標は実効按分×{ambition_multiplier:.2f}を能力/FTEで上限クリップ",
        "在支診の多くは患者規模が小さいため、全届出数での単純割りは過小評価になる",
        f"競合指数 {competition_index:.0f}/100（需要1000人あたり実効競合 {density:.1f}）",
    ]
    if fte_cap is not None:
        notes.append(f"医師FTE上限 {fte_cap:.0f}人（{physician_fte}×{per_fte:.0f}）")

    return AcquisitionIndicator(
        regional_home_demand=round(home, 1),
        regional_visit_demand=round(visit, 1),
        competitors_clinics=round(clinics, 1),
        competitors_hospitals=round(hospitals, 1),
        hospital_weight=round(hw, 3),
        raw_supply_units=round(raw_units, 2),
        effective_supply_units=round(effective_units, 2),
        active_competitor_rate=active_competitor_rate,
        equilibrium_home=round(equilibrium, 1),
        competitive_home=round(competitive, 1),
        top_quartile_home=round(top_q, 1),
        market_share_equilibrium_pct=round(100.0 * equilibrium / home, 3) if home else 0.0,
        market_share_competitive_pct=round(100.0 * competitive / home, 3) if home else 0.0,
        capacity_cap_home=round(capacity_cap, 1),
        fte_cap_home=round(fte_cap, 1) if fte_cap is not None else None,
        acquisition_floor_home=int(round(floor)),
        acquisition_target_home=int(round(target)),
        acquisition_stretch_home=int(round(stretch)),
        competition_index=round(competition_index, 1),
        competition_label=_competition_label(competition_index),
        notes=notes,
        assumptions={
            "active_competitor_rate": active_competitor_rate,
            "top_quartile_multiplier": top_quartile_multiplier,
            "ambition_multiplier": ambition_multiplier,
            "strategic_home_ratio": strategic_home_ratio,
            "t168_note": "active_competitor_rateは医療施設調査T168の活動層比率に基づく既定値",
        },
    )
