"""CLI: 院ID/座標 → 需要＋獲得KPI、ダッシュボード、アクション。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from home_care_target.actions import build_action_plans, public_action_summary, write_action_plans
from home_care_target.actuals_compare import compare_actuals_to_kpi, rows_to_public_summary
from home_care_target.dashboard import build_dashboard, public_dashboard, write_dashboard
from home_care_target.pipeline import analyze_all_wakasa, analyze_clinic, resolve_clinic


def _print_analysis(a, as_json: bool) -> None:
    if as_json:
        print(json.dumps(a.to_dict(), ensure_ascii=False, indent=2))
        return
    print("=" * 72)
    print(f"{a.clinic}（{a.alias}） r={a.radius_km}km FTE={a.physician_fte}")
    print("-" * 72)
    print(f"  需要居宅（重複補正）: {a.demand_home_adjusted:.0f}")
    print(f"  競合 在支診/病: {a.competitors_clinics:.0f} / {a.competitors_hospitals:.0f}")
    print(f"  機能強化型推定/従来型: {a.clinic_enhanced_est:.0f} / {a.clinic_standard_est:.0f}")
    print(f"  実効供給ユニット: {a.acquisition.effective_supply_units:.1f}")
    print(f"  競合: {a.acquisition.competition_label} ({a.acquisition.competition_index:.0f})")
    print()
    print("  【経営3本柱】")
    print(f"    獲得KPI（短期）: {a.kpi_target_home}")
    print(f"    能力上限:        {a.capacity_cap_home:.0f}（specialty {a.capacity.capacity_specialty_home}）")
    print(f"    FTE上限:         {a.fte_cap_home}")
    print(f"    フロア / 伸長:   {a.acquisition.acquisition_floor_home} / {a.acquisition.acquisition_stretch_home}")
    print()
    for n in a.notes[:4]:
        print(f"  - {n}")


def run_demo(as_json: bool = False, prefer_points: bool = True) -> int:
    rows = []
    for a in analyze_all_wakasa(prefer_points=prefer_points):
        rows.append(
            {
                "clinic": a.clinic,
                "competitors_clinics": a.competitors_clinics,
                "competitors_hospitals": a.competitors_hospitals,
                "clinic_enhanced_est": a.clinic_enhanced_est,
                "clinic_standard_est": a.clinic_standard_est,
                "extra_visit_units": a.extra_visit_units,
                "effective_supply_units": a.acquisition.effective_supply_units,
                "demand_home_overlap_adjusted": a.demand_home_adjusted,
                "equilibrium_home": a.acquisition.equilibrium_home,
                "competitive_home": a.acquisition.competitive_home,
                "acquisition_floor_home": a.acquisition.acquisition_floor_home,
                "acquisition_target_home": a.acquisition.acquisition_target_home,
                "acquisition_stretch_home": a.acquisition.acquisition_stretch_home,
                "competition_index": a.acquisition.competition_index,
                "competition_label": a.acquisition.competition_label,
                "capacity_specialty_home": a.capacity.capacity_specialty_home,
                "capacity_cap_home": a.capacity_cap_home,
                "physician_fte": a.physician_fte,
            }
        )

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 110)
    print("競合加味・患者獲得指標（機能強化型重み + 訪問実施軽加算）")
    print("=" * 110)
    hdr = (
        f"{'院名':<14} {'診':>4} {'強':>3} {'病':>3} {'実効U':>6} {'需要':>6} "
        f"{'KPI':>5} {'伸長':>5} {'能力':>5} {'判定':<10}"
    )
    print(hdr)
    print("-" * 110)
    for r in rows:
        short = r["clinic"].replace("わかさクリニック", "")
        print(
            f"{short:<14} {r['competitors_clinics']:>4.0f} {r['clinic_enhanced_est']:>3.0f} "
            f"{r['competitors_hospitals']:>3.0f} {r['effective_supply_units']:>6.1f} "
            f"{r['demand_home_overlap_adjusted']:>6.0f} "
            f"{r['acquisition_target_home']:>5} {r['acquisition_stretch_home']:>5} "
            f"{r['capacity_cap_home']:>5.0f} {r['competition_label']:<10}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="居宅患者目標・獲得KPI（院ID/座標で需要まで一発）"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--municipal-only", action="store_true")
    parser.add_argument(
        "--clinic",
        help="院ID/短称/正式名（例: ひばりが丘, 浦和, わかさクリニック府中）",
    )
    parser.add_argument("--lat", type=float, help="緯度（新規地点）")
    parser.add_argument("--lon", type=float, help="経度（新規地点）")
    parser.add_argument("--name", help="新規地点の表示名")
    parser.add_argument("--radius-km", type=float, default=8.0)
    parser.add_argument("--fte", type=float, help="医師FTE上書き")
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="経営3本柱ダッシュボードを出力（実績があれば達成率も）",
    )
    parser.add_argument(
        "--actions",
        action="store_true",
        help="院別アクション（月次新規・紹介経路）を出力",
    )
    parser.add_argument("--months", type=int, default=12, help="アクション計画の月数")
    parser.add_argument(
        "--compare-actuals",
        action="store_true",
        help="実績 vs 獲得KPI の公開サマリ",
    )
    parser.add_argument(
        "--write-outputs",
        action="store_true",
        help="dashboard/actions の JSON を data/processed と confidential に書き出し",
    )
    args = parser.parse_args(argv)

    prefer_points = not args.municipal_only

    if args.clinic or (args.lat is not None and args.lon is not None):
        point = resolve_clinic(
            args.clinic,
            lat=args.lat,
            lon=args.lon,
            name=args.name,
            radius_km=args.radius_km,
        )
        analysis = analyze_clinic(
            point, prefer_points=prefer_points, physician_fte=args.fte
        )
        _print_analysis(analysis, args.json)
        return 0

    if args.dashboard:
        dash = build_dashboard()
        out = public_dashboard(dash) if not args.json else dash
        # --json with dashboard still may include actuals; prefer public unless explicit write
        if args.json:
            print(json.dumps(dash, ensure_ascii=False, indent=2))
        else:
            print("経営ダッシュボード（獲得KPI / 能力上限 / 達成率）")
            print(
                f"{'院':<12} {'KPI':>5} {'能力':>5} {'達成率':>8} {'状態':<16} {'競合'}"
            )
            for r in dash["rows"]:
                att = r.get("attainment_vs_kpi")
                att_s = f"{att:.0%}" if att is not None else "-"
                print(
                    f"{r['alias']:<12} {r['acquisition_kpi_home']:>5} "
                    f"{r['capacity_cap_home']:>5.0f} {att_s:>8} "
                    f"{r.get('status','-'):<16} {r['competition_label']}"
                )
        if args.write_outputs:
            write_dashboard(
                Path("analysis/confidential/management_dashboard.json"),
                public_path=Path(
                    "home_care_target/data/processed/management_dashboard_public.json"
                ),
            )
        return 0

    if args.actions:
        plans = build_action_plans(months=args.months)
        if args.json:
            print(json.dumps(public_action_summary(plans), ensure_ascii=False, indent=2))
        else:
            print(f"院別アクション（{args.months}ヶ月）優先順")
            for p in plans:
                print(f"\n#{p.priority} {p.alias} [{p.status}] 競合={p.competition_label}")
                print(f"  KPI {p.kpi_target} / 月次新規(目標) {p.monthly_new_to_target}")
                for act in p.actions:
                    print(f"  - {act}")
                ch = " / ".join(c["channel"] for c in p.referral_mix)
                print(f"  紹介経路: {ch}")
        if args.write_outputs:
            write_action_plans(
                Path("analysis/confidential/clinic_action_plans.json"),
                Path("home_care_target/data/processed/clinic_action_plans_public.json"),
                months=args.months,
            )
        return 0

    if args.compare_actuals:
        try:
            rows = compare_actuals_to_kpi()
        except FileNotFoundError as e:
            print(f"実績ファイルなし: {e}")
            return 1
        pub = rows_to_public_summary(rows)
        if args.json:
            print(json.dumps(pub, ensure_ascii=False, indent=2))
        else:
            print("実績 vs 獲得KPI（公開サマリ）")
            for c in pub["clinics"]:
                short = c["clinic"].replace("わかさクリニック", "")
                print(
                    f"  {short:<14} target={c['acquisition_target_home']:>3} "
                    f"band={c['attainment_band']} gap={c['gap_vs_target_sign']}"
                )
            print("band_counts:", pub["band_counts"])
        return 0

    return run_demo(as_json=args.json, prefer_points=prefer_points)


if __name__ == "__main__":
    raise SystemExit(main())
