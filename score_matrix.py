#!/usr/bin/env python3
"""2026 世界杯比分概率矩阵 — 简化 Dixon-Coles 泊松模型。

用法:
    python3 score_matrix.py predict <match>   # 比分概率矩阵 + Top 10

<match> 支持: match_id (1-88)、英文队名、中文队名

原理: 从赔率隐含概率（70%）+ Elo 概率（30%）加权得到基准胜平负概率，
反推双泊松参数 λ₁/λ₂，应用 Dixon-Coles 低比分修正（ρ 参数），
生成完整比分概率矩阵。

依赖: 仅标准库
"""

import argparse
import math
import sys

from match_data import GROUP_MATCHES, ALL_MATCHES, MATCH_BY_ID, TEAM_CN, resolve_team_name
from elo_ratings import load_elo, elo_to_probs, load_odds_probs

MAX_GOALS = 7
RHO = -0.13


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def dixon_coles_tau(x: int, y: int, lam1: float, lam2: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lam1 * lam2 * rho
    if x == 0 and y == 1:
        return 1 + lam1 * rho
    if x == 1 and y == 0:
        return 1 + lam2 * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def build_matrix(lam1: float, lam2: float, rho: float = RHO) -> dict[tuple[int, int], float]:
    raw = {}
    for i in range(MAX_GOALS):
        for j in range(MAX_GOALS):
            p = poisson_pmf(i, lam1) * poisson_pmf(j, lam2)
            tau = dixon_coles_tau(i, j, lam1, lam2, rho)
            raw[(i, j)] = max(0.0, p * tau)
    total = sum(raw.values())
    if total <= 0:
        return raw
    return {k: v / total for k, v in raw.items()}


def matrix_probs(matrix: dict[tuple[int, int], float]) -> tuple[float, float, float]:
    ph = sum(p for (i, j), p in matrix.items() if i > j)
    pd = sum(p for (i, j), p in matrix.items() if i == j)
    pa = sum(p for (i, j), p in matrix.items() if i < j)
    return ph, pd, pa


def fit_lambdas(target_h: float, target_d: float, target_a: float) -> tuple[float, float]:
    best_err = float("inf")
    best = (1.2, 1.0)

    for l1_10 in range(2, 41):
        lam1 = l1_10 / 10.0
        for l2_10 in range(2, 41):
            lam2 = l2_10 / 10.0
            m = build_matrix(lam1, lam2)
            ph, pd, pa = matrix_probs(m)
            err = (ph - target_h) ** 2 + (pd - target_d) ** 2 + (pa - target_a) ** 2
            if err < best_err:
                best_err = err
                best = (lam1, lam2)

    l1_c, l2_c = best
    for dl1 in range(-12, 13):
        lam1 = l1_c + dl1 * 0.01
        if lam1 <= 0.05:
            continue
        for dl2 in range(-12, 13):
            lam2 = l2_c + dl2 * 0.01
            if lam2 <= 0.05:
                continue
            m = build_matrix(lam1, lam2)
            ph, pd, pa = matrix_probs(m)
            err = (ph - target_h) ** 2 + (pd - target_d) ** 2 + (pa - target_a) ** 2
            if err < best_err:
                best_err = err
                best = (lam1, lam2)

    return best


def resolve_match_arg(arg: str) -> int | None:
    try:
        mid = int(arg)
        if mid in MATCH_BY_ID:
            return mid
    except ValueError:
        pass
    en = resolve_team_name(arg)
    if en:
        for m in reversed(ALL_MATCHES):
            if (m.team1 == en or m.team2 == en) and not m.score:
                return m.match_id
        for m in reversed(ALL_MATCHES):
            if m.team1 == en or m.team2 == en:
                return m.match_id
    return None


def cmd_predict(args):
    mid = resolve_match_arg(args.match)
    if mid is None:
        print(f"  未找到比赛: {args.match}", file=sys.stderr)
        sys.exit(1)

    m = MATCH_BY_ID[mid]
    cn1 = TEAM_CN.get(m.team1, m.team1)
    cn2 = TEAM_CN.get(m.team2, m.team2)

    odds = load_odds_probs(mid)
    elo = load_elo()
    r1 = elo.get(m.team1, 1500)
    r2 = elo.get(m.team2, 1500)
    elo_p = elo_to_probs(r1, r2)

    if odds:
        target_h = 0.7 * odds[0] + 0.3 * elo_p[0]
        target_d = 0.7 * odds[1] + 0.3 * elo_p[1]
        target_a = 0.7 * odds[2] + 0.3 * elo_p[2]
    else:
        target_h, target_d, target_a = elo_p

    lam1, lam2 = fit_lambdas(target_h, target_d, target_a)
    matrix = build_matrix(lam1, lam2)
    model_h, model_d, model_a = matrix_probs(matrix)

    score_str = f"  {m.score}" if m.score else ""
    print()
    print("=" * 62)
    stage_label = f"Group {m.group}" if m.group else m.stage
    print(f"  {cn1} vs {cn2} (M{mid} · {stage_label} · {m.date_str}){score_str}")
    print("=" * 62)

    print()
    print(f"  模型参数: λ₁={lam1:.2f}（{cn1}期望进球） λ₂={lam2:.2f}（{cn2}期望进球）")
    print(f"  Dixon-Coles ρ={RHO}（低比分修正）")

    print()
    if odds:
        print(f"  赔率隐含:  {cn1}胜 {odds[0]:.0%}   平 {odds[1]:.0%}   {cn2}胜 {odds[2]:.0%}")
        print(f"  Elo 概率:  {cn1}胜 {elo_p[0]:.0%}   平 {elo_p[1]:.0%}   {cn2}胜 {elo_p[2]:.0%}")
    print(f"  模型输出:  {cn1}胜 {model_h:.0%}   平 {model_d:.0%}   {cn2}胜 {model_a:.0%}")

    # Matrix
    show = min(6, MAX_GOALS)
    label1 = cn1[:4] if len(cn1) > 4 else cn1
    label2 = cn2[:4] if len(cn2) > 4 else cn2

    print()
    print(f"  比分概率矩阵（%）")
    print()
    header = f"  {label1}＼{label2}"
    for j in range(show):
        header += f"  {j:>5}"
    print(header)
    print(f"  {'─' * (len(label1) + 2 + len(label2) + show * 7)}")

    for i in range(show):
        row = f"    {i}      "
        for j in range(show):
            pct = matrix.get((i, j), 0) * 100
            if pct >= 10:
                row += f" {pct:>5.1f}"
            elif pct >= 1:
                row += f"  {pct:>4.1f}"
            else:
                row += f"  {pct:>4.2f}"
        print(row)

    # Top scores
    ranked = sorted(matrix.items(), key=lambda x: -x[1])[:10]
    print()
    print(f"  最可能比分 Top 10:")
    print()
    for rank, ((g1, g2), prob) in enumerate(ranked, 1):
        result = "H" if g1 > g2 else ("D" if g1 == g2 else "A")
        bar_len = int(prob * 200)
        bar = "█" * bar_len
        print(f"    {rank:>2}. {g1}-{g2} ({result})  {prob:>5.1%}  {bar}")

    # Score group aggregation
    exact_draw = sum(matrix.get((i, i), 0) for i in range(MAX_GOALS))
    one_goal_win = sum(matrix.get((i, i - 1), 0) + matrix.get((i - 1, i), 0)
                       for i in range(1, MAX_GOALS))
    high_score = sum(p for (i, j), p in matrix.items() if i + j >= 4)

    print()
    print(f"  场景概率:")
    print(f"    平局:           {exact_draw:>5.1%}")
    print(f"    一球定胜负:     {one_goal_win:>5.1%}")
    print(f"    大比分(≥4球):   {high_score:>5.1%}")

    exp_total = sum((i + j) * p for (i, j), p in matrix.items())
    print(f"    期望总进球:     {exp_total:.2f}")

    print()
    print("=" * 62)
    print()


def main():
    parser = argparse.ArgumentParser(description="2026 世界杯比分概率矩阵")
    sub = parser.add_subparsers(dest="command")

    p_pred = sub.add_parser("predict", help="生成比分概率矩阵")
    p_pred.add_argument("match", help="match_id / 球队名（中英文）")

    args = parser.parse_args()
    if args.command == "predict":
        cmd_predict(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
