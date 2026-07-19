#!/usr/bin/env python3
"""本部向けパイプライン: 定義固定・重複除去・期待シェア帯・半径感度・施設KPI分離。"""

from __future__ import annotations

import argparse
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

from home_visit_demand.hq_analysis import (  # noqa: E402
    clinics_from_actuals_yaml,
    format_hq_report,
    run_hq_pipeline,
)


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
    args = p.parse_args()

    if not args.actuals.exists():
        print(f"actuals not found: {args.actuals}", file=sys.stderr)
        return 1

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
    print(f"\nwrote {args.output}", flush=True)
    print(f"wrote {args.json_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
