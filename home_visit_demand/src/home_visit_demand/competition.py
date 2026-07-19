"""外部競合密度（医療情報ネット公開診療所）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .estimator import haversine_km
from .precision import DATA_DIR

OWN_NAME_RE = ("わかさ", "Wakasa", "WAKASA")


@lru_cache(maxsize=1)
def _load_home_competitors() -> pd.DataFrame:
    path = DATA_DIR / "competitors_home.csv.gz"
    if not path.exists():
        return pd.DataFrame(columns=["ID", "name", "lat", "lon"])
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def _load_all_clinics() -> pd.DataFrame:
    path = DATA_DIR / "clinics_all_coords.csv.gz"
    if not path.exists():
        return pd.DataFrame(columns=["ID", "lat", "lon"])
    return pd.read_csv(path)


def load_competitors_meta() -> dict:
    path = DATA_DIR / "competitors_meta.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _count_in_radius(df: pd.DataFrame, lat: float, lon: float, radius_km: float) -> int:
    if df.empty:
        return 0
    ddeg = (radius_km + 1.0) / 80.0
    sub = df[
        (df["lat"] >= lat - ddeg)
        & (df["lat"] <= lat + ddeg)
        & (df["lon"] >= lon - ddeg)
        & (df["lon"] <= lon + ddeg)
    ]
    if sub.empty:
        return 0
    n = 0
    for r in sub.itertuples(index=False):
        if haversine_km(lat, lon, float(r.lat), float(r.lon)) <= radius_km:
            n += 1
    return n


def _home_competitors_excluding_own(
    lat: float, lon: float, radius_km: float
) -> tuple[int, list[dict]]:
    df = _load_home_competitors()
    if df.empty:
        return 0, []
    ddeg = (radius_km + 1.0) / 80.0
    sub = df[
        (df["lat"] >= lat - ddeg)
        & (df["lat"] <= lat + ddeg)
        & (df["lon"] >= lon - ddeg)
        & (df["lon"] <= lon + ddeg)
    ]
    hits: list[dict] = []
    for r in sub.itertuples(index=False):
        name = str(getattr(r, "name", "") or "")
        if any(x in name for x in OWN_NAME_RE):
            continue
        d = haversine_km(lat, lon, float(r.lat), float(r.lon))
        if d <= radius_km:
            hits.append({"name": name, "distance_km": round(d, 2), "address": getattr(r, "address", "")})
    hits.sort(key=lambda x: x["distance_km"])
    return len(hits), hits[:15]


def competition_metrics(lat: float, lon: float, radius_km: float, elderly_65: float) -> dict:
    """圏内の外部競合指標。"""
    home_n, top = _home_competitors_excluding_own(lat, lon, radius_km)
    all_n = _count_in_radius(_load_all_clinics(), lat, lon, radius_km)
    per_10k_home = 10000.0 * home_n / elderly_65 if elderly_65 else 0.0
    per_10k_all = 10000.0 * all_n / elderly_65 if elderly_65 else 0.0
    # 競合ティア
    if home_n >= 25 or per_10k_all >= 40:
        tier = "外部競合・高"
    elif home_n >= 10 or per_10k_all >= 25:
        tier = "外部競合・中"
    elif home_n >= 4 or per_10k_all >= 15:
        tier = "外部競合・低〜中"
    else:
        tier = "外部競合・低"
    return {
        "home_visit_competitors": home_n,
        "all_clinics_in_radius": all_n,
        "home_competitors_per_10k_elderly": round(per_10k_home, 2),
        "clinics_per_10k_elderly": round(per_10k_all, 2),
        "external_competition_tier": tier,
        "top_home_competitors": top,
        "meta": load_competitors_meta(),
    }


def adjust_share_for_external_competition(
    low: float, high: float, metrics: dict
) -> tuple[float, float, list[str]]:
    notes: list[str] = []
    tier = metrics.get("external_competition_tier", "")
    home_n = int(metrics.get("home_visit_competitors") or 0)
    if tier == "外部競合・高":
        low *= 0.65
        high *= 0.7
        notes.append(f"外部の在宅寄り診療所が{home_n}院→期待シェア帯を下方調整")
    elif tier == "外部競合・中":
        low *= 0.8
        high *= 0.85
        notes.append(f"外部の在宅寄り診療所が{home_n}院→期待シェア帯をやや下方調整")
    elif tier == "外部競合・低":
        low *= 1.05
        high *= 1.1
        notes.append("外部在宅寄り競合が相対的に薄い→期待シェア帯をやや上方調整")
    return round(low, 2), round(high, 2), notes
