#!/usr/bin/env python3
"""FIFA 官方 API 比赛数据工具 — 射门、角球、犯规、阵容等客观赛后统计。

用法:
    python3 fifa_stats.py list                 # 所有小组赛比赛列表
    python3 fifa_stats.py stats <match>        # 赛后统计摘要
    python3 fifa_stats.py lineup <match>       # 首发阵容 + 换人
    python3 fifa_stats.py friendlies <team>    # 球队 2026 热身赛列表
    python3 fifa_stats.py friendly <team> <N>  # 第 N 场热身赛详细数据

<match> 支持: 内部 match_id (1-72)、英文队名 (France)、中文队名 (法国)
<team> 支持: 英文队名、中文队名

依赖: 仅标准库
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

from match_data import GROUP_MATCHES, ALL_MATCHES, TEAM_CN

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMP = "17"
SEASON = "285023"
STAGE = "289273"

FRIENDLY_COMP = "cesdwwnxbc5fmajgroc0hqzy2"
FRIENDLY_SEASON = "dezv8l0fzgcxtejl0dwmy1gyc"
FRIENDLY_STAGE = "2m1wojm5bt709wu4kugtytxqs"

BASE = "https://api.fifa.com/api/v3"
CALENDAR_URL = f"{BASE}/calendar/matches?idCompetition={COMP}&idSeason={SEASON}&language=en&count=100"
TIMELINE_URL = f"{BASE}/timelines/{COMP}/{SEASON}/{STAGE}/{{mid}}?language=en"
LIVE_URL = f"{BASE}/live/football/{COMP}/{SEASON}/{STAGE}/{{mid}}?language=en"

FRIENDLY_CALENDAR_URL = (
    f"{BASE}/calendar/matches?idCompetition={FRIENDLY_COMP}"
    f"&from=2026-01-01T00:00:00Z&to=2026-06-11T00:00:00Z&language=en&count=500"
)
FRIENDLY_TIMELINE_URL = f"{BASE}/timelines/{FRIENDLY_COMP}/{FRIENDLY_SEASON}/{FRIENDLY_STAGE}/{{mid}}?language=en"
FRIENDLY_LIVE_URL = f"{BASE}/live/football/{FRIENDLY_COMP}/{FRIENDLY_SEASON}/{FRIENDLY_STAGE}/{{mid}}?language=en"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data", "fifa_stats")
BJT = timezone(timedelta(hours=8))

# Our canonical names → FIFA API names (only where they differ)
FIFA_NAME_MAP = {
    "South Korea": "Korea Republic",
    "Czech Republic": "Czechia",
    "Cape Verde": "Cabo Verde",
    "Iran": "IR Iran",
    "Turkey": "Türkiye",
    "Ivory Coast": "Côte d'Ivoire",
    "DR Congo": "Congo DR",
    "United States": "USA",
}
FIFA_NAME_REV = {v: k for k, v in FIFA_NAME_MAP.items()}

CN_TO_EN = {v: k for k, v in TEAM_CN.items()}

EVENT_TYPES = {
    0: "Goal",
    1: "Assist",
    2: "Yellow",
    3: "Red",
    5: "Substitution",
    12: "Shot",
    14: "FreeKick",
    15: "Offside",
    16: "Corner",
    18: "Foul",
    25: "Clearance",
    27: "Aerial",
    34: "OwnGoal",
    57: "GoalPrevention",
    71: "VAR",
}

POS_NAMES = {0: "GK", 1: "DF", 2: "MF", 3: "FW"}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  API 请求失败: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------

def _our_name(fifa_name: str) -> str:
    return FIFA_NAME_REV.get(fifa_name, fifa_name)


def _fifa_name(our_name: str) -> str:
    return FIFA_NAME_MAP.get(our_name, our_name)


def _team_cn(en_name: str) -> str:
    return TEAM_CN.get(en_name, en_name)


def _resolve_team_input(text: str) -> str | None:
    text = text.strip()
    if text in TEAM_CN:
        return text
    if text in CN_TO_EN:
        return CN_TO_EN[text]
    lower = text.lower()
    for en in TEAM_CN:
        if en.lower() == lower:
            return en
    return None


# ---------------------------------------------------------------------------
# Match index: map internal match_id → FIFA match_id
# ---------------------------------------------------------------------------

def _localized(arr: list) -> str:
    if arr and isinstance(arr, list):
        return arr[0].get("Description", "")
    return ""


def _build_match_index() -> dict:
    """Returns {internal_match_id: {fifa_id, home, away, score, date, ...}}"""
    data = _fetch_json(CALENDAR_URL)
    if not data:
        print("  无法获取 FIFA 比赛列表", file=sys.stderr)
        sys.exit(1)

    fifa_matches = {}
    for m in data.get("Results", []):
        home_obj = m.get("Home")
        away_obj = m.get("Away")
        if not home_obj or not away_obj:
            continue
        h_fifa = _localized(home_obj.get("TeamName", []))
        a_fifa = _localized(away_obj.get("TeamName", []))
        h_our = _our_name(h_fifa)
        a_our = _our_name(a_fifa)
        h_score = home_obj.get("Score")
        a_score = away_obj.get("Score")
        score_str = f"{h_score}-{a_score}" if h_score is not None and a_score is not None else None
        fifa_matches[(h_our, a_our)] = {
            "fifa_id": m.get("IdMatch", ""),
            "home": h_our,
            "away": a_our,
            "home_fifa": h_fifa,
            "away_fifa": a_fifa,
            "score": score_str,
            "date": m.get("Date", "")[:10],
            "attendance": m.get("Attendance", ""),
            "venue": _localized(m.get("Stadium", {}).get("Name", [])),
            "group": _localized(m.get("GroupName", [])),
            "h_tactics": home_obj.get("Tactics", ""),
            "a_tactics": away_obj.get("Tactics", ""),
        }

    index = {}
    for gm in ALL_MATCHES:
        key = (gm.team1, gm.team2)
        if key in fifa_matches:
            entry = fifa_matches[key].copy()
            entry["match_id"] = gm.match_id
            index[gm.match_id] = entry

    return index


def _resolve_match(arg: str, index: dict) -> dict | None:
    if arg.isdigit():
        mid = int(arg)
        if mid in index:
            return index[mid]
        print(f"  未找到 match_id={mid}", file=sys.stderr)
        return None

    team = _resolve_team_input(arg)
    if not team:
        print(f"  无法识别队名: {arg}", file=sys.stderr)
        return None

    candidates = []
    for entry in index.values():
        if entry["home"] == team or entry["away"] == team:
            if entry["score"] is not None:
                candidates.append(entry)

    if not candidates:
        no_score = [e for e in index.values() if e["home"] == team or e["away"] == team]
        if no_score:
            print(f"  {_team_cn(team)} 的比赛尚未完赛", file=sys.stderr)
        else:
            print(f"  未找到 {_team_cn(team)} 的比赛", file=sys.stderr)
        return None

    candidates.sort(key=lambda e: e["date"], reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# Timeline parsing
# ---------------------------------------------------------------------------

def _fetch_timeline(fifa_id: str) -> list[dict]:
    data = _fetch_json(TIMELINE_URL.format(mid=fifa_id))
    if not data:
        return []
    return data.get("Event", [])


def _event_desc(event: dict) -> str:
    descs = event.get("EventDescription", [])
    return _localized(descs)


def _parse_stats(events: list[dict], match_info: dict) -> dict:
    """Parse timeline events into structured stats."""
    home_fifa = match_info["home_fifa"]
    away_fifa = match_info["away_fifa"]

    # Build team ID mapping from events
    team_ids = {}
    for e in events:
        desc = _event_desc(e)
        tid = e.get("IdTeam", "")
        if not tid:
            continue
        if home_fifa in desc or match_info["home"] in desc:
            team_ids[tid] = "home"
        elif away_fifa in desc or match_info["away"] in desc:
            team_ids[tid] = "away"

    def side(event):
        return team_ids.get(event.get("IdTeam", ""), None)

    shots = {"home": [0, 0], "away": [0, 0]}
    corners = {"home": 0, "away": 0}
    fouls = {"home": 0, "away": 0}
    offsides = {"home": 0, "away": 0}
    goals = []
    bookings = []
    subs = []

    for e in events:
        etype = e.get("Type", -1)
        s = side(e)
        period = e.get("Period", 0)  # 3=1st half, 5=2nd half
        minute = e.get("MatchMinute", "")

        if etype == 12 and s:  # Shot
            half_idx = 0 if period == 3 else 1
            shots[s][half_idx] += 1

        elif etype == 16 and s:  # Corner
            corners[s] += 1

        elif etype == 18 and s:  # Foul
            fouls[s] += 1

        elif etype == 15 and s:  # Offside
            offsides[s] += 1

        elif etype in (0, 34):  # Goal / Own goal
            goals.append({
                "minute": minute,
                "side": s or "?",
                "desc": _event_desc(e),
            })

        elif etype in (2, 3):  # Yellow / Red
            bookings.append({
                "minute": minute,
                "side": s or "?",
                "card": "yellow" if etype == 2 else "red",
                "desc": _event_desc(e),
            })

        elif etype == 5:  # Substitution
            subs.append({
                "minute": minute,
                "side": s or "?",
                "desc": _event_desc(e),
            })

    return {
        "shots": shots,
        "corners": corners,
        "fouls": fouls,
        "offsides": offsides,
        "goals": goals,
        "bookings": bookings,
        "substitutions": subs,
    }


# ---------------------------------------------------------------------------
# Live data (lineups)
# ---------------------------------------------------------------------------

def _fetch_live(fifa_id: str) -> dict | None:
    return _fetch_json(LIVE_URL.format(mid=fifa_id))


def _parse_lineup(team_data: dict) -> dict:
    """Parse a team's lineup from live data."""
    players = team_data.get("Players", [])
    starters = []
    bench = []
    for p in players:
        info = {
            "name": _localized(p.get("ShortName", p.get("PlayerName", []))),
            "number": p.get("ShirtNumber", 0),
            "position": POS_NAMES.get(p.get("Position", -1), "??"),
            "captain": p.get("Captain", False),
        }
        if p.get("Status") == 1:
            starters.append(info)
        else:
            bench.append(info)

    pos_order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    starters.sort(key=lambda x: (pos_order.get(x["position"], 9), x["number"]))
    bench.sort(key=lambda x: x["number"])

    subs = []
    for s in team_data.get("Substitutions", []):
        subs.append({
            "minute": s.get("Minute", ""),
            "off": _localized(s.get("PlayerOffName", [])),
            "on": _localized(s.get("PlayerOnName", [])),
        })
    subs.sort(key=lambda x: x["minute"])

    return {
        "tactics": team_data.get("Tactics", ""),
        "starters": starters,
        "bench": bench,
        "substitutions": subs,
    }


# ---------------------------------------------------------------------------
# Output: stats
# ---------------------------------------------------------------------------

def print_stats(match_info: dict, stats: dict):
    home = match_info["home"]
    away = match_info["away"]
    h_cn = _team_cn(home)
    a_cn = _team_cn(away)
    mid = match_info["match_id"]
    score = match_info["score"] or "? - ?"

    print()
    print("=" * 66)
    print(f"  {h_cn} {score} {a_cn} (M{mid} · {match_info['group']} · {match_info['date']})")
    if match_info.get("venue"):
        parts = [match_info["venue"]]
        if match_info.get("attendance"):
            parts.append(f"观众: {match_info['attendance']}")
        print(f"  {' · '.join(parts)}")
    print("=" * 66)

    sh = stats["shots"]
    h_total = sum(sh["home"])
    a_total = sum(sh["away"])

    lbl_w = 20
    col_w = 12

    print()
    print(f"  {'':>{lbl_w}} {h_cn:>{col_w}} {a_cn:>{col_w}}")
    print(f"  {'─' * (lbl_w + col_w * 2 + 2)}")
    print(f"  {'射门':<{lbl_w}} {h_total:>{col_w}} {a_total:>{col_w}}")
    print(f"  {'  上半场':<{lbl_w}} {sh['home'][0]:>{col_w}} {sh['away'][0]:>{col_w}}")
    print(f"  {'  下半场':<{lbl_w}} {sh['home'][1]:>{col_w}} {sh['away'][1]:>{col_w}}")
    print(f"  {'角球':<{lbl_w}} {stats['corners']['home']:>{col_w}} {stats['corners']['away']:>{col_w}}")
    print(f"  {'犯规':<{lbl_w}} {stats['fouls']['home']:>{col_w}} {stats['fouls']['away']:>{col_w}}")
    print(f"  {'越位':<{lbl_w}} {stats['offsides']['home']:>{col_w}} {stats['offsides']['away']:>{col_w}}")

    if match_info.get("h_tactics") or match_info.get("a_tactics"):
        ht = match_info.get("h_tactics", "")
        at = match_info.get("a_tactics", "")
        print(f"  {'阵型':<{lbl_w}} {ht:>{col_w}} {at:>{col_w}}")

    if stats["goals"]:
        print()
        print(f"  进球:")
        for g in stats["goals"]:
            print(f"    {g['minute']:>8}  {g['desc']}")

    if stats["substitutions"]:
        print()
        print(f"  换人:")
        for s in stats["substitutions"]:
            print(f"    {s['minute']:>8}  {s['desc']}")

    if stats["bookings"]:
        print()
        print(f"  纪律:")
        for b in stats["bookings"]:
            card = "🟨" if b["card"] == "yellow" else "🟥"
            print(f"    {b['minute']:>8}  {card} {b['desc']}")

    print()
    print("=" * 66)


# ---------------------------------------------------------------------------
# Output: lineup
# ---------------------------------------------------------------------------

def print_lineup(match_info: dict, home_lu: dict, away_lu: dict):
    h_cn = _team_cn(match_info["home"])
    a_cn = _team_cn(match_info["away"])
    score = match_info["score"] or "? - ?"

    print()
    print("=" * 66)
    print(f"  {h_cn} {score} {a_cn} · 阵容")
    print("=" * 66)

    h_tac = home_lu["tactics"]
    a_tac = away_lu["tactics"]
    print(f"\n  {h_cn} ({h_tac}){' ' * 16}{a_cn} ({a_tac})")
    print(f"  {'─' * 28}    {'─' * 28}")

    h_starters = home_lu["starters"]
    a_starters = away_lu["starters"]
    max_len = max(len(h_starters), len(a_starters))

    for i in range(max_len):
        h_line = ""
        a_line = ""
        if i < len(h_starters):
            p = h_starters[i]
            cap = "(C)" if p["captain"] else "   "
            h_line = f"{p['position']:>2} {p['number']:>2} {p['name']:<18}{cap}"
        if i < len(a_starters):
            p = a_starters[i]
            cap = "(C)" if p["captain"] else "   "
            a_line = f"{p['position']:>2} {p['number']:>2} {p['name']:<18}{cap}"
        print(f"  {h_line:<32}{a_line}")

    print(f"\n  替补席:")
    h_bench = home_lu["bench"]
    a_bench = away_lu["bench"]
    max_bench = max(len(h_bench), len(a_bench))
    for i in range(max_bench):
        h_line = ""
        a_line = ""
        if i < len(h_bench):
            p = h_bench[i]
            h_line = f"{p['position']:>2} {p['number']:>2} {p['name']}"
        if i < len(a_bench):
            p = a_bench[i]
            a_line = f"{p['position']:>2} {p['number']:>2} {p['name']}"
        print(f"  {h_line:<32}{a_line}")

    all_subs = []
    for s in home_lu["substitutions"]:
        all_subs.append((s["minute"], h_cn, s["off"], s["on"]))
    for s in away_lu["substitutions"]:
        all_subs.append((s["minute"], a_cn, s["off"], s["on"]))
    all_subs.sort(key=lambda x: x[0])

    if all_subs:
        print(f"\n  换人时间线:")
        for minute, team, off, on in all_subs:
            print(f"    {minute:>8}  {team}: {off} -> {on}")

    print()
    print("=" * 66)


# ---------------------------------------------------------------------------
# Output: match list
# ---------------------------------------------------------------------------

def print_match_list(index: dict):
    print()
    print("=" * 72)
    print(f"  2026 世界杯小组赛 · FIFA API 比赛索引")
    print("=" * 72)
    print()
    print(f"  {'M#':>3}  {'日期':<12} {'组':>5}  {'比赛':<30} {'比分':>8}  {'FIFA ID'}")
    print(f"  {'──':>3}  {'────':<12} {'─':>5}  {'────':<30} {'──':>8}  {'───────'}")

    for mid in sorted(index.keys()):
        e = index[mid]
        h_cn = _team_cn(e["home"])
        a_cn = _team_cn(e["away"])
        name = f"{h_cn} vs {a_cn}"
        score = e["score"] if e["score"] else "  -  "
        grp = e["group"].replace("Group ", "") if e["group"] else ""
        print(f"  {mid:>3}  {e['date']:<12} {grp:>5}  {name:<30} {score:>8}  {e['fifa_id']}")

    total = len(index)
    played = sum(1 for e in index.values() if e["score"])
    print()
    print(f"  共 {total} 场 · 已完赛 {played} 场 · 未完赛 {total - played} 场")
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_stats(match_info: dict, stats: dict, lineup: dict | None = None):
    os.makedirs(DATA_DIR, exist_ok=True)
    mid = match_info["match_id"]
    payload = {
        "matchId": mid,
        "fifaMatchId": match_info["fifa_id"],
        "fetchTime": datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S"),
        "home": match_info["home"],
        "away": match_info["away"],
        "score": match_info["score"],
        "date": match_info["date"],
        "venue": match_info.get("venue", ""),
        "attendance": match_info.get("attendance", ""),
        "tactics": {
            "home": match_info.get("h_tactics", ""),
            "away": match_info.get("a_tactics", ""),
        },
        "stats": {
            "shots": stats["shots"],
            "corners": stats["corners"],
            "fouls": stats["fouls"],
            "offsides": stats["offsides"],
        },
        "goals": stats["goals"],
        "substitutions": stats["substitutions"],
        "bookings": stats["bookings"],
    }
    if lineup:
        payload["lineup"] = lineup

    path = os.path.join(DATA_DIR, f"match_{mid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存至 {path}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(_args):
    index = _build_match_index()
    print_match_list(index)


def cmd_stats(args):
    index = _build_match_index()
    match_info = _resolve_match(args.match, index)
    if not match_info:
        sys.exit(1)

    if not match_info["score"]:
        h_cn = _team_cn(match_info["home"])
        a_cn = _team_cn(match_info["away"])
        print(f"  {h_cn} vs {a_cn} (M{match_info['match_id']}) 尚未完赛")
        sys.exit(1)

    print(f"\n  获取 M{match_info['match_id']} 的赛后数据...")
    events = _fetch_timeline(match_info["fifa_id"])
    if not events:
        print("  未获取到时间线数据", file=sys.stderr)
        sys.exit(1)

    stats = _parse_stats(events, match_info)
    print_stats(match_info, stats)
    save_stats(match_info, stats)


def cmd_lineup(args):
    index = _build_match_index()
    match_info = _resolve_match(args.match, index)
    if not match_info:
        sys.exit(1)

    if not match_info["score"]:
        h_cn = _team_cn(match_info["home"])
        a_cn = _team_cn(match_info["away"])
        print(f"  {h_cn} vs {a_cn} (M{match_info['match_id']}) 尚未完赛")
        sys.exit(1)

    print(f"\n  获取 M{match_info['match_id']} 的阵容数据...")
    live = _fetch_live(match_info["fifa_id"])
    if not live:
        print("  未获取到阵容数据", file=sys.stderr)
        sys.exit(1)

    home_lu = _parse_lineup(live["HomeTeam"])
    away_lu = _parse_lineup(live["AwayTeam"])

    # Update tactics from live data if available
    if home_lu["tactics"]:
        match_info["h_tactics"] = home_lu["tactics"]
    if away_lu["tactics"]:
        match_info["a_tactics"] = away_lu["tactics"]

    print_lineup(match_info, home_lu, away_lu)

    lineup_data = {
        "home": {"tactics": home_lu["tactics"], "starters": home_lu["starters"], "bench": home_lu["bench"]},
        "away": {"tactics": away_lu["tactics"], "starters": away_lu["starters"], "bench": away_lu["bench"]},
    }

    events = _fetch_timeline(match_info["fifa_id"])
    stats = _parse_stats(events, match_info) if events else None
    if stats:
        save_stats(match_info, stats, lineup=lineup_data)


def cmd_batch(_args):
    import time
    index = _build_match_index()
    played = sorted(mid for mid, e in index.items() if e["score"])
    already = set()
    for f in os.listdir(DATA_DIR) if os.path.isdir(DATA_DIR) else []:
        if f.startswith("match_") and f.endswith(".json"):
            try:
                already.add(int(f[6:-5]))
            except ValueError:
                pass

    to_fetch = [mid for mid in played if mid not in already]
    if not to_fetch:
        print(f"\n  所有 {len(played)} 场已完赛比赛的数据均已保存")
        return

    print(f"\n  共 {len(played)} 场已完赛，{len(already)} 场已缓存，需获取 {len(to_fetch)} 场\n")

    for i, mid in enumerate(to_fetch, 1):
        info = index[mid]
        h_cn = _team_cn(info["home"])
        a_cn = _team_cn(info["away"])
        print(f"  [{i}/{len(to_fetch)}] M{mid} {h_cn} {info['score']} {a_cn}...", end="", flush=True)

        events = _fetch_timeline(info["fifa_id"])
        if not events:
            print(" 跳过（无数据）")
            continue

        stats = _parse_stats(events, info)

        live = _fetch_live(info["fifa_id"])
        lineup = None
        if live:
            home_lu = _parse_lineup(live["HomeTeam"])
            away_lu = _parse_lineup(live["AwayTeam"])
            if home_lu["tactics"]:
                info["h_tactics"] = home_lu["tactics"]
            if away_lu["tactics"]:
                info["a_tactics"] = away_lu["tactics"]
            lineup = {
                "home": {"tactics": home_lu["tactics"], "starters": home_lu["starters"], "bench": home_lu["bench"]},
                "away": {"tactics": away_lu["tactics"], "starters": away_lu["starters"], "bench": away_lu["bench"]},
            }

        save_stats(info, stats, lineup=lineup)
        print(" OK")
        if i < len(to_fetch):
            time.sleep(0.5)

    print(f"\n  批量获取完成，共保存 {len(to_fetch)} 场比赛数据至 {DATA_DIR}/")


# ---------------------------------------------------------------------------
# Friendly matches
# ---------------------------------------------------------------------------

def _build_friendly_index(team_en: str) -> list[dict]:
    """Returns list of 2026 friendly matches involving team_en, sorted by date."""
    data = _fetch_json(FRIENDLY_CALENDAR_URL)
    if not data:
        return []

    team_fifa = _fifa_name(team_en)
    matches = []

    for m in data.get("Results", []):
        home_obj = m.get("Home", {})
        away_obj = m.get("Away", {})
        h_arr = home_obj.get("TeamName", [{}])
        a_arr = away_obj.get("TeamName", [{}])
        h_fifa = h_arr[0].get("Description", "") if isinstance(h_arr, list) and h_arr else ""
        a_fifa = a_arr[0].get("Description", "") if isinstance(a_arr, list) and a_arr else ""

        if h_fifa != team_fifa and a_fifa != team_fifa:
            continue

        h_score = home_obj.get("Score")
        a_score = away_obj.get("Score")
        score_str = f"{h_score}-{a_score}" if h_score is not None and a_score is not None else None

        matches.append({
            "fifa_id": m.get("IdMatch", ""),
            "home": _our_name(h_fifa),
            "away": _our_name(a_fifa),
            "home_fifa": h_fifa,
            "away_fifa": a_fifa,
            "score": score_str,
            "date": m.get("Date", "")[:10],
            "venue": _localized(m.get("Stadium", {}).get("Name", [])),
            "h_tactics": home_obj.get("Tactics", ""),
            "a_tactics": away_obj.get("Tactics", ""),
            "is_home": h_fifa == team_fifa,
        })

    matches.sort(key=lambda x: x["date"])
    return matches


def cmd_friendlies(args):
    team = _resolve_team_input(args.team)
    if not team:
        print(f"  无法识别队名: {args.team}", file=sys.stderr)
        sys.exit(1)

    cn = _team_cn(team)
    print(f"\n  获取 {cn} 的 2026 年热身赛数据...")
    matches = _build_friendly_index(team)
    if not matches:
        print(f"  未找到 {cn} 的热身赛数据")
        return

    print()
    print("=" * 78)
    print(f"  {cn} · 2026 年热身赛 ({len(matches)} 场)")
    print("=" * 78)
    print()
    print(f"  {'#':>3}  {'日期':<12} {'对手':<16} {'比分':>6}  {'主/客':>4}  {'本队阵型':<12} {'对手阵型'}")
    print(f"  {'─' * 74}")

    tactics_counter = Counter()
    results = {"W": 0, "D": 0, "L": 0}

    for i, m in enumerate(matches, 1):
        opp = m["away"] if m["is_home"] else m["home"]
        opp_cn = _team_cn(opp) if opp in TEAM_CN else opp
        loc = "主场" if m["is_home"] else "客场"
        own_tac = m["h_tactics"] if m["is_home"] else m["a_tactics"]
        opp_tac = m["a_tactics"] if m["is_home"] else m["h_tactics"]
        own_tac_str = own_tac if own_tac and own_tac != "None" else "-"
        opp_tac_str = opp_tac if opp_tac and opp_tac != "None" else "-"
        score = m["score"] or "-"

        if own_tac_str != "-":
            tactics_counter[own_tac_str] += 1

        if m["score"]:
            h, a = map(int, m["score"].split("-"))
            own_goals = h if m["is_home"] else a
            opp_goals = a if m["is_home"] else h
            if own_goals > opp_goals:
                results["W"] += 1
            elif own_goals == opp_goals:
                results["D"] += 1
            else:
                results["L"] += 1

        print(f"  {i:>3}  {m['date']:<12} {opp_cn:<16} {score:>6}  {loc:>4}  {own_tac_str:<12} {opp_tac_str}")

    print()
    print(f"  战绩: {results['W']}胜 {results['D']}平 {results['L']}负")
    if tactics_counter:
        top = tactics_counter.most_common(3)
        tac_str = "、".join(f"{t}({c}次)" for t, c in top)
        print(f"  常用阵型: {tac_str}")
    print()
    print(f"  💡 使用 'python3 fifa_stats.py friendly {args.team} <N>' 查看第 N 场的详细数据")
    print("=" * 78)
    print()


def cmd_friendly(args):
    team = _resolve_team_input(args.team)
    if not team:
        print(f"  无法识别队名: {args.team}", file=sys.stderr)
        sys.exit(1)

    cn = _team_cn(team)
    matches = _build_friendly_index(team)
    if not matches:
        print(f"  未找到 {cn} 的热身赛数据")
        sys.exit(1)

    n = args.n
    if n < 1 or n > len(matches):
        print(f"  序号超出范围: {n} (有效范围 1-{len(matches)})", file=sys.stderr)
        sys.exit(1)

    m = matches[n - 1]
    h_cn = _team_cn(m["home"]) if m["home"] in TEAM_CN else m["home"]
    a_cn = _team_cn(m["away"]) if m["away"] in TEAM_CN else m["away"]

    print(f"\n  获取 {h_cn} vs {a_cn} ({m['date']}) 的详细数据...")

    events = _fetch_json(FRIENDLY_TIMELINE_URL.format(mid=m["fifa_id"]))
    events = events.get("Event", []) if events else []

    live = _fetch_json(FRIENDLY_LIVE_URL.format(mid=m["fifa_id"]))

    if not events and not live:
        print("  未获取到详细数据", file=sys.stderr)
        sys.exit(1)

    fake_info = {
        "match_id": f"F{n}",
        "fifa_id": m["fifa_id"],
        "home": m["home"],
        "away": m["away"],
        "home_fifa": m["home_fifa"],
        "away_fifa": m["away_fifa"],
        "score": m["score"],
        "date": m["date"],
        "venue": m.get("venue", ""),
        "attendance": "",
        "group": "Friendly",
        "h_tactics": m.get("h_tactics", ""),
        "a_tactics": m.get("a_tactics", ""),
    }

    if events:
        stats = _parse_stats(events, fake_info)
        print_stats(fake_info, stats)

    if live:
        home_lu = _parse_lineup(live["HomeTeam"])
        away_lu = _parse_lineup(live["AwayTeam"])
        if home_lu["tactics"]:
            fake_info["h_tactics"] = home_lu["tactics"]
        if away_lu["tactics"]:
            fake_info["a_tactics"] = away_lu["tactics"]
        print_lineup(fake_info, home_lu, away_lu)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FIFA 官方 API 比赛数据工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python3 fifa_stats.py list\n"
               "  python3 fifa_stats.py stats 49\n"
               "  python3 fifa_stats.py stats 法国\n"
               "  python3 fifa_stats.py lineup France\n"
               "  python3 fifa_stats.py friendlies 法国\n"
               "  python3 fifa_stats.py friendly 法国 2\n",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="所有小组赛比赛列表")

    p_stats = sub.add_parser("stats", help="赛后统计摘要")
    p_stats.add_argument("match", help="match_id (1-72) 或队名 (中/英文)")

    p_lineup = sub.add_parser("lineup", help="首发阵容 + 换人")
    p_lineup.add_argument("match", help="match_id (1-72) 或队名 (中/英文)")

    sub.add_parser("batch", help="批量获取所有已完赛比赛数据")

    p_friendlies = sub.add_parser("friendlies", help="球队 2026 热身赛列表")
    p_friendlies.add_argument("team", help="队名 (中/英文)")

    p_friendly = sub.add_parser("friendly", help="热身赛详细数据 (stats + lineup)")
    p_friendly.add_argument("team", help="队名 (中/英文)")
    p_friendly.add_argument("n", type=int, help="第几场 (从 friendlies 列表中的序号)")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "lineup":
        cmd_lineup(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "friendlies":
        cmd_friendlies(args)
    elif args.command == "friendly":
        cmd_friendly(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
