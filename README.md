# 在宅医療・居宅患者分析

| パッケージ | 内容 |
|------------|------|
| [`home_care_target/`](home_care_target/README.md) | 在支診・在支病の精密集計と居宅患者**目標**（供給×能力） |
| [`home_visit_demand/`](home_visit_demand/README.md) | NDB年齢別受療率による地域**需要**（居宅患者数）推定 |

両パッケージを組み合わせると、需要と供給から院ごとの居宅目標を算出できます。

```bash
PYTHONPATH=home_care_target/src:home_visit_demand/src \
  python3 -m home_care_target.cli
```
