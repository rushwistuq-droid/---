# 在宅支援施設の精密集計と居宅患者目標計算

地域の **在宅療養支援診療所（在支診）**・**在宅療養支援病院（在支病）** を公的データで精密に数え、
1拠点あたりの **居宅患者数の目標水準（獲得KPI）** を算出します。

`home_visit_demand`（NDB年齢別需要推定）と連携する精度強化版です。

## 精度強化ポイント

| # | 改善 | 実装 |
|---|------|------|
| 1 | 年齢・地域別需要 | 第10回NDB年齢別受療率 × 社人研人口。都道府県別居宅シェア |
| 2 | 施設点競合 | JMAP在支診/在支病を施設単位でジオコード（約2,400件） |
| 3 | 地域別居宅シェア | NDB都道府県別・同一建物以外比率 |
| 4 | 病院ウェイト | 医療施設調査の訪問診療「件数/施設」比 |
| 5 | 円交差キャッチメント | 市区町村を等面積円近似し交差面積比で重み付け |
| 6 | 能力ティア | standard / active / specialty / enhanced |
| 7 | グループ重複按分 | 16km以内の自グループ院に需要を距離逆数で按分 |

## 経営指標（本命）

院別ダッシュボードは次の3本に固定します。

| 指標 | 意味 |
|------|------|
| **獲得KPI** | 競合加味の短期目標（実効按分×野心度を能力・FTEで上限） |
| **能力上限** | specialty / 地域平均 × 戦略居宅比、および FTE 上限 |
| **実績/KPI比** | 達成率（機密実績がある場合） |

### 実効競合（v0.4）

```
effective =
  機能強化型在支診 × 1.0
  + 従来型在支診 × 0.35
  + 在支病 × 病院ウェイト
  + 非在支の訪問実施診の軽加算（在支診×0.08）
```

機能強化型比率は、施設点合計に市区町村合算の内訳比率を当てて推定します。

## CLI

```bash
PYTHONPATH=home_care_target/src:home_visit_demand/src

# 全院デモ
python3 -m home_care_target.cli

# 院ID → 需要＋獲得KPI 一発
python3 -m home_care_target.cli --clinic ひばりが丘
python3 -m home_care_target.cli --clinic 浦和 --json
python3 -m home_care_target.cli --lat 35.75 --lon 139.54 --name 試作地点 --fte 1.5

# 経営ダッシュボード / 院別アクション
python3 -m home_care_target.cli --dashboard
python3 -m home_care_target.cli --actions --months 12
python3 -m home_care_target.cli --dashboard --write-outputs
python3 -m home_care_target.cli --compare-actuals
```

実績YAMLは `analysis/confidential/`（gitignore）。公開JSONは人数の生値を出しません。

## プログラム接続

```python
from home_care_target.pipeline import analyze_clinic, resolve_clinic

a = analyze_clinic(resolve_clinic("市川"))
print(a.kpi_target_home, a.capacity_cap_home, a.acquisition.competition_label)
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
  data/processed/     # 正規化JSON・施設点・公開ダッシュボード
  src/home_care_target/
  scripts/
  tests/
home_visit_demand/    # NDB年齢別需要エンジン（連携）
analysis/confidential/  # 実績・詳細ダッシュボード（gitignore）
```
