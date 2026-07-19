"""在支診・在支病の供給スナップショットと居宅患者目標の算出."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from .catchment import CatchmentSupply
from .data_loader import load_constants


@dataclass
class SupplySnapshot:
    """地域の在宅支援供給。"""

    home_support_clinics: float
    home_support_hospitals: float
    supply_units: float
    clinic_enhanced: float = 0.0
    hospital_enhanced: float = 0.0
    avg_patients_per_clinic: Optional[float] = None
    patients_managed_total: Optional[float] = None
    elderly_65: Optional[float] = None
    sources: list[str] = field(default_factory=list)

    @classmethod
    def from_catchment(cls, supply: CatchmentSupply) -> "SupplySnapshot":
        return cls(
            home_support_clinics=supply.home_support_clinics,
            home_support_hospitals=supply.home_support_hospitals,
            supply_units=supply.supply_units,
            clinic_enhanced=supply.clinic_enhanced,
            hospital_enhanced=supply.hospital_enhanced,
            avg_patients_per_clinic=supply.avg_patients_local_proxy,
            patients_managed_total=supply.patients_managed_proxy,
            elderly_65=supply.weighted_elderly_65,
            sources=list(supply.sources),
        )


@dataclass
class HomePatientTargetResult:
    """居宅患者の目標水準（1拠点あたり）。"""

    # 需要側
    regional_visit_patients: float
    regional_home_patients: float
    home_share: float

    # 供給側
    home_support_clinics: float
    home_support_hospitals: float
    supply_units: float

    # 目標（居宅）
    fair_share_home: int
    capacity_baseline_home: int
    capacity_active_home: int
    capacity_local_home: Optional[int]
    capacity_enhanced_home: int
    recommended_short_term_home: int
    recommended_mid_term_home: int

    # 参考（総患者＝居宅+施設）
    fair_share_total: int
    capacity_baseline_total: int
    capacity_active_total: int

    # メタ
    density_clinics_per_100k_elderly: Optional[float]
    notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    assumptions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _estimate_visit_demand(
    elderly_65: Optional[float],
    regional_visit_patients: Optional[float],
    regional_home_patients: Optional[float],
    home_share: float,
    elderly_rate: float,
) -> tuple[float, float, list[str]]:
    notes: list[str] = []
    if regional_home_patients is not None and regional_visit_patients is None:
        visit = regional_home_patients / max(home_share, 1e-6)
        home = float(regional_home_patients)
        notes.append("居宅需要の外部入力から総訪問診療需要を逆算")
        return visit, home, notes
    if regional_visit_patients is not None:
        visit = float(regional_visit_patients)
        home = (
            float(regional_home_patients)
            if regional_home_patients is not None
            else visit * home_share
        )
        notes.append("訪問診療需要の外部入力を使用（並行の需要推定ロジックと接続可能）")
        return visit, home, notes
    if elderly_65 is None or elderly_65 <= 0:
        raise ValueError(
            "regional_visit_patients / regional_home_patients / elderly_65 のいずれかが必要です"
        )
    visit = float(elderly_65) * elderly_rate
    home = visit * home_share
    notes.append(
        f"需要フォールバック: 65歳以上×{elderly_rate:.1%}（厚労省系推計で用いられる粗い係数）"
    )
    return visit, home, notes


def compute_home_patient_targets(
    supply: SupplySnapshot,
    *,
    regional_visit_patients: Optional[float] = None,
    regional_home_patients: Optional[float] = None,
    home_share: Optional[float] = None,
    strategic_home_ratio: float = 0.60,
    physician_fte: Optional[float] = None,
) -> HomePatientTargetResult:
    """
    在支診・在支病の供給と地域需要から、1拠点あたりの居宅患者目標を計算する。

    目標の考え方
    ------------
    1. 競合按分 (fair share) … 参照値
       地域の居宅需要 ÷ (在支診 + 在支病×重み)
       需要の居宅化には市場の home_share（NDB同一建物以外, 既定42.1%）を用いる
    2. 施設能力ベンチマーク (capacity) … 運営目標の主軸
       厚労省医療施設調査の在支診受け持ち患者数（総数）に、
       訪問特化拠点向けの strategic_home_ratio（既定60%）を乗じて居宅目標化
    3. 推奨
       短期 = 活動層総患者 × strategic_home_ratio
       中期 = max(活動層, 二次医療圏平均) × strategic_home_ratio
       医師FTEがある場合は 100人/FTE 程度で上限
    """
    constants = load_constants()
    mix = constants["mix"]
    cap = constants["capacity_benchmarks"]
    demand_fb = constants["demand_fallback"]
    if home_share is None:
        home_share = float(mix["home_share_of_visit_patients"])

    visit, home, notes = _estimate_visit_demand(
        supply.elderly_65,
        regional_visit_patients,
        regional_home_patients,
        home_share,
        float(demand_fb["elderly65_visit_rate"]),
    )

    units = max(float(supply.supply_units), 1.0)
    fair_total = visit / units
    fair_home = home / units

    baseline_total = float(cap["t108_mean_patients"])
    active_total = float(cap["active_mean_patients_ge20"])
    enhanced_total = float(cap["enhanced_proxy_patients"])
    local_total = supply.avg_patients_per_clinic

    # 市場平均ミックスでの居宅換算（参照）
    baseline_home_market = baseline_total * home_share
    active_home_market = active_total * home_share
    local_home_market = local_total * home_share if local_total is not None else None

    # 訪問特化拠点の戦略ミックスでの居宅目標
    baseline_home = baseline_total * strategic_home_ratio
    active_home = active_total * strategic_home_ratio
    enhanced_home = enhanced_total * strategic_home_ratio
    local_home = local_total * strategic_home_ratio if local_total is not None else None

    short = max(baseline_home, active_home)
    mid = max(short, local_home or short)
    if local_home is not None:
        notes.append(
            f"二次医療圏の在支診平均患者数 {local_total:.1f} 人 × 戦略居宅比 "
            f"{strategic_home_ratio:.0%} を中期目標に反映"
        )
    notes.append(
        f"市場按分（参照）は居宅 {fair_home:.0f} 人 / 市場ミックス換算の活動層は "
        f"{active_home_market:.0f} 人"
    )

    # 医師FTEがある場合は過大目標を抑制（訪問特化の目安: 居宅100人/FTE）
    if physician_fte and physician_fte > 0:
        per_fte_cap = 100.0
        short = min(short, physician_fte * per_fte_cap)
        mid = min(mid, physician_fte * per_fte_cap * 1.2)
        notes.append(
            f"医師FTE {physician_fte} による上限（居宅目安 {per_fte_cap:.0f}人/FTE）を適用"
        )

    density = None
    if supply.elderly_65 and supply.elderly_65 > 0:
        density = supply.home_support_clinics / supply.elderly_65 * 100_000

    sources = list(supply.sources)
    sources.extend(
        [
            constants["sources"]["medical_facility_survey_r5"]["name"],
            constants["sources"]["facility_standard_notifications"]["name"],
            constants["sources"]["ndb_home_share"]["name"],
        ]
    )

    notes.append(
        "在支病は医療施設調査に専用の患者数表がないため、供給ユニットとして在支診と等重量（概況の"
        "施設当たり訪問件数が近似）で競合按分に算入"
    )
    notes.append(
        f"需要側の居宅シェア {home_share:.1%} は NDB 同一建物以外比率。"
        f"目標側の戦略居宅比 {strategic_home_ratio:.0%} は訪問特化拠点のミックス仮定"
    )

    return HomePatientTargetResult(
        regional_visit_patients=round(visit, 1),
        regional_home_patients=round(home, 1),
        home_share=home_share,
        home_support_clinics=supply.home_support_clinics,
        home_support_hospitals=supply.home_support_hospitals,
        supply_units=round(units, 2),
        fair_share_home=int(round(fair_home)),
        capacity_baseline_home=int(round(baseline_home)),
        capacity_active_home=int(round(active_home)),
        capacity_local_home=int(round(local_home)) if local_home is not None else None,
        capacity_enhanced_home=int(round(enhanced_home)),
        recommended_short_term_home=int(round(short)),
        recommended_mid_term_home=int(round(mid)),
        fair_share_total=int(round(fair_total)),
        capacity_baseline_total=int(round(baseline_total)),
        capacity_active_total=int(round(active_total)),
        density_clinics_per_100k_elderly=round(density, 1) if density is not None else None,
        notes=notes,
        sources=sources,
        assumptions={
            "t108_mean_patients": baseline_total,
            "t168_active_mean_ge20": active_total,
            "t168_enhanced_proxy": enhanced_total,
            "market_home_share": home_share,
            "strategic_home_ratio": strategic_home_ratio,
            "capacity_baseline_home_market_mix": round(baseline_home_market, 1),
            "capacity_active_home_market_mix": round(active_home_market, 1),
            "capacity_local_home_market_mix": round(local_home_market, 1)
            if local_home_market is not None
            else None,
            "hospital_weight": constants["supply_weights"]["home_support_hospital"],
            "national_home_support_clinics": constants["national"]["home_support_clinics"],
            "national_home_support_hospitals": constants["national"][
                "home_support_hospitals_2023_07"
            ],
        },
    )
