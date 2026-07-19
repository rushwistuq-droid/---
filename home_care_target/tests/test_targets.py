"""Unit tests for home-care target logic."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from home_care_target.catchment import (  # noqa: E402
    CatchmentPoint,
    MunicipalityGeo,
    aggregate_catchment_supply,
    compute_regional_supply,
)
from home_care_target.data_loader import (  # noqa: E402
    get_municipal_facilities,
    get_prefecture_clinic_stats,
    get_secondary_clinic_stats,
    load_constants,
)
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets  # noqa: E402


class TestOfficialData(unittest.TestCase):
    def test_national_constants(self):
        c = load_constants()
        self.assertEqual(c["national"]["home_support_clinics"], 14725)
        self.assertEqual(c["national"]["home_support_clinic_patients_managed"], 967975)
        self.assertEqual(c["national"]["home_support_hospitals_2023_07"], 2021)
        self.assertAlmostEqual(
            c["capacity_benchmarks"]["t108_mean_patients"], 65.74, places=1
        )

    def test_prefecture_tokyo(self):
        tokyo = get_prefecture_clinic_stats("東京都")
        self.assertIsNotNone(tokyo)
        self.assertEqual(tokyo["home_support_clinics"], 1661)
        self.assertEqual(tokyo["patients_managed"], 171756)

    def test_secondary_kitama(self):
        area = get_secondary_clinic_stats("1312")
        self.assertIsNotNone(area)
        self.assertEqual(area["name"], "北多摩北部")
        self.assertEqual(area["home_support_clinics"], 71)

    def test_municipal_tokorozawa(self):
        m = get_municipal_facilities("所沢市")
        self.assertEqual(m["home_support_clinics"], 30)
        self.assertEqual(m["home_support_hospitals"], 6)


class TestSupplyAndTargets(unittest.TestCase):
    def test_regional_sum(self):
        s = compute_regional_supply(["所沢市", "西東京市"])
        self.assertEqual(s["home_support_clinics"], 68)
        self.assertEqual(s["home_support_hospitals"], 9)

    def test_catchment_and_targets(self):
        munis = [
            MunicipalityGeo("西東京市", "東京都", 35.73, 139.54, 15.75, 51578, 30184, 210968, "1312", "北多摩北部"),
            MunicipalityGeo("練馬区", "東京都", 35.74, 139.65, 48.08, 177834, 100541, 756832, "1305", "区西北部"),
            MunicipalityGeo("清瀬市", "東京都", 35.77, 139.52, 10.0, 17500, 10200, 75000, "1312", "北多摩北部"),
            MunicipalityGeo("東久留米市", "東京都", 35.76, 139.53, 12.0, 27500, 16000, 118000, "1312", "北多摩北部"),
            MunicipalityGeo("新座市", "埼玉県", 35.79, 139.57, 11.0, 45000, 27000, 163000, "1102", "南西部"),
        ]
        point = CatchmentPoint("ひばりが丘", 35.745, 139.538, 8.0)
        supply = aggregate_catchment_supply(point, munis)
        self.assertGreater(supply.home_support_clinics, 30)
        self.assertGreater(supply.home_support_hospitals, 0)

        snap = SupplySnapshot.from_catchment(supply)
        # external demand path (sibling agent interface)
        target = compute_home_patient_targets(
            snap,
            regional_visit_patients=10000,
            regional_home_patients=4200,
            physician_fte=2.0,
        )
        self.assertEqual(target.regional_home_patients, 4200)
        self.assertGreater(target.recommended_short_term_home, 0)
        self.assertGreaterEqual(
            target.recommended_mid_term_home, target.recommended_short_term_home
        )
        self.assertIn("market_home_share", target.assumptions)
        self.assertIn("strategic_home_ratio", target.assumptions)

    def test_processed_files_exist(self):
        processed = ROOT / "data" / "processed"
        for name in (
            "mhlw_constants.json",
            "prefecture_home_support_clinics.json",
            "secondary_home_support_clinics.json",
            "municipal_home_support_facilities.json",
        ):
            self.assertTrue((processed / name).exists(), name)
            json.loads((processed / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
