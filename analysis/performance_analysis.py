#!/usr/bin/env python3
"""
機密オペレーションデータ × 地域データ 統合分析
confidential/operational_data.yaml を読み込み（Git管理外）
"""

import math
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

# 地域分析モジュールを再利用
sys.path.insert(0, str(Path(__file__).parent))
from wakasa_clinic_regional_analysis import CLINICS, calculate_catchment_metrics, RADIUS_KM

CONF_DIR = Path(__file__).parent / "confidential"
DATA_FILE = CONF_DIR / "operational_data.yaml"
OUTPUT_FILE = CONF_DIR / "performance_report.txt"

# 分析用の院名マッピング
CLINIC_KEY_MAP = {
    "01": "本院", "02": "所沢", "03": "ひばりが丘", "04": "石神井公園",
    "05": "三鷹", "06": "府中", "07": "調布", "08": "三軒茶屋",
    "09": "津田沼", "10": "西日暮里", "11": "高円寺", "12": "リーフシティ市川",
}


def load_ops():
    with open(DATA_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def analyze():
    ops = load_ops()
    physicians = ops["physicians_fte"]
    patients = ops["patients"]
    w_home = ops["revenue_weight"]["home"]
    w_fac = ops["revenue_weight"]["facility"]

    rows = []
    regional = {}

    for clinic in CLINICS:
        if clinic.id == "13":
            continue
        key = CLINIC_KEY_MAP.get(clinic.id)
        if not key or key not in patients:
            continue

        reg = calculate_catchment_metrics(clinic)
        regional[key] = reg

        p = patients[key]
        home, fac = p["home"], p["facility"]
        total = home + fac
        fac_ratio = fac / total * 100 if total else 0

        fte = physicians.get(key)
        if fte is None:
            raise ValueError(f"医師数未設定: {key}")
        fte_note = ""

        weighted = home * w_home + fac * w_fac
        rev_index_per_fte = weighted / fte if fte else 0
        patients_per_fte = total / fte if fte else 0
        home_per_fte = home / fte if fte else 0

        est_demand = reg["estimated_home_patients"]
        # 施設患者は地域推計に含まれないため、居宅のみでシェア算出
        home_share = home / est_demand * 100 if est_demand else 0
        total_share = total / est_demand * 100 if est_demand else 0

        theoretical = reg["theoretical_share_per_clinic"]
        effort_index = total / theoretical * 100 if theoretical else 0

        # 競合調整後効率 = 実患者/理論枠 を医師数で割った相対値
        efficiency_vs_market = (total / max(theoretical, 1)) / fte * 100

        # 地域難易度（競合密度ベース、0-100）
        comp_density = reg["home_support_per_100k_elderly"]
        regional_difficulty = min(100, comp_density / 65 * 60 + reg["wakasa_overlap_count"] * 4)

        # 努力補正スコア = 効率指数 / 地域難易度（高いほど地域以上に成果）
        performance_score = efficiency_vs_market / max(regional_difficulty, 10) * 100

        rows.append({
            "key": key,
            "home": home, "facility": fac, "total": total,
            "fac_ratio": fac_ratio,
            "fte": fte,
            "fte_used": fte,
            "fte_note": fte_note,
            "weighted": weighted,
            "rev_index_per_fte": rev_index_per_fte,
            "patients_per_fte": patients_per_fte,
            "home_per_fte": home_per_fte,
            "home_share": home_share,
            "total_share": total_share,
            "theoretical": theoretical,
            "effort_index": effort_index,
            "efficiency_vs_market": efficiency_vs_market,
            "regional_difficulty": regional_difficulty,
            "performance_score": performance_score,
            "comp_density": comp_density,
            "overlap": reg["wakasa_overlap_count"],
            "elderly": reg["total_elderly_65"],
        })

    # 浦和（地域分析に未登録のため簡易）
    if "浦和針ヶ谷" in patients:
        p = patients["浦和針ヶ谷"]
        home, fac = p["home"], p["facility"]
        total = home + fac
        fte = physicians.get("浦和針ヶ谷", 1.0)
        weighted = home * w_home + fac * w_fac
        rows.append({
            "key": "浦和針ヶ谷",
            "home": home, "facility": fac, "total": total,
            "fac_ratio": fac / total * 100 if total else 100,
            "fte": fte, "fte_used": fte, "fte_note": "（地域推計未実装・新規院）",
            "weighted": weighted,
            "rev_index_per_fte": weighted / fte,
            "patients_per_fte": total / fte,
            "home_per_fte": home / fte,
            "home_share": None, "total_share": None,
            "theoretical": None,
            "effort_index": None,
            "efficiency_vs_market": None,
            "regional_difficulty": None,
            "performance_score": None,
            "comp_density": None,
            "overlap": None,
            "elderly": None,
        })

    rows.sort(key=lambda x: x.get("performance_score") or 0, reverse=True)

    lines = []
    lines.append("=" * 100)
    lines.append("【機密】わかさクリニックグループ 実績×地域 統合分析")
    lines.append(f"前提: 半径{RADIUS_KM}km圏 / 収益代理: 居宅×{w_home} + 施設×{w_fac}")
    lines.append("=" * 100)
    lines.append("")

    # サマリー
    hdr = f"{'院名':<14} {'居宅':>6} {'施設':>6} {'計':>6} {'施設%':>6} {'医師':>5} {'患者/医師':>8} {'収益指数/医師':>12} {'居宅シェア':>8} {'努力指数':>8} {'成果スコア':>8}"
    lines.append(hdr)
    lines.append("-" * 100)

    group_home = group_fac = group_total = group_weighted = group_fte = 0
    for r in rows:
        fte_disp = f"{r['fte']:.1f}"
        share_disp = f"{r['home_share']:.1f}%" if r['home_share'] is not None else "  n/a"
        effort_disp = f"{r['effort_index']:.0f}" if r['effort_index'] is not None else "  n/a"
        perf_disp = f"{r['performance_score']:.0f}" if r['performance_score'] is not None else "  n/a"
        lines.append(
            f"{r['key']:<14} {r['home']:>6} {r['facility']:>6} {r['total']:>6} "
            f"{r['fac_ratio']:>5.0f}% {fte_disp:>5} {r['patients_per_fte']:>8.0f} "
            f"{r['rev_index_per_fte']:>12.0f} {share_disp:>8} {effort_disp:>8} {perf_disp:>8}"
        )
        if r['fte'] is not None and r['key'] != '浦和針ヶ谷':
            group_home += r['home']
            group_fac += r['facility']
            group_total += r['total']
            group_weighted += r['weighted']
            group_fte += r['fte']

    lines.append("-" * 100)
    lines.append(
        f"{'合計(浦和除く)':<14} {group_home:>6} {group_fac:>6} {group_total:>6} "
        f"{group_fac/group_total*100:>5.0f}% {group_fte:>5.0f} {group_total/group_fte:>8.0f} "
        f"{group_weighted/group_fte:>12.0f}"
    )
    lines.append("")

    # 解釈セクション
    lines.append("■ 指標の読み方")
    lines.append("  収益指数/医師 = 居宅×1.0 + 施設×0.58 を医師常勤で割った相対値（売上の代理指標）")
    lines.append("  居宅シェア = 当院居宅患者数 ÷ 8km圏推定居宅需要（高齢者×4.5%）")
    lines.append("  努力指数 = 実患者合計 ÷ 理論獲得枠 ×100（100超=地域平均以上の獲得）")
    lines.append("  成果スコア = 市場効率を地域難易度で補正（高い=地域以上に好成績）")
    lines.append("")

    # ランキング
    ranked = [r for r in rows if r['performance_score'] is not None]
    ranked.sort(key=lambda x: x['rev_index_per_fte'], reverse=True)

    lines.append("■ 医師1人あたり収益指数ランキング（施設/居宅構成反映）")
    for i, r in enumerate(ranked, 1):
        lines.append(f"  {i:2}. {r['key']}: {r['rev_index_per_fte']:.0f} （患者{r['patients_per_fte']:.0f}/医師, 施設{r['fac_ratio']:.0f}%）")
    lines.append("")

    # 地域 vs 努力の判定
    lines.append("■ 地域性 vs 努力の判定")
    for r in sorted([x for x in rows if x['performance_score']], key=lambda x: x['performance_score'], reverse=True):
        if r['performance_score'] >= 120:
            verdict = "★地域以上の高成果（努力・体制が機能）"
        elif r['performance_score'] >= 80:
            verdict = "○地域並み（適正）"
        elif r['effort_index'] and r['effort_index'] >= 100:
            verdict = "△患者数は確保も効率面で課題"
        else:
            verdict = "×地域要因＋獲得不足の両面"
        lines.append(f"  {r['key']}: 成果スコア{r['performance_score']:.0f} / 努力指数{r['effort_index']:.0f} → {verdict}")
    lines.append("")

    # 施設偏重分析
    lines.append("■ 施設偏重院の収益構造")
    fac_heavy = sorted([r for r in rows if r['total'] > 0], key=lambda x: x['fac_ratio'], reverse=True)
    for r in fac_heavy[:5]:
        lines.append(
            f"  {r['key']}: 施設{r['fac_ratio']:.0f}% → "
            f"患者数は{r['total']}人だが収益指数は{r['rev_index_per_fte']:.0f}/医師 "
            f"（居宅{r['home']}人換算で同等収益なら施設偏重は{r['facility']}×0.58≈{r['facility']*w_fac:.0f}の寄与）"
        )
    lines.append("")

    # 本部向け提言
    lines.append("■ 本部評価への提言（実績データ反映）")
    lines.append("  1. 本院・所沢は患者/医師・居宅シェアとも最高水準 → 「努力不足」評価は不適切")
    lines.append("  2. 津田沼は施設70%超・患者475人/2医師 → 数量は良いが収益指数は施設ミックスで中位")
    lines.append("  3. 西日暮里・市川・浦和は医師1名体制で母数小 → 地域規模との比較で必ず最下位群")
    lines.append("  4. 高円寺は医師1名・患者250人・収益指数216 → 三軒茶屋と同型の高効率1医師体制")
    lines.append("  5. 調布は施設54%で患者325人/1.5医師=217/医師 → 多摩で高効率")
    lines.append("")

    report = "\n".join(lines)
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[機密] レポート保存: {OUTPUT_FILE}")
    return rows


if __name__ == "__main__":
    analyze()
