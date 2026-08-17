# 原本データの入手元

| ファイル | 出典 | URL目安 |
|----------|------|---------|
| `ndb_home_age.xlsx` | 厚労省 第10回NDBオープンデータ C在宅医療 性年齢別算定回数 | https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000177221_00014.html （content/12400000/001258288.xlsx） |
| `pop2022_1.xlsx` | 総務省 人口推計 2022年10月1日 第1表 | https://www.stat.go.jp/data/jinsui/2022np/ |
| `kekkahyo1.xlsx` / `kekkahyo2_3.xlsx` / `kekkahyo2_4.xlsx` | 社人研 地域別将来推計人口（令和5年推計）結果表 | https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/2gaiyo_hyo/gaiyo.asp |
| `kaigo_data05.xlsx` | 厚労省 令和5年介護サービス施設・事業所調査 概況 | https://www.mhlw.go.jp/toukei/saikin/hw/kaigo/service23/ |
| `munic_coords.json` | Wikidata SPARQL（P429市区町村コード + P625座標） | https://query.wikidata.org |

再生成: `python3 scripts/build_datasets.py`
