#!/usr/bin/env python3
"""2026 世界杯预测追踪与 Brier Score 回测。

用法:
    python3 prediction_tracker.py record <match_id> <pH> <pD> <pA> [--score 2-1] [--score2 1-1] [--note "..."]
    python3 prediction_tracker.py anchor <match_id> [--adj-h X] [--adj-d X] [--adj-a X] [--score ...] [--note ...]
    python3 prediction_tracker.py list
    python3 prediction_tracker.py score

依赖: 仅标准库 + elo_ratings.py（anchor 命令）
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from match_data import GROUP_MATCHES, ALL_MATCHES, MATCH_BY_ID, TEAM_CN

BJT = timezone(timedelta(hours=8))
DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data")
PRED_FILE = os.path.join(DATA_DIR, "predictions.json")
ODDS_FILE = os.path.join(DATA_DIR, "sporttery_odds.json")


def load_predictions() -> list[dict]:
    if os.path.exists(PRED_FILE):
        with open(PRED_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("predictions", [])
    return []


def save_predictions(preds: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRED_FILE, "w", encoding="utf-8") as f:
        json.dump({"predictions": preds}, f, ensure_ascii=False, indent=2)


def load_odds_probs(match_id: int) -> tuple[float, float, float] | None:
    if not os.path.exists(ODDS_FILE):
        return None
    with open(ODDS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("matches", []):
        if m.get("wcMatchId") == match_id:
            h, d, a = m["oddsH"], m["oddsD"], m["oddsA"]
            if h > 0 and d > 0 and a > 0:
                raw_h, raw_d, raw_a = 1 / h, 1 / d, 1 / a
                total = raw_h + raw_d + raw_a
                return raw_h / total, raw_d / total, raw_a / total
    return None


def parse_actual_result(score_str: str) -> tuple[float, float, float] | None:
    if not score_str:
        return None
    base = score_str.split("(")[0].strip()
    parts = base.split("-")
    if len(parts) != 2:
        return None
    try:
        g1, g2 = int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None
    if g1 > g2:
        return (1.0, 0.0, 0.0)
    elif g1 < g2:
        return (0.0, 0.0, 1.0)
    else:
        return (0.0, 1.0, 0.0)


def brier_score(probs: tuple[float, float, float], actual: tuple[float, float, float]) -> float:
    return sum((p - a) ** 2 for p, a in zip(probs, actual))


def cmd_record(args):
    mid = args.match_id
    if mid not in MATCH_BY_ID:
        print(f"  match_id {mid} 不存在", file=sys.stderr)
        sys.exit(1)

    m = MATCH_BY_ID[mid]
    ph, pd, pa = args.pH, args.pD, args.pA
    total = ph + pd + pa
    if total <= 0:
        print("  概率之和须大于 0", file=sys.stderr)
        sys.exit(1)
    ph, pd, pa = ph / total, pd / total, pa / total

    preds = load_predictions()
    existing = next((p for p in preds if p["matchId"] == mid), None)

    odds = load_odds_probs(mid)
    entry = {
        "matchId": mid,
        "recordTime": datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
        "probH": round(ph, 3),
        "probD": round(pd, 3),
        "probA": round(pa, 3),
    }
    if args.score:
        entry["predScore"] = args.score
    if args.score2:
        entry["predScore2"] = args.score2
    if args.note:
        entry["note"] = args.note
    if odds:
        entry["oddsProbH"] = round(odds[0], 3)
        entry["oddsProbD"] = round(odds[1], 3)
        entry["oddsProbA"] = round(odds[2], 3)

    if existing:
        preds = [p for p in preds if p["matchId"] != mid]
        print(f"\n  更新 M{mid} 的预测（覆盖旧记录）")
    else:
        print(f"\n  录入 M{mid} 的预测")

    preds.append(entry)
    preds.sort(key=lambda x: x["matchId"])
    save_predictions(preds)

    cn1 = TEAM_CN.get(m.team1, m.team1)
    cn2 = TEAM_CN.get(m.team2, m.team2)
    print(f"  {cn1} vs {cn2} ({m.date_str})")
    print(f"  我方:  {cn1}胜 {ph:.0%}   平 {pd:.0%}   {cn2}胜 {pa:.0%}")
    if odds:
        print(f"  赔率:  {cn1}胜 {odds[0]:.0%}   平 {odds[1]:.0%}   {cn2}胜 {odds[2]:.0%}")
    if args.score:
        s2 = f" / {args.score2}" if args.score2 else ""
        print(f"  比分:  {args.score}{s2}")
    print(f"  已保存至 {PRED_FILE}\n")


def cmd_list(_args):
    preds = load_predictions()
    if not preds:
        print("\n  暂无预测记录。用 record 命令录入。\n")
        return

    print()
    print("=" * 72)
    print("  预测记录")
    print("=" * 72)
    print()
    print(f"  {'M':>3}  {'比赛':<16} {'我H':>5} {'我D':>5} {'我A':>5}  {'赔H':>5} {'赔D':>5} {'赔A':>5}  {'实际':>5}  {'比分':<6}")
    print(f"  {'──':>3}  {'────':<16} {'──':>5} {'──':>5} {'──':>5}  {'──':>5} {'──':>5} {'──':>5}  {'──':>5}  {'──':<6}")

    for p in preds:
        mid = p["matchId"]
        m = MATCH_BY_ID[mid]
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        label = f"{cn1}v{cn2}"
        if len(label) > 14:
            label = label[:14]

        ph = f"{p['probH']:.0%}"
        pd_val = f"{p['probD']:.0%}"
        pa = f"{p['probA']:.0%}"

        oh = f"{p['oddsProbH']:.0%}" if "oddsProbH" in p else "  -"
        od = f"{p['oddsProbD']:.0%}" if "oddsProbD" in p else "  -"
        oa = f"{p['oddsProbA']:.0%}" if "oddsProbA" in p else "  -"

        actual = ""
        if m.score:
            result = parse_actual_result(m.score)
            if result:
                if result[0] == 1:
                    actual = "H"
                elif result[1] == 1:
                    actual = "D"
                else:
                    actual = "A"

        score_str = m.score or ""
        pred_score = p.get("predScore", "")

        print(f"  {mid:>3}  {label:<16} {ph:>5} {pd_val:>5} {pa:>5}  {oh:>5} {od:>5} {oa:>5}  {actual:>5}  {pred_score:<6}")

    print()
    finished = sum(1 for p in preds if MATCH_BY_ID.get(p["matchId"]) and MATCH_BY_ID[p["matchId"]].score)
    print(f"  共 {len(preds)} 条预测，{finished} 场已完赛")
    print("=" * 72)
    print()


def cmd_score(_args):
    preds = load_predictions()
    if not preds:
        print("\n  暂无预测记录。\n")
        return

    scored = []
    for p in preds:
        mid = p["matchId"]
        m = MATCH_BY_ID[mid]
        actual = parse_actual_result(m.score)
        if actual is None:
            continue
        our_probs = (p["probH"], p["probD"], p["probA"])
        our_bs = brier_score(our_probs, actual)

        odds_bs = None
        if "oddsProbH" in p:
            odds_probs = (p["oddsProbH"], p["oddsProbD"], p["oddsProbA"])
            odds_bs = brier_score(odds_probs, actual)

        scored.append({
            "matchId": mid,
            "match": m,
            "actual": actual,
            "ourProbs": our_probs,
            "ourBS": our_bs,
            "oddsProbs": (p.get("oddsProbH"), p.get("oddsProbD"), p.get("oddsProbA")) if "oddsProbH" in p else None,
            "oddsBS": odds_bs,
            "predScore": p.get("predScore"),
        })

    if not scored:
        print("\n  尚无已完赛的预测记录，无法计算 Brier Score。\n")
        return

    n = len(scored)
    our_avg_bs = sum(s["ourBS"] for s in scored) / n
    odds_count = sum(1 for s in scored if s["oddsBS"] is not None)
    odds_avg_bs = sum(s["oddsBS"] for s in scored if s["oddsBS"] is not None) / odds_count if odds_count else None

    our_correct = sum(1 for s in scored if _direction_correct(s["ourProbs"], s["actual"]))
    odds_correct = sum(1 for s in scored if s["oddsProbs"] and _direction_correct(s["oddsProbs"], s["actual"])) if odds_count else 0

    our_score_hit = sum(1 for s in scored if s["predScore"] and _score_match(s["predScore"], s["match"].score))

    print()
    print("=" * 68)
    print(f"  预测准确度报告 (N={n} 场已完赛)")
    print("=" * 68)
    print()
    print(f"  Brier Score（越低越好，均匀猜测≈0.667）")
    print(f"    我方:  {our_avg_bs:.3f}", end="")
    if odds_avg_bs is not None:
        diff = our_avg_bs - odds_avg_bs
        marker = "✓" if diff <= 0 else "⚠"
        print(f"    赔率:  {odds_avg_bs:.3f}    差值: {diff:+.3f} {marker}")
    else:
        print()

    print()
    print(f"  方向准确率（最高概率项命中）")
    print(f"    我方:  {our_correct}/{n} ({our_correct/n:.0%})", end="")
    if odds_count:
        print(f"    赔率:  {odds_correct}/{odds_count} ({odds_correct/odds_count:.0%})")
    else:
        print()

    pred_with_score = sum(1 for s in scored if s["predScore"])
    if pred_with_score:
        print(f"  比分命中:  {our_score_hit}/{pred_with_score}")

    print()
    print(f"  逐场明细:")

    for s in scored:
        mid = s["matchId"]
        m = s["match"]
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        label = f"{cn1}v{cn2}"

        result_char = "H" if s["actual"][0] == 1 else ("D" if s["actual"][1] == 1 else "A")
        our_h, our_d, our_a = [int(x * 100) for x in s["ourProbs"]]

        line = f"  M{mid:<3} {label:<12} 我[H{our_h}/D{our_d}/A{our_a}]"
        if s["oddsProbs"]:
            oh, od, oa = [int(x * 100) for x in s["oddsProbs"]]
            line += f" 赔[H{oh}/D{od}/A{oa}]"
        line += f" 实:{m.score}({result_char})"
        line += f" BS我{s['ourBS']:.2f}"
        if s["oddsBS"] is not None:
            line += f"/赔{s['oddsBS']:.2f}"
        print(line)

    print()
    print("=" * 68)
    print()


def _direction_correct(probs: tuple, actual: tuple) -> bool:
    pred_idx = max(range(3), key=lambda i: probs[i])
    return actual[pred_idx] == 1.0


def _score_match(pred_score: str, actual_score: str | None) -> bool:
    if not actual_score:
        return False
    pred_base = pred_score.split("(")[0].strip()
    actual_base = actual_score.split("(")[0].strip()
    return pred_base == actual_base


def _team_matches_played(team: str) -> int:
    return sum(1 for m in ALL_MATCHES if m.score and (m.team1 == team or m.team2 == team))


def cmd_anchor(args):
    from elo_ratings import load_elo, elo_to_probs

    mid = args.match_id
    if mid not in MATCH_BY_ID:
        print(f"  match_id {mid} 不存在", file=sys.stderr)
        sys.exit(1)

    m = MATCH_BY_ID[mid]
    cn1 = TEAM_CN.get(m.team1, m.team1)
    cn2 = TEAM_CN.get(m.team2, m.team2)

    odds = load_odds_probs(mid)
    if not odds:
        print(f"  未找到 M{mid} 的赔率数据，请先运行 sporttery_odds.py fetch", file=sys.stderr)
        sys.exit(1)

    elo = load_elo()
    r1 = elo.get(m.team1, 1500)
    r2 = elo.get(m.team2, 1500)
    elo_p = elo_to_probs(r1, r2)

    played = max(_team_matches_played(m.team1), _team_matches_played(m.team2))
    if played >= 2:
        odds_w, elo_w = 0.85, 0.15
        stage_label = "MD3"
    elif played >= 1:
        odds_w, elo_w = 0.80, 0.20
        stage_label = "MD2"
    else:
        odds_w, elo_w = 0.70, 0.30
        stage_label = "MD1"

    base_h = odds_w * odds[0] + elo_w * elo_p[0]
    base_d = odds_w * odds[1] + elo_w * elo_p[1]
    base_a = odds_w * odds[2] + elo_w * elo_p[2]

    adj_h = args.adj_h or 0.0
    adj_d = args.adj_d or 0.0
    adj_a = args.adj_a or 0.0

    is_structural = getattr(args, "structural", False)
    adj_limit = 0.25 if is_structural else 0.10
    adj_type = "structural" if is_structural else "tactical"

    raw_h = max(0.01, base_h + adj_h)
    raw_d = max(0.01, base_d + adj_d)
    raw_a = max(0.01, base_a + adj_a)
    total = raw_h + raw_d + raw_a
    final_h, final_d, final_a = raw_h / total, raw_d / total, raw_a / total

    print()
    print(f"  {cn1} vs {cn2} (M{mid} · Group {m.group} · {m.date_str})")
    print()
    print(f"  赔率隐含:  {cn1}胜 {odds[0]:.0%}   平 {odds[1]:.0%}   {cn2}胜 {odds[2]:.0%}")
    print(f"  Elo 概率:  {cn1}胜 {elo_p[0]:.0%}   平 {elo_p[1]:.0%}   {cn2}胜 {elo_p[2]:.0%}")
    print(f"  加权基准:  {cn1}胜 {base_h:.0%}   平 {base_d:.0%}   {cn2}胜 {base_a:.0%}  ({stage_label}: 赔率{odds_w:.0%}+Elo{elo_w:.0%})")

    if adj_h != 0 or adj_d != 0 or adj_a != 0:
        label = "结构性调整" if is_structural else "战术调整"
        print(f"  {label}:  {cn1}胜 {adj_h:+.0%}   平 {adj_d:+.0%}   {cn2}胜 {adj_a:+.0%}")

    print(f"  {'─' * 50}")
    print(f"  最终预测:  {cn1}胜 {final_h:.0%}   平 {final_d:.0%}   {cn2}胜 {final_a:.0%}")
    print()

    diff_h = final_h - odds[0]
    diff_d = final_d - odds[1]
    diff_a = final_a - odds[2]
    print(f"  与赔率偏差: {cn1}胜 {diff_h:+.0%}  平 {diff_d:+.0%}  {cn2}胜 {diff_a:+.0%}")

    max_adj = max(abs(adj_h), abs(adj_d), abs(adj_a))
    if max_adj > adj_limit:
        print(f"  ⚠ 调整超过 ±{adj_limit:.0%}（{adj_type}上限），请确认有充分理由")
    elif max_adj > 0:
        print(f"  调整幅度在合理范围内（{adj_type} ≤{adj_limit:.0%}）")

    preds = load_predictions()
    existing = next((p for p in preds if p["matchId"] == mid), None)
    if existing:
        preds = [p for p in preds if p["matchId"] != mid]

    entry = {
        "matchId": mid,
        "recordTime": datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
        "probH": round(final_h, 3),
        "probD": round(final_d, 3),
        "probA": round(final_a, 3),
        "oddsProbH": round(odds[0], 3),
        "oddsProbD": round(odds[1], 3),
        "oddsProbA": round(odds[2], 3),
        "method": "anchor",
        "adjustType": adj_type,
        "adjH": adj_h,
        "adjD": adj_d,
        "adjA": adj_a,
        "oddsWeight": odds_w,
        "eloWeight": elo_w,
    }
    if args.score:
        entry["predScore"] = args.score
    if args.score2:
        entry["predScore2"] = args.score2
    if args.note:
        entry["note"] = args.note

    preds.append(entry)
    preds.sort(key=lambda x: x["matchId"])
    save_predictions(preds)

    print()
    action = "更新" if existing else "录入"
    print(f"  已{action}预测 → {PRED_FILE}")
    print()


def cmd_trend(_args):
    preds = load_predictions()
    scored = []
    for p in preds:
        mid = p["matchId"]
        m = MATCH_BY_ID[mid]
        actual = parse_actual_result(m.score)
        if actual is None:
            continue
        our_bs = brier_score((p["probH"], p["probD"], p["probA"]), actual)
        odds_bs = None
        if "oddsProbH" in p:
            odds_bs = brier_score((p["oddsProbH"], p["oddsProbD"], p["oddsProbA"]), actual)
        scored.append({"matchId": mid, "ourBS": our_bs, "oddsBS": odds_bs, "match": m})

    if not scored:
        print("\n  尚无已完赛的预测记录\n")
        return

    print()
    print("=" * 68)
    print(f"  Brier Score 滚动趋势 (N={len(scored)})")
    print("=" * 68)
    print()
    print(f"  {'场次':<8} {'比赛':<16} {'我方BS':>8} {'赔率BS':>8} {'差值':>8} {'滚动5场':>8}")
    print(f"  {'──':<8} {'────':<16} {'────':>8} {'────':>8} {'──':>8} {'────':>8}")

    consecutive_worse = 0
    for i, s in enumerate(scored):
        mid = s["matchId"]
        m = s["match"]
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        label = f"{cn1}v{cn2}"[:14]

        odds_str = f"{s['oddsBS']:.2f}" if s["oddsBS"] is not None else "  -"
        diff_str = f"{s['ourBS'] - s['oddsBS']:+.2f}" if s["oddsBS"] is not None else "  -"

        window = scored[max(0, i - 4):i + 1]
        rolling = sum(x["ourBS"] for x in window) / len(window)
        rolling_str = f"{rolling:.3f}"

        if s["oddsBS"] is not None and s["ourBS"] > s["oddsBS"]:
            consecutive_worse += 1
        else:
            consecutive_worse = 0

        print(f"  M{mid:<6} {label:<16} {s['ourBS']:>8.2f} {odds_str:>8} {diff_str:>8} {rolling_str:>8}")

    print()
    our_avg = sum(s["ourBS"] for s in scored) / len(scored)
    odds_items = [s for s in scored if s["oddsBS"] is not None]
    odds_avg = sum(s["oddsBS"] for s in odds_items) / len(odds_items) if odds_items else None

    print(f"  总体 BS:   我方 {our_avg:.3f}", end="")
    if odds_avg is not None:
        print(f"   赔率 {odds_avg:.3f}")
    else:
        print()

    if consecutive_worse >= 3:
        print(f"\n  ⚠ 最近 {consecutive_worse} 场连续差于赔率 → 建议缩减战术调整幅度至 ±5%")
    elif consecutive_worse >= 2:
        print(f"\n  注意: 最近 {consecutive_worse} 场连续差于赔率")

    print()
    print("=" * 68)
    print()


def cmd_calibration(_args):
    preds = load_predictions()
    buckets: dict[str, list[tuple[float, int]]] = {
        "0-20%": [], "20-40%": [], "40-60%": [], "60-80%": [], "80-100%": [],
    }

    for p in preds:
        mid = p["matchId"]
        m = MATCH_BY_ID[mid]
        actual = parse_actual_result(m.score)
        if actual is None:
            continue
        for i, (prob, act) in enumerate(zip([p["probH"], p["probD"], p["probA"]], actual)):
            if prob < 0.20:
                buckets["0-20%"].append((prob, int(act)))
            elif prob < 0.40:
                buckets["20-40%"].append((prob, int(act)))
            elif prob < 0.60:
                buckets["40-60%"].append((prob, int(act)))
            elif prob < 0.80:
                buckets["60-80%"].append((prob, int(act)))
            else:
                buckets["80-100%"].append((prob, int(act)))

    print()
    print("=" * 60)
    print(f"  校准曲线 (Calibration)")
    print("=" * 60)
    print()
    print(f"  {'预测区间':<10} {'样本数':>6} {'平均预测':>8} {'实际命中':>8} {'偏差':>8}")
    print(f"  {'────':<10} {'──':>6} {'────':>8} {'────':>8} {'──':>8}")

    total_cal_error = 0
    total_samples = 0

    for bucket_name, items in buckets.items():
        n = len(items)
        if n == 0:
            print(f"  {bucket_name:<10} {n:>6}       -        -        -")
            continue
        avg_pred = sum(p for p, _ in items) / n
        actual_rate = sum(a for _, a in items) / n
        diff = actual_rate - avg_pred
        total_cal_error += abs(diff) * n
        total_samples += n
        print(f"  {bucket_name:<10} {n:>6} {avg_pred:>8.1%} {actual_rate:>8.1%} {diff:>+8.1%}")

    if total_samples > 0:
        avg_cal_error = total_cal_error / total_samples
        print()
        print(f"  加权平均校准误差: {avg_cal_error:.1%}")
        if avg_cal_error < 0.05:
            print(f"  校准良好")
        elif avg_cal_error < 0.10:
            print(f"  校准可接受")
        else:
            print(f"  ⚠ 校准偏差较大，预测概率与实际命中率存在系统性差异")

    print()
    print("=" * 60)
    print()


def main():
    parser = argparse.ArgumentParser(description="2026 世界杯预测追踪")
    sub = parser.add_subparsers(dest="command")

    p_rec = sub.add_parser("record", help="录入预测")
    p_rec.add_argument("match_id", type=int, help="比赛 ID (1-72)")
    p_rec.add_argument("pH", type=float, help="主胜概率")
    p_rec.add_argument("pD", type=float, help="平局概率")
    p_rec.add_argument("pA", type=float, help="客胜概率")
    p_rec.add_argument("--score", help="预测比分 (如 2-1)")
    p_rec.add_argument("--score2", help="第二预测比分")
    p_rec.add_argument("--note", help="备注")

    p_anc = sub.add_parser("anchor", help="赔率锚定预测（赔率+Elo加权 + 战术微调）")
    p_anc.add_argument("match_id", type=int, help="比赛 ID (1-72)")
    p_anc.add_argument("--adj-h", type=float, default=0.0, help="主胜概率调整 (如 +0.05)")
    p_anc.add_argument("--adj-d", type=float, default=0.0, help="平局概率调整")
    p_anc.add_argument("--adj-a", type=float, default=0.0, help="客胜概率调整")
    p_anc.add_argument("--structural", action="store_true", help="结构性调整（上限25%）")
    p_anc.add_argument("--score", help="预测比分 (如 2-1)")
    p_anc.add_argument("--score2", help="第二预测比分")
    p_anc.add_argument("--note", help="备注")

    sub.add_parser("list", help="所有预测及状态")
    sub.add_parser("score", help="Brier Score 报告")
    sub.add_parser("trend", help="Brier Score 滚动趋势")
    sub.add_parser("calibration", help="校准曲线")

    args = parser.parse_args()
    if args.command == "record":
        cmd_record(args)
    elif args.command == "anchor":
        cmd_anchor(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "trend":
        cmd_trend(args)
    elif args.command == "calibration":
        cmd_calibration(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
