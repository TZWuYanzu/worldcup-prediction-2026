"""Historical World Cup knockout stage data (2018 + 2022) for calibration."""

# Each entry: (round, team1, team2, score_90min, aet, penalties, favorite)
# score_90min = score at end of regular time (90' + stoppage)
# favorite = which team was generally considered the favorite ("team1", "team2", or "even")

DATA_2018 = [
    # Round of 16
    ("R16", "France", "Argentina", "4-3", False, False, "even"),
    ("R16", "Uruguay", "Portugal", "2-1", False, False, "even"),
    ("R16", "Spain", "Russia", "1-1", True, True, "team1"),
    ("R16", "Croatia", "Denmark", "1-1", True, True, "team1"),
    ("R16", "Brazil", "Mexico", "2-0", False, False, "team1"),
    ("R16", "Belgium", "Japan", "3-2", False, False, "team1"),
    ("R16", "Sweden", "Switzerland", "1-0", False, False, "even"),
    ("R16", "Colombia", "England", "1-1", True, True, "team2"),
    # Quarter-finals
    ("QF", "Uruguay", "France", "0-2", False, False, "team2"),
    ("QF", "Brazil", "Belgium", "1-2", False, False, "team1"),
    ("QF", "Sweden", "England", "0-2", False, False, "team2"),
    ("QF", "Russia", "Croatia", "2-2", True, True, "team2"),
    # Semi-finals
    ("SF", "France", "Belgium", "1-0", False, False, "even"),
    ("SF", "Croatia", "England", "1-1", True, False, "team2"),
    # Third place
    ("3rd", "Belgium", "England", "2-0", False, False, "even"),
    # Final
    ("F", "France", "Croatia", "4-2", False, False, "team1"),
]

DATA_2022 = [
    # Round of 16
    ("R16", "Netherlands", "United States", "3-1", False, False, "team1"),
    ("R16", "Argentina", "Australia", "2-1", False, False, "team1"),
    ("R16", "France", "Poland", "3-1", False, False, "team1"),
    ("R16", "England", "Senegal", "3-0", False, False, "team1"),
    ("R16", "Japan", "Croatia", "1-1", True, True, "team2"),
    ("R16", "Brazil", "South Korea", "4-1", False, False, "team1"),
    ("R16", "Morocco", "Spain", "0-0", True, True, "team2"),
    ("R16", "Portugal", "Switzerland", "6-1", False, False, "team1"),
    # Quarter-finals
    ("QF", "Croatia", "Brazil", "0-0", True, True, "team2"),  # 0-0 at 90', goals in ET
    ("QF", "Netherlands", "Argentina", "2-2", True, True, "team2"),
    ("QF", "Morocco", "Portugal", "1-0", False, False, "team2"),
    ("QF", "England", "France", "1-2", False, False, "even"),
    # Semi-finals
    ("SF", "Argentina", "Croatia", "3-0", False, False, "team1"),
    ("SF", "France", "Morocco", "2-0", False, False, "team1"),
    # Third place
    ("3rd", "Croatia", "Morocco", "2-1", False, False, "even"),
    # Final
    ("F", "Argentina", "France", "2-2", True, True, "even"),
]

ALL_DATA = DATA_2018 + DATA_2022
