"""2026 FIFA World Cup match data and team name resolution."""

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Match dataclass
# ---------------------------------------------------------------------------

@dataclass
class Match:
    match_id: int
    stage: str                          # "group", "R32", "R16", "QF", "SF", "3rd", "F"
    group: Optional[str]                # "A"-"L" for group stage, None for knockout
    date_str: str                       # UTC date "2026-06-DD"
    utc_hour: int
    utc_min: int
    team1: str                          # English canonical name
    team2: str
    venue: str
    score: Optional[str] = None         # e.g. "2-1", "1-1 (4-3 pen)"
    calendar_event_uid: Optional[str] = None

# ---------------------------------------------------------------------------
# Team name mapping (48 teams, English -> Chinese)
# ---------------------------------------------------------------------------

TEAM_CN: dict[str, str] = {
    "Mexico": "墨西哥", "South Africa": "南非", "South Korea": "韩国",
    "Czech Republic": "捷克", "Canada": "加拿大", "Bosnia and Herzegovina": "波黑",
    "Qatar": "卡塔尔", "Switzerland": "瑞士", "Brazil": "巴西",
    "Morocco": "摩洛哥", "Haiti": "海地", "Scotland": "苏格兰",
    "United States": "美国", "Paraguay": "巴拉圭", "Australia": "澳大利亚",
    "Turkey": "土耳其", "Germany": "德国", "Curaçao": "库拉索",
    "Ivory Coast": "科特迪瓦", "Ecuador": "厄瓜多尔", "Netherlands": "荷兰",
    "Japan": "日本", "Sweden": "瑞典", "Tunisia": "突尼斯",
    "Belgium": "比利时", "Egypt": "埃及", "Iran": "伊朗",
    "New Zealand": "新西兰", "Spain": "西班牙", "Cape Verde": "佛得角",
    "Saudi Arabia": "沙特", "Uruguay": "乌拉圭", "France": "法国",
    "Senegal": "塞内加尔", "Iraq": "伊拉克", "Norway": "挪威",
    "Argentina": "阿根廷", "Algeria": "阿尔及利亚", "Austria": "奥地利",
    "Jordan": "约旦", "Portugal": "葡萄牙", "DR Congo": "刚果(金)",
    "Uzbekistan": "乌兹别克", "Colombia": "哥伦比亚", "England": "英格兰",
    "Croatia": "克罗地亚", "Ghana": "加纳", "Panama": "巴拿马",
}

CN_TO_EN: dict[str, str] = {v: k for k, v in TEAM_CN.items()}

# Default "other hot" teams (yellow tier)
DEFAULT_HOT_TEAMS: set[str] = {
    "Argentina", "Brazil", "Portugal", "Netherlands", "Japan", "Morocco",
}

# ---------------------------------------------------------------------------
# Team name resolution
# ---------------------------------------------------------------------------

def resolve_team_name(name: str) -> Optional[str]:
    """Accept Chinese or English (case-insensitive), return canonical English name or None."""
    name = name.strip()
    if name in TEAM_CN:
        return name
    if name in CN_TO_EN:
        return CN_TO_EN[name]
    lower = name.lower()
    for en in TEAM_CN:
        if en.lower() == lower:
            return en
    return None


def get_all_team_names() -> list[tuple[str, str]]:
    """Return [(english, chinese), ...] sorted by English name."""
    return sorted(TEAM_CN.items(), key=lambda x: x[0])

# ---------------------------------------------------------------------------
# Group stage matches (72 matches, match_id 1-72)
# ---------------------------------------------------------------------------

_RAW_MATCHES = [
    # Group A
    ("A", "2026-06-11", 19, 0, "Mexico", "South Africa", "Estadio Azteca, Mexico City"),
    ("A", "2026-06-12", 2, 0, "South Korea", "Czech Republic", "Estadio Akron, Zapopan"),
    ("A", "2026-06-18", 16, 0, "Czech Republic", "South Africa", "Mercedes-Benz Stadium, Atlanta"),
    ("A", "2026-06-19", 1, 0, "Mexico", "South Korea", "Estadio Akron, Zapopan"),
    ("A", "2026-06-25", 1, 0, "Czech Republic", "Mexico", "Estadio Azteca, Mexico City"),
    ("A", "2026-06-25", 1, 0, "South Africa", "South Korea", "Estadio BBVA, Guadalupe"),
    # Group B
    ("B", "2026-06-12", 19, 0, "Canada", "Bosnia and Herzegovina", "BMO Field, Toronto"),
    ("B", "2026-06-13", 19, 0, "Qatar", "Switzerland", "Levi's Stadium, Santa Clara"),
    ("B", "2026-06-18", 19, 0, "Switzerland", "Bosnia and Herzegovina", "SoFi Stadium, Inglewood"),
    ("B", "2026-06-18", 22, 0, "Canada", "Qatar", "BC Place, Vancouver"),
    ("B", "2026-06-24", 19, 0, "Switzerland", "Canada", "BC Place, Vancouver"),
    ("B", "2026-06-24", 19, 0, "Bosnia and Herzegovina", "Qatar", "Lumen Field, Seattle"),
    # Group C
    ("C", "2026-06-13", 22, 0, "Brazil", "Morocco", "MetLife Stadium, East Rutherford"),
    ("C", "2026-06-14", 1, 0, "Haiti", "Scotland", "Gillette Stadium, Foxborough"),
    ("C", "2026-06-19", 22, 0, "Scotland", "Morocco", "Gillette Stadium, Foxborough"),
    ("C", "2026-06-20", 0, 30, "Brazil", "Haiti", "Lincoln Financial Field, Philadelphia"),
    ("C", "2026-06-24", 22, 0, "Scotland", "Brazil", "Hard Rock Stadium, Miami Gardens"),
    ("C", "2026-06-24", 22, 0, "Morocco", "Haiti", "Mercedes-Benz Stadium, Atlanta"),
    # Group D
    ("D", "2026-06-13", 1, 0, "United States", "Paraguay", "SoFi Stadium, Inglewood"),
    ("D", "2026-06-14", 4, 0, "Australia", "Turkey", "BC Place, Vancouver"),
    ("D", "2026-06-19", 19, 0, "United States", "Australia", "Lumen Field, Seattle"),
    ("D", "2026-06-20", 3, 0, "Turkey", "Paraguay", "Levi's Stadium, Santa Clara"),
    ("D", "2026-06-26", 2, 0, "Turkey", "United States", "SoFi Stadium, Inglewood"),
    ("D", "2026-06-26", 2, 0, "Paraguay", "Australia", "Levi's Stadium, Santa Clara"),
    # Group E
    ("E", "2026-06-14", 17, 0, "Germany", "Curaçao", "NRG Stadium, Houston"),
    ("E", "2026-06-14", 23, 0, "Ivory Coast", "Ecuador", "Lincoln Financial Field, Philadelphia"),
    ("E", "2026-06-20", 20, 0, "Germany", "Ivory Coast", "BMO Field, Toronto"),
    ("E", "2026-06-21", 0, 0, "Ecuador", "Curaçao", "Arrowhead Stadium, Kansas City"),
    ("E", "2026-06-25", 20, 0, "Curaçao", "Ivory Coast", "Lincoln Financial Field, Philadelphia"),
    ("E", "2026-06-25", 20, 0, "Ecuador", "Germany", "MetLife Stadium, East Rutherford"),
    # Group F
    ("F", "2026-06-14", 20, 0, "Netherlands", "Japan", "AT&T Stadium, Arlington"),
    ("F", "2026-06-15", 2, 0, "Sweden", "Tunisia", "Estadio BBVA, Guadalupe"),
    ("F", "2026-06-20", 17, 0, "Netherlands", "Sweden", "NRG Stadium, Houston"),
    ("F", "2026-06-21", 4, 0, "Tunisia", "Japan", "Estadio BBVA, Guadalupe"),
    ("F", "2026-06-25", 23, 0, "Japan", "Sweden", "AT&T Stadium, Arlington"),
    ("F", "2026-06-25", 23, 0, "Tunisia", "Netherlands", "Arrowhead Stadium, Kansas City"),
    # Group G
    ("G", "2026-06-15", 19, 0, "Belgium", "Egypt", "Lumen Field, Seattle"),
    ("G", "2026-06-16", 1, 0, "Iran", "New Zealand", "SoFi Stadium, Inglewood"),
    ("G", "2026-06-21", 19, 0, "Belgium", "Iran", "SoFi Stadium, Inglewood"),
    ("G", "2026-06-22", 1, 0, "New Zealand", "Egypt", "BC Place, Vancouver"),
    ("G", "2026-06-27", 3, 0, "Egypt", "Iran", "Lumen Field, Seattle"),
    ("G", "2026-06-27", 3, 0, "New Zealand", "Belgium", "BC Place, Vancouver"),
    # Group H
    ("H", "2026-06-15", 16, 0, "Spain", "Cape Verde", "Mercedes-Benz Stadium, Atlanta"),
    ("H", "2026-06-15", 22, 0, "Saudi Arabia", "Uruguay", "Hard Rock Stadium, Miami Gardens"),
    ("H", "2026-06-21", 16, 0, "Spain", "Saudi Arabia", "Mercedes-Benz Stadium, Atlanta"),
    ("H", "2026-06-21", 22, 0, "Uruguay", "Cape Verde", "Hard Rock Stadium, Miami Gardens"),
    ("H", "2026-06-27", 0, 0, "Cape Verde", "Saudi Arabia", "NRG Stadium, Houston"),
    ("H", "2026-06-27", 0, 0, "Uruguay", "Spain", "Estadio Akron, Zapopan"),
    # Group I
    ("I", "2026-06-16", 19, 0, "France", "Senegal", "MetLife Stadium, East Rutherford"),
    ("I", "2026-06-16", 22, 0, "Iraq", "Norway", "Gillette Stadium, Foxborough"),
    ("I", "2026-06-22", 21, 0, "France", "Iraq", "Lincoln Financial Field, Philadelphia"),
    ("I", "2026-06-23", 0, 0, "Norway", "Senegal", "MetLife Stadium, East Rutherford"),
    ("I", "2026-06-26", 19, 0, "Norway", "France", "Gillette Stadium, Foxborough"),
    ("I", "2026-06-26", 19, 0, "Senegal", "Iraq", "BMO Field, Toronto"),
    # Group J
    ("J", "2026-06-17", 1, 0, "Argentina", "Algeria", "Arrowhead Stadium, Kansas City"),
    ("J", "2026-06-17", 4, 0, "Austria", "Jordan", "Levi's Stadium, Santa Clara"),
    ("J", "2026-06-22", 17, 0, "Argentina", "Austria", "AT&T Stadium, Arlington"),
    ("J", "2026-06-23", 3, 0, "Jordan", "Algeria", "Levi's Stadium, Santa Clara"),
    ("J", "2026-06-28", 2, 0, "Algeria", "Austria", "Arrowhead Stadium, Kansas City"),
    ("J", "2026-06-28", 2, 0, "Jordan", "Argentina", "AT&T Stadium, Arlington"),
    # Group K
    ("K", "2026-06-17", 17, 0, "Portugal", "DR Congo", "NRG Stadium, Houston"),
    ("K", "2026-06-18", 2, 0, "Uzbekistan", "Colombia", "Estadio Azteca, Mexico City"),
    ("K", "2026-06-23", 17, 0, "Portugal", "Uzbekistan", "NRG Stadium, Houston"),
    ("K", "2026-06-24", 2, 0, "Colombia", "DR Congo", "Estadio Akron, Zapopan"),
    ("K", "2026-06-27", 23, 30, "Colombia", "Portugal", "Hard Rock Stadium, Miami Gardens"),
    ("K", "2026-06-27", 23, 30, "DR Congo", "Uzbekistan", "Mercedes-Benz Stadium, Atlanta"),
    # Group L
    ("L", "2026-06-17", 20, 0, "England", "Croatia", "AT&T Stadium, Arlington"),
    ("L", "2026-06-17", 23, 0, "Ghana", "Panama", "BMO Field, Toronto"),
    ("L", "2026-06-23", 20, 0, "England", "Ghana", "Gillette Stadium, Foxborough"),
    ("L", "2026-06-23", 23, 0, "Panama", "Croatia", "BMO Field, Toronto"),
    ("L", "2026-06-27", 21, 0, "Panama", "England", "MetLife Stadium, East Rutherford"),
    ("L", "2026-06-27", 21, 0, "Croatia", "Ghana", "Lincoln Financial Field, Philadelphia"),
]

GROUP_MATCHES: list[Match] = [
    Match(
        match_id=i + 1,
        stage="group",
        group=row[0],
        date_str=row[1],
        utc_hour=row[2],
        utc_min=row[3],
        team1=row[4],
        team2=row[5],
        venue=row[6],
    )
    for i, row in enumerate(_RAW_MATCHES)
]

# ---------------------------------------------------------------------------
# Knockout stage templates (STUB for future use)
# ---------------------------------------------------------------------------

KNOCKOUT_TEMPLATES: list[Match] = []
# Will be populated with Match objects like:
# Match(match_id=73, stage="R32", group=None, date_str="2026-06-28",
#       utc_hour=..., team1="A1", team2="C2/D2/E2", venue="...")
# team1/team2 use placeholder codes (e.g. "A1" = Group A winner)
# until update-bracket resolves them to actual team names.
