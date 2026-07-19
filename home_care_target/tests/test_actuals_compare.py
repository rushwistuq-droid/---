"""Tests for actuals YAML loader and gap banding."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from home_care_target.actuals_compare import (
    _parse_simple_actuals_yaml,
    load_actuals,
    rows_to_public_summary,
)
from home_care_target.wakasa_demo_data import CLINIC_ALIASES, CLINICS


SAMPLE = """
as_of: "2026-07"
clinics:
  - alias: ひばりが丘
    facility: 393
    home: 122
  - alias: 浦和
    facility: 0
    home: 14
"""


class TestActualsLoader(unittest.TestCase):
    def test_simple_yaml_parse(self):
        data = _parse_simple_actuals_yaml(SAMPLE)
        self.assertEqual(len(data["clinics"]), 2)
        self.assertEqual(data["clinics"][0]["home"], 122)
        self.assertEqual(data["clinics"][1]["facility"], 0)

    def test_load_actuals_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.yaml"
            p.write_text(SAMPLE, encoding="utf-8")
            out = load_actuals(p)
            self.assertIn(CLINIC_ALIASES["ひばりが丘"], out)
            self.assertIn(CLINIC_ALIASES["浦和"], out)
            self.assertEqual(out[CLINIC_ALIASES["浦和"]]["home"], 14)

    def test_public_summary_hides_raw_counts(self):
        # synthetic rows via public summary shape
        from home_care_target.actuals_compare import ActualVsKpiRow

        rows = [
            ActualVsKpiRow(
                clinic="わかさクリニック浦和",
                alias="浦和",
                actual_facility=0,
                actual_home=14,
                actual_total=14,
                actual_home_share=1.0,
                acquisition_floor_home=20,
                acquisition_target_home=40,
                acquisition_stretch_home=60,
                competitive_home=30.0,
                gap_vs_target=-26,
                gap_vs_floor=-6,
                attainment_vs_target=0.35,
                competition_label="中",
                competitors_clinics=100,
                competitors_hospitals=10,
                demand_home_adjusted=1000.0,
                physician_fte=1.0,
                note="フロア未達（優先獲得）",
            )
        ]
        pub = rows_to_public_summary(rows)
        self.assertTrue(all(not k.startswith("actual_") for k in pub["clinics"][0]))
        self.assertEqual(pub["band_counts"]["フロア未達（優先獲得）"], 1)

    def test_urawa_in_clinics(self):
        names = [c.name for c in CLINICS]
        self.assertIn("わかさクリニック浦和", names)


if __name__ == "__main__":
    unittest.main()
