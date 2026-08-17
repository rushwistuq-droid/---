# わかさクリニックグループ 訪問診療 地域・実績分析

**新規参加者は [`analysis/引き継ぎ資料.md`](analysis/引き継ぎ資料.md) から読んでください。**

## クイックスタート

```bash
# 公開統計ベースの8km圏比較
python3 analysis/wakasa_clinic_regional_analysis.py

# 実績統合（要: analysis/confidential/operational_data.yaml）
python3 analysis/performance_analysis.py
```

機密データの復元方法は引き継ぎ資料 §4 を参照。

## 関連 PR（別ブランチ）

| PR | 内容 |
|----|------|
| #1 | 本 `analysis/` ディレクトリ |
| #2 | `home_visit_demand/` 高精度居宅需要推定 |
| #3 | `home_care_target/` 居宅患者目標KPI |
