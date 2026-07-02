#!/usr/bin/env python3
"""2026 FIFA World Cup knockout stage Monte Carlo simulator.

Simulates the full bracket (R32→Final) 10,000 times using model predictions
(where available) and Elo-based probabilities, outputting advancement and
championship probabilities for every team.

Usage:
    python3 knockout_simulator.py              # full simulation
    python3 knockout_simulator.py --team Brazil # single team path
"""

import json
import os
import random
import sys
from collections import defaultdict

from match_data import KNOCKOUT_MATCHES, MATCH_BY_ID, TEAM_CN, ALL_MATCHES
from elo_ratings import compute_updated_elo, elo_to_probs

DATA_DIR = os.path.join(os.path.dirname(__file__), "02_data")
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.json")

NUM_SIMS = 10_000

# ---------------------------------------------------------------------------
# Bracket structure: match_id -> (home_source, away_source)
# Source is another match_id whose winner feeds in
# ---------------------------------------------------------------------------

BRACKET = {
    89: (75, 78),   90: (73, 76),
    91: (74, 77),   92: (79, 80),
    93: (84, 83),   94: (82, 81),
    95: (87, 86),   96: (85, 88),
    97: (89, 90),   98: (93, 94),
    99: (91, 92),  100: (95, 96),
    101: (97, 98), 102: (99, 100),
    104: (101, 102),
}

ROUND_NAMES = {
    "R32": "32强赛", "R16": "16强赛", "QF": "四分之一决赛",
    "SF": "半决赛", "F": "决赛",
}

ROUND_ORDER = ["R32", "R16", "QF", "SF", "F"]

R32_IDS = list(range(73, 89))
R16_IDS = list(range(89, 97))
QF_IDS = [97, 98, 99, 100]
SF_IDS = [101, 102]
F_IDS = [104]

MATCH_ROUND = {}
for mid in R32_IDS:
    MATCH_ROUND[mid] = "R32"
for mid in R16_IDS:
    MATCH_ROUND[mid] = "R16"
for mid in QF_IDS:
    MATCH_ROUND[mid] = "QF"
for mid in SF_IDS:
    MATCH_ROUND[mid] = "SF"
for mid in F_IDS:
    MATCH_ROUND[mid] = "F"


def load_predictions() -> dict[int, dict]:
    if not os.path.exists(PREDICTIONS_FILE):
        return {}
    with open(PREDICTIONS_FILE) as f:
        data = json.load(f)
    return {p["matchId"]: p for p in data.get("predictions", [])}


def get_winner_from_score(match_id: int) -> str | None:
    m = MATCH_BY_ID.get(match_id)
    if not m or not m.score:
        return None
    parts = m.score.replace(" ", "").split("-")
    h, a = int(parts[0]), int(parts[1].split("(")[0] if "(" in parts[1] else parts[1])
    if h > a:
        return m.team1
    elif a > h:
        return m.team2
    if "aet" in m.score:
        aet = m.score.split("aet")[1].strip().rstrip(")")
        ah, aa = map(int, aet.split("-"))
        return m.team1 if ah > aa else m.team2
    if "pen" in m.score:
        pen = m.score.split("(")[1].split(")")[0]
        ph, pa = map(int, pen.split("-"))
        return m.team1 if ph > pa else m.team2
    return None


def get_match_probs(team1: str, team2: str, match_id: int,
                    predictions: dict, elo: dict) -> tuple[float, float]:
    """Return (advance_home, advance_away) probabilities."""
    pred = predictions.get(match_id)
    if pred:
        ph, pd, pa = pred["probH"], pred["probD"], pred["probA"]
    else:
        r1 = elo.get(team1, 1500)
        r2 = elo.get(team2, 1500)
        ph, pd, pa = elo_to_probs(r1, r2)
        if pd < 0.25:
            deficit = 0.25 - pd
            ph -= deficit * ph / (ph + pa) if (ph + pa) > 0 else deficit / 2
            pa -= deficit * pa / (ph + pa + deficit) if (ph + pa) > 0 else deficit / 2
            pd = 0.25

    denom = ph + pa
    if denom <= 0:
        adv_h = 0.5
    else:
        adv_h = ph + pd * (ph / denom)
    adv_a = 1.0 - adv_h
    return adv_h, adv_a


def simulate_once(predictions: dict, elo: dict) -> dict[str, str]:
    """Run one simulation. Returns {match_id: winner_team_name}."""
    winners = {}

    for mid in R32_IDS:
        m = MATCH_BY_ID[mid]
        actual = get_winner_from_score(mid)
        if actual:
            winners[mid] = actual
        else:
            adv_h, adv_a = get_match_probs(m.team1, m.team2, mid, predictions, elo)
            winners[mid] = m.team1 if random.random() < adv_h else m.team2

    for mid in R16_IDS + QF_IDS + SF_IDS + F_IDS:
        src_h, src_a = BRACKET[mid]
        team_h = winners[src_h]
        team_a = winners[src_a]
        adv_h, _ = get_match_probs(team_h, team_a, mid, predictions, elo)
        winners[mid] = team_h if random.random() < adv_h else team_a

    return winners


def run_simulation(n: int = NUM_SIMS) -> dict:
    predictions = load_predictions()
    elo = compute_updated_elo()

    all_teams = set()
    for mid in R32_IDS:
        m = MATCH_BY_ID[mid]
        all_teams.add(m.team1)
        all_teams.add(m.team2)

    round_counts = {r: defaultdict(int) for r in ROUND_ORDER}
    champion_count = defaultdict(int)

    for _ in range(n):
        winners = simulate_once(predictions, elo)

        round_winners = {r: set() for r in ROUND_ORDER}
        for mid, winner in winners.items():
            rnd = MATCH_ROUND.get(mid)
            if rnd:
                round_winners[rnd].add(winner)

        for rnd in ROUND_ORDER:
            for team in round_winners[rnd]:
                round_counts[rnd][team] += 1

        champion = winners[104]
        champion_count[champion] += 1

    results = {}
    for team in all_teams:
        results[team] = {
            "team_cn": TEAM_CN.get(team, team),
            "R32": round_counts["R32"].get(team, 0) / n,
            "R16": round_counts["R16"].get(team, 0) / n,
            "QF": round_counts["QF"].get(team, 0) / n,
            "SF": round_counts["SF"].get(team, 0) / n,
            "F": round_counts["F"].get(team, 0) / n,
            "champion": champion_count.get(team, 0) / n,
        }

    return {
        "results": results,
        "predictions": predictions,
        "elo": elo,
        "n": n,
    }


def print_full_report(sim: dict):
    results = sim["results"]
    predictions = sim["predictions"]
    elo = sim["elo"]
    n = sim["n"]

    ranked = sorted(results.items(), key=lambda x: -x[1]["champion"])

    print("=" * 64)
    print(f"  2026世界杯淘汰赛推演（{n:,}次蒙特卡洛模拟）")
    print("=" * 64)
    print()

    print("  夺冠概率 TOP 16:")
    print("  " + "─" * 50)
    max_pct = ranked[0][1]["champion"] * 100
    for i, (team, data) in enumerate(ranked[:16]):
        cn = data["team_cn"]
        pct = data["champion"] * 100
        bar_len = int(pct / max_pct * 20) if max_pct > 0 else 0
        bar = "█" * bar_len + "▏" if bar_len > 0 else "▏"
        marker = " ★" if i < 3 else ""
        print(f"  {i+1:>2}. {cn:8s} {pct:5.1f}%  {bar}{marker}")
    print()

    print("  各轮次晋级概率:")
    print("  " + "─" * 62)
    print(f"  {'球队':8s}  {'R32':>6s}  {'R16':>6s}  {'QF':>6s}  {'SF':>6s}  {'冠军':>6s}")
    print("  " + "─" * 62)
    for team, data in ranked[:16]:
        cn = data["team_cn"]
        r32 = f"{data['R32']*100:.0f}%"
        r16 = f"{data['R16']*100:.0f}%"
        qf = f"{data['QF']*100:.0f}%"
        sf = f"{data['SF']*100:.0f}%"
        champ = f"{data['champion']*100:.1f}%"
        print(f"  {cn:8s}  {r32:>6s}  {r16:>6s}  {qf:>6s}  {sf:>6s}  {champ:>6s}")
    print()

    print("  R32 晋级预测:")
    print("  " + "─" * 55)
    for mid in R32_IDS:
        m = MATCH_BY_ID[mid]
        cn1 = TEAM_CN.get(m.team1, m.team1)
        cn2 = TEAM_CN.get(m.team2, m.team2)
        actual = get_winner_from_score(mid)
        if actual:
            wcn = TEAM_CN.get(actual, actual)
            print(f"  M{mid} {cn1} vs {cn2:8s} → {wcn} ✅ (已完赛 {m.score})")
        else:
            adv_h, adv_a = get_match_probs(m.team1, m.team2, mid, predictions, elo)
            print(f"  M{mid} {cn1} vs {cn2:8s} → {cn1} {adv_h*100:.0f}% / {cn2} {adv_a*100:.0f}%")
    print()

    print("  潜在对决 — R16 (最可能对阵):")
    print("  " + "─" * 55)
    for mid in R16_IDS:
        src_h, src_a = BRACKET[mid]
        m_h, m_a = MATCH_BY_ID[src_h], MATCH_BY_ID[src_a]
        w_h = get_winner_from_score(src_h)
        w_a = get_winner_from_score(src_a)
        if not w_h:
            adv_h, _ = get_match_probs(m_h.team1, m_h.team2, src_h, predictions, elo)
            w_h = m_h.team1 if adv_h >= 0.5 else m_h.team2
        if not w_a:
            adv_h, _ = get_match_probs(m_a.team1, m_a.team2, src_a, predictions, elo)
            w_a = m_a.team1 if adv_h >= 0.5 else m_a.team2
        cn_h = TEAM_CN.get(w_h, w_h)
        cn_a = TEAM_CN.get(w_a, w_a)
        print(f"  M{mid}: {cn_h} vs {cn_a}")
    print()

    print("=" * 64)


def print_team_report(sim: dict, team_name: str):
    from match_data import resolve_team_name
    resolved = resolve_team_name(team_name)
    if not resolved:
        print(f"未找到球队: {team_name}")
        return

    results = sim["results"]
    data = results.get(resolved)
    if not data:
        print(f"{resolved} 不在淘汰赛中")
        return

    cn = data["team_cn"]
    elo_val = sim["elo"].get(resolved, 0)

    print("=" * 50)
    print(f"  {cn} ({resolved}) 晋级路径")
    print(f"  Elo: {elo_val:.0f}")
    print("=" * 50)
    print()
    print(f"  R32 晋级:  {data['R32']*100:.0f}%")
    print(f"  R16 晋级:  {data['R16']*100:.0f}%")
    print(f"  QF 晋级:   {data['QF']*100:.0f}%")
    print(f"  SF 晋级:   {data['SF']*100:.0f}%")
    print(f"  夺冠:      {data['champion']*100:.1f}%")
    print()

    for mid in R32_IDS:
        m = MATCH_BY_ID[mid]
        if m.team1 == resolved or m.team2 == resolved:
            opp = m.team2 if m.team1 == resolved else m.team1
            opp_cn = TEAM_CN.get(opp, opp)
            actual = get_winner_from_score(mid)
            if actual:
                status = "✅ 晋级" if actual == resolved else "❌ 已淘汰"
                print(f"  R32: vs {opp_cn} → {status} ({m.score})")
            else:
                adv_h, adv_a = get_match_probs(m.team1, m.team2, mid,
                                                sim["predictions"], sim["elo"])
                prob = adv_h if m.team1 == resolved else adv_a
                print(f"  R32: vs {opp_cn} → 晋级概率 {prob*100:.0f}%")
            break

    print("=" * 50)


if __name__ == "__main__":
    random.seed(42)

    team_arg = None
    if "--team" in sys.argv:
        idx = sys.argv.index("--team")
        if idx + 1 < len(sys.argv):
            team_arg = sys.argv[idx + 1]

    sim = run_simulation()

    if team_arg:
        print_team_report(sim, team_arg)
    else:
        print_full_report(sim)
