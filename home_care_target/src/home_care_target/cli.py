"""CLI: 地域の在支診・在支病集計と居宅患者目標を出力."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from home_care_target.catchment import aggregate_catchment_supply
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets
from home_care_target.wakasa_demo_data import CLINICS, MUNICIPALITIES, PHYSICIAN_FTE


def run_demo(as_json: bool = False) -> int:
    munis = list(MUNICIPALITIES.values())
    rows = []
    for clinic in CLINICS:
        supply = aggregate_catchment_supply(clinic, munis)
        snap = SupplySnapshot.from_catchment(supply)
        fte = PHYSICIAN_FTE.get(clinic.name)
        target = compute_home_patient_targets(snap, physician_fte=fte)
        rows.append(
            {
                "clinic": clinic.name,
                "radius_km": clinic.radius_km,
                "municipalities": len(supply.municipalities),
                "home_support_clinics": supply.home_support_clinics,
                "home_support_hospitals": supply.home_support_hospitals,
                "clinic_enhanced": supply.clinic_enhanced,
                "hospital_enhanced": supply.hospital_enhanced,
                "supply_units": supply.supply_units,
                "elderly_65": supply.weighted_elderly_65,
                "avg_patients_local_proxy": supply.avg_patients_local_proxy,
                "density_per_100k_elderly": target.density_clinics_per_100k_elderly,
                "regional_home_patients": target.regional_home_patients,
                "fair_share_home": target.fair_share_home,
                "capacity_baseline_home": target.capacity_baseline_home,
                "capacity_active_home": target.capacity_active_home,
                "capacity_local_home": target.capacity_local_home,
                "recommended_short_term_home": target.recommended_short_term_home,
                "recommended_mid_term_home": target.recommended_mid_term_home,
                "physician_fte": fte,
                "sources": supply.sources,
            }
        )

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 110)
    print("在宅支援診療所・在宅支援病院の精密集計 → 居宅患者目標")
    print("供給: JMAP市区町村別（厚生局届出系） / 能力: 厚労省医療施設調査R5 / 需要: 65歳×4.5%×居宅シェア42.1%")
    print("=" * 110)
    hdr = (
        f"{'院名':<22} {'在支診':>7} {'在支病':>6} {'供給U':>7} "
        f"{'按分居宅':>8} {'能力基準':>8} {'活動層':>7} {'短期目標':>8} {'中期目標':>8}"
    )
    print(hdr)
    print("-" * 110)
    for r in rows:
        short = r["clinic"].replace("わかさクリニック", "")
        print(
            f"{short:<22} {r['home_support_clinics']:>7.1f} {r['home_support_hospitals']:>6.1f} "
            f"{r['supply_units']:>7.1f} {r['fair_share_home']:>8} {r['capacity_baseline_home']:>8} "
            f"{r['capacity_active_home']:>7} {r['recommended_short_term_home']:>8} "
            f"{r['recommended_mid_term_home']:>8}"
        )
    print()
    print("詳細（ひばりが丘）:")
    hibari = next(r for r in rows if "ひばりが丘" in r["clinic"])
    for k, v in hibari.items():
        print(f"  {k}: {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="居宅患者目標計算")
    parser.add_argument("--json", action="store_true", help="JSON出力")
    parser.add_argument(
        "--demo",
        action="store_true",
        default=True,
        help="わかさクリニック12院デモ（既定）",
    )
    args = parser.parse_args(argv)
    return run_demo(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
