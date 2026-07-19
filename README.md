# 訪問診療・居宅患者数の地域推定

`home_visit_demand/` に、クリニック住所から半径8km圏の居宅訪問診療患者数を推計するロジックがあります。

```bash
cd home_visit_demand
pip install -r requirements.txt
python scripts/build_datasets.py
PYTHONPATH=src python -m home_visit_demand "埼玉県所沢市若狭4-2468-31"
```

詳細は [home_visit_demand/README.md](home_visit_demand/README.md) を参照してください。
