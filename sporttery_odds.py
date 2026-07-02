#!/usr/bin/env python3
"""体彩竞彩足球赔率获取与预测分析工具。

用法:
    python3 sporttery_odds.py fetch     # 获取 HAD 胜平负赔率
    python3 sporttery_odds.py ttg       # 获取 TTG 总进球数赔率
    python3 sporttery_odds.py all       # 获取 HAD + TTG 全部赔率
    python3 sporttery_odds.py predict   # 基于赔率做预测分析

依赖: 仅标准库
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

from match_data import TEAM_CN, GROUP_MATCHES, ALL_MATCHES

SPORTTERY_HAD_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/"
    "getMatchCalculatorV1.qry?poolCode=HAD&channel=c"
)
SPORTTERY_TTG_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/"
    "getMatchCalculatorV1.qry?poolCode=TTG&channel=c"
)
SPORTTERY_CRS_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/"
    "getMatchCalculatorV1.qry?poolCode=CRS&channel=c"
)
SPORTTERY_HHAD_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/"
    "getMatchCalculatorV1.qry?poolCode=HHAD&channel=c"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    ),
    "Referer": "https://m.sporttery.cn/",
}
DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data")
ODDS_FILE = os.path.join(DATA_DIR, "sporttery_odds.json")

BJT = timezone(timedelta(hours=8))

CN_TO_EN = {v: k for k, v in TEAM_CN.items()}
CN_ALIASES = {
    "刚果(金)": "DR Congo",
    "刚果（金）": "DR Congo",
    "库拉索": "Curaçao",
    "乌兹别克斯坦": "Uzbekistan",
    "乌兹别克": "Uzbekistan",
}


def _resolve_cn(name: str) -> str | None:
    if name in CN_TO_EN:
        return CN_TO_EN[name]
    if name in CN_ALIASES:
        return CN_ALIASES[name]
    for cn, en in CN_TO_EN.items():
        if cn in name or name in cn:
            return en
    return None


def _fetch_sporttery(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    if not data.get("success"):
        print(f"API 错误: {data.get('errorMessage', '未知')}", file=sys.stderr)
        sys.exit(1)
    return data


def _resolve_match(home_cn: str, away_cn: str) -> tuple[str | None, str | None, int | None]:
    home_en = _resolve_cn(home_cn)
    away_en = _resolve_cn(away_cn)
    wc_match_id = None
    if home_en and away_en:
        for wm in ALL_MATCHES:
            if wm.team1 == home_en and wm.team2 == away_en:
                wc_match_id = wm.match_id
                break
    return home_en, away_en, wc_match_id


def fetch_odds() -> list[dict]:
    data = _fetch_sporttery(SPORTTERY_HAD_API)

    results = []
    for day in data["value"].get("matchInfoList", []):
        for m in day.get("subMatchList", []):
            if m.get("leagueCode") != "WCC":
                continue
            had = m.get("had", {})
            h, d, a = had.get("h", "0"), had.get("d", "0"), had.get("a", "0")

            home_cn = m.get("homeTeamAllName", "")
            away_cn = m.get("awayTeamAllName", "")
            home_en, away_en, wc_match_id = _resolve_match(home_cn, away_cn)

            results.append({
                "matchNum": m.get("matchNumStr", ""),
                "matchDate": m.get("matchDate", ""),
                "matchTime": m.get("matchTime", ""),
                "homeCn": home_cn,
                "awayCn": away_cn,
                "homeEn": home_en,
                "awayEn": away_en,
                "oddsH": float(h),
                "oddsD": float(d),
                "oddsA": float(a),
                "updateDate": had.get("updateDate", ""),
                "updateTime": had.get("updateTime", ""),
                "status": m.get("matchStatus", ""),
                "wcMatchId": wc_match_id,
            })

    return results


def fetch_ttg() -> list[dict]:
    data = _fetch_sporttery(SPORTTERY_TTG_API)

    results = []
    for day in data["value"].get("matchInfoList", []):
        for m in day.get("subMatchList", []):
            if m.get("leagueCode") != "WCC":
                continue
            ttg = m.get("ttg", {})

            home_cn = m.get("homeTeamAllName", "")
            away_cn = m.get("awayTeamAllName", "")
            home_en, away_en, wc_match_id = _resolve_match(home_cn, away_cn)

            odds = {}
            for i in range(8):
                key = f"s{i}"
                val = ttg.get(key)
                if val is not None:
                    odds[str(i) if i < 7 else "7+"] = float(val)

            results.append({
                "matchNum": m.get("matchNumStr", ""),
                "matchDate": m.get("matchDate", ""),
                "matchTime": m.get("matchTime", ""),
                "homeCn": home_cn,
                "awayCn": away_cn,
                "homeEn": home_en,
                "awayEn": away_en,
                "ttgOdds": odds,
                "updateDate": ttg.get("updateDate", ""),
                "updateTime": ttg.get("updateTime", ""),
                "status": m.get("matchStatus", ""),
                "wcMatchId": wc_match_id,
            })

    return results


def fetch_crs() -> list[dict]:
    data = _fetch_sporttery(SPORTTERY_CRS_API)

    results = []
    for day in data["value"].get("matchInfoList", []):
        for m in day.get("subMatchList", []):
            if m.get("leagueCode") != "WCC":
                continue
            crs = m.get("crs", {})

            home_cn = m.get("homeTeamAllName", "")
            away_cn = m.get("awayTeamAllName", "")
            home_en, away_en, wc_match_id = _resolve_match(home_cn, away_cn)

            scores: dict[str, float] = {}
            for k, v in crs.items():
                if not k.startswith("s") or k.endswith("f"):
                    continue
                if k in ("s1sa", "s1sd", "s1sh"):
                    label = {"s1sa": "负其他", "s1sd": "平其他", "s1sh": "胜其他"}[k]
                    scores[label] = float(v)
                elif "s" in k[1:]:
                    parts = k[1:].split("s")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        scores[f"{parts[0]}-{parts[1]}"] = float(v)

            results.append({
                "matchNum": m.get("matchNumStr", ""),
                "matchDate": m.get("matchDate", ""),
                "matchTime": m.get("matchTime", ""),
                "homeCn": home_cn,
                "awayCn": away_cn,
                "homeEn": home_en,
                "awayEn": away_en,
                "crsOdds": scores,
                "status": m.get("matchStatus", ""),
                "wcMatchId": wc_match_id,
            })

    return results


def odds_to_prob(h: float, d: float, a: float) -> tuple[float, float, float]:
    raw_h, raw_d, raw_a = 1 / h, 1 / d, 1 / a
    total = raw_h + raw_d + raw_a
    return raw_h / total, raw_d / total, raw_a / total


TTG_FILE = os.path.join(DATA_DIR, "sporttery_ttg.json")
CRS_FILE = os.path.join(DATA_DIR, "sporttery_crs.json")
HHAD_FILE = os.path.join(DATA_DIR, "sporttery_hhad.json")
ODDS_HISTORY = os.path.join(DATA_DIR, "sporttery_odds_history.json")
TTG_HISTORY = os.path.join(DATA_DIR, "sporttery_ttg_history.json")
CRS_HISTORY = os.path.join(DATA_DIR, "sporttery_crs_history.json")
HHAD_HISTORY = os.path.join(DATA_DIR, "sporttery_hhad_history.json")


def _append_history(history_path: str, matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"snapshots": []}
    data["snapshots"].append({"fetchTime": now, "matches": matches})
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_odds(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    payload = {"fetchTime": now, "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ODDS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _append_history(ODDS_HISTORY, matches)
    print(f"\n  💾 HAD 赔率已保存至 {ODDS_FILE}")


def save_ttg(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    payload = {"fetchTime": now, "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TTG_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _append_history(TTG_HISTORY, matches)
    print(f"  💾 TTG 赔率已保存至 {TTG_FILE}")


def load_odds() -> list[dict]:
    if not os.path.exists(ODDS_FILE):
        print("未找到赔率数据，正在获取...\n")
        matches = fetch_odds()
        save_odds(matches)
        return matches
    with open(ODDS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  📂 读取缓存赔率 (获取时间: {data['fetchTime']})\n")
    return data["matches"]


def print_odds_table(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    print()
    print("═" * 72)
    print(f"  2026 世界杯 · 体彩竞彩赔率 (HAD 胜平负)")
    print(f"  数据时间: {now}")
    print("═" * 72)
    print()
    print(f"  {'编号':<10} {'比赛':<22} {'北京时间':<16} {'胜':>6} {'平':>6} {'负':>6}")
    print(f"  {'────':<10} {'────':<22} {'────────':<16} {'──':>6} {'──':>6} {'──':>6}")

    for m in matches:
        name = f"{m['homeCn']} vs {m['awayCn']}"
        dt = f"{m['matchDate'][5:]} {m['matchTime'][:5]}"
        print(
            f"  {m['matchNum']:<10} {name:<22} {dt:<16} "
            f"{m['oddsH']:>6.2f} {m['oddsD']:>6.2f} {m['oddsA']:>6.2f}"
        )

    print()
    print(f"  共 {len(matches)} 场世界杯比赛在售")
    print("═" * 72)


def ttg_to_prob(odds: dict[str, float]) -> dict[str, float]:
    raw = {k: 1 / v for k, v in odds.items() if v > 0}
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def print_ttg_table(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    print()
    print("=" * 80)
    print(f"  2026 世界杯 · 体彩竞彩赔率 (TTG 总进球数)")
    print(f"  数据时间: {now}")
    print("=" * 80)
    print()

    hdr = f"  {'比赛':<22}"
    for i in range(8):
        label = f"{i}球" if i < 7 else "7+球"
        hdr += f" {label:>6}"
    print(hdr)
    print(f"  {'────':<22}" + " ──────" * 8)

    for m in matches:
        name = f"{m['homeCn']} vs {m['awayCn']}"
        odds = m["ttgOdds"]
        line = f"  {name:<22}"
        for i in range(8):
            key = str(i) if i < 7 else "7+"
            val = odds.get(key, 0)
            line += f" {val:>6.2f}"
        print(line)

    print()

    print(f"  {'比赛':<22}  最可能总球数   隐含概率   期望总球数")
    print(f"  {'────':<22}  ──────────   ────────   ──────────")
    for m in matches:
        name = f"{m['homeCn']} vs {m['awayCn']}"
        odds = m["ttgOdds"]
        probs = ttg_to_prob(odds)
        best_k = max(probs, key=probs.get)
        expected = sum(
            (int(k) if k != "7+" else 7) * p for k, p in probs.items()
        )
        print(f"  {name:<22}    {best_k:>3} 球     {probs[best_k]:>6.1%}       {expected:.2f}")

    print()
    print(f"  共 {len(matches)} 场世界杯比赛在售")
    print("=" * 80)
    print()


def save_crs(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    payload = {"fetchTime": now, "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CRS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _append_history(CRS_HISTORY, matches)
    print(f"  💾 CRS 赔率已保存至 {CRS_FILE}")


def fetch_hhad() -> list[dict]:
    data = _fetch_sporttery(SPORTTERY_HHAD_API)

    results = []
    for day in data["value"].get("matchInfoList", []):
        for m in day.get("subMatchList", []):
            if m.get("leagueCode") != "WCC":
                continue
            hhad = m.get("hhad", {})

            home_cn = m.get("homeTeamAllName", "")
            away_cn = m.get("awayTeamAllName", "")
            home_en, away_en, wc_match_id = _resolve_match(home_cn, away_cn)

            goal_line = hhad.get("goalLine", "")
            h = hhad.get("h", "0")
            d = hhad.get("d", "0")
            a = hhad.get("a", "0")

            results.append({
                "matchNum": m.get("matchNumStr", ""),
                "matchDate": m.get("matchDate", ""),
                "matchTime": m.get("matchTime", ""),
                "homeCn": home_cn,
                "awayCn": away_cn,
                "homeEn": home_en,
                "awayEn": away_en,
                "goalLine": goal_line,
                "oddsH": float(h),
                "oddsD": float(d),
                "oddsA": float(a),
                "updateDate": hhad.get("updateDate", ""),
                "updateTime": hhad.get("updateTime", ""),
                "status": m.get("matchStatus", ""),
                "wcMatchId": wc_match_id,
            })

    return results


def save_hhad(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    payload = {"fetchTime": now, "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HHAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _append_history(HHAD_HISTORY, matches)
    print(f"  💾 HHAD 赔率已保存至 {HHAD_FILE}")


def print_hhad_table(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    print()
    print("=" * 78)
    print(f"  2026 世界杯 · 体彩竞彩赔率 (HHAD 让球胜平负)")
    print(f"  数据时间: {now}")
    print("=" * 78)
    print()
    print(f"  {'编号':<10} {'比赛':<22} {'让球':>6} {'胜':>6} {'平':>6} {'负':>6}")
    print(f"  {'────':<10} {'────':<22} {'──':>6} {'──':>6} {'──':>6} {'──':>6}")

    for m in matches:
        name = f"{m['homeCn']} vs {m['awayCn']}"
        gl = m['goalLine']
        print(
            f"  {m['matchNum']:<10} {name:<22} {gl:>6} "
            f"{m['oddsH']:>6.2f} {m['oddsD']:>6.2f} {m['oddsA']:>6.2f}"
        )

    print()
    print(f"  共 {len(matches)} 场世界杯比赛在售")
    print("=" * 78)
    print()


def print_movement():
    if not os.path.exists(ODDS_HISTORY):
        print("\n  暂无赔率历史数据，请先多次运行 fetch 命令\n")
        return
    with open(ODDS_HISTORY, encoding="utf-8") as f:
        data = json.load(f)
    snapshots = data.get("snapshots", [])
    if len(snapshots) < 2:
        print(f"\n  仅有 {len(snapshots)} 次快照，至少需要 2 次才能计算变动")
        print(f"  请再运行一次 fetch 命令\n")
        return

    first = {m.get("wcMatchId", m.get("matchNum")): m for m in snapshots[0]["matches"]}
    last = {m.get("wcMatchId", m.get("matchNum")): m for m in snapshots[-1]["matches"]}

    print()
    print("=" * 82)
    print(f"  HAD 赔率变动追踪")
    print(f"  首次: {snapshots[0]['fetchTime']}  →  最新: {snapshots[-1]['fetchTime']}")
    print(f"  共 {len(snapshots)} 次快照")
    print("=" * 82)
    print()
    print(f"  {'比赛':<22} {'初始赔率':>14} {'当前赔率':>14} {'概率变化':>20} {'信号':>4}")
    print(f"  {'────':<22} {'──────':>14} {'──────':>14} {'──────':>20} {'──':>4}")

    for key in last:
        if key not in first:
            continue
        f_m = first[key]
        l_m = last[key]
        name = f"{l_m['homeCn']} vs {l_m['awayCn']}"

        f_h, f_d, f_a = f_m["oddsH"], f_m["oddsD"], f_m["oddsA"]
        l_h, l_d, l_a = l_m["oddsH"], l_m["oddsD"], l_m["oddsA"]

        fp_h, fp_d, fp_a = odds_to_prob(f_h, f_d, f_a)
        lp_h, lp_d, lp_a = odds_to_prob(l_h, l_d, l_a)

        dh = lp_h - fp_h
        dd = lp_d - fp_d
        da = lp_a - fp_a

        max_change = max(abs(dh), abs(dd), abs(da))
        signal = " " if max_change < 0.03 else ("!" if max_change < 0.10 else "!!")

        init_str = f"{f_h:.2f}/{f_d:.2f}/{f_a:.2f}"
        curr_str = f"{l_h:.2f}/{l_d:.2f}/{l_a:.2f}"
        prob_str = f"H{dh:+.0%} D{dd:+.0%} A{da:+.0%}"

        print(f"  {name:<22} {init_str:>14} {curr_str:>14} {prob_str:>20} {signal:>4}")

    print()
    print("=" * 82)
    print()


def print_crs_table(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    print()
    print("=" * 80)
    print(f"  2026 世界杯 · 体彩竞彩赔率 (CRS 比分)")
    print(f"  数据时间: {now}")
    print("=" * 80)
    print()

    for m in matches:
        scores = m["crsOdds"]
        top5 = sorted(
            [(k, v) for k, v in scores.items() if k not in ("负其他", "平其他", "胜其他")],
            key=lambda x: x[1],
        )[:5]
        name = f"{m['homeCn']} vs {m['awayCn']}"
        mc = f" (M{m['wcMatchId']})" if m.get("wcMatchId") else ""
        line = f"  {name}{mc}:  "
        line += "  ".join(f"{s} @{o:.2f}" for s, o in top5)
        print(line)

    print()
    print(f"  共 {len(matches)} 场世界杯比赛在售")
    print("=" * 80)
    print()


def print_prediction(matches: list[dict]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    print()
    print("═" * 72)
    print(f"  2026 世界杯 · 体彩赔率预测分析")
    print(f"  分析时间: {now}")
    print("═" * 72)

    for m in matches:
        ph, pd, pa = odds_to_prob(m["oddsH"], m["oddsD"], m["oddsA"])
        margin = 1 / m["oddsH"] + 1 / m["oddsD"] + 1 / m["oddsA"] - 1

        probs = [("胜", ph, m["oddsH"]), ("平", pd, m["oddsD"]), ("负", pa, m["oddsA"])]
        probs_sorted = sorted(probs, key=lambda x: -x[1])
        best = probs_sorted[0]

        if best[1] >= 0.60:
            confidence = "🔴 高置信"
        elif best[1] >= 0.45:
            confidence = "🟡 中置信"
        else:
            confidence = "🟢 低置信（均势）"

        if best[0] == "胜":
            result_text = f"{m['homeCn']}获胜"
        elif best[0] == "负":
            result_text = f"{m['awayCn']}获胜"
        else:
            result_text = "平局"

        dt = f"{m['matchDate'][5:]} {m['matchTime'][:5]}"
        mc_id = f" (M{m['wcMatchId']})" if m["wcMatchId"] else ""

        print(f"\n  ┌─ {m['matchNum']}{mc_id} {m['homeCn']} vs {m['awayCn']}")
        print(f"  │  北京时间: {dt}")
        print(f"  │")
        print(f"  │  赔率:  胜 {m['oddsH']:.2f}  平 {m['oddsD']:.2f}  负 {m['oddsA']:.2f}")
        print(f"  │  概率:  胜 {ph:.1%}   平 {pd:.1%}   负 {pa:.1%}")
        print(f"  │  庄家利润率: {margin:.1%}")
        print(f"  │")
        print(f"  │  📊 推荐: {best[0]}（{result_text}）— {best[1]:.1%} {confidence}")

        if ph >= 0.60:
            gap = m["oddsH"]
            if gap <= 1.20:
                print(f"  │  💡 赔率极低({gap:.2f})，强队碾压局，大概率大胜")
            else:
                print(f"  │  💡 主胜概率高，稳健选择")
        elif pa >= 0.60:
            print(f"  │  💡 客队实力占优，客胜概率大")
        elif max(ph, pd, pa) - min(ph, pd, pa) < 0.10:
            print(f"  │  💡 三项概率接近，混战局面，慎选")
        elif pd >= ph and pd >= pa:
            print(f"  │  💡 平局概率最高或接近，可考虑防平")

        print(f"  └{'─' * 50}")

    print()
    print("═" * 72)
    print(f"  ⚠  赔率仅反映市场预期，不构成投注建议")
    print("═" * 72)
    print()


def cmd_fetch(args):
    print("\n  📡 正在获取体彩竞彩 HAD 赔率...")
    matches = fetch_odds()
    if not matches:
        print("  ⚠  当前无世界杯比赛在售")
        return
    print_odds_table(matches)
    save_odds(matches)


def cmd_ttg(args):
    print("\n  📡 正在获取体彩竞彩 TTG 赔率...")
    matches = fetch_ttg()
    if not matches:
        print("  ⚠  当前无世界杯比赛在售")
        return
    print_ttg_table(matches)
    save_ttg(matches)


def cmd_crs(args):
    print("\n  📡 正在获取体彩竞彩 CRS 比分赔率...")
    matches = fetch_crs()
    if not matches:
        print("  ⚠  当前无世界杯比赛在售")
        return
    print_crs_table(matches)
    save_crs(matches)


def cmd_hhad(args):
    print("\n  📡 正在获取体彩竞彩 HHAD 让球赔率...")
    matches = fetch_hhad()
    if not matches:
        print("  ⚠  当前无世界杯比赛在售")
        return
    print_hhad_table(matches)
    save_hhad(matches)


def cmd_movement(args):
    print_movement()


def cmd_all(args):
    print("\n  📡 正在获取体彩竞彩赔率 (HAD + TTG + CRS + HHAD)...")
    had = fetch_odds()
    if had:
        print_odds_table(had)
        save_odds(had)

    ttg = fetch_ttg()
    if ttg:
        print_ttg_table(ttg)
        save_ttg(ttg)

    crs = fetch_crs()
    if crs:
        print_crs_table(crs)
        save_crs(crs)

    hhad = fetch_hhad()
    if hhad:
        print_hhad_table(hhad)
        save_hhad(hhad)

    if not had and not ttg and not crs and not hhad:
        print("  ⚠  当前无世界杯比赛在售")


def cmd_predict(args):
    matches = load_odds()
    if not matches:
        print("  ⚠  无赔率数据可供分析")
        return
    print_prediction(matches)


def main():
    parser = argparse.ArgumentParser(description="体彩竞彩世界杯赔率工具")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("fetch", help="获取当前 HAD 胜平负赔率")
    sub.add_parser("ttg", help="获取当前 TTG 总进球数赔率")
    sub.add_parser("crs", help="获取当前 CRS 比分赔率")
    sub.add_parser("hhad", help="获取当前 HHAD 让球胜平负赔率")
    sub.add_parser("all", help="获取 HAD + TTG + CRS + HHAD 全部赔率")
    sub.add_parser("movement", help="HAD 赔率变动追踪")
    sub.add_parser("predict", help="基于赔率做预测分析")

    args = parser.parse_args()
    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "ttg":
        cmd_ttg(args)
    elif args.command == "crs":
        cmd_crs(args)
    elif args.command == "hhad":
        cmd_hhad(args)
    elif args.command == "all":
        cmd_all(args)
    elif args.command == "movement":
        cmd_movement(args)
    elif args.command == "predict":
        cmd_predict(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
