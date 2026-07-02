#!/usr/bin/env python3
"""2026 世界杯简化 xG（预期进球）模型 — 基于 FIFA API 射门坐标。

用法:
    python3 xg_model.py match <match>    # 单场 xG 分析
    python3 xg_model.py team <team>      # 球队累计 xG/xGA 汇总
    python3 xg_model.py subs <match>     # 单场换人效果分析
    python3 xg_model.py subs <team>      # 球队换人模式汇总

<match> 支持: match_id (1-72)、英文队名、中文队名
<team> 支持: 英文队名、中文队名

依赖: 仅标准库 + fifa_stats.py（复用 FIFA API 函数）
"""

import argparse
import math
import re
import sys

from fifa_stats import (
    _build_match_index,
    _fetch_timeline,
    _fetch_live,
    _parse_lineup,
    _our_name,
    _team_cn,
    _resolve_team_input,
    _localized,
)
from match_data import GROUP_MATCHES, ALL_MATCHES, TEAM_CN

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
GOAL_WIDTH = 7.32

POST_Y1 = 50.0 - GOAL_WIDTH / 2 * 100 / PITCH_WIDTH  # ~44.62
POST_Y2 = 50.0 + GOAL_WIDTH / 2 * 100 / PITCH_WIDTH  # ~55.38


def shot_geometry(x: float, y: float) -> tuple[float, float]:
    if x < 50:
        goal_x = 0.0
    else:
        goal_x = 100.0

    dx = abs(x - goal_x) * PITCH_LENGTH / 100
    dy = abs(y - 50.0) * PITCH_WIDTH / 100
    distance = math.sqrt(dx * dx + dy * dy)

    p_dx = abs(x - goal_x) * PITCH_LENGTH / 100
    p1_dy = (y - POST_Y1) * PITCH_WIDTH / 100
    p2_dy = (y - POST_Y2) * PITCH_WIDTH / 100

    a1 = math.atan2(p1_dy, p_dx)
    a2 = math.atan2(p2_dy, p_dx)
    angle = abs(a1 - a2)

    return distance, angle


def shot_xg(distance_m: float, angle_rad: float) -> float:
    base = 0.96 * math.exp(-distance_m / 12.0)
    max_angle = math.pi / 2
    angle_factor = (min(angle_rad, max_angle) / max_angle) ** 0.5
    xg = base * angle_factor
    return max(0.01, min(0.95, xg))


def extract_shots(events: list[dict], match_info: dict) -> list[dict]:
    home_fifa = match_info["home_fifa"]
    away_fifa = match_info["away_fifa"]
    home_en = match_info["home"]
    away_en = match_info["away"]

    team_ids: dict[str, str] = {}
    for e in events:
        tid = e.get("IdTeam", "")
        if not tid:
            continue
        desc = _localized(e.get("EventDescription", []))
        if home_fifa in desc or home_en in desc:
            team_ids[tid] = home_en
        elif away_fifa in desc or away_en in desc:
            team_ids[tid] = away_en

    goal_keys: set[tuple] = set()
    for e in events:
        if e.get("Type") == 0:
            x = e.get("PositionX")
            y = e.get("PositionY")
            minute = e.get("MatchMinute", "")
            if x is not None and y is not None:
                goal_keys.add((minute, round(x, 2), round(y, 2)))

    shots = []
    seen: set[tuple] = set()
    for e in events:
        etype = e.get("Type", -1)
        if etype not in (0, 12):
            continue
        x = e.get("PositionX")
        y = e.get("PositionY")
        if x is None or y is None:
            continue

        minute = e.get("MatchMinute", "")
        key = (minute, round(x, 2), round(y, 2))
        if key in seen:
            continue
        seen.add(key)

        tid = e.get("IdTeam", "")
        team = team_ids.get(tid, "?")

        desc = _localized(e.get("EventDescription", []))
        player = ""
        if desc:
            for part in desc.split("("):
                part = part.strip()
                if part and not part.startswith(("attempts", "scores", "Goal")):
                    player = part.rstrip(") ")
                    break

        dist, angle = shot_geometry(x, y)
        xg = shot_xg(dist, angle)
        is_goal = key in goal_keys

        shots.append({
            "minute": minute,
            "team": team,
            "player": player,
            "x": x,
            "y": y,
            "distance": dist,
            "angle": angle,
            "xg": xg,
            "is_goal": is_goal,
        })

    return shots


def parse_minute_num(minute_str: str) -> int:
    m = re.match(r"(\d+)'\+?(\d+)?", minute_str.strip())
    if m:
        return int(m.group(1)) + (int(m.group(2)) if m.group(2) else 0)
    m2 = re.match(r"(\d+)\+?(\d+)?", minute_str.strip())
    if m2:
        return int(m2.group(1)) + (int(m2.group(2)) if m2.group(2) else 0)
    return 0


def get_substitutions(fifa_id: str, match_info: dict) -> dict[str, list[dict]]:
    live = _fetch_live(fifa_id)
    if not live:
        return {"home": [], "away": []}
    result = {}
    for side, key in [("home", "HomeTeam"), ("away", "AwayTeam")]:
        team_data = live.get(key, {})
        lineup = _parse_lineup(team_data)
        subs = []
        for s in lineup.get("substitutions", []):
            minute = parse_minute_num(s["minute"])
            minute_str = s["minute"]
            if minute == 0 and not minute_str.startswith("0'"):
                minute = 46
                minute_str = "46'(HT)"
            subs.append({
                "minute": minute,
                "minute_str": minute_str,
                "off": s["off"],
                "on": s["on"],
            })
        subs.sort(key=lambda x: x["minute"])
        result[side] = subs
    return result


def split_by_subs(shots: list[dict], subs: list[dict], team: str,
                  match_end: int = 95) -> list[dict]:
    sub_times = sorted(set(s["minute"] for s in subs))
    boundaries = [0] + sub_times + [match_end]

    phases = []
    for i in range(len(boundaries) - 1):
        t_start, t_end = boundaries[i], boundaries[i + 1]
        duration = max(t_end - t_start, 1)

        phase_shots_for = [s for s in shots
                           if s["team"] == team
                           and t_start <= parse_minute_num(s["minute"]) < t_end]
        phase_shots_against = [s for s in shots
                               if s["team"] != team and s["team"] != "?"
                               and t_start <= parse_minute_num(s["minute"]) < t_end]

        xg_for = sum(s["xg"] for s in phase_shots_for)
        xg_against = sum(s["xg"] for s in phase_shots_against)
        goals_for = sum(1 for s in phase_shots_for if s["is_goal"])
        goals_against = sum(1 for s in phase_shots_against if s["is_goal"])

        subs_at = [s for s in subs if s["minute"] == t_start] if t_start > 0 else []

        phases.append({
            "start": t_start,
            "end": t_end,
            "duration": duration,
            "xg_for": xg_for,
            "xg_against": xg_against,
            "shots_for": len(phase_shots_for),
            "shots_against": len(phase_shots_against),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "xg_rate": xg_for / duration * 10,
            "xga_rate": xg_against / duration * 10,
            "subs_at": subs_at,
            "shot_details_for": phase_shots_for,
        })
    return phases


def _find_sub_goals(phases: list[dict], subs: list[dict]) -> list[str]:
    sub_players = set()
    results = []
    for phase in phases:
        for s in phase["subs_at"]:
            sub_players.add(s["on"].upper())
        for shot in phase["shot_details_for"]:
            if shot["is_goal"] and shot["player"].upper() in sub_players:
                results.append(
                    f"{shot['player']} ({shot['minute']}, xG={shot['xg']:.3f})"
                )
    return results


def _resolve_match(arg: str, index: dict) -> dict | None:
    if arg.isdigit():
        mid = int(arg)
        if mid in index:
            return index[mid]
        print(f"  未找到 match_id={mid}", file=sys.stderr)
        return None

    team = _resolve_team_input(arg)
    if not team:
        print(f"  无法识别: {arg}", file=sys.stderr)
        return None

    candidates = [e for e in index.values()
                  if (e["home"] == team or e["away"] == team) and e["score"]]
    if not candidates:
        print(f"  {_team_cn(team)} 无已完赛比赛", file=sys.stderr)
        return None

    candidates.sort(key=lambda e: e["date"], reverse=True)
    return candidates[0]


def cmd_match(args):
    print("\n  正在获取 FIFA 比赛数据...")
    index = _build_match_index()
    info = _resolve_match(args.match, index)
    if not info:
        sys.exit(1)

    events = _fetch_timeline(info["fifa_id"])
    if not events:
        print("  无法获取比赛事件数据", file=sys.stderr)
        sys.exit(1)

    shots = extract_shots(events, info)
    if not shots:
        print("  未找到射门数据")
        return

    h_cn = _team_cn(info["home"])
    a_cn = _team_cn(info["away"])
    mid = info["match_id"]

    h_xg = sum(s["xg"] for s in shots if s["team"] == info["home"])
    a_xg = sum(s["xg"] for s in shots if s["team"] == info["away"])
    h_goals = sum(1 for s in shots if s["team"] == info["home"] and s["is_goal"])
    a_goals = sum(1 for s in shots if s["team"] == info["away"] and s["is_goal"])

    print()
    print("=" * 68)
    print(f"  {h_cn} {info['score']} {a_cn} (M{mid}) · xG 分析")
    print("=" * 68)
    print()
    print(f"  xG 总计:  {h_cn} {h_xg:.2f}  vs  {a_cn} {a_xg:.2f}")
    print()
    print(f"  {'Min':<10} {'球队':<10} {'球员':<18} {'距离':>6} {'角度':>6} {'xG':>6}  {'结果':<6}")
    print(f"  {'───':<10} {'──':<10} {'────':<18} {'──':>6} {'──':>6} {'──':>6}  {'──':<6}")

    for s in shots:
        team_label = _team_cn(s["team"]) if s["team"] != "?" else "?"
        if len(team_label) > 8:
            team_label = team_label[:8]
        player = s["player"][:16] if s["player"] else "?"
        result = "进球" if s["is_goal"] else ""
        print(
            f"  {s['minute']:<10} {team_label:<10} {player:<18} "
            f"{s['distance']:>5.1f}m {s['angle']:>5.2f} {s['xg']:>5.3f}  {result:<6}"
        )

    print()
    print(f"  进球 vs xG:")
    h_diff = h_goals - h_xg
    a_diff = a_goals - a_xg
    h_tag = "运气偏高" if h_diff > 0.5 else ("运气偏低" if h_diff < -0.5 else "正常")
    a_tag = "运气偏高" if a_diff > 0.5 else ("运气偏低" if a_diff < -0.5 else "正常")
    print(f"    {h_cn}: 实际 {h_goals} 球 / xG {h_xg:.2f} → 超额 {h_diff:+.2f}（{h_tag}）")
    print(f"    {a_cn}: 实际 {a_goals} 球 / xG {a_xg:.2f} → 超额 {a_diff:+.2f}（{a_tag}）")
    print()
    print("=" * 68)
    print()


def cmd_team(args):
    team = _resolve_team_input(args.team)
    if not team:
        print(f"  无法识别球队: {args.team}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  正在获取 {_team_cn(team)} 的比赛数据...")
    index = _build_match_index()

    matches = [e for e in index.values()
               if (e["home"] == team or e["away"] == team) and e["score"]]
    matches.sort(key=lambda e: e["date"])

    if not matches:
        print(f"  {_team_cn(team)} 无已完赛比赛")
        return

    cn = _team_cn(team)
    total_xg, total_xga, total_g, total_ga = 0.0, 0.0, 0, 0
    rows = []

    for info in matches:
        events = _fetch_timeline(info["fifa_id"])
        if not events:
            continue
        shots = extract_shots(events, info)

        xg_for = sum(s["xg"] for s in shots if s["team"] == team)
        xg_against = sum(s["xg"] for s in shots if s["team"] != team and s["team"] != "?")
        goals_for = sum(1 for s in shots if s["team"] == team and s["is_goal"])
        goals_against = sum(1 for s in shots if s["team"] != team and s["team"] != "?" and s["is_goal"])

        opp = info["away"] if info["home"] == team else info["home"]
        opp_cn = _team_cn(opp)
        mid = info["match_id"]
        score = info["score"]

        is_home = info["home"] == team
        rows.append((mid, opp_cn, score, xg_for, xg_against, goals_for, goals_against, is_home))
        total_xg += xg_for
        total_xga += xg_against
        total_g += goals_for
        total_ga += goals_against

    print()
    print("=" * 68)
    print(f"  {cn} · xG 汇总 ({len(rows)} 场)")
    print("=" * 68)
    print()
    print(f"  {'比赛':<20} {'比分':>6} {'':>3} {'xG':>7} {'xGA':>7} {'xGD':>7}")
    print(f"  {'────':<20} {'──':>6} {'':>3} {'──':>7} {'──':>7} {'──':>7}")

    for mid, opp_cn, score, xf, xa, gf, ga, is_home in rows:
        label = f"M{mid} vs {opp_cn}"
        if len(label) > 18:
            label = label[:18]
        xgd = xf - xa
        team_score = f"{gf}-{ga}"
        wdl = "W" if gf > ga else ("D" if gf == ga else "L")
        print(f"  {label:<20} {team_score:>6} ({wdl}) {xf:>7.2f} {xa:>7.2f} {xgd:>+7.2f}")

    total_xgd = total_xg - total_xga
    total_score = f"{total_g}-{total_ga}"
    print(f"  {'─' * 60}")
    print(f"  {'合计':<20} {total_score:>6} {total_xg:>7.2f} {total_xga:>7.2f} {total_xgd:>+7.2f}")

    g_diff = total_g - total_xg
    ga_diff = total_ga - total_xga
    print()
    print(f"  进攻效率: 实际 {total_g} 球 / xG {total_xg:.2f} → {g_diff:+.2f}")
    print(f"  防守效率: 实际失 {total_ga} 球 / xGA {total_xga:.2f} → {ga_diff:+.2f}")

    print()
    print("=" * 68)
    print()


def _print_subs_single(info: dict, shots: list[dict], all_subs: dict):
    h_cn = _team_cn(info["home"])
    a_cn = _team_cn(info["away"])
    mid = info["match_id"]

    last_shot_min = max((parse_minute_num(s["minute"]) for s in shots), default=90)
    match_end = max(last_shot_min + 1, 91)

    print()
    print("=" * 68)
    print(f"  {h_cn} {info['score']} {a_cn} (M{mid}) · 换人效果分析")
    print("=" * 68)

    for side, team_en, team_cn in [("home", info["home"], h_cn),
                                    ("away", info["away"], a_cn)]:
        subs = all_subs[side]
        if not subs:
            print(f"\n  {team_cn}: 无换人")
            continue

        print(f"\n  {team_cn} 换人:")
        grouped: dict[int, list] = {}
        for s in subs:
            grouped.setdefault(s["minute"], []).append(s)
        for minute, group in sorted(grouped.items()):
            offs = "/".join(s["off"] for s in group)
            ons = "/".join(s["on"] for s in group)
            print(f"    {group[0]['minute_str']}  {offs} ↓  {ons} ↑")

        phases = split_by_subs(shots, subs, team_en, match_end)

        print()
        print(f"  {'阶段':<12} {'时长':>4} {'xG创造':>7} {'射门':>4} "
              f"{'xGA承受':>7} {'射门':>4} {'进球':>4} {'xG/10min':>9}")
        print(f"  {'─' * 60}")

        starter_xg_rate = phases[0]["xg_rate"] if phases else 0
        for p in phases:
            if p["start"] == 0:
                label = f"0'-{p['end']}'"
            elif p["end"] >= match_end:
                label = f"{p['start']}'-FT"
            else:
                label = f"{p['start']}'-{p['end']}'"

            trend = ""
            if p["start"] > 0 and starter_xg_rate > 0:
                change = (p["xg_rate"] - starter_xg_rate) / starter_xg_rate
                if change > 0.3:
                    trend = " ⬆"
                elif change < -0.3:
                    trend = " ⬇"

            print(f"  {label:<12} {p['duration']:>3}' {p['xg_for']:>7.2f} "
                  f"{p['shots_for']:>4} {p['xg_against']:>7.2f} "
                  f"{p['shots_against']:>4} {p['goals_for']:>4} "
                  f"{p['xg_rate']:>8.2f}{trend}")

        sub_goals = _find_sub_goals(phases, subs)
        if sub_goals:
            print()
            for sg in sub_goals:
                print(f"  ⚡ 替补进球: {sg}")

        post_sub_phases = [p for p in phases if p["start"] > 0]
        if post_sub_phases:
            post_dur = sum(p["duration"] for p in post_sub_phases)
            post_xg = sum(p["xg_for"] for p in post_sub_phases)
            post_rate = post_xg / post_dur * 10 if post_dur > 0 else 0
            if starter_xg_rate > 0:
                change_pct = (post_rate - starter_xg_rate) / starter_xg_rate * 100
                marker = "⬆" if change_pct > 15 else ("⬇" if change_pct < -15 else "→")
                print(f"  首发 xG率 {starter_xg_rate:.2f}/10min → "
                      f"换人后 {post_rate:.2f}/10min ({change_pct:+.0f}%) {marker}")

        print(f"\n  {'─' * 40}")

    print()
    print("=" * 68)
    print()


def _print_subs_team(team: str, index: dict):
    cn = _team_cn(team)
    print(f"\n  正在获取 {cn} 的比赛数据...")

    matches = [e for e in index.values()
               if (e["home"] == team or e["away"] == team) and e["score"]]
    matches.sort(key=lambda e: e["date"])

    if not matches:
        print(f"  {cn} 无已完赛比赛")
        return

    all_first_sub_mins = []
    starter_rates = []
    post_rates = []
    sub_player_goals: dict[str, list] = {}
    match_summaries = []

    for info in matches:
        events = _fetch_timeline(info["fifa_id"])
        if not events:
            continue
        shots = extract_shots(events, info)
        all_subs = get_substitutions(info["fifa_id"], info)

        side = "home" if info["home"] == team else "away"
        subs = all_subs[side]
        if not subs:
            continue

        all_first_sub_mins.append(subs[0]["minute"])

        last_shot_min = max((parse_minute_num(s["minute"]) for s in shots), default=90)
        match_end = max(last_shot_min + 1, 91)
        phases = split_by_subs(shots, subs, team, match_end)

        if phases:
            starter_rates.append(phases[0]["xg_rate"])
            post_phases = [p for p in phases if p["start"] > 0]
            if post_phases:
                post_dur = sum(p["duration"] for p in post_phases)
                post_xg = sum(p["xg_for"] for p in post_phases)
                post_rates.append(post_xg / post_dur * 10 if post_dur > 0 else 0)

        for sg_name in _find_sub_goals(phases, subs):
            player = sg_name.split("(")[0].strip()
            sub_player_goals.setdefault(player, []).append(info["match_id"])

        opp = info["away"] if info["home"] == team else info["home"]
        is_home = info["home"] == team
        raw_parts = info["score"].split("-") if info["score"] else ["0", "0"]
        h_goals, a_goals = int(raw_parts[0]), int(raw_parts[1])
        gf = h_goals if is_home else a_goals
        ga = a_goals if is_home else h_goals
        wdl = "W" if gf > ga else ("D" if gf == ga else "L")
        match_summaries.append({
            "mid": info["match_id"],
            "opp": _team_cn(opp),
            "score": f"{gf}-{ga}",
            "wdl": wdl,
            "first_sub": subs[0]["minute"],
            "num_subs": len(subs),
            "starter_rate": phases[0]["xg_rate"] if phases else 0,
        })

    print()
    print("=" * 68)
    print(f"  {cn} · 换人模式汇总 ({len(match_summaries)} 场)")
    print("=" * 68)

    if all_first_sub_mins:
        avg_first = sum(all_first_sub_mins) / len(all_first_sub_mins)
        earliest = min(all_first_sub_mins)
        latest = max(all_first_sub_mins)
        timing = "偏早" if avg_first < 60 else ("偏晚" if avg_first > 75 else "正常")
        print(f"\n  换人时间: 平均首次 {avg_first:.0f}' ({timing}), "
              f"最早 {earliest}' / 最晚 {latest}'")

    if starter_rates and post_rates:
        avg_starter = sum(starter_rates) / len(starter_rates)
        avg_post = sum(post_rates) / len(post_rates)
        if avg_starter > 0:
            change = (avg_post - avg_starter) / avg_starter * 100
            marker = "⬆" if change > 15 else ("⬇" if change < -15 else "→")
            print(f"\n  换人前后 xG 率:")
            print(f"    首发阶段: {avg_starter:.2f} xG/10min (场均)")
            print(f"    换人后:   {avg_post:.2f} xG/10min (场均)  "
                  f"{change:+.0f}% {marker}")

    if sub_player_goals:
        print(f"\n  替补球员直接产出:")
        for player, mids in sorted(sub_player_goals.items()):
            matches_str = ", ".join(f"M{m}" for m in mids)
            print(f"    {player}: {len(mids)}球 ({matches_str})")

    print(f"\n  逐场明细:")
    print(f"  {'比赛':<18} {'比分':>6} {'':>3} {'首换':>5} {'换人数':>5} {'首发xG率':>9}")
    print(f"  {'─' * 55}")
    for ms in match_summaries:
        label = f"M{ms['mid']} vs {ms['opp']}"[:16]
        print(f"  {label:<18} {ms['score']:>6} ({ms['wdl']}) {ms['first_sub']:>4}' "
              f"{ms['num_subs']:>5} {ms['starter_rate']:>8.2f}")

    print()
    print("=" * 68)
    print()


def cmd_subs(args):
    print("\n  正在获取数据...")
    index = _build_match_index()

    team = _resolve_team_input(args.target)
    if team:
        _print_subs_team(team, index)
        return

    info = _resolve_match(args.target, index)
    if not info:
        sys.exit(1)

    events = _fetch_timeline(info["fifa_id"])
    if not events:
        print("  无法获取比赛事件数据", file=sys.stderr)
        sys.exit(1)

    shots = extract_shots(events, info)
    all_subs = get_substitutions(info["fifa_id"], info)

    _print_subs_single(info, shots, all_subs)


def main():
    parser = argparse.ArgumentParser(description="2026 世界杯 xG 分析")
    sub = parser.add_subparsers(dest="command")

    p_match = sub.add_parser("match", help="单场 xG 分析")
    p_match.add_argument("match", help="match_id / 球队名")

    p_team = sub.add_parser("team", help="球队 xG 汇总")
    p_team.add_argument("team", help="球队名（中英文）")

    p_subs = sub.add_parser("subs", help="换人效果分析")
    p_subs.add_argument("target", help="match_id / 球队名")

    args = parser.parse_args()
    if args.command == "match":
        cmd_match(args)
    elif args.command == "team":
        cmd_team(args)
    elif args.command == "subs":
        cmd_subs(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
