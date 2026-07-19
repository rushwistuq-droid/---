#!/usr/bin/env python3
"""本部向けパイプライン: 定義・重複・競合・感度・施設KPI・アクション・ダッシュボード。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import yaml
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

from home_visit_demand.action_sheets import (  # noqa: E402
    build_action_sheets,
    format_action_sheets,
)
from home_visit_demand.dashboard import write_hq_dashboard  # noqa: E402
from home_visit_demand.hq_analysis import (  # noqa: E402
    clinics_from_actuals_yaml,
    format_hq_report,
    run_hq_pipeline,
)
from home_visit_demand.precision import DATA_DIR  # noqa: E402


def ensure_competitors() -> None:
    home = DATA_DIR / "competitors_home.csv.gz"
    allc = DATA_DIR / "clinics_all_coords.csv.gz"
    if home.exists() and allc.exists():
        return
    print("competitors dataset missing; building...", flush=True)
    path = ROOT / "scripts" / "build_competitors.py"
    spec = importlib.util.spec_from_file_location("build_competitors", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    mod.build()


def main() -> int:
    p = argparse.ArgumentParser(description="本部向け地域分析パイプライン")
    p.add_argument(
        "actuals",
        type=Path,
        nargs="?",
        default=ROOT / "data" / "confidential" / "actuals_2026-07.yaml",
    )
    p.add_argument("--radius-km", type=float, default=8.0)
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "examples" / "wakasa_hq_pipeline_report.txt",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "examples" / "wakasa_hq_pipeline.json",
    )
    p.add_argument(
        "--actions-out",
        type=Path,
        default=ROOT / "examples" / "wakasa_action_sheets.txt",
    )
    p.add_argument(
        "--dashboard-out",
        type=Path,
        default=ROOT / "examples" / "wakasa_hq_dashboard.html",
    )
    p.add_argument("--skip-build-competitors", action="store_true")
    args = p.parse_args()

    if not args.actuals.exists():
        print(f"actuals not found: {args.actuals}", file=sys.stderr)
        return 1

    if not args.skip_build_competitors:
        ensure_competitors()

    data = yaml.safe_load(args.actuals.read_text(encoding="utf-8"))
    clinics = clinics_from_actuals_yaml(data)
    print(f"running HQ pipeline for {len(clinics)} clinics...", flush=True)
    result = run_hq_pipeline(clinics, primary_radius_km=args.radius_km)
    text = format_hq_report(result)
    print(text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    args.json_out.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    actions = build_action_sheets(result)
    actions_text = format_action_sheets(actions)
    args.actions_out.write_text(actions_text, encoding="utf-8")
    print(actions_text)

    dash = write_hq_dashboard(result, args.dashboard_out)
    rules = ROOT / "docs" / "HQ_OPERATING_RULES.md"
    print(f"\nwrote {args.output}", flush=True)
    print(f"wrote {args.json_out}", flush=True)
    print(f"wrote {args.actions_out}", flush=True)
    print(f"wrote {dash}", flush=True)
    print(f"radius rules: {rules}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
