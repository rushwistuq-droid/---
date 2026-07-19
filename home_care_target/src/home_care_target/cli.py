"""CLI: 精度強化版 — 在支診/在支病精密集計と居宅患者目標。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from home_care_target.acquisition import compute_acquisition_indicator
from home_care_target.catchment import aggregate_catchment_supply
from home_care_target.demand import estimate_demand_for_catchment
from home_care_target.facilities import (
    adjusted_demand,
    count_facilities_in_radius,
    hospital_weight_for_prefs,
    load_facility_points,
)
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets
from home_care_target.wakasa_demo_data import CLINICS, MUNICIPALITIES, PHYSICIAN_FTE


def run_demo(as_json: bool = False, prefer_points: bool = True) -> int:
    munis = list(MUNICIPALITIES.values())
    points = load_facility_points()
    clinic_xy = [(c.name, c.lat, c.lon) for c in CLINICS]
    rows = []

    for clinic in CLINICS:
        # municipal aggregate (always) for demographics / secondary averages
        muni_supply = aggregate_catchment_supply(clinic, munis)
        prefs = {MUNICIPALITIES[n].pref for n in muni_supply.municipalities if n in MUNICIPALITIES}
        hw = hospital_weight_for_prefs(prefs)

        # demand via NDB age bands + regional home share
        demand = estimate_demand_for_catchment(
            clinic.lat, clinic.lon, munis, radius_km=clinic.radius_km
        )

        # supply: prefer facility points when available
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
            # if point count is empty (data gap), fall back
            if point_supply.clinics + point_supply.hospitals < 1:
                snap = SupplySnapshot.from_catchment(muni_supply, hospital_weight=hw)
                snap.elderly_65 = demand.elderly_65
        else:
            snap = SupplySnapshot.from_catchment(muni_supply, hospital_weight=hw)
            snap.elderly_65 = demand.elderly_65

        home_adj, total_adj, overlap_share = adjusted_demand(
            demand.recommended_home_patients,
            demand.visit_patients_total,
            clinic.name,
            clinic_xy,
        )

        fte = PHYSICIAN_FTE.get(clinic.name)
        target = compute_home_patient_targets(
            snap,
            regional_visit_patients=total_adj,
            regional_home_patients=home_adj,
            home_share=demand.home_share_used,
            physician_fte=fte,
            group_overlap_share=None,  # already applied in adjusted_demand
            clinic_tier="specialty",
        )
        # stash overlap for display
        target.group_overlap_share = overlap_share

        acq = compute_acquisition_indicator(
            regional_home_demand=home_adj,
            regional_visit_demand=total_adj,
            competitors_clinics=snap.home_support_clinics,
            competitors_hospitals=snap.home_support_hospitals,
            hospital_weight=snap.hospital_weight,
            physician_fte=fte,
            local_avg_total_patients=muni_supply.avg_patients_local_proxy,
        )

        rows.append(
            {
                "clinic": clinic.name,
                "radius_km": clinic.radius_km,
                "supply_method": snap.supply_method,
                "competitors_clinics": snap.home_support_clinics,
                "competitors_hospitals": snap.home_support_hospitals,
                "hospital_weight": snap.hospital_weight,
                "raw_supply_units": acq.raw_supply_units,
                "effective_supply_units": acq.effective_supply_units,
                "elderly_65": demand.elderly_65,
                "home_share_regional": demand.home_share_used,
                "demand_visit_total": demand.visit_patients_total,
                "demand_home_raw": demand.recommended_home_patients,
                "demand_home_overlap_adjusted": round(home_adj, 1),
                "group_overlap_share": round(overlap_share, 3),
                "equilibrium_home": acq.equilibrium_home,
                "competitive_home": acq.competitive_home,
                "acquisition_floor_home": acq.acquisition_floor_home,
                "acquisition_target_home": acq.acquisition_target_home,
                "acquisition_stretch_home": acq.acquisition_stretch_home,
                "competition_index": acq.competition_index,
                "competition_label": acq.competition_label,
                "capacity_specialty_home": target.capacity_specialty_home,
                "recommended_capacity_short": target.recommended_short_term_home,
                "recommended_capacity_mid": target.recommended_mid_term_home,
                "physician_fte": fte,
                "acquisition_notes": acq.notes,
                "capacity_notes": target.notes,
            }
        )

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 120)
    print("競合加味・患者獲得指標（在支診/在支病を本軸）")
    print(
        "需要: NDB年齢別+都道府県居宅シェア / 競合: 施設点×活動率0.45+病院ウェイト / "
        "KPI: 実効按分×野心度を能力・FTEで上限"
    )
    print("=" * 120)
    hdr = (
        f"{'院名':<16} {'診':>4} {'病':>3} {'実効U':>6} {'需要':>6} "
        f"{'均衡':>5} {'実効':>5} {'獲得KPI':>7} {'伸長':>5} {'競合':>4} {'判定':<10}"
    )
    print(hdr)
    print("-" * 120)
    for r in rows:
        short = r["clinic"].replace("わかさクリニック", "")
        print(
            f"{short:<16} {r['competitors_clinics']:>4.0f} {r['competitors_hospitals']:>3.0f} "
            f"{r['effective_supply_units']:>6.1f} {r['demand_home_overlap_adjusted']:>6.0f} "
            f"{r['equilibrium_home']:>5.0f} {r['competitive_home']:>5.0f} "
            f"{r['acquisition_target_home']:>7} {r['acquisition_stretch_home']:>5} "
            f"{r['competition_index']:>4.0f} {r['competition_label']:<10}"
        )
    print()
    hibari = next(r for r in rows if "ひばりが丘" in r["clinic"])
    print("詳細（ひばりが丘）:")
    for k, v in hibari.items():
        if k not in ("acquisition_notes", "capacity_notes"):
            print(f"  {k}: {v}")
    print("  acquisition_notes:")
    for n in hibari["acquisition_notes"]:
        print(f"    - {n}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="居宅患者目標計算（精度強化版）")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--municipal-only",
        action="store_true",
        help="施設点を使わず市区町村合算のみ",
    )
    parser.add_argument(
        "--compare-actuals",
        action="store_true",
        help="機密実績YAMLがあれば取得KPIとの差分サマリを出す（生実績はconfidentialのみ）",
    )
    args = parser.parse_args(argv)
    if args.compare_actuals:
        from home_care_target.actuals_compare import (
            compare_actuals_to_kpi,
            rows_to_public_summary,
        )

        try:
            rows = compare_actuals_to_kpi()
        except FileNotFoundError as e:
            print(f"実績ファイルなし: {e}")
            return 1
        pub = rows_to_public_summary(rows)
        if args.json:
            print(json.dumps(pub, ensure_ascii=False, indent=2))
        else:
            print("実績 vs 獲得KPI（公開サマリ・生実績人数は非表示）")
            for c in pub["clinics"]:
                short = c["clinic"].replace("わかさクリニック", "")
                print(
                    f"  {short:<14} target={c['acquisition_target_home']:>3} "
                    f"band={c['attainment_band']} gap={c['gap_vs_target_sign']} "
                    f"競合={c['competition_label']}"
                )
            print("band_counts:", pub["band_counts"])
        return 0
    return run_demo(as_json=args.json, prefer_points=not args.municipal_only)


if __name__ == "__main__":
    raise SystemExit(main())
