#!/usr/bin/env python3
"""2026 World Cup calendar manager — CLI entry point.

Usage:
    python3 add_to_calendar.py groups [--my-teams T1 T2 ...] [--dry-run]
    python3 add_to_calendar.py update-scores   (stub)
    python3 add_to_calendar.py add-knockout     (stub)
    python3 add_to_calendar.py update-bracket   (stub)
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Optional

from match_data import (
    TEAM_CN,
    DEFAULT_HOT_TEAMS,
    GROUP_MATCHES,
    ALL_MATCHES,
    Match,
    resolve_team_name,
    get_all_team_names,
)
import calendar_engine as cal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILE = os.path.join(os.path.dirname(__file__), "calendar_state.json")

CAL_RED = ("世界杯-我的主队", (65535, 0, 0))
CAL_YELLOW = ("世界杯-热门场次", (65535, 50000, 0))
CAL_GREEN = ("世界杯-一般场次", (0, 45000, 0))

COLOR_ICON = {"red": "\U0001f534", "yellow": "\U0001f7e1", "green": "\U0001f7e2"}
COLOR_CAL = {"red": CAL_RED[0], "yellow": CAL_YELLOW[0], "green": CAL_GREEN[0]}

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def get_local_time(
    utc_hour: int, utc_min: int, date_str: str, tz_offset: int = 8
) -> tuple[str, int, int]:
    """Convert UTC to local time. Returns (local_date_str, local_hour, local_min)."""
    from datetime import datetime, timedelta
    y, mo, d = (int(x) for x in date_str.split("-"))
    dt = datetime(y, mo, d, utc_hour, utc_min) + timedelta(hours=tz_offset)
    return dt.strftime("%Y-%m-%d"), dt.hour, dt.minute


def fmt_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"

# ---------------------------------------------------------------------------
# Color classification
# ---------------------------------------------------------------------------

def classify_match(
    match: Match,
    my_teams: set[str],
    hot_teams: set[str],
    tz_offset: int,
) -> str:
    """Return 'red', 'yellow_candidate', or 'green'."""
    if my_teams and (match.team1 in my_teams or match.team2 in my_teams):
        return "red"
    if match.team1 in hot_teams or match.team2 in hot_teams:
        _, local_h, local_m = get_local_time(
            match.utc_hour, match.utc_min, match.date_str, tz_offset
        )
        if local_h * 60 + local_m >= 7 * 60:
            return "yellow_candidate"
    return "green"


def _yellow_priority(match: Match, local_h: int, local_m: int) -> int:
    """Higher = more likely to keep yellow when per-day cap applies."""
    score = 0
    tier_a = {"Argentina", "Portugal", "Brazil"}
    tier_b = {"Netherlands", "Japan", "Morocco"}
    for team in (match.team1, match.team2):
        if team in tier_a:
            score += 25
        elif team in tier_b:
            score += 15
    if match.team1 in DEFAULT_HOT_TEAMS and match.team2 in DEFAULT_HOT_TEAMS:
        score += 20
    if 8 <= local_h <= 11:
        score += 10
    elif 7 <= local_h < 8 or 11 < local_h <= 12:
        score += 5
    return score


def compute_colors(
    matches: list[Match],
    my_teams: set[str],
    hot_teams: set[str],
    tz_offset: int = 8,
    yellow_max_per_day: int = 3,
) -> list[str]:
    """Assign final color ('red'/'yellow'/'green') to each match."""
    raw = []
    yellow_candidates = []

    for i, m in enumerate(matches):
        c = classify_match(m, my_teams, hot_teams, tz_offset)
        local_date, local_h, local_m = get_local_time(
            m.utc_hour, m.utc_min, m.date_str, tz_offset
        )
        raw.append(c)
        if c == "yellow_candidate":
            pri = _yellow_priority(m, local_h, local_m)
            yellow_candidates.append((i, local_date, pri))

    yellow_candidates.sort(key=lambda x: x[2], reverse=True)
    day_counts: dict[str, int] = defaultdict(int)
    yellow_set: set[int] = set()
    for idx, ld, _ in yellow_candidates:
        if day_counts[ld] < yellow_max_per_day:
            yellow_set.add(idx)
            day_counts[ld] += 1

    return [
        "red" if c == "red"
        else ("yellow" if i in yellow_set else "green") if c == "yellow_candidate"
        else "green"
        for i, c in enumerate(raw)
    ]

# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state() -> Optional[dict]:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ---------------------------------------------------------------------------
# Team name resolution helper
# ---------------------------------------------------------------------------

def resolve_team_list(raw_names: list[str]) -> list[str]:
    """Resolve a list of possibly-Chinese team names to English.
    Exits with error message if any name is unrecognized.
    """
    resolved = []
    errors = []
    for name in raw_names:
        en = resolve_team_name(name)
        if en is None:
            errors.append(name)
        else:
            resolved.append(en)
    if errors:
        print(f"ERROR: unrecognized team name(s): {', '.join(errors)}")
        print("Available teams:")
        for en, cn in get_all_team_names():
            print(f"  {cn} / {en}")
        sys.exit(1)
    return resolved

# ---------------------------------------------------------------------------
# Action: groups
# ---------------------------------------------------------------------------

def run_groups(args: argparse.Namespace) -> None:
    my_teams: set[str] = set()
    if args.my_teams:
        my_teams = set(resolve_team_list(args.my_teams))

    hot_teams = DEFAULT_HOT_TEAMS - my_teams
    tz_offset = args.timezone
    matches = GROUP_MATCHES
    colors = compute_colors(matches, my_teams, hot_teams, tz_offset, args.yellow_max)

    has_red = any(c == "red" for c in colors)
    has_yellow = any(c == "yellow" for c in colors)

    print("=" * 60)
    print("2026 FIFA 世界杯 - 小组赛添加至 macOS 日历")
    print("=" * 60)
    print()

    if my_teams:
        cn_names = ", ".join(TEAM_CN.get(t, t) for t in sorted(my_teams))
        print(f"  \U0001f534 我的主队: {cn_names}")
    hot_cn = ", ".join(TEAM_CN.get(t, t) for t in sorted(hot_teams))
    print(f"  \U0001f7e1 热门球队: {hot_cn}")
    print(f"  \U0001f7e2 其余比赛")
    print(f"  \U0001f30f 时区: UTC+{tz_offset} | 黄色每天上限: {args.yellow_max}")
    print()

    if args.dry_run:
        print("  [DRY RUN] 仅预览，不写入日历\n")

    # Create calendars
    if not args.dry_run:
        cals = []
        if has_red:
            cals.append(CAL_RED)
        if has_yellow:
            cals.append(CAL_YELLOW)
        cals.append(CAL_GREEN)
        # Also clean up the old unified calendar name
        cal.delete_calendar("世界杯-重点场次")
        if not cal.ensure_calendars(cals):
            print("ERROR: failed to create calendars")
            sys.exit(1)
        cal_names = ", ".join(f"{n} ({['红','黄','绿'][i]})" for i, (n, _) in enumerate(cals))
        print(f"  已创建日历: {cal_names}\n")

    state = {
        "my_teams": sorted(my_teams),
        "hot_teams": sorted(hot_teams),
        "timezone_offset": tz_offset,
        "events": {},
    }
    counts = {"red": 0, "yellow": 0, "green": 0}

    for i, m in enumerate(matches):
        color = colors[i]
        local_date, local_h, local_m = get_local_time(
            m.utc_hour, m.utc_min, m.date_str, tz_offset
        )
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        icon = COLOR_ICON[color]
        cal_name = COLOR_CAL[color]

        title = f"⚽ {cn1} vs {cn2}"
        notes = f"小组{m.group} | 北京时间 {fmt_time(local_h, local_m)} | {m.venue}"

        print(
            f"{icon} [{m.match_id:02d}/72] {m.group}组: "
            f"{cn1} vs {cn2} | 北京 {local_date} {fmt_time(local_h, local_m)}"
        )

        if not args.dry_run:
            year, month, _ = local_date.split("-")
            day = int(local_date.split("-")[2])
            end_h = local_h + 2
            end_day = day
            if end_h >= 24:
                end_h -= 24
                end_day += 1

            uid = cal.add_event(
                calendar_name=cal_name,
                title=title,
                start=(int(year), int(month), day, local_h, local_m),
                end=(int(year), int(month), end_day, end_h, local_m),
                location=m.venue,
                notes=notes,
            )
            if uid:
                counts[color] += 1
                state["events"][str(m.match_id)] = {
                    "match_id": m.match_id,
                    "calendar_name": cal_name,
                    "color": color,
                    "uid": uid,
                    "score": None,
                }
        else:
            counts[color] += 1

    if not args.dry_run:
        save_state(state)

    print()
    print("=" * 60)
    total = sum(counts.values())
    mode = "[DRY RUN] 预览" if args.dry_run else "完成"
    print(f"  {mode}! 共 {total} 场比赛")
    if has_red:
        print(f"  \U0001f534 我的主队 (红色): {counts['red']} 场")
    if has_yellow:
        print(f"  \U0001f7e1 热门场次 (黄色): {counts['yellow']} 场")
    print(f"  \U0001f7e2 一般场次 (绿色): {counts['green']} 场")
    print("=" * 60)

# ---------------------------------------------------------------------------
# Stub actions (future features)
# ---------------------------------------------------------------------------

def run_update_scores(args: argparse.Namespace) -> None:
    """Update scores for completed matches.

    Usage:
        python3 add_to_calendar.py update-scores 1:2-0 2:2-1 13:1-1
        python3 add_to_calendar.py update-scores --file scores.txt
    """
    state = load_state()
    if not state:
        print("ERROR: calendar_state.json 不存在，请先运行 groups 命令")
        sys.exit(1)

    scores: dict[int, str] = {}

    if args.score_file:
        with open(args.score_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                mid_str, score = line.split(":", 1)
                scores[int(mid_str.strip())] = score.strip()
    elif args.scores:
        for s in args.scores:
            mid_str, score = s.split(":", 1)
            scores[int(mid_str.strip())] = score.strip()
    else:
        print("ERROR: 请提供比分，如: update-scores 1:2-0 2:2-1")
        print("  或: update-scores --file scores.txt")
        sys.exit(1)

    tz_offset = state.get("timezone_offset", 8)
    match_map = {m.match_id: m for m in ALL_MATCHES}
    updated = 0
    skipped = 0

    print("=" * 60)
    print("2026 FIFA 世界杯 - 更新比分")
    print("=" * 60)
    print()

    for mid, score in sorted(scores.items()):
        mid_key = str(mid)
        m = match_map.get(mid)
        if not m:
            print(f"  ⚠ Match {mid} 不存在，跳过")
            skipped += 1
            continue

        ev = state["events"].get(mid_key)
        if not ev:
            print(f"  ⚠ Match {mid} 无日历事件，跳过")
            skipped += 1
            continue

        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        old_score = ev.get("score")

        new_title = f"⚽ {cn1} {score} {cn2}"
        local_date, local_h, local_m = get_local_time(
            m.utc_hour, m.utc_min, m.date_str, tz_offset
        )
        stage_label = f"小组{m.group}" if m.group else (m.stage or "")
        new_notes = (
            f"{stage_label} | 北京时间 {fmt_time(local_h, local_m)} | "
            f"比分: {score} | {m.venue}"
        )

        ev["score"] = score
        if not args.dry_run:
            cal_name = ev["calendar_name"]
            uid = ev.get("uid")
            ok, resolved_uid = cal.update_event_by_uid_or_title(
                cal_name, uid, cn1, cn2, new_title, new_notes,
            )
            if ok:
                if resolved_uid and resolved_uid != uid:
                    ev["uid"] = resolved_uid
                icon = "✅"
            else:
                icon = "⚠️"
        else:
            icon = "📝"
        updated += 1

        change = f" (was {old_score})" if old_score else ""
        print(f"  {icon} [{mid:02d}] {cn1} {score} {cn2}{change}")

    if not args.dry_run:
        save_state(state)

    print()
    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"  {mode}更新: {updated} 场 | 跳过: {skipped} 场")
    print("=" * 60)


def run_add_knockout(args: argparse.Namespace) -> None:
    """Add knockout stage matches to the macOS calendar."""
    STAGE_CN = {
        "R32": "32强淘汰赛", "R16": "16强淘汰赛",
        "QF": "四分之一决赛", "SF": "半决赛", "Final": "决赛",
    }
    CAL_KNOCKOUT = ("世界杯-淘汰赛", (255 * 257, 165 * 257, 0))  # orange

    knockout = [m for m in ALL_MATCHES if m.match_id >= 73]
    if not knockout:
        print("  暂无淘汰赛数据")
        return

    tz_offset = args.timezone
    my_teams: set[str] = set()
    if args.my_teams:
        my_teams = set(resolve_team_list(args.my_teams))

    print("=" * 60)
    print("2026 FIFA 世界杯 - 淘汰赛添加至 macOS 日历")
    print("=" * 60)
    print()

    if args.dry_run:
        print("  [DRY RUN] 仅预览，不写入日历\n")

    if not args.dry_run:
        cals_to_create = [CAL_KNOCKOUT]
        if my_teams:
            cals_to_create.insert(0, CAL_RED)
        cal.ensure_calendars(cals_to_create)

    state = load_state() or {"events": {}}
    added = 0

    for m in knockout:
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        local_date, local_h, local_m = get_local_time(
            m.utc_hour, m.utc_min, m.date_str, tz_offset
        )
        stage_cn = STAGE_CN.get(m.stage, m.stage)

        is_my = my_teams and (m.team1 in my_teams or m.team2 in my_teams)
        cal_name = CAL_RED[0] if is_my else CAL_KNOCKOUT[0]
        icon = "\U0001f534" if is_my else "\U0001f7e0"

        if m.score:
            regular = m.score.split("(")[0].strip() if "(" in m.score else m.score
            title = f"⚽ {cn1} {regular} {cn2}"
            extra = ""
            if "aet" in m.score:
                aet_score = m.score.split("aet")[1].strip().rstrip(")")
                extra = f" | 加时 {aet_score}"
            elif "pen" in m.score:
                pen_score = m.score.split("pen")[1].strip().rstrip(")")
                extra = f" | 点球 {pen_score}"
            notes = f"{stage_cn} | 北京时间 {fmt_time(local_h, local_m)} | 比分: {m.score}{extra} | {m.venue}"
            status = f" ✅ {m.score}"
        else:
            title = f"⚽ {cn1} vs {cn2}"
            notes = f"{stage_cn} | 北京时间 {fmt_time(local_h, local_m)} | {m.venue}"
            status = ""

        print(f"{icon} M{m.match_id:02d} {stage_cn}: {cn1} vs {cn2} | 北京 {local_date} {fmt_time(local_h, local_m)}{status}")

        if not args.dry_run:
            year, month, _ = local_date.split("-")
            day = int(local_date.split("-")[2])
            end_h = local_h + 2
            end_day = day
            if end_h >= 24:
                end_h -= 24
                end_day += 1
            uid = cal.add_event(
                calendar_name=cal_name,
                title=title,
                start=(int(year), int(month), day, local_h, local_m),
                end=(int(year), int(month), end_day, end_h, local_m),
                location=m.venue,
                notes=notes,
            )
            if uid:
                added += 1
                state["events"][str(m.match_id)] = {
                    "match_id": m.match_id,
                    "calendar_name": cal_name,
                    "color": "red" if is_my else "orange",
                    "uid": uid,
                    "score": m.score,
                }

    if not args.dry_run:
        save_state(state)

    print()
    mode = "[DRY RUN] 预览" if args.dry_run else "完成"
    print(f"  {mode}! 共 {len(knockout)} 场淘汰赛" + (f"，已添加 {added} 场" if not args.dry_run else ""))
    print("=" * 60)


def run_update_bracket(args: argparse.Namespace) -> None:
    """STUB: update knockout match events with qualified team names."""
    print("update-bracket: 此功能尚在开发中")
    print("预期功能: 小组赛结束后自动填入晋级球队到对应淘汰赛日历事件")
    sys.exit(0)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

ACTIONS = {
    "groups": run_groups,
    "update-scores": run_update_scores,
    "add-knockout": run_add_knockout,
    "update-bracket": run_update_bracket,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2026 FIFA World Cup — macOS Calendar Manager"
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="groups",
        choices=ACTIONS.keys(),
        help="Action to perform (default: groups)",
    )
    parser.add_argument(
        "scores",
        nargs="*",
        default=None,
        help="Scores in match_id:score format, e.g. 1:2-0 2:2-1 (for update-scores)",
    )
    parser.add_argument(
        "--my-teams",
        nargs="+",
        default=None,
        help="Favorite teams to mark RED (Chinese or English names)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to calendar",
    )
    parser.add_argument(
        "--yellow-max",
        type=int,
        default=3,
        help="Max yellow (hot) matches per day (default: 3)",
    )
    parser.add_argument(
        "--timezone",
        type=int,
        default=8,
        help="UTC offset for local time display (default: 8 for Beijing)",
    )
    parser.add_argument(
        "--file",
        dest="score_file",
        default=None,
        help="Read scores from file (one per line: match_id:score)",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    action_fn = ACTIONS[args.action]
    action_fn(args)


if __name__ == "__main__":
    main()
