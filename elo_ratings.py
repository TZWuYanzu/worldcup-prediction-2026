#!/usr/bin/env python3
"""2026 世界杯 Elo 评分系统 — 球队实力量化基准。

用法:
    python3 elo_ratings.py list               # 48 队 Elo 排名
    python3 elo_ratings.py predict <match>     # Elo 预测胜平负概率
    python3 elo_ratings.py update              # 根据已有结果更新 Elo

<match> 支持: match_id (1-72)、英文队名、中文队名

依赖: 仅标准库
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta

from match_data import GROUP_MATCHES, ALL_MATCHES, MATCH_BY_ID, TEAM_CN, resolve_team_name

BJT = timezone(timedelta(hours=8))
DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data")
ELO_FILE = os.path.join(DATA_DIR, "elo_ratings.json")

K_BASE = 60

PRE_TOURNAMENT_ELO: dict[str, int] = {
    "Argentina": 2073, "France": 2045, "Spain": 2037, "England": 2020,
    "Brazil": 1986, "Portugal": 1980, "Netherlands": 1940, "Belgium": 1930,
    "Germany": 1927, "Colombia": 1910, "Morocco": 1905, "Uruguay": 1895,
    "Croatia": 1880, "Japan": 1870, "Senegal": 1810, "Norway": 1810,
    "United States": 1800, "Switzerland": 1795, "Mexico": 1790,
    "South Korea": 1780, "Iran": 1775, "Australia": 1770,
    "Ecuador": 1768, "Turkey": 1765, "Egypt": 1760,
    "Austria": 1755, "Ivory Coast": 1750, "Canada": 1735,
    "Scotland": 1720, "Sweden": 1715, "Saudi Arabia": 1700,
    "Tunisia": 1695, "Algeria": 1690, "Iraq": 1685,
    "Czech Republic": 1680, "Ghana": 1665, "Paraguay": 1660,
    "Bosnia and Herzegovina": 1655, "DR Congo": 1650,
    "Uzbekistan": 1645, "South Africa": 1640, "Panama": 1570,
    "Jordan": 1555, "Qatar": 1545, "New Zealand": 1530,
    "Cape Verde": 1525, "Haiti": 1455, "Curaçao": 1410,
}

TEAM_GROUP: dict[str, str] = {}
for m in GROUP_MATCHES:
    if m.group:
        TEAM_GROUP.setdefault(m.team1, m.group)
        TEAM_GROUP.setdefault(m.team2, m.group)


def elo_expected(r_self: float, r_opp: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((r_opp - r_self) / 400.0))


def elo_k(goal_diff: int) -> float:
    return K_BASE * math.log(abs(goal_diff) + 1)


def elo_update(r_self: float, r_opp: float, score: float, goal_diff: int) -> float:
    e = elo_expected(r_self, r_opp)
    k = elo_k(goal_diff)
    return r_self + k * (score - e)


def elo_to_probs(elo_home: float, elo_away: float) -> tuple[float, float, float]:
    d = elo_home - elo_away
    exp_home = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
    draw_base = 0.26
    draw_prob = draw_base * (1.0 - 1.3 * abs(exp_home - 0.5))
    draw_prob = max(0.10, min(0.30, draw_prob))
    remain = 1.0 - draw_prob
    home_prob = remain * exp_home
    away_prob = remain * (1.0 - exp_home)
    return home_prob, draw_prob, away_prob


def parse_score(score_str: str) -> tuple[int, int] | None:
    if not score_str:
        return None
    base = score_str.split("(")[0].strip()
    parts = base.split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None


def compute_updated_elo() -> dict[str, float]:
    elo = {k: float(v) for k, v in PRE_TOURNAMENT_ELO.items()}

    played = [(m.match_id, m) for m in ALL_MATCHES if m.score]
    played.sort(key=lambda x: (x[1].date_str, x[1].utc_hour, x[1].utc_min))

    for _mid, m in played:
        sc = parse_score(m.score)
        if sc is None:
            continue
        g1, g2 = sc
        gd = abs(g1 - g2)

        r1 = elo.get(m.team1, 1500)
        r2 = elo.get(m.team2, 1500)

        if g1 > g2:
            s1, s2 = 1.0, 0.0
        elif g1 < g2:
            s1, s2 = 0.0, 1.0
        else:
            s1, s2 = 0.5, 0.5

        new_r1 = elo_update(r1, r2, s1, gd)
        new_r2 = elo_update(r2, r1, s2, gd)
        elo[m.team1] = new_r1
        elo[m.team2] = new_r2

    return elo


def save_elo(elo: dict[str, float]):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    matches_played = sum(1 for m in ALL_MATCHES if m.score)
    payload = {
        "updateTime": now,
        "matchesProcessed": matches_played,
        "ratings": {k: round(v) for k, v in elo.items()},
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ELO_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_elo() -> dict[str, float]:
    if os.path.exists(ELO_FILE):
        with open(ELO_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {k: float(v) for k, v in data["ratings"].items()}
    return compute_updated_elo()


def resolve_match(arg: str) -> int | None:
    try:
        mid = int(arg)
        if mid in MATCH_BY_ID:
            return mid
    except ValueError:
        pass
    en = resolve_team_name(arg)
    if en:
        for m in reversed(ALL_MATCHES):
            if m.score and (m.team1 == en or m.team2 == en):
                return m.match_id
        for m in ALL_MATCHES:
            if m.team1 == en or m.team2 == en:
                return m.match_id
    return None


def load_odds_probs(match_id: int) -> tuple[float, float, float] | None:
    odds_file = os.path.join(DATA_DIR, "sporttery_odds.json")
    if not os.path.exists(odds_file):
        return None
    with open(odds_file, encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("matches", []):
        if m.get("wcMatchId") == match_id:
            h, d, a = m["oddsH"], m["oddsD"], m["oddsA"]
            if h > 0 and d > 0 and a > 0:
                raw_h, raw_d, raw_a = 1 / h, 1 / d, 1 / a
                total = raw_h + raw_d + raw_a
                return raw_h / total, raw_d / total, raw_a / total
    return None


def cmd_list(_args):
    elo = load_elo()
    pre = PRE_TOURNAMENT_ELO

    ranked = sorted(elo.items(), key=lambda x: -x[1])

    print()
    print("=" * 62)
    print("  2026 世界杯 48 队 Elo 评分")
    print("=" * 62)
    print()
    print(f"  {'#':>3}  {'球队':<14} {'Elo':>6} {'变动':>6}  {'组':>2}")
    print(f"  {'──':>3}  {'────':<14} {'───':>6} {'───':>6}  {'─':>2}")

    for i, (team, rating) in enumerate(ranked, 1):
        cn = TEAM_CN.get(team, team)
        delta = round(rating - pre.get(team, rating))
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        group = TEAM_GROUP.get(team, "?")
        display = cn if len(cn) <= 6 else cn[:6]
        print(f"  {i:>3}  {display:<14} {round(rating):>6} {delta_str:>6}  {group:>2}")

    matches_played = sum(1 for m in ALL_MATCHES if m.score)
    print()
    print(f"  已处理 {matches_played}/72 场比赛结果")
    print("=" * 62)
    print()


def cmd_predict(args):
    mid = resolve_match(args.match)
    if mid is None:
        print(f"  未找到比赛: {args.match}", file=sys.stderr)
        sys.exit(1)

    m = MATCH_BY_ID[mid]
    elo = load_elo()

    r1 = elo.get(m.team1, 1500)
    r2 = elo.get(m.team2, 1500)
    ph, pd, pa = elo_to_probs(r1, r2)

    cn1 = TEAM_CN.get(m.team1, m.team1)
    cn2 = TEAM_CN.get(m.team2, m.team2)
    score_str = f"  {m.score}" if m.score else ""

    print()
    print(f"  {cn1} vs {cn2} (M{mid} · Group {m.group} · {m.date_str}){score_str}")
    print()
    print(f"  Elo:   {cn1} {round(r1)}  vs  {cn2} {round(r2)}  (差值 {round(r1-r2):+d})")
    print(f"  Elo:   {cn1}胜 {ph:.0%}   平 {pd:.0%}   {cn2}胜 {pa:.0%}")

    odds = load_odds_probs(mid)
    if odds:
        oh, od, oa = odds
        print(f"  赔率:  {cn1}胜 {oh:.0%}   平 {od:.0%}   {cn2}胜 {oa:.0%}")

        diffs = []
        if abs(ph - oh) > 0.05:
            if ph > oh:
                diffs.append(f"Elo 更看好{cn1} ({ph-oh:+.0%})")
            else:
                diffs.append(f"Elo 更看好{cn2} ({pa-oa:+.0%})")
        if abs(pd - od) > 0.05:
            diffs.append(f"Elo 平局概率{'偏高' if pd > od else '偏低'} ({pd-od:+.0%})")

        if diffs:
            print(f"  分歧:  {'; '.join(diffs)}")
        else:
            print(f"  分歧:  Elo 与赔率基本一致")

    print()


def cmd_update(_args):
    print("\n  正在计算 Elo 更新...")
    elo = compute_updated_elo()
    save_elo(elo)

    matches_played = sum(1 for m in ALL_MATCHES if m.score)
    print(f"  已处理 {matches_played} 场比赛结果")

    ranked = sorted(elo.items(), key=lambda x: -x[1])[:5]
    print(f"\n  当前 Top 5:")
    for i, (team, rating) in enumerate(ranked, 1):
        cn = TEAM_CN.get(team, team)
        delta = round(rating - PRE_TOURNAMENT_ELO.get(team, rating))
        print(f"    {i}. {cn} {round(rating)} ({delta:+d})")

    print(f"\n  已保存至 {ELO_FILE}")
    print()


def main():
    parser = argparse.ArgumentParser(description="2026 世界杯 Elo 评分系统")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="48 队 Elo 排名")

    p_pred = sub.add_parser("predict", help="Elo 预测胜平负概率")
    p_pred.add_argument("match", help="match_id / 球队名（中英文）")

    sub.add_parser("update", help="根据已有结果更新 Elo")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "predict":
        cmd_predict(args)
    elif args.command == "update":
        cmd_update(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
