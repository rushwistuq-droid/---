#!/usr/bin/env bash
# 引き継ぎZIPバンドルを生成する
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE_NAME="wakasa-clinic-analysis-handover"
STAGING="$ROOT/dist/$BUNDLE_NAME"
ZIP_PATH="$ROOT/dist/${BUNDLE_NAME}.zip"
ARTIFACTS_DIR="/opt/cursor/artifacts"

rm -rf "$ROOT/dist"
mkdir -p "$STAGING"

echo "==> 系統A: analysis/ (現ブランチ)"
mkdir -p "$STAGING/analysis"
cp -r "$ROOT/analysis/"* "$STAGING/analysis/" 2>/dev/null || true
# confidential を確実に同梱
mkdir -p "$STAGING/analysis/confidential"
if [[ -f "$ROOT/analysis/confidential/operational_data.yaml" ]]; then
  cp "$ROOT/analysis/confidential/operational_data.yaml" "$STAGING/analysis/confidential/"
fi
if [[ -f "$ROOT/analysis/confidential/performance_report.txt" ]]; then
  cp "$ROOT/analysis/confidential/performance_report.txt" "$STAGING/analysis/confidential/"
fi

echo "==> 系統B: home_visit_demand/ (PR #2)"
git -C "$ROOT" archive origin/cursor/home-visit-patient-estimation-28cb home_visit_demand | tar -x -C "$STAGING"

echo "==> 系統C: home_care_target/ (PR #3)"
git -C "$ROOT" archive origin/cursor/home-care-target-patients-1cfb home_care_target | tar -x -C "$STAGING"

echo "==> PR #3 追加ドキュメント"
mkdir -p "$STAGING/_pr3_analysis"
git -C "$ROOT" archive origin/cursor/home-care-target-patients-1cfb analysis | tar -x -C "$STAGING/_pr3_analysis"
# PR3 analysis をマージ（重複は現ブランチ優先、追加ファイルのみ）
for f in "$STAGING/_pr3_analysis/analysis/"*; do
  base="$(basename "$f")"
  if [[ ! -e "$STAGING/analysis/$base" ]]; then
    cp -r "$f" "$STAGING/analysis/"
  fi
done
# artifacts pdf
if [[ -d "$STAGING/_pr3_analysis/analysis/artifacts" ]]; then
  mkdir -p "$STAGING/analysis/artifacts"
  cp -r "$STAGING/_pr3_analysis/analysis/artifacts/"* "$STAGING/analysis/artifacts/" 2>/dev/null || true
fi
rm -rf "$STAGING/_pr3_analysis"

echo "==> ルートファイル"
cp "$ROOT/scripts/新規リポジトリセットアップ手順.md" "$STAGING/"
cp "$ROOT/.gitignore" "$STAGING/"

cat > "$STAGING/README.md" << 'EOF'
# わかさクリニックグループ 訪問診療分析 — 引き継ぎパッケージ

**作成日**: 2026-08-17  
**内容**: 3系統の分析ツール + 引き継ぎ資料 + 機密データ（ローカル用）

## 最初に読む

1. [`analysis/引き継ぎ資料.md`](analysis/引き継ぎ資料.md) — 全体像・データ・会話履歴
2. [`新規リポジトリセットアップ手順.md`](新規リポジトリセットアップ手順.md) — 新リポジトリ化・エージェント指令

## クイックスタート

```bash
python3 analysis/wakasa_clinic_regional_analysis.py
python3 analysis/performance_analysis.py
```

## 構成

| ディレクトリ | 役割 |
|-------------|------|
| `analysis/` | 8km圏比較・実績統合（軽量） |
| `home_visit_demand/` | 高精度居宅需要推定 |
| `home_care_target/` | 居宅患者目標KPI |

## 機密データ

`analysis/confidential/` は **Gitに含めない** こと。  
本ZIPには引き継ぎ用に同梱しています。
EOF

echo "==> ZIP作成"
mkdir -p "$ROOT/dist"
(cd "$ROOT/dist" && zip -r -q "${BUNDLE_NAME}.zip" "$BUNDLE_NAME")

# Cursor artifacts（ダウンロード用）
if [[ -d "$ARTIFACTS_DIR" ]]; then
  cp "$ZIP_PATH" "$ARTIFACTS_DIR/"
  echo "==> Artifacts: $ARTIFACTS_DIR/${BUNDLE_NAME}.zip"
fi

SIZE=$(du -h "$ZIP_PATH" | cut -f1)
echo "==> 完了: $ZIP_PATH ($SIZE)"
unzip -l "$ZIP_PATH" | tail -5
