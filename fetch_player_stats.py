#!/usr/bin/env python3
"""从 API-Football 获取球员级别数据（包括位置统计）。

在本地终端运行:
    python3 fetch_player_stats.py

会自动查找法国世界杯赛程，获取球员详细数据并保存。
"""
import json
import os
import urllib.request

API_KEY = "95d0b2c78b9ddf07a73ed6ff9fa2cdf4"
BASE = "https://v3.football.api-sports.io"
DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data")


def api_get(endpoint):
    url = f"{BASE}/{endpoint}"
    req = urllib.request.Request(url, headers={"x-apisports-key": API_KEY})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    print("Step 1: 查找法国世界杯赛程...")
    data = api_get("fixtures?league=1&season=2026&team=2")
    fixtures = data.get("response", [])
    print(f"  找到 {len(fixtures)} 场比赛")

    for f in fixtures:
        fid = f["fixture"]["id"]
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        score_h = f["goals"]["home"]
        score_a = f["goals"]["away"]
        print(f"  fixture_id={fid}: {home} {score_h}-{score_a} {away}")

    if not fixtures:
        print("  未找到比赛，退出")
        return

    for fix in fixtures:
        fid = fix["fixture"]["id"]
        home = fix["teams"]["home"]["name"]
        away = fix["teams"]["away"]["name"]
        print(f"\nStep 2: 获取 {home} vs {away} (fixture {fid}) 球员详细数据...")

        pdata = api_get(f"fixtures/players?fixture={fid}")
        teams = pdata.get("response", [])

        for team in teams:
            tname = team.get("team", {}).get("name", "?")
            players = team.get("players", [])
            print(f"\n  {tname} ({len(players)} 球员):")

            for p in players:
                player = p.get("player", {})
                stats_list = p.get("statistics", [])
                stats = stats_list[0] if stats_list else {}
                pos = stats.get("games", {}).get("position", "?")
                name = player.get("name", "?")
                rating = stats.get("games", {}).get("rating")
                minutes = stats.get("games", {}).get("minutes")

                shots_total = stats.get("shots", {}).get("total")
                shots_on = stats.get("shots", {}).get("on")
                goals = stats.get("goals", {}).get("total")
                assists = stats.get("goals", {}).get("assists")
                passes = stats.get("passes", {}).get("total")
                key_passes = stats.get("passes", {}).get("key")
                pass_acc = stats.get("passes", {}).get("accuracy")
                dribbles_att = stats.get("dribbles", {}).get("attempts")
                dribbles_suc = stats.get("dribbles", {}).get("success")
                tackles = stats.get("tackles", {}).get("total")
                duels_won = stats.get("duels", {}).get("won")
                duels_total = stats.get("duels", {}).get("total")

                if minutes:
                    print(f"    {name:25s} {pos:4s} {minutes:3}' "
                          f"rating={rating or '-':>4} "
                          f"shots={shots_total or 0}/{shots_on or 0} "
                          f"goals={goals or 0} ast={assists or 0} "
                          f"pass={passes or 0}({pass_acc or '-'}%) "
                          f"key={key_passes or 0} "
                          f"drib={dribbles_suc or 0}/{dribbles_att or 0} "
                          f"tackle={tackles or 0} "
                          f"duels={duels_won or 0}/{duels_total or 0}")

        outfile = os.path.join(DATA_DIR, f"apif_players_fixture_{fid}.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(outfile, "w") as f:
            json.dump(pdata, f, indent=2, ensure_ascii=False)
        print(f"\n  完整数据已保存至 {outfile}")

    print("\n检查API剩余配额...")
    status = api_get("status")
    account = status.get("response", {}).get("requests", {})
    print(f"  今日请求: {account.get('current', '?')}/{account.get('limit_day', '?')}")


if __name__ == "__main__":
    main()
