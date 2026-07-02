#!/usr/bin/env python3
"""ESPN 高阶数据工具 — 控球率、传球、铲球、拦截、传中、长传等球队级统计。

用法:
    python3 advanced_stats.py match <match>      # 单场高阶统计（球队级）
    python3 advanced_stats.py team <team>         # 球队累计高阶数据
    python3 advanced_stats.py compare <m1> <m2>   # 两场比赛横向对比
    python3 advanced_stats.py setup               # 建立 ESPN event ID 映射

<match> 支持: match_id (1-72)、英文队名、中文队名
<team> 支持: 英文队名、中文队名

数据来源: ESPN FC 公开 API（无需 API Key）
依赖: 仅标准库
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

from match_data import GROUP_MATCHES, TEAM_CN

# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "02_data")
CACHE_DIR = os.path.join(DATA_DIR, "advanced_stats")
EVENT_MAP_PATH = os.path.join(DATA_DIR, "espn_event_map.json")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko)"
    ),
}

# ESPN team name -> our canonical name
ESPN_NAME_MAP = {
    "Côte d'Ivoire": "Ivory Coast",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "IR Iran": "Iran",
    "USA": "United States",
    "Congo DR": "DR Congo",
}

# Key stats to display (ordered)
STAT_DISPLAY = [
    ("possessionPct", "控球率", "%", True),
    ("totalPasses", "传球总数", "", False),
    ("accuratePasses", "准确传球", "", False),
    ("passPct", "传球成功率", "%", True),
    ("totalShots", "射门", "", False),
    ("shotsOnTarget", "射正", "", False),
    ("shotPct", "射正率", "%", True),
    ("wonCorners", "角球", "", False),
    ("foulsCommitted", "犯规", "", False),
    ("offsides", "越位", "", False),
    ("effectiveTackles", "成功铲球", "", False),
    ("totalTackles", "总铲球", "", False),
    ("tacklePct", "铲球成功率", "%", True),
    ("interceptions", "拦截", "", False),
    ("effectiveClearance", "解围", "", False),
    ("accurateCrosses", "准确传中", "", False),
    ("totalCrosses", "总传中", "", False),
    ("crossPct", "传中成功率", "%", True),
    ("accurateLongBalls", "准确长传", "", False),
    ("totalLongBalls", "总长传", "", False),
    ("longballPct", "长传成功率", "%", True),
    ("blockedShots", "封堵射门", "", False),
    ("saves", "扑救", "", False),
]

CN_TO_EN = {v: k for k, v in TEAM_CN.items()}


# ---------------------------------------------------------------------------
# Team name resolution
# ---------------------------------------------------------------------------

def _resolve_espn_name(espn_name: str) -> str:
    return ESPN_NAME_MAP.get(espn_name, espn_name)


def _team_cn(en_name: str) -> str:
    return TEAM_CN.get(en_name, en_name)


def _resolve_team_input(text: str) -> tuple[str | None, list]:
    text = text.strip()
    if text.isdigit():
        mid = int(text)
        matches = [m for m in GROUP_MATCHES if m.match_id == mid]
        return (None, matches) if matches else (None, [])

    en = text
    if text in CN_TO_EN:
        en = CN_TO_EN[text]
    elif text in TEAM_CN:
        en = text
    else:
        lower = text.lower()
        for name in TEAM_CN:
            if name.lower() == lower:
                en = name
                break
        else:
            for cn, eng in CN_TO_EN.items():
                if cn in text or text in cn:
                    en = eng
                    break

    matches = [m for m in GROUP_MATCHES if m.team1 == en or m.team2 == en]
    return (en, matches)


# ---------------------------------------------------------------------------
# HTTP fetching
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"  ❌ 请求失败: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# ESPN Event ID mapping
# ---------------------------------------------------------------------------

def _load_event_map() -> dict[int, str]:
    if os.path.exists(EVENT_MAP_PATH):
        with open(EVENT_MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {int(k): v for k, v in data.get("map", {}).items()}
    return {}


def _save_event_map(mapping: dict[int, str]):
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(EVENT_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump({"buildTime": now, "map": {str(k): v for k, v in mapping.items()}},
                  f, ensure_ascii=False, indent=2)


def _build_event_map() -> dict[int, str]:
    print("  建立 ESPN Event ID 映射...")
    mapping: dict[int, str] = {}

    dates_needed = set()
    for m in GROUP_MATCHES:
        d = datetime.strptime(m.date_str, "%Y-%m-%d")
        dates_needed.add(d.strftime("%Y%m%d"))
        next_d = (d + timedelta(days=1)).strftime("%Y%m%d")
        dates_needed.add(next_d)
        prev_d = (d - timedelta(days=1)).strftime("%Y%m%d")
        dates_needed.add(prev_d)

    espn_events: dict[str, dict] = {}

    for date_str in sorted(dates_needed):
        url = f"{ESPN_BASE}/scoreboard?dates={date_str}"
        data = _fetch_json(url)
        if not data:
            continue
        for ev in data.get("events", []):
            eid = ev.get("id", "")
            comp = ev.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            if len(teams) < 2:
                continue
            h = _resolve_espn_name(teams[0].get("team", {}).get("displayName", ""))
            a = _resolve_espn_name(teams[1].get("team", {}).get("displayName", ""))
            if teams[0].get("homeAway") == "away":
                h, a = a, h
            espn_events[eid] = {"home": h, "away": a}

    print(f"  ESPN 共找到 {len(espn_events)} 场比赛")

    for m in GROUP_MATCHES:
        for eid, info in espn_events.items():
            if info["home"] == m.team1 and info["away"] == m.team2:
                mapping[m.match_id] = eid
                break

    print(f"  成功映射 {len(mapping)}/{len(GROUP_MATCHES)} 场")
    _save_event_map(mapping)
    return mapping


def _get_event_id(match_id: int) -> str | None:
    mapping = _load_event_map()
    if match_id in mapping:
        return mapping[match_id]
    mapping = _build_event_map()
    return mapping.get(match_id)


# ---------------------------------------------------------------------------
# Data fetching with cache
# ---------------------------------------------------------------------------

def _cache_path(match_id: int) -> str:
    return os.path.join(CACHE_DIR, f"match_{match_id}_stats.json")


def fetch_match_stats(match_id: int, refresh: bool = False) -> dict | None:
    cache = _cache_path(match_id)
    if not refresh and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)

    event_id = _get_event_id(match_id)
    if not event_id:
        print(f"  ❌ 无法找到 M{match_id} 的 ESPN Event ID", file=sys.stderr)
        return None

    url = f"{ESPN_BASE}/summary?event={event_id}"
    data = _fetch_json(url)
    if not data:
        return None

    boxscore = data.get("boxscore", {})
    teams_data = boxscore.get("teams", [])

    result = {"match_id": match_id, "event_id": event_id, "teams": {}}

    for t in teams_data:
        team_name = _resolve_espn_name(t.get("team", {}).get("displayName", "?"))
        stats_list = t.get("statistics", [])
        stats_dict = {}
        for s in stats_list:
            name = s.get("name", "")
            val = s.get("displayValue", "")
            try:
                stats_dict[name] = float(val)
            except (ValueError, TypeError):
                stats_dict[name] = val
        result["teams"][team_name] = stats_dict

    # Also extract player-level basic stats from rosters
    rosters = data.get("rosters", [])
    result["players"] = {}
    for roster in rosters:
        team_name = _resolve_espn_name(roster.get("team", {}).get("displayName", "?"))
        players = []
        for p in roster.get("roster", []):
            athlete = p.get("athlete", {})
            pdata = {
                "name": athlete.get("displayName", "?"),
                "position": p.get("position", {}).get("abbreviation", "?"),
                "starter": p.get("starter", False),
                "jersey": p.get("jersey", ""),
                "stats": {},
            }
            for s in p.get("stats", []):
                pdata["stats"][s.get("name", "")] = s.get("displayValue", "")
            if pdata["starter"] or any(v != "0" and v != "" for v in pdata["stats"].values()):
                players.append(pdata)
        result["players"][team_name] = players

    game_info = data.get("gameInfo", {})
    officials = game_info.get("officials", [])
    if officials:
        result["officials"] = [
            {"name": o.get("displayName", "?"), "role": o.get("position", {}).get("displayName", "?")}
            for o in officials
        ]

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ---------------------------------------------------------------------------
# Display functions
# ---------------------------------------------------------------------------

def _format_val(val, suffix: str, is_pct: bool) -> str:
    if isinstance(val, float):
        if is_pct:
            if val <= 1.0:
                return f"{val*100:.1f}{suffix}"
            return f"{val:.1f}{suffix}"
        return f"{val:.0f}"
    return str(val)


def print_match_stats(match_id: int, refresh: bool = False):
    m = GROUP_MATCHES[match_id - 1]
    data = fetch_match_stats(match_id, refresh)
    if not data:
        print(f"  ❌ 无法获取 M{match_id} 的数据")
        return

    teams = data.get("teams", {})
    if len(teams) < 2:
        print(f"  ❌ 数据不完整")
        return

    home_name = m.team1
    away_name = m.team2
    home_stats = teams.get(home_name, {})
    away_stats = teams.get(away_name, {})

    home_cn = _team_cn(home_name)
    away_cn = _team_cn(away_name)
    score = m.score or "vs"

    print()
    print("═" * 62)
    print(f"  {home_cn} {score} {away_cn} (M{match_id} · Group {m.group})")
    print(f"  高阶统计 (数据来源: ESPN)")
    print("═" * 62)
    print()
    print(f"  {'指标':<14} {home_cn:>12}   {away_cn:>12}")
    print(f"  {'─' * 14} {'─' * 12}   {'─' * 12}")

    for key, label, suffix, is_pct in STAT_DISPLAY:
        h_val = home_stats.get(key)
        a_val = away_stats.get(key)
        if h_val is None and a_val is None:
            continue
        h_str = _format_val(h_val, suffix, is_pct) if h_val is not None else "—"
        a_str = _format_val(a_val, suffix, is_pct) if a_val is not None else "—"
        print(f"  {label:<14} {h_str:>12}   {a_str:>12}")

    print()

    # Highlight key tactical indicators
    h_poss = home_stats.get("possessionPct", 0)
    a_poss = away_stats.get("possessionPct", 0)
    h_pass_pct = home_stats.get("passPct", 0)
    a_pass_pct = away_stats.get("passPct", 0)
    h_tackles = home_stats.get("effectiveTackles", 0)
    a_tackles = away_stats.get("effectiveTackles", 0)

    print("  💡 战术指标:")
    if abs(h_poss - a_poss) > 15:
        dominant = home_cn if h_poss > a_poss else away_cn
        print(f"     控球差距显著 → {dominant}主导控球")
    if isinstance(h_pass_pct, float) and isinstance(a_pass_pct, float):
        if h_pass_pct > 0 and a_pass_pct > 0:
            hp = h_pass_pct * 100 if h_pass_pct <= 1 else h_pass_pct
            ap = a_pass_pct * 100 if a_pass_pct <= 1 else a_pass_pct
            if abs(hp - ap) > 8:
                better = home_cn if hp > ap else away_cn
                print(f"     传球质量差距 → {better}传球更精准")
    h_long = home_stats.get("totalLongBalls", 0)
    a_long = away_stats.get("totalLongBalls", 0)
    h_total = home_stats.get("totalPasses", 1)
    a_total = away_stats.get("totalPasses", 1)
    if h_total > 0 and a_total > 0:
        h_long_ratio = h_long / h_total if isinstance(h_long, (int, float)) and isinstance(h_total, (int, float)) else 0
        a_long_ratio = a_long / a_total if isinstance(a_long, (int, float)) and isinstance(a_total, (int, float)) else 0
        if h_long_ratio > 0.12 or a_long_ratio > 0.12:
            long_team = home_cn if h_long_ratio > a_long_ratio else away_cn
            print(f"     {long_team}长传比例偏高 → 可能推进链路受阻/战术选择")

    print()
    print("═" * 62)


def print_team_summary(team_name: str):
    matches = [m for m in GROUP_MATCHES if (m.team1 == team_name or m.team2 == team_name) and m.score]
    if not matches:
        print(f"  ❌ {team_name} 无已完赛比赛")
        return

    cn = _team_cn(team_name)
    print()
    print("═" * 62)
    print(f"  {cn} ({team_name}) · 累计高阶统计")
    print("═" * 62)

    all_stats: list[tuple[str, dict]] = []
    for m in matches:
        data = fetch_match_stats(m.match_id)
        if not data:
            continue
        teams = data.get("teams", {})
        stats = teams.get(team_name, {})
        if stats:
            opp = m.team2 if m.team1 == team_name else m.team1
            all_stats.append((_team_cn(opp), stats))

    if not all_stats:
        print(f"  无可用数据")
        return

    # Print per-match comparison
    print()
    header = f"  {'指标':<14}"
    for opp_cn, _ in all_stats:
        header += f" {'vs'+opp_cn:>12}"
    header += f" {'平均':>10}"
    print(header)
    print(f"  {'─' * 14}" + f" {'─' * 12}" * len(all_stats) + f" {'─' * 10}")

    for key, label, suffix, is_pct in STAT_DISPLAY:
        vals = []
        for _, stats in all_stats:
            v = stats.get(key)
            vals.append(v)

        if all(v is None for v in vals):
            continue

        line = f"  {label:<14}"
        numeric_vals = []
        for v in vals:
            if v is not None:
                line += f" {_format_val(v, suffix, is_pct):>12}"
                if isinstance(v, (int, float)):
                    numeric_vals.append(v)
            else:
                line += f" {'—':>12}"

        if numeric_vals:
            avg = sum(numeric_vals) / len(numeric_vals)
            line += f" {_format_val(avg, suffix, is_pct):>10}"
        else:
            line += f" {'—':>10}"

        print(line)

    print()
    print("═" * 62)


def print_compare(mid1: int, mid2: int):
    m1 = GROUP_MATCHES[mid1 - 1]
    m2 = GROUP_MATCHES[mid2 - 1]
    d1 = fetch_match_stats(mid1)
    d2 = fetch_match_stats(mid2)
    if not d1 or not d2:
        print("  ❌ 无法获取比赛数据")
        return

    print()
    print("═" * 72)
    print(f"  M{mid1} {_team_cn(m1.team1)} vs {_team_cn(m1.team2)} ({m1.score})")
    print(f"  M{mid2} {_team_cn(m2.team1)} vs {_team_cn(m2.team2)} ({m2.score})")
    print(f"  横向对比")
    print("═" * 72)
    print()

    header = f"  {'指标':<12}"
    for mid, m in [(mid1, m1), (mid2, m2)]:
        header += f" {_team_cn(m.team1):>8} {_team_cn(m.team2):>8}"
    print(header)
    print(f"  {'─' * 12}" + f" {'─' * 8} {'─' * 8}" * 2)

    for key, label, suffix, is_pct in STAT_DISPLAY:
        vals = []
        for d, m in [(d1, m1), (d2, m2)]:
            teams = d.get("teams", {})
            h_v = teams.get(m.team1, {}).get(key)
            a_v = teams.get(m.team2, {}).get(key)
            vals.extend([h_v, a_v])

        if all(v is None for v in vals):
            continue

        line = f"  {label:<12}"
        for v in vals:
            if v is not None:
                line += f" {_format_val(v, suffix, is_pct):>8}"
            else:
                line += f" {'—':>8}"
        print(line)

    print()
    print("═" * 72)


def print_lineup(match_id: int):
    m = GROUP_MATCHES[match_id - 1]
    data = fetch_match_stats(match_id)
    if not data or "players" not in data:
        print(f"  无法获取 M{match_id} 的球员数据")
        return

    home_cn = _team_cn(m.team1)
    away_cn = _team_cn(m.team2)
    score = m.score or "vs"

    print()
    print("=" * 72)
    print(f"  {home_cn} {score} {away_cn} (M{match_id} · Group {m.group})")
    print(f"  首发阵容 + 球员数据 (ESPN)")
    print("=" * 72)

    for team_name in [m.team1, m.team2]:
        players = data.get("players", {}).get(team_name, [])
        if not players:
            continue

        cn = _team_cn(team_name)
        starters = [p for p in players if p.get("starter")]
        subs = [p for p in players if not p.get("starter")]

        print(f"\n  {cn} ({team_name}):")
        print(f"  {'位置':<4} {'#':>3} {'球员':<22} {'进球':>4} {'助攻':>4} {'射门':>4} {'犯规':>4} {'黄牌':>4} {'标记':>4}")
        print(f"  {'──':<4} {'─':>3} {'────':<22} {'──':>4} {'──':>4} {'──':>4} {'──':>4} {'──':>4} {'──':>4}")

        for p in starters:
            _print_player_row(p)

        if subs:
            active_subs = [s for s in subs if any(v not in ("0", "") for v in s.get("stats", {}).values())]
            if active_subs:
                print(f"  {'—— 替补 ——':^60}")
                for p in active_subs:
                    _print_player_row(p)

    officials = data.get("officials", [])
    if officials:
        ref = officials[0] if officials else {}
        print(f"\n  裁判: {ref.get('name', '?')}")

    print()
    print("=" * 72)


def _print_player_row(p: dict):
    stats = p.get("stats", {})
    goals = stats.get("goals", "0")
    assists = stats.get("assists", "0")
    shots = stats.get("totalShots", stats.get("shotsTotal", "0"))
    fouls = stats.get("foulsCommitted", "0")
    yellows = stats.get("yellowCards", "0")

    mark = ""
    try:
        if int(goals) > 0:
            mark = "G"
        if int(shots) >= 3:
            mark += "S"
        if int(fouls) >= 3 or int(yellows) >= 1:
            mark += "!"
    except (ValueError, TypeError):
        pass

    pos = p.get("position", "?")
    jersey = p.get("jersey", "")
    name = p.get("name", "?")
    if len(name) > 20:
        name = name[:20]

    print(f"  {pos:<4} {jersey:>3} {name:<22} {goals:>4} {assists:>4} {shots:>4} {fouls:>4} {yellows:>4} {mark:>4}")


def print_player_search(query: str):
    query_lower = query.lower()
    found = []

    for match_file in sorted(os.listdir(CACHE_DIR)):
        if not match_file.startswith("match_") or not match_file.endswith("_stats.json"):
            continue
        mid = int(match_file.split("_")[1])
        filepath = os.path.join(CACHE_DIR, match_file)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        for team_name, players in data.get("players", {}).items():
            for p in players:
                pname = p.get("name", "")
                if query_lower in pname.lower():
                    m = GROUP_MATCHES[mid - 1]
                    opp = m.team2 if m.team1 == team_name else m.team1
                    found.append({
                        "mid": mid, "team": team_name, "opp": opp,
                        "name": pname, "pos": p.get("position", "?"),
                        "starter": p.get("starter", False),
                        "stats": p.get("stats", {}), "score": m.score,
                    })

    if not found:
        print(f"\n  未找到球员: {query}")
        print(f"  提示: 使用球员英文名（如 VINICIUS JUNIOR, SON Heungmin）\n")
        return

    player_name = found[0]["name"]
    team = found[0]["team"]
    team_cn = _team_cn(team)

    print()
    print("=" * 72)
    print(f"  {player_name} ({team_cn}) · 跨场统计")
    print("=" * 72)
    print()
    print(f"  {'场次':<8} {'对手':<12} {'首发':>4} {'进球':>4} {'助攻':>4} {'射门':>4} {'犯规':>4} {'黄牌':>4}")
    print(f"  {'──':<8} {'────':<12} {'──':>4} {'──':>4} {'──':>4} {'──':>4} {'──':>4} {'──':>4}")

    for f in found:
        s = f["stats"]
        starter = "Y" if f["starter"] else "N"
        opp_cn = _team_cn(f["opp"])
        score_str = f["score"] or ""
        goals = s.get("goals", "0")
        assists = s.get("assists", "0")
        shots = s.get("totalShots", s.get("shotsTotal", "0"))
        fouls = s.get("foulsCommitted", "0")
        yellows = s.get("yellowCards", "0")

        label = f"M{f['mid']}"
        print(f"  {label:<8} {opp_cn:<12} {starter:>4} {goals:>4} {assists:>4} {shots:>4} {fouls:>4} {yellows:>4}")

    print()
    print("=" * 72)


def print_referee_summary():
    if not os.path.exists(CACHE_DIR):
        print("\n  无缓存数据，请先运行 match 命令获取比赛数据\n")
        return

    referee_stats: dict[str, list[dict]] = {}

    for match_file in sorted(os.listdir(CACHE_DIR)):
        if not match_file.startswith("match_") or not match_file.endswith("_stats.json"):
            continue
        mid = int(match_file.split("_")[1])
        filepath = os.path.join(CACHE_DIR, match_file)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        officials = data.get("officials", [])
        if not officials:
            continue
        ref_name = officials[0].get("name", "?")
        teams = data.get("teams", {})

        total_yellows = 0
        total_fouls = 0
        for t_stats in teams.values():
            total_yellows += int(t_stats.get("yellowCards", 0))
            total_fouls += int(t_stats.get("foulsCommitted", 0))

        m = GROUP_MATCHES[mid - 1]
        match_info = {
            "mid": mid, "yellows": total_yellows, "fouls": total_fouls,
            "home": m.team1, "away": m.team2, "score": m.score,
        }
        referee_stats.setdefault(ref_name, []).append(match_info)

    if not referee_stats:
        print("\n  无裁判数据（缓存中无 officials 字段）")
        print("  提示: 用 --refresh 重新获取比赛数据以包含裁判信息\n")
        return

    print()
    print("=" * 72)
    print(f"  2026 世界杯裁判执法统计")
    print("=" * 72)
    print()
    print(f"  {'裁判':<28} {'场次':>4} {'场均黄牌':>8} {'场均犯规':>8}")
    print(f"  {'────':<28} {'──':>4} {'────':>8} {'────':>8}")

    for ref, matches in sorted(referee_stats.items(), key=lambda x: -len(x[1])):
        n = len(matches)
        avg_y = sum(m["yellows"] for m in matches) / n
        avg_f = sum(m["fouls"] for m in matches) / n
        print(f"  {ref:<28} {n:>4} {avg_y:>8.1f} {avg_f:>8.1f}")

    print()
    for ref, matches in sorted(referee_stats.items(), key=lambda x: -len(x[1])):
        if len(matches) >= 2:
            print(f"  {ref} 执法场次:")
            for m in matches:
                h_cn = _team_cn(m["home"])
                a_cn = _team_cn(m["away"])
                print(f"    M{m['mid']} {h_cn} {m['score']} {a_cn} — 黄牌{m['yellows']} 犯规{m['fouls']}")

    print()
    print("=" * 72)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_setup(args):
    print()
    print("═" * 60)
    print("  ESPN 高阶数据映射建立")
    print("═" * 60)
    print()
    mapping = _build_event_map()
    if mapping:
        print(f"\n  ✅ 映射已保存至 {EVENT_MAP_PATH}")
        print(f"  现在可以使用: python3 advanced_stats.py match <N>")
    else:
        print(f"\n  ❌ 映射建立失败")


def cmd_match(args):
    text = " ".join(args.match)
    team, matches = _resolve_team_input(text)
    if not matches:
        print(f"  ❌ 未找到比赛: {text}")
        return

    if team:
        completed = [m for m in matches if m.score]
        if not completed:
            print(f"  ❌ {_team_cn(team)} 无已完赛比赛")
            return
        for m in completed:
            print_match_stats(m.match_id, args.refresh)
    else:
        m = matches[0]
        if not m.score:
            print(f"  ❌ M{m.match_id} 尚未完赛")
            return
        print_match_stats(m.match_id, args.refresh)


def cmd_team(args):
    text = " ".join(args.team)
    team, matches = _resolve_team_input(text)
    if not team:
        if matches:
            m = matches[0]
            team = m.team1
        else:
            print(f"  ❌ 未找到球队: {text}")
            return
    print_team_summary(team)


def cmd_compare(args):
    print_compare(int(args.match1), int(args.match2))


def cmd_lineup(args):
    text = " ".join(args.match)
    team, matches = _resolve_team_input(text)
    if not matches:
        print(f"  未找到比赛: {text}")
        return
    if team:
        completed = [m for m in matches if m.score]
        if not completed:
            print(f"  {_team_cn(team)} 无已完赛比赛")
            return
        for m in completed:
            print_lineup(m.match_id)
    else:
        m = matches[0]
        if not m.score:
            print(f"  M{m.match_id} 尚未完赛")
            return
        print_lineup(m.match_id)


def cmd_player(args):
    query = " ".join(args.name)
    print_player_search(query)


def cmd_referee(args):
    print_referee_summary()


def main():
    parser = argparse.ArgumentParser(description="ESPN 世界杯高阶数据工具")
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="建立 ESPN Event ID 映射")

    p_match = sub.add_parser("match", help="单场高阶统计")
    p_match.add_argument("match", nargs="+", help="match_id 或球队名")
    p_match.add_argument("--refresh", action="store_true", help="强制刷新缓存")

    p_team = sub.add_parser("team", help="球队累计高阶数据")
    p_team.add_argument("team", nargs="+", help="球队名")

    p_cmp = sub.add_parser("compare", help="两场比赛横向对比")
    p_cmp.add_argument("match1", help="第一场 match_id")
    p_cmp.add_argument("match2", help="第二场 match_id")

    p_lineup = sub.add_parser("lineup", help="首发阵容 + 球员数据")
    p_lineup.add_argument("match", nargs="+", help="match_id 或球队名")

    p_player = sub.add_parser("player", help="球员跨场统计")
    p_player.add_argument("name", nargs="+", help="球员名（英文）")

    sub.add_parser("referee", help="裁判执法统计")

    args = parser.parse_args()
    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "match":
        cmd_match(args)
    elif args.command == "team":
        cmd_team(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "lineup":
        cmd_lineup(args)
    elif args.command == "player":
        cmd_player(args)
    elif args.command == "referee":
        cmd_referee(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
