"""Unit tests for accuracy-enhanced home-care target logic."""

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
)
from home_care_target.data_loader import (  # noqa: E402
    get_municipal_facilities,
    get_prefecture_clinic_stats,
    load_constants,
)
from home_care_target.demand import estimate_demand_for_catchment  # noqa: E402
from home_care_target.facilities import (  # noqa: E402
    adjusted_demand,
    group_overlap_shares,
    hospital_weight_for_prefs,
)
from home_care_target.geometry import circle_intersection_weight  # noqa: E402
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets  # noqa: E402


class TestOfficialData(unittest.TestCase):
    def test_national_constants(self):
        c = load_constants()
        self.assertEqual(c["national"]["home_support_clinics"], 14725)
        self.assertIn("capacity_tiers", c)

    def test_prefecture_tokyo(self):
        tokyo = get_prefecture_clinic_stats("東京都")
        self.assertEqual(tokyo["home_support_clinics"], 1661)

    def test_municipal_tokorozawa(self):
        m = get_municipal_facilities("所沢市")
        self.assertEqual(m["home_support_clinics"], 30)

    def test_home_shares(self):
        path = ROOT / "data" / "processed" / "prefecture_home_shares.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(data["prefectures"]["東京都"]["home_share"], 0.45)
        self.assertLess(data["prefectures"]["埼玉県"]["home_share"], 0.40)

    def test_hospital_weights(self):
        w = hospital_weight_for_prefs(["東京都"])
        self.assertGreater(w, 1.0)
        w2 = hospital_weight_for_prefs(["千葉県"])
        self.assertLess(w2, 1.0)


class TestGeometryAndOverlap(unittest.TestCase):
    def test_full_containment(self):
        # small muni fully inside
        w = circle_intersection_weight(0.0, 8.0, 3.0)
        self.assertAlmostEqual(w, 1.0, places=5)

    def test_no_overlap(self):
        w = circle_intersection_weight(20.0, 8.0, 10.0)
        self.assertEqual(w, 0.0)

    def test_partial(self):
        w = circle_intersection_weight(8.0, 8.0, 50.0)
        self.assertGreater(w, 0.0)
        self.assertLess(w, 1.0)

    def test_overlap_shares(self):
        points = [
            ("A", 35.80, 139.45),
            ("B", 35.80, 139.46),  # ~1km
            ("C", 36.50, 140.00),  # far
        ]
        shares = group_overlap_shares(points, overlap_radius_km=16.0)
        self.assertLess(shares["A"], 1.0)
        self.assertAlmostEqual(shares["C"], 1.0, places=5)
        home, total, s = adjusted_demand(1000, 2000, "A", points)
        self.assertLess(home, 1000)


class TestDemandAndTargets(unittest.TestCase):
    def test_ndb_demand(self):
        munis = [
            MunicipalityGeo(
                "西東京市", "東京都", 35.73, 139.54, 15.75, 51578, 30184, 210968, "1312", "北多摩北部"
            ),
            MunicipalityGeo(
                "練馬区", "東京都", 35.74, 139.65, 48.08, 177834, 100541, 756832, "1305", "区西北部"
            ),
        ]
        d = estimate_demand_for_catchment(35.745, 139.538, munis, radius_km=8.0)
        self.assertGreater(d.visit_patients_total, 0)
        self.assertGreater(d.recommended_home_patients, 0)
        self.assertGreater(d.home_share_used, 0.3)

    def test_specialty_targets(self):
        snap = SupplySnapshot(
            home_support_clinics=100,
            home_support_hospitals=10,
            supply_units=110,
            elderly_65=200000,
            hospital_weight=1.2,
            supply_method="test",
        )
        t = compute_home_patient_targets(
            snap,
            regional_visit_patients=8000,
            regional_home_patients=4000,
            home_share=0.5,
            physician_fte=2.0,
            clinic_tier="specialty",
        )
        self.assertGreater(t.recommended_short_term_home, 0)
        self.assertGreaterEqual(t.recommended_mid_term_home, t.recommended_short_term_home)
        self.assertIn("capacity_specialty_home", t.to_dict())
        self.assertEqual(t.assumptions["clinic_tier"], "specialty")

    def test_catchment_circle_weight(self):
        munis = [
            MunicipalityGeo("所沢市", "埼玉県", 35.80, 139.47, 71.0, 101816, 60400, 339782, "1107", "西部"),
        ]
        point = CatchmentPoint("本院", 35.805, 139.455, 8.0)
        s = aggregate_catchment_supply(point, munis, weight_method="circle_intersection")
        self.assertGreater(s.home_support_clinics, 0)
        self.assertTrue(any("circle_intersection" in x for x in s.sources))


if __name__ == "__main__":
    unittest.main()
