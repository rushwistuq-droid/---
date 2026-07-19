# 在宅支援施設の精密集計と居宅患者目標計算

地域の **在宅療養支援診療所（在支診）**・**在宅療養支援病院（在支病）** を公的データで精密に数え、
1拠点あたりの **居宅患者数の目標水準** を算出します。

`home_visit_demand`（NDB年齢別需要推定）と連携する精度強化版です。

## 精度強化ポイント（v0.2）

| # | 改善 | 実装 |
|---|------|------|
| 1 | 年齢・地域別需要 | 第10回NDB年齢別受療率 × 社人研人口。都道府県別居宅シェア（東京≈55%、埼玉≈32%） |
| 2 | 施設点競合 | JMAPの在支診/在支病を施設単位で取得し、国土地理院APIでジオコード（2,242件） |
| 3 | 地域別居宅シェア | NDB都道府県別・同一建物以外比率 |
| 4 | 病院ウェイト | 医療施設調査の訪問診療「件数/施設」比（東京1.21、全国1.03、千葉0.49） |
| 5 | 円交差キャッチメント | 市区町村を等面積円近似し、半径円との交差面積比で重み付け |
| 6 | 能力ティア | standard / active / specialty（訪問特化） / enhanced |
| 7 | グループ重複按分 | 16km以内の自グループ院に需要を距離逆数で按分 |

## すぐ使う

```bash
# 依存（需要推定側）
# home_visit_demand/data/processed が同リポジトリにあれば追加インストール不要

PYTHONPATH=home_care_target/src:home_visit_demand/src \
  python3 -m home_care_target.cli

# JSON
PYTHONPATH=... python3 -m home_care_target.cli --json

# 施設点を使わず市区町村合算のみ
PYTHONPATH=... python3 -m home_care_target.cli --municipal-only
```

### デモ結果例（ひばりが丘・半径8km）

| 指標 | 値 |
|------|-----|
| 在支診（施設点） | 225 |
| 在支病 | 25 |
| 病院ウェイト | 0.95 |
| 地域居宅シェア | 49.1% |
| 需要居宅（重複補正後） | 約4,121人 |
| 市場按分（参照） | 17人 |
| 短期 / 中期 / 伸長目標 | **63 / 90 / 120** |

## データソース

| データ | 出所 |
|--------|------|
| 在支診数・受け持ち患者 | 厚労省 令和5年医療施設調査 e-Stat 第108/24/168表 |
| 在支病届出数 | 厚労省保険局 届出状況（中医協） |
| 施設点 | JMAP（厚生局届出系）+ 国土地理院住所検索 |
| 年齢別受療率 | 第10回NDBオープンデータ C在宅医療 |
| 都道府県居宅シェア | 同上・都道府県別算定回数 |
| 訪問件数ウェイト | 医療施設調査 第68/107表 |
| 人口 | 社人研 地域別将来推計（令和5年推計）2025年 |

## プログラム接続

```python
from home_care_target.demand import estimate_demand_for_catchment
from home_care_target.facilities import count_facilities_in_radius, adjusted_demand
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets

demand = estimate_demand_for_catchment(lat, lon, municipalities)
supply = count_facilities_in_radius(lat, lon, 8.0)
snap = SupplySnapshot.from_point_supply(supply, elderly_65=demand.elderly_65)
target = compute_home_patient_targets(
    snap,
    regional_home_patients=demand.recommended_home_patients,
    home_share=demand.home_share_used,
    clinic_tier="specialty",
    physician_fte=2.0,
)
```

## テスト

```bash
PYTHONPATH=home_care_target/src:home_visit_demand/src \
  python3 -m unittest discover -s home_care_target/tests -v
```

## ディレクトリ

```
home_care_target/
  data/raw/           # e-Stat / NDB 原文
  data/processed/     # 正規化JSON・施設点・デモ出力
  src/home_care_target/
  scripts/build_accuracy_datasets.py
  tests/
home_visit_demand/    # NDB年齢別需要エンジン（連携）
```
