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
    "TBD": "待定",
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
# Actual results (updated as matches are played)
# ---------------------------------------------------------------------------

_RESULTS: dict[int, str] = {
    # Group A – MD1 (June 11)
    1: "2-0",    # Mexico 2-0 South Africa
    2: "2-1",    # South Korea 2-1 Czech Republic
    # Group B – MD1 (June 12-13)
    7: "1-1",    # Canada 1-1 Bosnia and Herzegovina
    8: "1-1",    # Qatar 1-1 Switzerland
    # Group C – MD1 (June 13)
    13: "1-1",   # Brazil 1-1 Morocco
    14: "0-1",   # Haiti 0-1 Scotland
    # Group D – MD1 (June 12-13)
    19: "4-1",   # United States 4-1 Paraguay
    20: "2-0",   # Australia 2-0 Turkey
    # Group E – MD1 (June 14)
    25: "7-1",   # Germany 7-1 Curaçao
    26: "1-0",   # Ivory Coast 1-0 Ecuador
    # Group F – MD1 (June 14)
    31: "2-2",   # Netherlands 2-2 Japan
    32: "5-1",   # Sweden 5-1 Tunisia
    # Group G – MD1 (June 15)
    37: "1-1",   # Belgium 1-1 Egypt
    38: "2-2",   # Iran 2-2 New Zealand
    # Group H – MD1 (June 15)
    43: "0-0",   # Spain 0-0 Cape Verde
    44: "1-1",   # Saudi Arabia 1-1 Uruguay
    # Group I – MD1 (June 16)
    49: "3-1",   # France 3-1 Senegal
    50: "1-4",   # Iraq 1-4 Norway
    # Group J – MD1 (June 17)
    55: "3-0",   # Argentina 3-0 Algeria
    56: "3-1",   # Austria 3-1 Jordan
    # Group K – MD1 (June 17-18)
    61: "1-1",   # Portugal 1-1 DR Congo
    62: "1-3",   # Uzbekistan 1-3 Colombia
    # Group L – MD1 (June 17)
    67: "4-2",   # England 4-2 Croatia
    68: "1-0",   # Ghana 1-0 Panama
    # Group A – MD2 (June 18-19)
    3: "1-1",    # Czech Republic 1-1 South Africa
    4: "1-0",    # Mexico 1-0 South Korea
    # Group B – MD2 (June 18)
    9: "4-1",    # Switzerland 4-1 Bosnia and Herzegovina
    10: "6-0",   # Canada 6-0 Qatar
    # Group C – MD2 (June 19-20)
    15: "0-1",   # Scotland 0-1 Morocco
    16: "3-0",   # Brazil 3-0 Haiti
    # Group D – MD2 (June 19-20)
    21: "2-0",   # United States 2-0 Australia
    22: "0-1",   # Turkey 0-1 Paraguay
    # Group E – MD2 (June 20-21)
    27: "2-1",   # Germany 2-1 Ivory Coast
    28: "0-0",   # Ecuador 0-0 Curaçao
    # Group F – MD2 (June 20-21)
    33: "5-1",   # Netherlands 5-1 Sweden
    34: "0-4",   # Tunisia 0-4 Japan
    # Group G – MD2 (June 21-22)
    39: "0-0",   # Belgium 0-0 Iran
    40: "1-3",   # New Zealand 1-3 Egypt
    # Group H – MD2 (June 21-22)
    45: "4-0",   # Spain 4-0 Saudi Arabia
    46: "2-2",   # Uruguay 2-2 Cape Verde
    # Group I – MD2 (June 22-23)
    51: "3-0",   # France 3-0 Iraq
    52: "3-2",   # Norway 3-2 Senegal
    # Group J – MD2 (June 22-23)
    57: "2-0",   # Argentina 2-0 Austria
    58: "1-2",   # Jordan 1-2 Algeria
    # Group K – MD2 (June 23-24)
    63: "5-0",   # Portugal 5-0 Uzbekistan
    64: "1-0",   # Colombia 1-0 DR Congo
    # Group L – MD2 (June 23)
    69: "0-0",   # England 0-0 Ghana
    70: "0-1",   # Panama 0-1 Croatia
    # Group B – MD3 (June 24-25)
    11: "2-1",   # Switzerland 2-1 Canada
    12: "3-1",   # Bosnia and Herzegovina 3-1 Qatar
    # Group C – MD3 (June 24-25)
    17: "0-3",   # Scotland 0-3 Brazil
    18: "4-2",   # Morocco 4-2 Haiti
    # Group A – MD3 (June 25)
    5: "0-3",    # Czech Republic 0-3 Mexico
    6: "1-0",    # South Africa 1-0 South Korea
    # Group D – MD3 (June 26)
    23: "3-2",   # Turkey 3-2 United States
    24: "0-0",   # Paraguay 0-0 Australia
    # Group E – MD3 (June 25)
    29: "0-2",   # Curaçao 0-2 Ivory Coast
    30: "2-1",   # Ecuador 2-1 Germany
    # Group F – MD3 (June 25)
    35: "1-1",   # Japan 1-1 Sweden
    36: "1-3",   # Tunisia 1-3 Netherlands
    # Group I – MD3 (June 26)
    53: "1-4",   # Norway 1-4 France
    54: "5-0",   # Senegal 5-0 Iraq
    # Group G – MD3 (June 27)
    41: "1-1",   # Egypt 1-1 Iran
    42: "1-5",   # New Zealand 1-5 Belgium
    # Group H – MD3 (June 27)
    47: "0-0",   # Cape Verde 0-0 Saudi Arabia
    48: "0-1",   # Uruguay 0-1 Spain
    # Group K – MD3 (June 27)
    65: "0-0",   # Colombia 0-0 Portugal
    66: "3-1",   # DR Congo 3-1 Uzbekistan
    # Group L – MD3 (June 27)
    71: "0-2",   # Panama 0-2 England
    72: "2-1",   # Croatia 2-1 Ghana
    # Group J – MD3 (June 28)
    59: "3-3",   # Algeria 3-3 Austria
    60: "1-3",   # Jordan 1-3 Argentina
}

for _mid, _score in _RESULTS.items():
    GROUP_MATCHES[_mid - 1].score = _score

# ---------------------------------------------------------------------------
# Knockout stage — Round of 32
# ---------------------------------------------------------------------------

KNOCKOUT_MATCHES: list[Match] = [
    Match(match_id=73, stage="R32", group=None, date_str="2026-06-29",
          utc_hour=19, utc_min=0, team1="South Africa", team2="Canada",
          venue="BC Place, Vancouver"),
    Match(match_id=74, stage="R32", group=None, date_str="2026-06-30",
          utc_hour=17, utc_min=0, team1="Brazil", team2="Japan",
          venue="AT&T Stadium, Dallas"),
    Match(match_id=75, stage="R32", group=None, date_str="2026-06-30",
          utc_hour=20, utc_min=30, team1="Germany", team2="Paraguay",
          venue="Hard Rock Stadium, Miami"),
    Match(match_id=76, stage="R32", group=None, date_str="2026-06-30",
          utc_hour=1, utc_min=0, team1="Netherlands", team2="Morocco",
          venue="Lincoln Financial Field, Philadelphia"),
    Match(match_id=77, stage="R32", group=None, date_str="2026-07-01",
          utc_hour=17, utc_min=0, team1="Ivory Coast", team2="Norway",
          venue="Mercedes-Benz Stadium, Atlanta"),
    Match(match_id=78, stage="R32", group=None, date_str="2026-07-01",
          utc_hour=21, utc_min=0, team1="France", team2="Sweden",
          venue="MetLife Stadium, New York/New Jersey"),
    Match(match_id=79, stage="R32", group=None, date_str="2026-07-01",
          utc_hour=1, utc_min=0, team1="Mexico", team2="Ecuador",
          venue="Estadio Azteca, Mexico City"),
    Match(match_id=80, stage="R32", group=None, date_str="2026-07-02",
          utc_hour=16, utc_min=0, team1="England", team2="DR Congo",
          venue="Lumen Field, Seattle"),
    Match(match_id=81, stage="R32", group=None, date_str="2026-07-02",
          utc_hour=20, utc_min=0, team1="Belgium", team2="Senegal",
          venue="NRG Stadium, Houston"),
    Match(match_id=82, stage="R32", group=None, date_str="2026-07-02",
          utc_hour=0, utc_min=0, team1="United States", team2="Bosnia and Herzegovina",
          venue="SoFi Stadium, Los Angeles"),
    Match(match_id=83, stage="R32", group=None, date_str="2026-07-03",
          utc_hour=19, utc_min=0, team1="Spain", team2="Austria",
          venue="Gillette Stadium, Boston"),
    Match(match_id=84, stage="R32", group=None, date_str="2026-07-03",
          utc_hour=23, utc_min=0, team1="Portugal", team2="Croatia",
          venue="MetLife Stadium, New York/New Jersey"),
    Match(match_id=85, stage="R32", group=None, date_str="2026-07-03",
          utc_hour=3, utc_min=0, team1="Switzerland", team2="Algeria",
          venue="BMO Field, Toronto"),
    Match(match_id=86, stage="R32", group=None, date_str="2026-07-04",
          utc_hour=18, utc_min=0, team1="Australia", team2="Egypt",
          venue="Levi's Stadium, San Francisco"),
    Match(match_id=87, stage="R32", group=None, date_str="2026-07-04",
          utc_hour=22, utc_min=0, team1="Argentina", team2="Cape Verde",
          venue="Hard Rock Stadium, Miami"),
    Match(match_id=88, stage="R32", group=None, date_str="2026-07-04",
          utc_hour=1, utc_min=30, team1="Colombia", team2="Ghana",
          venue="Mercedes-Benz Stadium, Atlanta"),
    # --- Round of 16 ---
    Match(match_id=89, stage="R16", group=None, date_str="2026-07-05",
          utc_hour=17, utc_min=0, team1="Paraguay", team2="France",
          venue="Lincoln Financial Field, Philadelphia"),
    Match(match_id=90, stage="R16", group=None, date_str="2026-07-05",
          utc_hour=21, utc_min=0, team1="Canada", team2="Morocco",
          venue="NRG Stadium, Houston"),
    Match(match_id=91, stage="R16", group=None, date_str="2026-07-06",
          utc_hour=17, utc_min=0, team1="Brazil", team2="Norway",
          venue="MetLife Stadium, New York/New Jersey"),
    Match(match_id=92, stage="R16", group=None, date_str="2026-07-06",
          utc_hour=21, utc_min=0, team1="Mexico", team2="England",
          venue="Estadio Azteca, Mexico City"),
    Match(match_id=93, stage="R16", group=None, date_str="2026-07-07",
          utc_hour=17, utc_min=0, team1="Portugal", team2="Spain",
          venue="AT&T Stadium, Dallas"),
    Match(match_id=94, stage="R16", group=None, date_str="2026-07-07",
          utc_hour=21, utc_min=0, team1="United States", team2="Belgium",
          venue="Lumen Field, Seattle"),
    Match(match_id=95, stage="R16", group=None, date_str="2026-07-08",
          utc_hour=17, utc_min=0, team1="TBD", team2="TBD",
          venue="Mercedes-Benz Stadium, Atlanta"),
    Match(match_id=96, stage="R16", group=None, date_str="2026-07-08",
          utc_hour=21, utc_min=0, team1="Switzerland", team2="TBD",
          venue="BC Place, Vancouver"),
    # --- Quarter-finals ---
    Match(match_id=97, stage="QF", group=None, date_str="2026-07-10",
          utc_hour=21, utc_min=0, team1="TBD", team2="TBD",
          venue="Gillette Stadium, Boston"),
    Match(match_id=98, stage="QF", group=None, date_str="2026-07-11",
          utc_hour=1, utc_min=0, team1="TBD", team2="TBD",
          venue="SoFi Stadium, Los Angeles"),
    Match(match_id=99, stage="QF", group=None, date_str="2026-07-12",
          utc_hour=17, utc_min=0, team1="TBD", team2="TBD",
          venue="Hard Rock Stadium, Miami"),
    Match(match_id=100, stage="QF", group=None, date_str="2026-07-12",
          utc_hour=21, utc_min=0, team1="TBD", team2="TBD",
          venue="Arrowhead Stadium, Kansas City"),
    # --- Semi-finals ---
    Match(match_id=101, stage="SF", group=None, date_str="2026-07-15",
          utc_hour=0, utc_min=0, team1="TBD", team2="TBD",
          venue="AT&T Stadium, Dallas"),
    Match(match_id=102, stage="SF", group=None, date_str="2026-07-16",
          utc_hour=0, utc_min=0, team1="TBD", team2="TBD",
          venue="Mercedes-Benz Stadium, Atlanta"),
    # --- Third-place & Final ---
    Match(match_id=103, stage="3rd", group=None, date_str="2026-07-19",
          utc_hour=21, utc_min=0, team1="TBD", team2="TBD",
          venue="Hard Rock Stadium, Miami"),
    Match(match_id=104, stage="F", group=None, date_str="2026-07-20",
          utc_hour=20, utc_min=0, team1="TBD", team2="TBD",
          venue="MetLife Stadium, New York/New Jersey"),
]

_KNOCKOUT_RESULTS: dict[int, str] = {
    73: "0-1",   # South Africa 0-1 Canada
    74: "2-1",   # Brazil 2-1 Japan
    75: "1-1 (aet 3-4)",  # Germany 1-1 Paraguay (90'), Paraguay wins 3-4 aet
    76: "1-1 (aet 2-3)",  # Netherlands 1-1 Morocco (90'), Morocco wins 3-2 aet
    77: "1-2",   # Ivory Coast 1-2 Norway
    78: "3-0",   # France 3-0 Sweden
    79: "2-0",   # Mexico 2-0 Ecuador
    80: "2-1",   # England 2-1 DR Congo
    81: "2-2 (aet 3-2)",  # Belgium 2-2 Senegal (90'), Belgium wins 3-2 aet
    82: "2-0",   # United States 2-0 Bosnia
    83: "3-0",   # Spain 3-0 Austria
    84: "2-1",   # Portugal 2-1 Croatia
    85: "2-0",   # Switzerland 2-0 Algeria
    86: "1-1 (pen 2-4)",  # Australia 1-1 Egypt (90'+aet), Egypt wins 4-2 pen
    87: "3-2 (aet)",      # Argentina 3-2 Cape Verde (aet)
    88: "1-0",            # Colombia 1-0 Ghana
    89: "0-1",            # Paraguay 0-1 France
    90: "0-3",            # Canada 0-3 Morocco
}

_ko_by_id = {m.match_id: m for m in KNOCKOUT_MATCHES}
for _mid, _score in _KNOCKOUT_RESULTS.items():
    _ko_by_id[_mid].score = _score

ALL_MATCHES: list[Match] = GROUP_MATCHES + KNOCKOUT_MATCHES
MATCH_BY_ID: dict[int, Match] = {m.match_id: m for m in ALL_MATCHES}
