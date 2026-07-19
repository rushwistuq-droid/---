# 在宅支援施設の精密集計と居宅患者目標計算

地域の **在宅療養支援診療所（在支診）**・**在宅療養支援病院（在支病）** を公的データに基づき精密に数え、
1拠点あたりの **居宅患者数の目標水準** を算出するロジックです。

並行エージェントが開発する「地域の訪問診療需要・居宅患者数推定」と接続し、
需要（どれだけいるか）× 供給（在支診・在支病がどれだけあるか）から目標を導きます。

## データソース（可能な範囲で厚労省等の公表値）

| データ | 出所 | 用途 |
|--------|------|------|
| 在支診数・受け持ち患者数（都道府県／指定都市等） | 厚労省「令和5年医療施設調査」e-Stat 第108表（2023-10-01） | 公式の在支診数・患者総数 |
| 在支診数・受け持ち患者数（二次医療圏） | 同 二次医療圏編 第24表 | 圏域別の施設能力平均 |
| 在支診の患者数階級 | 同 全国編 第168表 | 能力ベンチマーク（平均・活動層・上位） |
| 在支病・在支診の届出数（全国） | 厚労省保険局「主な施設基準の届出状況」（中医協資料, 2023-07-01） | 在支病 2,021 施設など |
| 市区町村別 在支診／在支病（機能強化型内訳） | JMAP（地方厚生局届出等に基づくウェルネスDB） | 半径圏の精密供給集計 |
| 居宅シェア | NDB 在宅患者訪問診療料の同一建物以外比率（既定 42.1%） | 総患者→居宅換算 |

全国の主要定数（R5調査）:

- 在支診 **14,725** 施設、受け持ち在宅療養患者 **967,975** 人 → 平均 **65.7** 人/施設
- 在支病（届出, 2023-07） **2,021** 施設（うち機能強化型 782）

## 計算ロジック

### 1. 供給の精密化

```
供給ユニット = 在支診数 + 在支病数 × 病院ウェイト（既定1.0）
```

- 院所在地から半径 R km（既定 8km）内の市区町村を距離重み付きで合算
- 市区町村値は JMAP（厚生局届出系）の最新件数。機能強化型／従来型も保持
- 二次医療圏・都道府県の e-Stat 値で「施設あたり受け持ち患者」の地域平均を併記

### 2. 居宅患者目標（1拠点）

| 指標 | 式 | 意味 |
|------|----|------|
| 競合按分 | `地域居宅需要 / 供給ユニット` | 市場を均等に分けたときの参照シェア |
| 能力・基準 | `T108全国平均65.7 × 戦略居宅比60%` | 厚労省平均規模での居宅目標 |
| 能力・活動層 | `T168（患者20人以上）平均 × 60%` | 実働在支診規模での居宅目標 |
| 能力・地域 | `二次医療圏の受け持ち平均 × 60%` | その圏の実態規模 |
| 短期推奨 | 活動層（医師FTE上限あり） | まず到達すべき運営規模 |
| 中期推奨 | max(短期, 地域平均) | 圏内標準〜上位に寄せるターゲット |

需要側の居宅化には市場シェア（NDB 同一建物以外 **42.1%**）を使い、
目標側には訪問特化拠点向けの戦略居宅比（既定 **60%**）を使います。

需要は次の優先順で取り込みます（並行エージェント接続用）:

1. `regional_home_patients`（居宅需要の直接入力）
2. `regional_visit_patients`（総訪問診療需要）× 居宅シェア
3. フォールバック: `65歳以上人口 × 4.5%` × 居宅シェア

## 使い方

```bash
# デモ（わかさ12院・半径8km）
PYTHONPATH=src python -m home_care_target.cli

# JSON
PYTHONPATH=src python -m home_care_target.cli --json

# テスト
PYTHONPATH=src python -m unittest tests.test_targets -v
```

### プログラムからの接続例

```python
from home_care_target.catchment import aggregate_catchment_supply, CatchmentPoint
from home_care_target.targets import SupplySnapshot, compute_home_patient_targets

supply = aggregate_catchment_supply(CatchmentPoint("某院", lat, lon), municipalities)
snap = SupplySnapshot.from_catchment(supply)

# 並行の需要推定ロジックの出力を渡す
target = compute_home_patient_targets(
    snap,
    regional_visit_patients=demand.total_visit_patients,
    regional_home_patients=demand.home_patients,
    physician_fte=2.0,
)
print(target.recommended_short_term_home, target.recommended_mid_term_home)
```

## ディレクトリ

```
home_care_target/
  data/raw/           # e-Stat 原文 CSV
  data/processed/     # 正規化 JSON（都道府県・二次医療圏・市区町村）
  src/home_care_target/
  tests/
  scripts/rebuild_estat_json.py
```

## 注意

- 在支病の「受け持ち患者数」は医療施設調査に在支診と同等の表がないため、供給ユニットとして算入し、能力ベンチマークは在支診の公的患者数分布を用います（概況では訪問診療の施設当たり件数は病院≈診療所）。
- JMAP 市区町村値は月次更新のため、e-Stat（年次）の都道府県合計と完全一致しません。監査時は e-Stat を正とし、圏内配分に JMAP を使う想定です。
- 本モジュールは目標水準のロジックであり、実績の医師・患者数（機密）は含みません。
