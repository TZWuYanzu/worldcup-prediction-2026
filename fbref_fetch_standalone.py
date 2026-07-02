#!/usr/bin/env python3
"""
FBref 世界杯球员数据抓取脚本（独立版，无项目依赖）

用法:
  # 单场抓取
  python3 fbref_fetch_standalone.py 78 "https://fbref.com/en/matches/xxxxx/France-Sweden-..."

  # 批量抓取（从 urls.txt 读取，每行格式: match_id url）
  python3 fbref_fetch_standalone.py --batch urls.txt

  # 自动发现：从 FBref 赛程页获取所有已完赛比赛的链接并批量抓取
  python3 fbref_fetch_standalone.py --auto

输出: 所有数据写入 fbref_results.json（当前目录）
"""

import sys, json, re, time

try:
    import requests
    import lxml.html
except ImportError:
    print("需要安装依赖: pip install requests lxml")
    sys.exit(1)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

FIELD_MAP = {
    "minutes": "mins", "goals": "goals", "assists": "assists",
    "xg": "xG", "xg_assist": "xA", "shots": "shots",
    "shots_on_target": "sot",
    "passes_completed": "pass_cmp", "passes": "pass_att",
    "passes_pct": "pass_pct", "assisted_shots": "key_passes",
    "passes_into_final_third": "pass_final3rd",
    "passes_into_penalty_area": "pass_pen_area",
    "progressive_passes": "prog_passes",
    "sca": "sca", "gca": "gca",
    "sca_passes_live": "sca_live", "sca_passes_dead": "sca_dead",
    "sca_take_ons": "sca_drib", "sca_shots": "sca_shot",
    "sca_fouled": "sca_foul",
    "carries": "carries", "progressive_carries": "prog_carries",
    "carries_into_final_third": "carry_final3rd",
    "carries_into_penalty_area": "carry_pen_area",
    "take_ons": "drib_att", "take_ons_won": "drib_won",
    "miscontrols": "miscontrols", "dispossessed": "dispossessed",
}

TABLE_TYPES = {"summary", "passing", "gca", "possession"}


def _to_num(v):
    if not v: return None
    try: return int(v) if "." not in v else float(v)
    except ValueError: return v


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def _extract_tables(html):
    tables = []
    doc = lxml.html.fromstring(html)
    tables.extend(doc.findall(".//table"))
    for c in doc.iter(lxml.html.HtmlComment):
        t = c.text or ""
        if "<table" in t:
            try:
                frag = lxml.html.fromstring(t)
                if frag.tag == "table":
                    tables.append(frag)
                tables.extend(frag.findall(".//table"))
            except Exception:
                pass
    return doc, tables


def _ttype(tid):
    for t in TABLE_TYPES:
        if f"_{t}" in tid and (t != "passing" or "_passing_types" not in tid):
            return t
    return None


def fetch_one(match_id, url):
    print(f"  [{match_id}] 正在获取 {url[:80]}...")
    html = _get(url)
    doc, tables = _extract_tables(html)

    teams = []
    sb = doc.find(".//div[@class='scorebox']")
    if sb is not None:
        for s in sb.findall(".//strong"):
            for a in s.findall(".//a"):
                h = a.get("href", "")
                if "/squads/" in h or "/country/" in h:
                    teams.append(a.text_content().strip())
    if len(teams) < 2:
        te = doc.find(".//title")
        if te is not None:
            ps = te.text_content().split(" vs. ")
            if len(ps) >= 2:
                teams = [ps[0].strip(), ps[1].split("|")[0].strip()]

    home = teams[0] if teams else "Home"
    away = teams[1] if len(teams) > 1 else "Away"
    print(f"  [{match_id}] {home} vs {away}")

    players = {}
    type_count = {}

    for tbl in tables:
        tid = tbl.get("id", "")
        st = _ttype(tid)
        if st is None:
            continue

        team_label = home if type_count.get(st, 0) == 0 else away
        type_count[st] = type_count.get(st, 0) + 1

        thead = tbl.find(".//thead")
        if thead is None: continue
        hrows = thead.findall(".//tr")
        if not hrows: continue
        hdrs = [th.get("data-stat", th.text_content().strip()) for th in hrows[-1]]

        tbody = tbl.find(".//tbody")
        if tbody is None: continue
        for row in tbody.findall(".//tr"):
            if "thead" in (row.get("class") or ""): continue
            cells = list(row)
            if len(cells) < 3: continue

            rd = {}
            for i, c in enumerate(cells):
                k = c.get("data-stat", "") or (hdrs[i] if i < len(hdrs) else "")
                rd[k] = c.text_content().strip()

            pname = rd.get("player", "")
            if not pname: continue

            pk = f"{pname}|{team_label}"
            if pk not in players:
                players[pk] = {"name": pname, "team": team_label}

            for fk, ok in FIELD_MAP.items():
                if fk in rd and rd[fk]:
                    v = _to_num(rd[fk])
                    if v is not None:
                        players[pk][ok] = v

    result = {
        "matchId": match_id,
        "url": url,
        "home": home, "away": away,
        "players": list(players.values()),
    }
    print(f"  [{match_id}] ✓ {len(result['players'])} 名球员")
    return result


def auto_discover():
    """从 FBref 赛程页自动发现所有已完赛比赛的 Match Report 链接"""
    schedule_urls = [
        "https://fbref.com/en/comps/1/schedule/FIFA-World-Cup-Scores-and-Fixtures",
        "https://fbref.com/en/comps/1/2025-2026/schedule/2025-2026-FIFA-World-Cup-Scores-and-Fixtures",
    ]

    html = None
    for u in schedule_urls:
        try:
            print(f"  尝试赛程页: {u[:70]}...")
            html = _get(u)
            break
        except Exception as e:
            print(f"  ✗ {e}")

    if not html:
        print("  无法获取赛程页。请手动提供 URL。")
        return []

    doc = lxml.html.fromstring(html)
    links = []
    for a in doc.findall(".//a"):
        href = a.get("href", "")
        text = a.text_content().strip()
        if "/matches/" in href and ("Match Report" in text or "比赛报告" in text):
            full = "https://fbref.com" + href if href.startswith("/") else href
            links.append(full)

    print(f"  发现 {len(links)} 场已完赛比赛")
    return links


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    results = []

    if sys.argv[1] == "--auto":
        links = auto_discover()
        for i, url in enumerate(links):
            mid = i + 1
            try:
                r = fetch_one(mid, url)
                results.append(r)
            except Exception as e:
                print(f"  [{mid}] ✗ {e}")
            if i < len(links) - 1:
                time.sleep(4)

    elif sys.argv[1] == "--batch":
        if len(sys.argv) < 3:
            print("用法: python3 fbref_fetch_standalone.py --batch urls.txt")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split(None, 1)
                if len(parts) < 2: continue
                mid, url = int(parts[0]), parts[1]
                try:
                    r = fetch_one(mid, url)
                    results.append(r)
                except Exception as e:
                    print(f"  [{mid}] ✗ {e}")
                time.sleep(4)
    else:
        if len(sys.argv) < 3:
            print("用法: python3 fbref_fetch_standalone.py <match_id> <url>")
            sys.exit(1)
        mid = int(sys.argv[1])
        url = sys.argv[2]
        results.append(fetch_one(mid, url))

    out = "fbref_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ 全部完成，共 {len(results)} 场 → {out}")


if __name__ == "__main__":
    main()
