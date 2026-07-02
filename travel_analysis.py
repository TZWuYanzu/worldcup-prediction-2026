"""Travel fatigue analysis for 2026 FIFA World Cup knockout stage.

Calculates travel distance, timezone change, and rest days between
a team's last match and their upcoming match.
"""

import math
from match_data import ALL_MATCHES, TEAM_CN

# ---------------------------------------------------------------------------
# Venue coordinates (lat, lon) and UTC offset
# Keyed by stadium name prefix (before the comma) to handle city name variants
# ---------------------------------------------------------------------------

VENUE_INFO: dict[str, tuple[float, float, int]] = {
    # (latitude, longitude, UTC_offset_hours)
    # Mexico
    "Estadio Azteca":           (19.303, -99.150, -6),
    "Estadio Akron":            (20.680, -103.462, -6),
    "Estadio BBVA":             (25.669, -100.246, -6),
    # Canada
    "BC Place":                 (49.277, -123.110, -7),
    "BMO Field":                (43.633, -79.418, -4),
    # US - West
    "SoFi Stadium":             (33.953, -118.339, -7),
    "Levi's Stadium":           (37.403, -121.970, -7),
    "Lumen Field":              (47.595, -122.332, -7),
    # US - Central
    "AT&T Stadium":             (32.748, -97.093, -5),
    "NRG Stadium":              (29.685, -95.411, -5),
    "Arrowhead Stadium":        (39.049, -94.484, -5),
    # US - East
    "MetLife Stadium":          (40.813, -74.074, -4),
    "Gillette Stadium":         (42.091, -71.264, -4),
    "Lincoln Financial Field":  (39.901, -75.167, -4),
    "Hard Rock Stadium":        (25.958, -80.239, -4),
    "Mercedes-Benz Stadium":    (33.755, -84.401, -4),
}


def _stadium_key(venue: str) -> str:
    return venue.split(",")[0].strip()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def get_venue_info(venue: str):
    key = _stadium_key(venue)
    return VENUE_INFO.get(key)


def travel_between(venue1: str, venue2: str) -> dict:
    info1 = get_venue_info(venue1)
    info2 = get_venue_info(venue2)
    if not info1 or not info2:
        return {"distance_km": None, "tz_change": None}
    dist = _haversine_km(info1[0], info1[1], info2[0], info2[1])
    tz = abs(info2[2] - info1[2])
    return {"distance_km": dist, "tz_change": tz}


def team_travel_report(team: str, upcoming_match_id: int) -> dict | None:
    """Compute travel burden for a team heading into a specific match.

    Returns dict with:
      - last_match: id of their most recent completed match
      - last_venue, next_venue: venue names
      - distance_km: straight-line km between venues
      - tz_change: timezone hour difference
      - rest_days: calendar days between last match and upcoming match
      - fatigue_rating: "低"/"中"/"高" qualitative rating
    """
    upcoming = None
    for m in ALL_MATCHES:
        if m.match_id == upcoming_match_id:
            upcoming = m
            break
    if not upcoming:
        return None

    played = [m for m in ALL_MATCHES
              if m.score and (m.team1 == team or m.team2 == team)]
    if not played:
        return None

    last = max(played, key=lambda m: (m.date_str, m.match_id))

    travel = travel_between(last.venue, upcoming.venue)
    dist = travel["distance_km"]
    tz = travel["tz_change"]

    from datetime import date
    d1 = date.fromisoformat(last.date_str)
    d2 = date.fromisoformat(upcoming.date_str)
    rest = (d2 - d1).days

    rating = _fatigue_rating(dist, tz, rest)

    return {
        "team": team,
        "team_cn": TEAM_CN.get(team, team),
        "last_match_id": last.match_id,
        "last_venue": last.venue,
        "next_venue": upcoming.venue,
        "distance_km": dist,
        "tz_change": tz,
        "rest_days": rest,
        "fatigue_rating": rating,
    }


def _fatigue_rating(dist_km: int | None, tz_change: int | None, rest_days: int) -> str:
    if dist_km is None:
        return "未知"
    score = 0
    if dist_km > 3000:
        score += 3
    elif dist_km > 1500:
        score += 2
    elif dist_km > 500:
        score += 1

    if tz_change and tz_change >= 3:
        score += 2
    elif tz_change and tz_change >= 1:
        score += 1

    if rest_days <= 2:
        score += 2
    elif rest_days <= 3:
        score += 1

    if score >= 4:
        return "高"
    elif score >= 2:
        return "中"
    return "低"


def compare_travel(match_id: int) -> str:
    """Print a formatted comparison of travel burden for both teams in a match."""
    m = None
    for match in ALL_MATCHES:
        if match.match_id == match_id:
            m = match
            break
    if not m:
        return f"Match {match_id} not found"

    r1 = team_travel_report(m.team1, match_id)
    r2 = team_travel_report(m.team2, match_id)

    lines = [f"M{match_id} 舟车劳顿对比: {TEAM_CN.get(m.team1, m.team1)} vs {TEAM_CN.get(m.team2, m.team2)}",
             "─" * 50]

    for r in [r1, r2]:
        if not r:
            continue
        lines.append(f"  {r['team_cn']}:")
        lines.append(f"    上场: M{r['last_match_id']} @ {r['last_venue']}")
        lines.append(f"    本场: @ {r['next_venue']}")
        if r["distance_km"] is not None:
            lines.append(f"    距离: {r['distance_km']:,} km | 时区差: {r['tz_change']}h | 休息: {r['rest_days']}天")
        lines.append(f"    疲劳评级: {r['fatigue_rating']}")
        lines.append("")

    if r1 and r2 and r1["distance_km"] is not None and r2["distance_km"] is not None:
        diff = r1["distance_km"] - r2["distance_km"]
        if abs(diff) > 500:
            worse = r1["team_cn"] if diff > 0 else r2["team_cn"]
            lines.append(f"  ⚠ {worse} 多飞 {abs(diff):,} km，旅途负担更重")
        else:
            lines.append(f"  ≈ 双方旅途负担接近")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 travel_analysis.py <match_id> [match_id ...]")
        print("       python3 travel_analysis.py all  — all unplayed knockout matches")
        sys.exit(1)

    if sys.argv[1] == "all":
        ids = [m.match_id for m in ALL_MATCHES if m.stage != "group" and not m.score]
    else:
        ids = [int(x) for x in sys.argv[1:]]

    for mid in ids:
        print(compare_travel(mid))
        print()
