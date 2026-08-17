# 在宅医療・居宅患者分析

**わかさクリニックグループ 13院向け分析プロジェクト**

| 資料 | 内容 |
|------|------|
| [**引き継ぎ資料**](analysis/引き継ぎ資料.md) | 複数エージェント作業の統合サマリ（新規作業はここから） |
| [成果資料](analysis/わかさ_居宅患者目標_成果資料.md) | 経営向け成果サマリ |
| [北多摩比較](analysis/北多摩北部3市_居宅開拓比較.md) | 西東京・清瀬・東久留米 |

| パッケージ | 内容 |
|------------|------|
| [`home_care_target/`](home_care_target/README.md) | 在支診・在支病の精密集計と居宅患者**目標**（供給×能力） |
| [`home_visit_demand/`](home_visit_demand/README.md) | NDB年齢別受療率による地域**需要**（居宅患者数）推定 |

両パッケージを組み合わせると、需要と供給から院ごとの居宅目標を算出できます。

**作業ブランチ**: `cursor/home-care-target-patients-1cfb`（[PR #3](https://github.com/rushwistuq-droid/---/pull/3)）

```bash
PYTHONPATH=home_care_target/src:home_visit_demand/src \
  python3 -m home_care_target.cli
```
