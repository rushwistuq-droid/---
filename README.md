# 訪問診療・居宅患者数の地域推定（高精度版）

`home_visit_demand/` に、クリニック住所から半径8kmの居宅訪問診療患者数を推計するシステムがあります。

**高精度版**では次を実装済みです。

- 国勢調査メッシュ人口（約250m）
- 社人研市区町村5歳階級（2025スケール）
- 都道府県別NDB受療率（居宅/施設の強度分離）
- 介護情報公表システムの施設座標・定員
- 同一建物の施設/集合住宅分解
- 実績キャリブレーション

```bash
cd home_visit_demand
pip install -r requirements.txt
python3 scripts/build_v2_datasets.py
PYTHONPATH=src python3 -m home_visit_demand "埼玉県所沢市若狭4-2468-31"
```

詳細は [home_visit_demand/README.md](home_visit_demand/README.md)。
