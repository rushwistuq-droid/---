# 訪問診療・居宅患者数 地域推定エンジン（高精度版）

クリニック住所から半径8km圏の**居宅訪問診療患者数**を、公的統計に基づき推計します。本部説明用に手法・出典・品質フラグをレポート出力します。

## すぐ使う

```bash
cd home_visit_demand
pip install -r requirements.txt
python3 scripts/download_raw_data.py         # 原本の再取得（任意）
python3 scripts/build_v2_datasets.py          # 初回・データ更新時
PYTHONPATH=src python3 -m home_visit_demand "埼玉県所沢市若狭4-2468-31"
```

緯度経度指定:

```bash
PYTHONPATH=src python3 -m home_visit_demand "所沢" --lat 35.805 --lon 139.455
```

旧ロジック（市区町村代表点）:

```bash
PYTHONPATH=src python3 -m home_visit_demand "..." --legacy
```

## 高精度版でやっていること

| # | 改善 | 内容 |
|---|------|------|
| 1 | メッシュ人口 | 令和2年国勢調査 1/4メッシュ（約250m）で半径円と交差集計 |
| 2 | 5歳階級・将来人口 | 社人研市区町村5歳階級（2020→2025伸び率）でスケール |
| 3 | 都道府県別受療率 | NDBを**居宅/施設で別強度**補正（施設が多い都心で居宅を過大推計しない） |
| 4 | 施設実在 | 介護情報公表システムの入居系事業所（座標・定員）を圏内集計 |
| 5 | 同一建物の分解 | 施設由来と集合住宅居宅を分離 |
| 6 | ポリゴン交差モジュール | `polygons.py`（shapely利用時は面積交差、無ければbbox近似） |
| 7 | 実績キャリブレーション | `scripts/calibrate.py` + YAMLで実績÷推計の縮小推定 |

## 出力の見方

- **推奨・推定居宅訪問診療患者数**: 本部判断の中心値
- **真・施設患者**: 定員法とNDB法の統合
- **集合住宅（同一建物の居宅分）**: 施設ではない同一建物患者
- **品質フラグ**: データ欠落・地域差の注意喚起

## 実績キャリブレーション

```bash
# data/processed/calibration_template.yaml をコピーして実績を記入
PYTHONPATH=src python3 scripts/calibrate.py path/to/actuals.yaml
# → data/processed/calibration.yaml に係数が出力される
```

## データ出典

- 厚労省 第10回NDBオープンデータ（在宅医療・性年齢/都道府県）
- 厚労省 社会医療診療行為別統計（2023年）
- 総務省 令和2年国勢調査 地域メッシュ統計 T001102
- 社人研 地域別将来推計人口（令和5年推計）市区町村5歳階級
- 厚労省 介護サービス情報公表システム オープンデータ
- OpenStreetMap Nominatim / Wikidata

入手元の詳細は `data/SOURCES.md`。

## テスト

```bash
PYTHONPATH=src python3 -m unittest tests.test_estimator tests.test_precision -v
```

## ディレクトリ

```text
home_visit_demand/
  data/mesh_zips/          # 全都道府県メッシュ（再生成用）
  data/ipss_age_raw/       # 社人研5歳階級
  data/facilities_raw/     # 介護情報公表CSV
  data/processed/          # 推定用加工データ
  scripts/build_v2_datasets.py
  scripts/calibrate.py
  src/home_visit_demand/
    precision.py           # 高精度エンジン
    estimator.py           # 旧ロジック
    polygons.py            # ポリゴン交差
  examples/
```
