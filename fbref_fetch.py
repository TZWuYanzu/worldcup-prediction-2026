#!/usr/bin/env python3
"""
fbref_fetch.py — 从 FBref 比赛页面提取球员级传球/创造力数据

用法:
  python3 fbref_fetch.py fetch <match_id> <fbref_url>
  python3 fbref_fetch.py list
  python3 fbref_fetch.py show  <match_id>
  python3 fbref_fetch.py top   <match_id>        # 按影响力排序

示例:
  python3 fbref_fetch.py fetch 78 "https://fbref.com/en/matches/abc123/France-Sweden-..."

如何找到 FBref 比赛页面:
  1. 打开 https://fbref.com/en/comps/1/2025-2026/schedule/2025-2026-FIFA-World-Cup-Scores-and-Fixtures
  2. 找到对应比赛，点击 "Match Report"
  3. 复制页面 URL

⚠ 此脚本需要在你自己的终端运行（非阿里云IP），FBref 会封锁云服务器IP。
"""

import sys
import json
import os
import re
from pathlib import Path

import requests
import lxml.html

DATA_DIR = Path(__file__).parent / "02_data" / "fbref_stats"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# FBref data-stat → 我们的字段名
FIELD_MAP = {
    # summary
    "minutes":              "mins",
    "goals":                "goals",
    "assists":              "assists",
    "xg":                   "xG",
    "xg_assist":            "xA",
    "shots":                "shots",
    "shots_on_target":      "sot",
    # passing
    "passes_completed":     "pass_cmp",
    "passes":               "pass_att",
    "passes_pct":           "pass_pct",
    "assisted_shots":       "key_passes",
    "passes_into_final_third": "pass_final3rd",
    "passes_into_penalty_area": "pass_pen_area",
    "progressive_passes":   "prog_passes",
    # gca
    "sca":                  "sca",
    "gca":                  "gca",
    "sca_passes_live":      "sca_live",
    "sca_passes_dead":      "sca_dead",
    "sca_take_ons":         "sca_drib",
    "sca_shots":            "sca_shot",
    "sca_fouled":           "sca_foul",
    # possession / carries
    "carries":              "carries",
    "progressive_carries":  "prog_carries",
    "carries_into_final_third":  "carry_final3rd",
    "carries_into_penalty_area": "carry_pen_area",
    "take_ons":             "drib_att",
    "take_ons_won":         "drib_won",
    "miscontrols":          "miscontrols",
    "dispossessed":         "dispossessed",
}

TABLE_TYPES = {"summary", "passing", "gca", "possession"}


def _to_num(val: str):
    """Try converting string to int or float."""
    if not val or val == "":
        return None
    try:
        return int(val) if "." not in val else float(val)
    except ValueError:
        return val


def _parse_tables(html_text: str) -> list[lxml.html.HtmlElement]:
    """Extract all <table> elements, including those hidden in HTML comments."""
    tables = []
    doc = lxml.html.fromstring(html_text)
    tables.extend(doc.findall(".//table"))

    for comment in doc.iter(lxml.html.HtmlComment):
        text = comment.text or ""
        if "<table" in text:
            try:
                frag = lxml.html.fromstring(text)
                tables.extend(frag.findall(".//table"))
                if frag.tag == "table":
                    tables.append(frag)
            except Exception:
                pass
    return tables


def _table_type(table_id: str) -> str | None:
    for t in TABLE_TYPES:
        if f"_{t}" in table_id:
            if t == "passing" and "_passing_types" in table_id:
                return None
            return t
    return None


def _detect_team(table, doc, teams: list[str]) -> str | None:
    """Try to figure out which team a stats table belongs to."""
    tid = table.get("id", "")
    for team_id_frag in teams:
        if team_id_frag.lower().replace(" ", "").replace("-", "") in tid.lower().replace("-", ""):
            return team_id_frag
    return None


def fetch_match(match_id: int, url: str) -> dict:
    print(f"  正在获取 FBref 数据...")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 403:
        print("  ✗ 403 Forbidden — FBref 封锁了当前IP。")
        print("    请在你自己的终端（非云服务器）运行此脚本。")
        sys.exit(1)
    resp.raise_for_status()
    html = resp.text

    doc = lxml.html.fromstring(html)

    # --- team names ---
    teams = []
    scorebox = doc.find(".//div[@class='scorebox']")
    if scorebox is not None:
        for strong in scorebox.findall(".//strong"):
            for a in strong.findall(".//a"):
                href = a.get("href", "")
                if "/squads/" in href or "/country/" in href:
                    teams.append(a.text_content().strip())
    if len(teams) < 2:
        title_el = doc.find(".//title")
        if title_el is not None:
            parts = title_el.text_content().split(" vs. ")
            if len(parts) >= 2:
                teams = [parts[0].strip(), parts[1].split("|")[0].strip()]

    home = teams[0] if teams else "Home"
    away = teams[1] if len(teams) > 1 else "Away"
    print(f"  对阵: {home} vs {away}")

    # --- parse all tables ---
    all_tables = _parse_tables(html)
    players: dict[str, dict] = {}
    team_table_count: dict[str, int] = {}

    for table in all_tables:
        tid = table.get("id", "")
        stype = _table_type(tid)
        if stype is None:
            continue

        # determine team by table order: first occurrence = home, second = away
        if stype not in team_table_count:
            team_table_count[stype] = 0
        team_label = home if team_table_count[stype] == 0 else away
        team_table_count[stype] = team_table_count.get(stype, 0) + 1

        # parse header (last <tr> in <thead>)
        thead = table.find(".//thead")
        if thead is None:
            continue
        header_rows = thead.findall(".//tr")
        if not header_rows:
            continue
        headers = []
        for th in header_rows[-1]:
            ds = th.get("data-stat", th.text_content().strip())
            headers.append(ds)

        # parse body
        tbody = table.find(".//tbody")
        if tbody is None:
            continue
        for row in tbody.findall(".//tr"):
            if "thead" in (row.get("class") or ""):
                continue
            cells = list(row)
            if len(cells) < 3:
                continue

            row_data = {}
            for i, cell in enumerate(cells):
                ds = cell.get("data-stat", "")
                key = ds if ds else (headers[i] if i < len(headers) else "")
                row_data[key] = cell.text_content().strip()

            pname = row_data.get("player", "")
            if not pname:
                continue

            pkey = f"{pname}|{team_label}"
            if pkey not in players:
                players[pkey] = {"name": pname, "team": team_label}

            for fbref_key, our_key in FIELD_MAP.items():
                if fbref_key in row_data and row_data[fbref_key]:
                    val = _to_num(row_data[fbref_key])
                    if val is not None:
                        players[pkey][our_key] = val

    result = {
        "matchId": match_id,
        "url": url,
        "home": home,
        "away": away,
        "players": list(players.values()),
    }

    out_path = DATA_DIR / f"M{match_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n = len(result["players"])
    print(f"  ✓ 已提取 {n} 名球员数据 → {out_path}")
    _print_table(result)
    return result


# ── display helpers ──────────────────────────────────────────

COL_SPEC = [
    ("球员",          "name",          "<18"),
    ("队",            "team",          "<6"),
    ("分钟",          "mins",          ">4"),
    ("xG",            "xG",            ">5"),
    ("xA",            "xA",            ">5"),
    ("关键传球",      "key_passes",    ">6"),
    ("SCA",           "sca",           ">4"),
    ("GCA",           "gca",           ">4"),
    ("前进传",        "prog_passes",   ">5"),
    ("前进带",        "prog_carries",  ">5"),
    ("过人",          "drib_won",      ">4"),
]

def _fmt(val, spec: str) -> str:
    if val is None or val == "":
        return format("", spec)
    if isinstance(val, float):
        return format(f"{val:.2f}", spec)
    return format(str(val), spec)


def _print_table(data: dict, sort_key: str = "sca"):
    players = data["players"]
    if not players:
        print("  （无球员数据）")
        return

    header = "  "
    sep    = "  "
    for label, _, spec in COL_SPEC:
        w = int(re.search(r"\d+", spec).group())
        header += format(label, spec) + " "
        sep    += "─" * w + " "
    print()
    print(header)
    print(sep)

    def sort_val(p):
        v = p.get(sort_key, 0)
        return v if isinstance(v, (int, float)) else 0

    for p in sorted(players, key=sort_val, reverse=True)[:20]:
        line = "  "
        for _, key, spec in COL_SPEC:
            line += _fmt(p.get(key), spec) + " "
        print(line)


def _impact_score(p: dict) -> float:
    """Composite impact score: xG + xA*1.2 + SCA*0.3 + progP*0.1 + progC*0.1 + KP*0.5"""
    xg  = p.get("xG", 0)  or 0
    xa  = p.get("xA", 0)  or 0
    sca = p.get("sca", 0) or 0
    kp  = p.get("key_passes", 0) or 0
    pp  = p.get("prog_passes", 0) or 0
    pc  = p.get("prog_carries", 0) or 0
    dw  = p.get("drib_won", 0) or 0
    return float(xg) + float(xa)*1.2 + float(sca)*0.3 + float(kp)*0.5 + float(pp)*0.1 + float(pc)*0.1 + float(dw)*0.2


def cmd_list():
    files = sorted(DATA_DIR.glob("M*.json"))
    if not files:
        print("  暂无已抓取的 FBref 数据。")
        print("  用法: python3 fbref_fetch.py fetch <match_id> <fbref_url>")
        return
    for f in files:
        with open(f) as fp:
            d = json.load(fp)
        n = len(d.get("players", []))
        print(f"  M{d['matchId']}: {d['home']} vs {d['away']} ({n} 球员)")


def cmd_show(match_id: int):
    path = DATA_DIR / f"M{match_id}.json"
    if not path.exists():
        print(f"  M{match_id} 数据不存在，请先用 fetch 抓取。")
        return
    with open(path) as f:
        data = json.load(f)
    print(f"\n  M{data['matchId']}: {data['home']} vs {data['away']}")
    _print_table(data)


def cmd_top(match_id: int):
    path = DATA_DIR / f"M{match_id}.json"
    if not path.exists():
        print(f"  M{match_id} 数据不存在。")
        return
    with open(path) as f:
        data = json.load(f)

    print(f"\n  M{data['matchId']}: {data['home']} vs {data['away']}")
    print(f"  按综合影响力排序 (xG + xA×1.2 + SCA×0.3 + KP×0.5 + ProgP×0.1 + ProgC×0.1 + DribW×0.2)")

    players = data["players"]
    for p in players:
        p["_impact"] = _impact_score(p)

    header = f"  {'球员':<18} {'队':<6} {'分钟':>4} {'影响力':>6} │ {'xG':>5} {'xA':>5} {'KP':>3} {'SCA':>4} {'PrgP':>4} {'PrgC':>4} {'DrW':>3}"
    sep    = f"  {'─'*18} {'─'*6} {'─'*4} {'─'*6} │ {'─'*5} {'─'*5} {'─'*3} {'─'*4} {'─'*4} {'─'*4} {'─'*3}"
    print()
    print(header)
    print(sep)

    for p in sorted(players, key=lambda x: x["_impact"], reverse=True)[:16]:
        name = p["name"][:18]
        team = (p.get("team") or "")[:6]
        mins = p.get("mins", "")
        imp  = f"{p['_impact']:.1f}"
        xg   = f"{p['xG']:.2f}" if isinstance(p.get("xG"), (int,float)) else ""
        xa   = f"{p['xA']:.2f}" if isinstance(p.get("xA"), (int,float)) else ""
        kp   = p.get("key_passes", "")
        sca  = p.get("sca", "")
        pp   = p.get("prog_passes", "")
        pc   = p.get("prog_carries", "")
        dw   = p.get("drib_won", "")
        print(f"  {name:<18} {team:<6} {mins:>4} {imp:>6} │ {xg:>5} {xa:>5} {kp:>3} {sca:>4} {pp:>4} {pc:>4} {dw:>3}")


# ── main ─────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "fetch":
        if len(sys.argv) < 4:
            print("用法: python3 fbref_fetch.py fetch <match_id> <fbref_url>")
            sys.exit(1)
        fetch_match(int(sys.argv[2]), sys.argv[3])

    elif cmd == "list":
        cmd_list()

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("用法: python3 fbref_fetch.py show <match_id>")
            sys.exit(1)
        cmd_show(int(sys.argv[2]))

    elif cmd == "top":
        if len(sys.argv) < 3:
            print("用法: python3 fbref_fetch.py top <match_id>")
            sys.exit(1)
        cmd_top(int(sys.argv[2]))

    else:
        # backward compat: treat as fetch <match_id> <url>
        try:
            mid = int(cmd)
            if len(sys.argv) >= 3:
                fetch_match(mid, sys.argv[2])
            else:
                print("用法: python3 fbref_fetch.py fetch <match_id> <fbref_url>")
        except ValueError:
            print(f"未知命令: {cmd}")
            print(__doc__)
            sys.exit(1)


if __name__ == "__main__":
    main()
