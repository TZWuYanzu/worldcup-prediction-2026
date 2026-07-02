---
description: "对阵前瞻：双方深度对比+xG+热身赛+关键对位。当用户提到「前瞻」「对阵」「preview」「对比」时使用。"
allowed-tools:
  - Bash
  - Read
  - WebFetch
---

# 对阵前瞻

对即将进行的特定比赛做深度双方对比分析。

## 解析用户意图

从 `$ARGUMENTS` 中提取：
- match_id（如 `73`）→ 从 match_data 获取双方
- 两个球队名（如 `法国 vs 德国` 或 `法国 德国`）→ 直接使用
- 单个球队名 → 找到该队下一场比赛

## 执行步骤

### Step 1: 确认对阵双方

```bash
python3 -c "
from match_data import GROUP_MATCHES, TEAM_CN
# 根据 match_id 或球队名找到比赛
mid = 目标match_id
m = GROUP_MATCHES[mid - 1]
t1cn = TEAM_CN.get(m.team1, m.team1)
t2cn = TEAM_CN.get(m.team2, m.team2)
print(f'M{m.match_id}: {t1cn}(主) vs {t2cn}(客) | {m.date_str} | {m.venue}')
"
```

### Step 2: 双方 xG 档案

对两队分别运行：
```bash
python3 xg_model.py team <team1>
python3 xg_model.py team <team2>
```

输出已包含从该队视角的比分和 W/D/L 标记（如 `1-2 (L)`），直接使用即可。

### Step 2.5: 数据交叉验证【必做】

**此步骤防止主客场比分混淆导致的分析错误。** 对两支球队分别运行以下脚本，自动从 `match_data.py` 生成球队事实卡：

```bash
python3 -c "
from match_data import ALL_MATCHES, TEAM_CN

team = '<team_english_name>'  # 替换为实际队名
for m in ALL_MATCHES:
    if not m.score:
        continue
    if m.team1 == team or m.team2 == team:
        is_home = m.team1 == team
        opp = m.team2 if is_home else m.team1
        parts = m.score.split('-')
        h, a = int(parts[0]), int(parts[1])
        gf, ga = (h, a) if is_home else (a, h)
        wdl = 'W' if gf > ga else ('D' if gf == ga else 'L')
        opp_cn = TEAM_CN.get(opp, opp)
        stage = f'{m.group}组' if m.group else m.stage
        print(f'  M{m.match_id}: {wdl} {gf}-{ga} vs {opp_cn} ({stage}) [{\"主\" if is_home else \"客\"}]')
"
```

**验证清单：**
1. W/D/L 记录是否与 xg_model.py 输出一致
2. 进球/失球总数是否吻合
3. 小组排名和积分是否正确（3分制：W=3, D=1, L=0）
4. 如果发现不一致，以 `match_data.py` 的数据为准（它存储的是经过验证的 home-away 比分）

**在撰写分析文本时，必须使用验证后的 W/D/L 和比分，不得直接从 xG 输出的原始比分推断胜负。**

### Step 3: 双方换人效果

```bash
python3 xg_model.py subs <team1>
python3 xg_model.py subs <team2>
```

### Step 4: 双方热身赛

用 WebFetch 分别获取两队的 Wikipedia 页面热身赛数据。

特别关注：
- 两队是否在热身赛中交过手
- 对共同对手的成绩对比
- 关键球员在热身赛中的状态

### Step 5: 赔率参考

```bash
python3 sporttery_odds.py fetch
```

### Step 6: 比分矩阵

```bash
python3 score_matrix.py predict <match_id>
```

### Step 6.5: 舟车劳顿对比【淘汰赛必做】

```bash
python3 travel_analysis.py <match_id>
```

对比双方旅途负担（距离、时区差、休息天数），评估体力不对称。

### Step 7: 综合对比分析

## 输出格式

```
================================================================
  M73 对阵前瞻: 法国 vs 德国
  2026-06-30 · 某球场
================================================================

  ┌─────────────────┬────────────────────┐
  │     法国         │        德国         │
  ├─────────────────┼────────────────────┤
  │ 小组赛 3场       │ 小组赛 3场          │
  │ xG: 5.97 (1.99) │ xG: 8.19 (2.73)   │
  │ xGA: 2.02(0.67) │ xGA: 6.28(2.09)   │
  │ xGD: +3.95      │ xGD: +1.91        │
  │ 进球: 9 (+3.03)  │ 进球: 10 (+1.81)  │
  │ 失球: 1          │ 失球: 3           │
  ├─────────────────┼────────────────────┤
  │ 热身赛 4场       │ 热身赛 3场          │
  │ 10-3 (3胜1平)   │ 7-2 (2胜1负)       │
  │ vs强队: 2胜      │ vs强队: 1负        │
  └─────────────────┴────────────────────┘

  关键对位:
  ─────────────────────────────────────
  1. Mbappé vs 德国右后卫 → [分析]
  2. Wirtz vs 法国中场线 → [分析]
  3. 定位球: 法国角球威胁 vs 德国头球优势

  分阶段 xG 匹配:
  ─────────────────────────────────────
  0-30':  法国 X.XX vs 德国 X.XX → [谁开局更强]
  30-45': ...
  46-60': ...
  60-90': ... → [谁尾盘更危险]

  舟车劳顿:
  ─────────────────────────────────────
  法国: 上场@波士顿 → 本场@纽约, 273km, 0h时区差, 休息5天 [低]
  德国: 上场@纽约 → 本场@纽约, 0km, 0h时区差, 休息5天 [低]
  → [双方接近 / XX方旅途负担更重]

  历史交手 / 共同对手:
  ─────────────────────────────────────
  热身赛: [如有直接交手]
  共同对手: vs XX队，法国Y-Z，德国Y-Z

  预测:
  ─────────────────────────────────────
  法国 XX% / 平 XX% / 德国 XX%
  预测比分: X-X
  关键变量: [决定比赛走向的1-2个因素]
================================================================
```

### 关键原则

- **交叉验证** — xG、热身赛、赔率三个数据源必须互证
- **关键对位优先** — 2-3组最重要的对位关系决定比赛走向
- **分阶段匹配** — 找出双方各在哪个时段最强/最弱
- **不做主观偏好** — 预测基于数据而非名气或情感
