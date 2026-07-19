"""CLI: 精度強化版 — 在支診/在支病精密集計と居宅患者目標。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

        rows.append(
            {
                "clinic": clinic.name,
                "radius_km": clinic.radius_km,
                "supply_method": snap.supply_method,
                "home_support_clinics": snap.home_support_clinics,
                "home_support_hospitals": snap.home_support_hospitals,
                "hospital_weight": snap.hospital_weight,
                "supply_units": snap.supply_units,
                "elderly_65": demand.elderly_65,
                "home_share_regional": demand.home_share_used,
                "demand_visit_total": demand.visit_patients_total,
                "demand_home_raw": demand.recommended_home_patients,
                "demand_home_overlap_adjusted": home_adj,
                "group_overlap_share": round(overlap_share, 3),
                "fair_share_home": target.fair_share_home,
                "capacity_baseline_home": target.capacity_baseline_home,
                "capacity_active_home": target.capacity_active_home,
                "capacity_specialty_home": target.capacity_specialty_home,
                "capacity_local_home": target.capacity_local_home,
                "recommended_short_term_home": target.recommended_short_term_home,
                "recommended_mid_term_home": target.recommended_mid_term_home,
                "recommended_stretch_home": target.recommended_stretch_home,
                "physician_fte": fte,
                "notes": target.notes,
            }
        )

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 120)
    print("精度強化版: 在支診・在支病 × NDB需要 × 居宅患者目標")
    print(
        "需要: NDB年齢別受療率+都道府県居宅シェア / 供給: 施設点(優先)+病院ウェイト / "
        "重み: 円交差 / 重複: グループ按分 / 能力: 訪問特化ティア"
    )
    print("=" * 120)
    hdr = (
        f"{'院名':<18} {'在支診':>6} {'在支病':>5} {'Hw':>4} {'需要居宅':>8} "
        f"{'按分':>5} {'短期':>5} {'中期':>5} {'伸長':>5} {'重複':>5}"
    )
    print(hdr)
    print("-" * 120)
    for r in rows:
        short = r["clinic"].replace("わかさクリニック", "")
        print(
            f"{short:<18} {r['home_support_clinics']:>6.0f} {r['home_support_hospitals']:>5.0f} "
            f"{r['hospital_weight']:>4.2f} {r['demand_home_overlap_adjusted']:>8.0f} "
            f"{r['fair_share_home']:>5} {r['recommended_short_term_home']:>5} "
            f"{r['recommended_mid_term_home']:>5} {r['recommended_stretch_home']:>5} "
            f"{r['group_overlap_share']:>5.2f}"
        )
    print()
    hibari = next(r for r in rows if "ひばりが丘" in r["clinic"])
    print("詳細（ひばりが丘）:")
    for k, v in hibari.items():
        if k != "notes":
            print(f"  {k}: {v}")
    print("  notes:")
    for n in hibari["notes"]:
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
    args = parser.parse_args(argv)
    return run_demo(as_json=args.json, prefer_points=not args.municipal_only)


if __name__ == "__main__":
    raise SystemExit(main())
