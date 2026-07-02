#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard for World Cup predictions."""

import json
import os
import html
from pathlib import Path
from match_data import ALL_MATCHES, TEAM_CN
from score_matrix import build_matrix, fit_lambdas

DATA_DIR = Path("02_data")
PREDICTIONS_FILE = DATA_DIR / "predictions.json"
ANALYSIS_DIR = DATA_DIR / "analysis"
OUTPUT_FILE = Path("dashboard.html")


def parse_score_parts(score_str):
    """Parse knockout score into structured parts: regular, aet, pen."""
    if not score_str:
        return None
    result = {"display": score_str, "regular": score_str}
    if "aet" in score_str:
        result["regular"] = score_str.split("(")[0].strip()
        result["aet"] = score_str.split("aet")[1].strip().rstrip(")")
    elif "pen" in score_str:
        result["regular"] = score_str.split("(")[0].strip()
        result["pen"] = score_str.split("pen")[1].strip().rstrip(")")
    return result


def load_predictions():
    with open(PREDICTIONS_FILE) as f:
        return json.load(f)["predictions"]


def get_actual_result(score_str):
    if not score_str:
        return None
    base = score_str.split("(")[0].strip()
    parts = base.split("-")
    h, a = int(parts[0].strip()), int(parts[1].strip())
    if h > a:
        return "H"
    elif h == a:
        return "D"
    else:
        return "A"


def compute_brier(pred, actual_result):
    actual = {"H": 0, "D": 0, "A": 0}
    actual[actual_result] = 1
    return (
        (pred["probH"] - actual["H"]) ** 2
        + (pred["probD"] - actual["D"]) ** 2
        + (pred["probA"] - actual["A"]) ** 2
    )


def compute_odds_brier(pred, actual_result):
    if "oddsProbH" not in pred or pred["oddsProbH"] is None:
        return None
    actual = {"H": 0, "D": 0, "A": 0}
    actual[actual_result] = 1
    return (
        (pred["oddsProbH"] - actual["H"]) ** 2
        + (pred["oddsProbD"] - actual["D"]) ** 2
        + (pred["oddsProbA"] - actual["A"]) ** 2
    )


def get_predicted_direction(pred):
    probs = {"H": pred["probH"], "D": pred["probD"], "A": pred["probA"]}
    return max(probs, key=probs.get)


def load_analysis(match_id):
    path = ANALYSIS_DIR / f"M{match_id}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def build_match_data():
    predictions = load_predictions()
    pred_by_id = {p["matchId"]: p for p in predictions}
    match_by_id = {m.match_id: m for m in ALL_MATCHES}

    total_brier = 0
    total_odds_brier = 0
    odds_count = 0
    completed = 0
    direction_correct = 0
    score_correct = 0
    total_predicted = len(predictions)

    matches = []
    for pred in sorted(predictions, key=lambda x: x["matchId"]):
        mid = pred["matchId"]
        m = match_by_id.get(mid)
        if not m:
            continue

        home_cn = TEAM_CN.get(m.team1, m.team1)
        away_cn = TEAM_CN.get(m.team2, m.team2)

        entry = {
            "id": mid,
            "home": home_cn,
            "away": away_cn,
            "homeEn": m.team1,
            "awayEn": m.team2,
            "date": m.date_str,
            "group": m.group,
            "stage": m.stage or ("group" if m.group else ""),
            "venue": m.venue,
            "score": m.score,
            "scoreParts": parse_score_parts(m.score),
            "probH": round(pred["probH"] * 100),
            "probD": round(pred["probD"] * 100),
            "probA": round(pred["probA"] * 100),
            "predScore": pred.get("predScore"),
            "oddsProbH": round(pred.get("oddsProbH", 0) * 100) if pred.get("oddsProbH") else None,
            "oddsProbD": round(pred.get("oddsProbD", 0) * 100) if pred.get("oddsProbD") else None,
            "oddsProbA": round(pred.get("oddsProbA", 0) * 100) if pred.get("oddsProbA") else None,
            "brier": None,
            "oddsBrier": None,
            "directionCorrect": None,
            "scoreCorrect": None,
            "analysis": load_analysis(mid),
            "topScores": [],
        }

        try:
            lam1, lam2 = fit_lambdas(pred["probH"], pred["probD"], pred["probA"])
            mat = build_matrix(lam1, lam2)
            top = sorted(mat.items(), key=lambda x: -x[1])[:5]
            entry["topScores"] = [
                {"score": f"{h}-{a}", "prob": round(p * 100, 1)} for (h, a), p in top
            ]
        except Exception:
            pass

        if m.score:
            actual = get_actual_result(m.score)
            bs = compute_brier(pred, actual)
            entry["brier"] = round(bs, 3)
            completed += 1
            total_brier += bs

            obs = compute_odds_brier(pred, actual)
            if obs is not None:
                entry["oddsBrier"] = round(obs, 3)
                total_odds_brier += obs
                odds_count += 1

            pred_dir = get_predicted_direction(pred)
            dc = pred_dir == actual
            entry["directionCorrect"] = dc
            if dc:
                direction_correct += 1

            regular_score = m.score.split("(")[0].strip() if m.score else None
            if pred.get("predScore") == regular_score:
                entry["scoreCorrect"] = True
                score_correct += 1
            elif pred.get("predScore"):
                entry["scoreCorrect"] = False

        matches.append(entry)

    predicted_ids = {e["id"] for e in matches}
    for m in ALL_MATCHES:
        if m.match_id not in predicted_ids and m.stage and m.stage != "group":
            home_cn = TEAM_CN.get(m.team1, m.team1)
            away_cn = TEAM_CN.get(m.team2, m.team2)
            matches.append({
                "id": m.match_id,
                "home": home_cn,
                "away": away_cn,
                "homeEn": m.team1,
                "awayEn": m.team2,
                "date": m.date_str,
                "group": m.group,
                "stage": m.stage,
                "venue": m.venue,
                "score": m.score,
                "scoreParts": parse_score_parts(m.score),
                "probH": None, "probD": None, "probA": None,
                "predScore": None,
                "oddsProbH": None, "oddsProbD": None, "oddsProbA": None,
                "brier": None, "oddsBrier": None,
                "directionCorrect": None, "scoreCorrect": None,
                "analysis": None,
                "noPrediction": True,
            })

    stats = {
        "totalPredicted": total_predicted,
        "completed": completed,
        "upcoming": total_predicted - completed,
        "brier": round(total_brier / completed, 3) if completed else None,
        "oddsBrier": round(total_odds_brier / odds_count, 3) if odds_count else None,
        "directionCorrect": direction_correct,
        "directionTotal": completed,
        "scoreCorrect": score_correct,
    }

    return {"stats": stats, "matches": matches}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 World Cup Predictions</title>
<style>
:root {
  --bg: #f8f9fb;
  --card-bg: #ffffff;
  --border: #eef0f4;
  --text: #1e2330;
  --text-secondary: #6b7280;
  --text-dim: #9ca3af;
  --accent: #f43f5e;
  --accent-soft: #fff1f2;
  --green: #10b981;
  --green-soft: #ecfdf5;
  --red: #ef4444;
  --red-soft: #fef2f2;
  --prob-h: #f43f5e;
  --prob-d: #d1d5db;
  --prob-a: #6366f1;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
  --radius: 16px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

.header {
  background: #ffffff;
  padding: 28px 32px;
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1280px;
  margin: 0 auto;
}
.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
}
.header h1 {
  font-size: 22px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.5px;
}
.header h1 .accent { color: var(--accent); }

.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.stat-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 16px;
}
.stat-chip .stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}
.stat-chip .stat-value.good { color: var(--green); }
.stat-chip .stat-label {
  font-size: 11px;
  color: var(--text-dim);
  font-weight: 500;
}

.toolbar {
  padding: 16px 32px;
  background: #ffffff;
  border-bottom: 1px solid var(--border);
}
.toolbar-inner {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  max-width: 1280px;
  margin: 0 auto;
  align-items: center;
}
.filter-btn {
  padding: 7px 18px;
  border-radius: 100px;
  border: 1px solid var(--border);
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.filter-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}
.filter-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(244,63,94,0.25);
}
.filter-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 32px 60px;
}

.match-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
  box-shadow: var(--shadow-sm);
}
.card:hover {
  box-shadow: var(--shadow-md);
  border-color: #ddd;
}
.card.expanded {
  box-shadow: var(--shadow-lg);
}

.card-main {
  display: grid;
  grid-template-columns: 4px 1fr auto;
  align-items: center;
  min-height: 72px;
  cursor: pointer;
}
.card-indicator {
  width: 4px;
  align-self: stretch;
  border-radius: 4px 0 0 4px;
}
.card.correct .card-indicator { background: var(--green); }
.card.wrong .card-indicator { background: var(--red); }
.card.upcoming .card-indicator { background: var(--border); }

.card-body {
  display: grid;
  grid-template-columns: 1fr 200px auto;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}

.match-info {}
.match-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-dim);
  font-weight: 500;
}
.match-meta .tag {
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
}
.match-teams {
  font-size: 16px;
  font-weight: 700;
  margin-top: 4px;
  color: var(--text);
  letter-spacing: -0.2px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.flag {
  font-size: 20px;
  line-height: 1;
}
.match-teams .vs {
  color: var(--text-dim);
  font-weight: 400;
  font-size: 13px;
  margin: 0 2px;
}

.prob-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 200px;
}
.prob-bar-container {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: #f1f2f6;
  gap: 1px;
}
.prob-bar-h { background: var(--prob-h); border-radius: 3px 0 0 3px; }
.prob-bar-d { background: var(--prob-d); }
.prob-bar-a { background: var(--prob-a); border-radius: 0 3px 3px 0; }
.prob-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-dim);
  font-weight: 500;
}
.prob-labels .predicted {
  font-weight: 700;
  color: var(--accent);
}

.card-right {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-right: 4px;
}
.actual-score {
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: 1px;
  font-variant-numeric: tabular-nums;
}
.pred-score {
  background: var(--bg);
  padding: 4px 10px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.pred-score.hit {
  background: var(--green-soft);
  color: var(--green);
}
.extra-score {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.brier-badge {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  padding: 4px 10px;
  border-radius: 8px;
  background: var(--bg);
  white-space: nowrap;
}
.brier-badge.good { background: var(--green-soft); color: var(--green); }
.brier-badge.bad { background: var(--red-soft); color: var(--red); }
.status-icon {
  font-size: 16px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}
.status-icon.correct-icon { background: var(--green-soft); }
.status-icon.wrong-icon { background: var(--red-soft); }
.status-icon.upcoming-icon { background: var(--bg); }

.card-detail {
  display: none;
  padding: 0 24px 20px;
  margin-left: 4px;
}
.card.expanded .card-detail { display: block; }

.detail-divider {
  height: 1px;
  background: var(--border);
  margin-bottom: 16px;
}
.detail-content {
  font-size: 13px;
  line-height: 1.9;
  color: var(--text-secondary);
  white-space: pre-wrap;
  font-family: "SF Mono", Menlo, "Cascadia Code", monospace;
  max-height: 400px;
  overflow-y: auto;
  background: var(--bg);
  border-radius: 12px;
  padding: 16px 20px;
}
.detail-content::-webkit-scrollbar { width: 4px; }
.detail-content::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.detail-item {
  background: var(--bg);
  border-radius: 12px;
  padding: 12px 16px;
}
.detail-item label {
  display: block;
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.detail-item .val {
  color: var(--text);
  font-weight: 600;
  font-size: 13px;
}
.edge-pos { color: var(--green); }
.edge-neg { color: var(--red); }

.expand-chevron {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}
.card.expanded .expand-chevron { transform: rotate(180deg); }

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-dim);
  font-size: 14px;
}

/* Search */
.search-box {
  position: relative;
  margin-left: auto;
}
.search-box input {
  width: 180px;
  padding: 7px 14px 7px 32px;
  border: 1px solid var(--border);
  border-radius: 100px;
  font-size: 13px;
  color: var(--text);
  background: #fff;
  outline: none;
  transition: border-color 0.2s, width 0.2s;
}
.search-box input:focus {
  border-color: var(--accent);
  width: 220px;
}
.search-box input::placeholder { color: var(--text-dim); }
.search-box .search-icon {
  position: absolute;
  left: 11px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-dim);
  font-size: 13px;
  pointer-events: none;
}

/* Date divider */
.date-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 0 8px;
}
.date-divider:first-child { padding-top: 4px; }
.date-divider .date-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  white-space: nowrap;
}
.date-divider .date-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}
.date-divider .date-count {
  font-size: 11px;
  color: var(--text-dim);
  font-weight: 500;
}

/* Rich detail sections */
.detail-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}
.detail-section {
  background: var(--bg);
  border-radius: 12px;
  padding: 14px 18px;
}
.detail-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.detail-section-body {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  white-space: pre-wrap;
}
.detail-prob-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.detail-prob-item {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 16px;
  flex: 1;
  min-width: 120px;
  text-align: center;
}
.detail-prob-item .prob-label {
  font-size: 11px;
  color: var(--text-dim);
  font-weight: 600;
}
.detail-prob-item .prob-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--text);
  margin: 2px 0;
}
.detail-prob-item .prob-value.accent { color: var(--accent); }
.detail-prob-item .prob-odds {
  font-size: 10px;
  color: var(--text-dim);
}
.detail-score-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.detail-score-chip {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.detail-score-chip .score-prob {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
  margin-left: 4px;
}
.detail-score-chip.predicted {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.detail-venue {
  font-size: 12px;
  color: var(--text-dim);
  padding-top: 8px;
  display: flex;
  gap: 16px;
}

@media (max-width: 900px) {
  .header { padding: 20px 16px; }
  .toolbar { padding: 12px 16px; }
  .container { padding: 16px; }
  .card-body {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 14px 16px;
  }
  .prob-section { min-width: unset; }
  .card-right { justify-content: flex-start; }
  .stats-bar { gap: 6px; }
  .stat-chip { padding: 6px 12px; }
  .stat-chip .stat-value { font-size: 15px; }
}

/* View toggle tabs */
.view-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg);
  border-radius: 10px;
  padding: 3px;
  margin-right: auto;
}
.view-tab {
  padding: 6px 16px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
}
.view-tab:hover { color: var(--text); }
.view-tab.active {
  background: #fff;
  color: var(--text);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* Bracket */
.bracket-container { display: none; overflow-x: auto; padding-bottom: 20px; }
.bracket-container.visible { display: block; }

.bracket-label {
  text-align: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  padding: 16px 0 8px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.bracket-half {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  gap: 0;
  min-width: 1100px;
  align-items: center;
  padding: 0 8px;
}
.bracket-col {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  min-height: 100%;
  padding: 0 6px;
}
.bracket-col-header {
  text-align: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 8px 0 12px;
}

.bk-node {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 12px;
  margin: 6px 0;
  min-width: 160px;
  position: relative;
  transition: box-shadow 0.15s;
}
.bk-node:hover { box-shadow: var(--shadow-md); }
.bk-node.played { border-color: #d1d5db; }
.bk-node.tbd {
  border-style: dashed;
  border-color: #e5e7eb;
  background: var(--bg);
}
.bk-node.final-node {
  border: 2px solid var(--accent);
  background: var(--accent-soft);
}

.bk-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 2px 0;
  font-size: 13px;
  font-weight: 600;
}
.bk-row .team-side {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  min-width: 0;
}
.bk-row .team-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bk-row .bk-flag { font-size: 16px; line-height: 1; flex-shrink: 0; }
.bk-row .bk-score {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--text);
  min-width: 14px;
  text-align: right;
}
.bk-row.winner { color: var(--text); }
.bk-row.loser { color: var(--text-dim); font-weight: 500; }
.bk-row.tbd-team { color: var(--text-dim); font-weight: 400; font-style: italic; font-size: 11px; }
.bk-mid {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0 0;
  border-top: 1px solid var(--border);
  margin-top: 2px;
}
.bk-mid .bk-id {
  font-size: 10px;
  color: var(--text-dim);
  font-weight: 500;
}
.bk-mid .bk-date {
  font-size: 10px;
  color: var(--text-dim);
}
.bk-mid .bk-extra {
  font-size: 9px;
  font-weight: 600;
  color: var(--accent);
  text-transform: uppercase;
}

.bracket-final-row {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 8px 0 16px;
}
.bracket-final-row .bk-node { min-width: 200px; }

.bracket-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
  margin: 4px 32px;
}

/* connector lines */
.bk-node::after {
  content: '';
  position: absolute;
  right: -12px;
  top: 50%;
  width: 12px;
  height: 1px;
  background: var(--border);
}
.bk-node::before {
  content: '';
  position: absolute;
  left: -12px;
  top: 50%;
  width: 12px;
  height: 1px;
  background: var(--border);
}
.bracket-col:first-child .bk-node::before { display: none; }
.bracket-col:last-child .bk-node::after { display: none; }

@media (max-width: 900px) {
  .bracket-half { min-width: 900px; }
  .bk-node { min-width: 130px; padding: 6px 8px; }
  .bk-row { font-size: 11px; }
}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="header-top">
      <h1>WC <span class="accent">2026</span> Predictions</h1>
      <div class="stats-bar" id="statsBar"></div>
    </div>
  </div>
</div>

<div class="toolbar" id="filters">
  <div class="toolbar-inner">
    <div class="view-tabs">
      <button class="view-tab active" data-view="list">List</button>
      <button class="view-tab" data-view="bracket">Bracket</button>
    </div>
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="group">Group</button>
    <button class="filter-btn" data-filter="knockout">Knockout</button>
    <span class="filter-sep"></span>
    <button class="filter-btn" data-filter="completed">Played</button>
    <button class="filter-btn" data-filter="upcoming">Upcoming</button>
    <span class="filter-sep"></span>
    <button class="filter-btn" data-filter="correct">Correct</button>
    <button class="filter-btn" data-filter="wrong">Wrong</button>
    <div class="search-box">
      <span class="search-icon">&#128269;</span>
      <input type="text" id="searchInput" placeholder="Search team..." oninput="onSearch(this.value)">
    </div>
  </div>
</div>

<div class="container">
  <div class="match-list" id="cardGrid"></div>
  <div class="bracket-container" id="bracketView"></div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

const FLAGS = {
  '墨西哥':'🇲🇽','南非':'🇿🇦','韩国':'🇰🇷','捷克':'🇨🇿',
  '加拿大':'🇨🇦','波黑':'🇧🇦','卡塔尔':'🇶🇦','瑞士':'🇨🇭',
  '巴西':'🇧🇷','摩洛哥':'🇲🇦','海地':'🇭🇹','苏格兰':'🏴󠁧󠁢󠁳󠁣󠁴󠁿',
  '美国':'🇺🇸','巴拉圭':'🇵🇾','澳大利亚':'🇦🇺','土耳其':'🇹🇷',
  '德国':'🇩🇪','库拉索':'🇨🇼','科特迪瓦':'🇨🇮','厄瓜多尔':'🇪🇨',
  '荷兰':'🇳🇱','日本':'🇯🇵','瑞典':'🇸🇪','突尼斯':'🇹🇳',
  '比利时':'🇧🇪','埃及':'🇪🇬','伊朗':'🇮🇷','新西兰':'🇳🇿',
  '西班牙':'🇪🇸','佛得角':'🇨🇻','沙特':'🇸🇦','乌拉圭':'🇺🇾',
  '法国':'🇫🇷','塞内加尔':'🇸🇳','伊拉克':'🇮🇶','挪威':'🇳🇴',
  '阿根廷':'🇦🇷','阿尔及利亚':'🇩🇿','奥地利':'🇦🇹','约旦':'🇯🇴',
  '葡萄牙':'🇵🇹','刚果(金)':'🇨🇩','乌兹别克':'🇺🇿','哥伦比亚':'🇨🇴',
  '英格兰':'🏴󠁧󠁢󠁥󠁮󠁧󠁿','克罗地亚':'🇭🇷','加纳':'🇬🇭','巴拿马':'🇵🇦'
};
function flag(name) { return FLAGS[name] || ''; }

const BRACKET_TREE = {
  upper: [
    {id:75, stage:'R32', next:89, slot:'home'},
    {id:78, stage:'R32', next:89, slot:'away'},
    {id:73, stage:'R32', next:90, slot:'home'},
    {id:76, stage:'R32', next:90, slot:'away'},
    {id:84, stage:'R32', next:93, slot:'home'},
    {id:83, stage:'R32', next:93, slot:'away'},
    {id:82, stage:'R32', next:94, slot:'home'},
    {id:81, stage:'R32', next:94, slot:'away'},
  ],
  lower: [
    {id:74, stage:'R32', next:91, slot:'home'},
    {id:77, stage:'R32', next:91, slot:'away'},
    {id:79, stage:'R32', next:92, slot:'home'},
    {id:80, stage:'R32', next:92, slot:'away'},
    {id:87, stage:'R32', next:95, slot:'home'},
    {id:86, stage:'R32', next:95, slot:'away'},
    {id:85, stage:'R32', next:96, slot:'home'},
    {id:88, stage:'R32', next:96, slot:'away'},
  ],
  r16: [
    {id:89, homeFrom:75, awayFrom:78, next:97, slot:'home'},
    {id:90, homeFrom:73, awayFrom:76, next:97, slot:'away'},
    {id:93, homeFrom:84, awayFrom:83, next:98, slot:'home'},
    {id:94, homeFrom:82, awayFrom:81, next:98, slot:'away'},
    {id:91, homeFrom:74, awayFrom:77, next:99, slot:'home'},
    {id:92, homeFrom:79, awayFrom:80, next:99, slot:'away'},
    {id:95, homeFrom:87, awayFrom:86, next:100, slot:'home'},
    {id:96, homeFrom:85, awayFrom:88, next:100, slot:'away'},
  ],
  qf: [
    {id:97, homeFrom:89, awayFrom:90, next:101, slot:'home'},
    {id:98, homeFrom:93, awayFrom:94, next:101, slot:'away'},
    {id:99, homeFrom:91, awayFrom:92, next:102, slot:'home'},
    {id:100, homeFrom:95, awayFrom:96, next:102, slot:'away'},
  ],
  sf: [
    {id:101, homeFrom:97, awayFrom:98, next:104, slot:'home'},
    {id:102, homeFrom:99, awayFrom:100, next:104, slot:'away'},
  ],
  final: [{id:104, homeFrom:101, awayFrom:102}],
  third: [{id:103, homeFrom:101, awayFrom:102, loserMatch:true}],
};

function getMatchById(id) {
  return DATA.matches.find(m => m.id === id);
}

function getWinner(matchData) {
  if (!matchData || !matchData.score) return null;
  var sp = matchData.scoreParts;
  if (!sp) return null;
  var base = sp.regular.split('-');
  var h = parseInt(base[0]), a = parseInt(base[1]);
  if (h > a) return {name: matchData.home, flag: flag(matchData.home)};
  if (a > h) return {name: matchData.away, flag: flag(matchData.away)};
  if (sp.aet) {
    var ap = sp.aet.split('-');
    if (parseInt(ap[0]) > parseInt(ap[1])) return {name: matchData.home, flag: flag(matchData.home)};
    return {name: matchData.away, flag: flag(matchData.away)};
  }
  if (sp.pen) {
    var pp = sp.pen.split('-');
    if (parseInt(pp[0]) > parseInt(pp[1])) return {name: matchData.home, flag: flag(matchData.home)};
    return {name: matchData.away, flag: flag(matchData.away)};
  }
  return null;
}

function getLoser(matchData) {
  if (!matchData || !matchData.score) return null;
  var w = getWinner(matchData);
  if (!w) return null;
  if (w.name === matchData.home) return {name: matchData.away, flag: flag(matchData.away)};
  return {name: matchData.home, flag: flag(matchData.home)};
}

function resolveTeam(fromId, isLoser) {
  var md = getMatchById(fromId);
  if (md && md.score) {
    var t = isLoser ? getLoser(md) : getWinner(md);
    if (t) return t;
  }
  return {name: 'M'+fromId+(isLoser?'负':'胜'), flag: '', tbd: true};
}

function renderBkNode(node, isR32) {
  var md = getMatchById(node.id);
  var home, away, score = null, date = '';

  if (isR32 && md) {
    home = {name: md.home, flag: flag(md.home)};
    away = {name: md.away, flag: flag(md.away)};
    score = md.score;
    date = md.date;
  } else if (!isR32) {
    var isLoser = node.loserMatch || false;
    home = resolveTeam(node.homeFrom, isLoser);
    away = resolveTeam(node.awayFrom, isLoser);
    if (md) { score = md.score; date = md.date; }
  } else {
    home = {name: '?', flag: '', tbd: true};
    away = {name: '?', flag: '', tbd: true};
  }

  var isTbd = (!md || !md.score) && !isR32;
  var isFinal = node.id === 104;
  var cls = 'bk-node' + (score ? ' played' : '') + (isTbd ? ' tbd' : '') + (isFinal ? ' final-node' : '');

  var hScore = '', aScore = '', extraLabel = '';
  var hCls = '', aCls = '';
  if (score) {
    var baseScore = score.split('(')[0].trim();
    var p = baseScore.split('-');
    hScore = p[0].trim(); aScore = p[1].trim();
    var hi = parseInt(hScore), ai = parseInt(aScore);
    if (hi > ai) { hCls = 'winner'; aCls = 'loser'; }
    else if (ai > hi) { aCls = 'winner'; hCls = 'loser'; }
    else if (score.indexOf('aet') >= 0) {
      var aetPart = score.split('aet')[1].trim().replace(')', '');
      var ap = aetPart.split('-');
      var ahi = parseInt(ap[0]), aai = parseInt(ap[1]);
      if (ahi > aai) { hCls = 'winner'; aCls = 'loser'; }
      else { aCls = 'winner'; hCls = 'loser'; }
      extraLabel = 'aet';
    } else if (score.indexOf('pen') >= 0) {
      var penPart = score.split('pen')[1].trim().replace(')', '');
      var pp = penPart.split('-');
      var phi = parseInt(pp[0]), pai = parseInt(pp[1]);
      if (phi > pai) { hCls = 'winner'; aCls = 'loser'; }
      else { aCls = 'winner'; hCls = 'loser'; }
      extraLabel = 'pen';
    }
  }

  var stageLabel = '';
  if (node.id === 104) stageLabel = 'Final';
  else if (node.id === 103) stageLabel = '3rd';

  var h = '<div class="' + cls + '">';
  h += '<div class="bk-row ' + hCls + (home.tbd ? ' tbd-team' : '') + '"><span class="team-side"><span class="bk-flag">' + home.flag + '</span><span class="team-name">' + escapeHtml(home.name) + '</span></span>';
  if (score) h += '<span class="bk-score">' + hScore + '</span>';
  h += '</div>';
  h += '<div class="bk-row ' + aCls + (away.tbd ? ' tbd-team' : '') + '"><span class="team-side"><span class="bk-flag">' + away.flag + '</span><span class="team-name">' + escapeHtml(away.name) + '</span></span>';
  if (score) h += '<span class="bk-score">' + aScore + '</span>';
  h += '</div>';
  h += '<div class="bk-mid"><span class="bk-id">' + (stageLabel || 'M' + node.id) + '</span>' + (extraLabel ? '<span class="bk-extra">' + extraLabel + '</span>' : '') + '<span class="bk-date">' + (date || '') + '</span></div>';
  h += '</div>';
  return h;
}

function renderBracketHalf(r32nodes, r16nodes, qfNodes, sfNode) {
  var html = '<div class="bracket-half">';

  html += '<div class="bracket-col">';
  for (var i = 0; i < r32nodes.length; i++) html += renderBkNode(r32nodes[i], true);
  html += '</div>';

  html += '<div class="bracket-col">';
  for (var i = 0; i < r16nodes.length; i++) html += renderBkNode(r16nodes[i], false);
  html += '</div>';

  html += '<div class="bracket-col">';
  for (var i = 0; i < qfNodes.length; i++) html += renderBkNode(qfNodes[i], false);
  html += '</div>';

  html += '<div class="bracket-col">';
  html += renderBkNode(sfNode, false);
  html += '</div>';

  html += '<div class="bracket-col"></div>';
  html += '</div>';
  return html;
}

function renderBracket() {
  var el = document.getElementById('bracketView');
  var html = '';

  var upperR16 = BRACKET_TREE.r16.slice(0, 4);
  var lowerR16 = BRACKET_TREE.r16.slice(4, 8);
  var upperQF = BRACKET_TREE.qf.slice(0, 2);
  var lowerQF = BRACKET_TREE.qf.slice(2, 4);

  html += '<div class="bracket-label">Upper Bracket</div>';
  html += renderBracketHalf(BRACKET_TREE.upper, upperR16, upperQF, BRACKET_TREE.sf[0]);

  html += '<div class="bracket-divider"></div>';
  html += '<div class="bracket-final-row">';
  html += renderBkNode(BRACKET_TREE.final[0], false);
  html += renderBkNode(BRACKET_TREE.third[0], false);
  html += '</div>';
  html += '<div class="bracket-divider"></div>';

  html += '<div class="bracket-label">Lower Bracket</div>';
  html += renderBracketHalf(BRACKET_TREE.lower, lowerR16, lowerQF, BRACKET_TREE.sf[1]);

  el.innerHTML = html;
}

function renderStats() {
  const s = DATA.stats;
  const bar = document.getElementById('statsBar');
  const items = [
    { label: 'Brier', value: s.brier !== null ? s.brier.toFixed(3) : '-', cls: s.brier < 0.5 ? 'good' : '' },
    { label: 'Baseline', value: s.oddsBrier !== null ? s.oddsBrier.toFixed(3) : '-', cls: '' },
    { label: 'Direction', value: s.directionCorrect + '/' + s.directionTotal, cls: (s.directionCorrect / s.directionTotal) > 0.65 ? 'good' : '' },
    { label: 'Exact', value: String(s.scoreCorrect), cls: s.scoreCorrect > 0 ? 'good' : '' },
  ];
  bar.innerHTML = items.map(i =>
    '<div class="stat-chip"><div class="stat-label">' + i.label + '</div><div class="stat-value ' + i.cls + '">' + i.value + '</div></div>'
  ).join('');
}

function getStatusClass(m) {
  if (!m.score) return 'upcoming';
  return m.directionCorrect ? 'correct' : 'wrong';
}

function getHighestProb(m) {
  if (m.probH >= m.probD && m.probH >= m.probA) return 'H';
  if (m.probA >= m.probH && m.probA >= m.probD) return 'A';
  return 'D';
}

function renderEdge(model, odds) {
  if (odds === null || odds === undefined) return '';
  const diff = model - odds;
  if (Math.abs(diff) < 1) return '';
  const cls = diff > 0 ? 'edge-pos' : 'edge-neg';
  const sign = diff > 0 ? '+' : '';
  return ' <span class="' + cls + '">(' + sign + diff + '%)</span>';
}

function parseAnalysisSections(text) {
  if (!text) return [];
  var lines = text.split('\n');
  var sections = [];
  var cur = null;
  for (var i = 0; i < lines.length; i++) {
    var l = lines[i];
    if (l.indexOf('## ') === 0) {
      if (cur) sections.push(cur);
      cur = {title: l.substring(3).trim(), body: ''};
    } else if (cur) {
      cur.body += (cur.body ? '\n' : '') + l;
    }
  }
  if (cur) sections.push(cur);
  if (sections.length === 0 && text.trim()) {
    sections.push({title: 'Analysis', body: text.trim()});
  }
  return sections;
}

function renderDetail(m) {
  let h = '<div class="detail-divider"></div><div class="detail-sections">';

  if (m.probH !== null) {
    h += '<div class="detail-section"><div class="detail-section-title">Win Probability</div>';
    h += '<div class="detail-prob-row">';
    var highest = getHighestProb(m);
    h += '<div class="detail-prob-item"><div class="prob-label">' + flag(m.home) + ' ' + escapeHtml(m.home) + '</div><div class="prob-value' + (highest==='H'?' accent':'') + '">' + m.probH + '%</div>';
    if (m.oddsProbH !== null) h += '<div class="prob-odds">Market ' + m.oddsProbH + '%' + renderEdge(m.probH, m.oddsProbH) + '</div>';
    h += '</div>';
    h += '<div class="detail-prob-item"><div class="prob-label">Draw</div><div class="prob-value' + (highest==='D'?' accent':'') + '">' + m.probD + '%</div>';
    if (m.oddsProbD !== null) h += '<div class="prob-odds">Market ' + m.oddsProbD + '%' + renderEdge(m.probD, m.oddsProbD) + '</div>';
    h += '</div>';
    h += '<div class="detail-prob-item"><div class="prob-label">' + flag(m.away) + ' ' + escapeHtml(m.away) + '</div><div class="prob-value' + (highest==='A'?' accent':'') + '">' + m.probA + '%</div>';
    if (m.oddsProbA !== null) h += '<div class="prob-odds">Market ' + m.oddsProbA + '%' + renderEdge(m.probA, m.oddsProbA) + '</div>';
    h += '</div>';
    h += '</div></div>';
  }

  if (m.predScore || (m.topScores && m.topScores.length)) {
    h += '<div class="detail-section"><div class="detail-section-title">Predicted Scores</div>';
    h += '<div class="detail-score-row">';
    if (m.topScores && m.topScores.length) {
      for (var i = 0; i < m.topScores.length; i++) {
        var ts = m.topScores[i];
        var isPred = ts.score === m.predScore;
        h += '<div class="detail-score-chip' + (isPred ? ' predicted' : '') + '">' + ts.score + '<span class="score-prob">' + ts.prob + '%</span></div>';
      }
      if (m.predScore) {
        var alreadyInTop = m.topScores.some(function(t){return t.score === m.predScore;});
        if (!alreadyInTop) {
          var predEntry = m.topScores.find(function(t){return t.score === m.predScore;});
          h += '<div class="detail-score-chip predicted">' + m.predScore + (predEntry ? '<span class="score-prob">' + predEntry.prob + '%</span>' : '') + '</div>';
        }
      }
    } else if (m.predScore) {
      h += '<div class="detail-score-chip predicted">' + m.predScore + '</div>';
    }
    h += '</div></div>';
  }

  var sections = parseAnalysisSections(m.analysis);
  for (var i = 0; i < sections.length; i++) {
    var sec = sections[i];
    h += '<div class="detail-section"><div class="detail-section-title">' + escapeHtml(sec.title) + '</div>';
    h += '<div class="detail-section-body">' + escapeHtml(sec.body.trim()) + '</div>';
    h += '</div>';
  }

  if (m.score) {
    h += '<div class="detail-section"><div class="detail-section-title">Result</div>';
    if (m.scoreParts && (m.scoreParts.aet || m.scoreParts.pen)) {
      h += '<div style="font-size:20px;font-weight:800;letter-spacing:1px;">' + m.scoreParts.regular + '</div>';
      if (m.scoreParts.aet) h += '<div style="margin-top:4px;"><span class="extra-score">aet ' + m.scoreParts.aet + '</span></div>';
      if (m.scoreParts.pen) h += '<div style="margin-top:4px;"><span class="extra-score">pen ' + m.scoreParts.pen + '</span></div>';
    } else {
      h += '<div style="font-size:20px;font-weight:800;letter-spacing:1px;">' + m.score + '</div>';
    }
    if (m.brier !== null) {
      var bc = m.brier < 0.4 ? 'good' : (m.brier > 0.8 ? 'bad' : '');
      h += '<div style="margin-top:4px;font-size:12px;"><span class="brier-badge ' + bc + '">Brier: ' + m.brier.toFixed(3) + '</span></div>';
    }
    h += '</div>';
  }

  var stage = m.group ? m.group + '组' : m.stage;
  h += '<div class="detail-venue"><span>' + stage + '</span><span>' + m.date + '</span><span>' + escapeHtml(m.venue || '') + '</span></div>';

  h += '</div>';
  return h;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderCard(m) {
  const cls = getStatusClass(m);
  const highest = getHighestProb(m);
  const hLabel = highest === 'H' ? 'predicted' : '';
  const dLabel = highest === 'D' ? 'predicted' : '';
  const aLabel = highest === 'A' ? 'predicted' : '';
  const stage = m.group ? m.group + '组' : (m.stage || '');

  let rightParts = [];
  if (m.predScore) {
    const hit = m.scoreCorrect === true ? ' hit' : '';
    rightParts.push('<span class="pred-score' + hit + '">' + m.predScore + '</span>');
  }
  if (m.brier !== null) {
    const bc = m.brier < 0.4 ? 'good' : (m.brier > 0.8 ? 'bad' : '');
    rightParts.push('<span class="brier-badge ' + bc + '">' + m.brier.toFixed(3) + '</span>');
  }
  if (m.score) {
    if (m.scoreParts && (m.scoreParts.aet || m.scoreParts.pen)) {
      rightParts.push('<span class="actual-score">' + m.scoreParts.regular + '</span>');
      if (m.scoreParts.aet) {
        rightParts.push('<span class="extra-score">aet ' + m.scoreParts.aet + '</span>');
      }
      if (m.scoreParts.pen) {
        rightParts.push('<span class="extra-score">pen ' + m.scoreParts.pen + '</span>');
      }
    } else {
      rightParts.push('<span class="actual-score">' + m.score + '</span>');
    }
    const iconCls = m.directionCorrect ? 'correct-icon' : 'wrong-icon';
    const icon = m.directionCorrect ? '&#10003;' : '&#10007;';
    rightParts.push('<span class="status-icon ' + iconCls + '">' + icon + '</span>');
  } else {
    rightParts.push('<span class="status-icon upcoming-icon">-</span>');
  }
  rightParts.push('<span class="expand-chevron">&#9660;</span>');

  return '<div class="card ' + cls + '" data-id="' + m.id + '">'
    + '<div class="card-main" onclick="toggleCard(event, this)">'
    + '<div class="card-indicator"></div>'
    + '<div class="card-body">'
    + '  <div class="match-info">'
    + '    <div class="match-meta"><span class="tag">M' + m.id + '</span><span>' + stage + '</span><span>' + m.date + '</span></div>'
    + '    <div class="match-teams"><span class="flag">' + flag(m.home) + '</span>' + escapeHtml(m.home) + '<span class="vs">vs</span>' + escapeHtml(m.away) + '<span class="flag">' + flag(m.away) + '</span></div>'
    + '  </div>'
    + '  <div class="prob-section">'
    + '    <div class="prob-bar-container">'
    + '      <div class="prob-bar-h" style="width:' + m.probH + '%"></div>'
    + '      <div class="prob-bar-d" style="width:' + m.probD + '%"></div>'
    + '      <div class="prob-bar-a" style="width:' + m.probA + '%"></div>'
    + '    </div>'
    + '    <div class="prob-labels">'
    + '      <span class="' + hLabel + '">' + m.probH + '%</span>'
    + '      <span class="' + dLabel + '">' + m.probD + '%</span>'
    + '      <span class="' + aLabel + '">' + m.probA + '%</span>'
    + '    </div>'
    + '  </div>'
    + '  <div class="card-right">' + rightParts.join('') + '</div>'
    + '</div>'
    + '</div>'
    + '<div class="card-detail">' + renderDetail(m) + '</div>'
    + '</div>';
}

function toggleCard(e, el) {
  e.stopPropagation();
  el.closest('.card').classList.toggle('expanded');
}

var currentFilter = 'all';
var currentSearch = '';

function applyFilters() {
  const grid = document.getElementById('cardGrid');
  let filtered = DATA.matches.filter(m => !m.noPrediction);

  if (currentFilter === 'group') filtered = filtered.filter(m => m.group);
  else if (currentFilter === 'knockout') filtered = filtered.filter(m => !m.group);
  else if (currentFilter === 'completed') filtered = filtered.filter(m => m.score);
  else if (currentFilter === 'upcoming') filtered = filtered.filter(m => !m.score);
  else if (currentFilter === 'correct') filtered = filtered.filter(m => m.directionCorrect === true);
  else if (currentFilter === 'wrong') filtered = filtered.filter(m => m.directionCorrect === false);

  if (currentSearch) {
    var q = currentSearch.toLowerCase();
    filtered = filtered.filter(m =>
      m.home.toLowerCase().indexOf(q) !== -1 ||
      m.away.toLowerCase().indexOf(q) !== -1 ||
      (m.homeEn && m.homeEn.toLowerCase().indexOf(q) !== -1) ||
      (m.awayEn && m.awayEn.toLowerCase().indexOf(q) !== -1)
    );
  }

  filtered.sort((a, b) => a.date > b.date ? -1 : a.date < b.date ? 1 : b.id - a.id);

  if (filtered.length === 0) {
    grid.innerHTML = '<div class="empty-state">No matches found</div>';
    return;
  }

  var html = '';
  var lastDate = '';
  for (var i = 0; i < filtered.length; i++) {
    var m = filtered[i];
    if (m.date !== lastDate) {
      var d = new Date(m.date);
      var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      var dayLabel = months[d.getMonth()] + ' ' + d.getDate();
      var weekdays = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
      dayLabel = weekdays[d.getDay()] + ', ' + dayLabel;
      var count = filtered.filter(x => x.date === m.date).length;
      html += '<div class="date-divider"><span class="date-label">' + dayLabel + '</span><div class="date-line"></div><span class="date-count">' + count + ' match' + (count > 1 ? 'es' : '') + '</span></div>';
      lastDate = m.date;
    }
    html += renderCard(m);
  }
  grid.innerHTML = html;
}

function renderAll(filter) {
  currentFilter = filter;
  applyFilters();
}

function onSearch(val) {
  currentSearch = val.trim();
  applyFilters();
}

document.getElementById('filters').addEventListener('click', e => {
  if (e.target.classList.contains('view-tab')) {
    document.querySelectorAll('.view-tab').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    var view = e.target.dataset.view;
    document.getElementById('cardGrid').style.display = view === 'list' ? '' : 'none';
    document.getElementById('bracketView').classList.toggle('visible', view === 'bracket');
    document.querySelectorAll('.filter-btn').forEach(b => b.style.display = view === 'bracket' ? 'none' : '');
    document.querySelectorAll('.filter-sep').forEach(b => b.style.display = view === 'bracket' ? 'none' : '');
    document.querySelector('.search-box').style.display = view === 'bracket' ? 'none' : '';
    if (view === 'bracket') renderBracket();
    return;
  }
  if (!e.target.classList.contains('filter-btn')) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  renderAll(e.target.dataset.filter);
});

renderStats();
renderAll('all');
</script>
</body>
</html>"""


DEPLOY_DIR = Path("deploy")


def generate():
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    data = build_match_data()
    data_json = json.dumps(data, ensure_ascii=False, indent=None)
    html_content = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    OUTPUT_FILE.write_text(html_content, encoding="utf-8")
    Path("index.html").write_text(html_content, encoding="utf-8")
    (DEPLOY_DIR / "index.html").write_text(html_content, encoding="utf-8")
    s = data["stats"]
    print(f"  Dashboard generated: {OUTPUT_FILE}")
    print(f"  {s['totalPredicted']} predictions, {s['completed']} completed")
    if s["brier"]:
        print(f"  Brier: {s['brier']:.3f} (odds: {s['oddsBrier']:.3f})")
    print(f"  Direction: {s['directionCorrect']}/{s['directionTotal']}")
    print(f"  Score hits: {s['scoreCorrect']}")


if __name__ == "__main__":
    generate()
