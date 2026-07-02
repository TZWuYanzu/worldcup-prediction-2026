---
description: "预测指定日期的比赛：xG+热身赛+赔率+比分矩阵。当用户提到「预测」「明天」「predict」「tomorrow」时使用。"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - WebFetch
---

# 比赛预测

对指定日期的待赛比赛进行完整预测，综合小组赛xG、热身赛数据、赔率分析生成概率和比分。

## 解析用户意图

从 `$ARGUMENTS` 中提取：
- 无参数 → 默认**明天**的比赛
- `6-29` 或 `06-29` 或 `2026-06-29` → 指定日期
- `今天` / `today` → 当天
- `明天` / `tomorrow` → 明天
- match_id（如 `73 74`）→ 直接预测指定比赛

## 执行步骤

### Step 1: 确定预测范围

```bash
python3 -c "
from match_data import ALL_MATCHES, MATCH_BY_ID, TEAM_CN
target = '目标日期'
matches = [m for m in ALL_MATCHES if m.date_str == target and not m.score]
for m in matches:
    t1cn = TEAM_CN.get(m.team1, m.team1)
    t2cn = TEAM_CN.get(m.team2, m.team2)
    stage = f'{m.group}组' if m.group else m.stage
    print(f'M{m.match_id}: {t1cn}(主) vs {t2cn}(客) | {stage}')
"
```

如果无待赛比赛，尝试当天或下一个比赛日。

### Step 2: 获取双方小组赛 xG 数据

对每场比赛的两支球队运行：
```bash
python3 xg_model.py team <team_name>
```

输出已包含从该队视角的比分和 W/D/L 标记（如 `1-2 (L)`），直接使用即可。

记录：场均xG、场均xGA、xGD、转化效率、分阶段xG特征。

### Step 2.5: 数据交叉验证【必做】

**此步骤防止主客场比分混淆导致的分析错误。** 对每支球队运行以下脚本，自动从 `match_data.py` 生成球队事实卡，与 Step 2 的 xG 数据交叉验证：

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

### Step 3: 获取热身赛数据【必做】

对每支球队，用 WebFetch 从 Wikipedia 获取 2026 年赛前热身赛数据：
```
https://en.wikipedia.org/wiki/<Team>_national_football_team
```

提取：日期、对手、比分、对手质量评级（强/中/弱）。

重点关注：
- 对强队（参赛队级别）的战绩
- 进失球模式是否与小组赛xG一致
- 关键球员是否在热身赛中有产出

### Step 4: 获取赔率

```bash
python3 sporttery_odds.py fetch
```

如需比分赔率：
```bash
python3 sporttery_odds.py crs
```

### Step 5: 生成比分矩阵

对每场运行：
```bash
python3 score_matrix.py predict <match_id>
```

### Step 5.5: 舟车劳顿分析【淘汰赛必做】

对每场比赛运行旅途负担对比：
```bash
python3 travel_analysis.py <match_id>
```

输出包含：双方上一场场地→本场场地的距离(km)、时区差、休息天数、疲劳评级。

**如何使用旅途数据：**
- 疲劳评级"高"（长途+跨时区+短休息）的一方，在体力相关指标上下调：
  - 60-90分钟 xG 产出打折（长途旅行影响后半场体力）
  - 如果双方实力接近，旅途劣势方的 D 概率上调 2-3%（更可能拖入加时）
- 双方旅途负担差距 >1500km 时视为显著不对称，纳入最终判断
- 旅途因素是 tiebreaker，不改变明确的实力差距判断

### Step 5.6: 淘汰赛历史校准【淘汰赛必做】

将模型输出的 H/D/A 概率与历史淘汰赛基准交叉验证（数据源: `historical_knockout.py`）：

**历史基准（2018+2022, 30场）：**
- 90分钟总平局率: **33%**（R16=31%, QF=38%）
- 热门队90分钟胜率: **54%**
- 冷门率(热门队输): **8.3%**
- 场均进球: 2.97（与小组赛无差异）

**按实力差距分层调整 D 概率：**

| 实力差距 | 历史D率 | D概率参考范围 | 典型案例 |
|---------|--------|-------------|---------|
| 大落差（xGD差>6） | ~15% | 15-20% | 法国3-1波兰, 巴西4-1韩国 |
| 中等落差（xGD差3-6） | ~35% | 28-35% | 西班牙1-1俄罗斯, 哥伦比亚1-1英格兰 |
| 均势（xGD差<3） | ~35% | 30-35% | 法国4-3阿根廷, 英格兰1-2法国 |

**校准步骤：**
1. 模型输出 D 概率如果低于同级别历史基准 5% 以上 → 上调至基准附近
2. D 概率增加部分主要从 H（热门方）扣除，A 基本不动
3. 小组赛校准的"强队上调5-8%"**不适用于淘汰赛**
4. QF 及之后的比赛，D 概率在上述基础上再 +3-5%

### Step 6: 综合分析 → 输出预测

对每场比赛，综合以下信息做出最终判断：
1. xG数据（权重最高）— 3场小组赛的攻防质量
2. 热身赛数据（补充样本）— 对强队战绩权重更高
3. 赔率隐含概率（市场参考）
4. 比分矩阵（概率分布）
5. **历史淘汰赛校准**（Step 5.6）— D概率是否符合历史基准
6. **舟车劳顿**（Step 5.5）— 旅途距离、时区差、休息天数的不对称
7. **淘汰赛特有因素**：
   - 体力/轮换：小组赛末轮是否主力全上或轮换休息
   - 交叉对位：双方踢法互克关系
   - 大赛淘汰赛经验：关键球员在高压环境下的表现
   - 90分钟内结束 vs 加时可能性

**淘汰赛注意：** 体彩竞彩以90分钟为准（含伤停补时）。平局 = 进加时赛。需同时给出：
- 90分钟 H/D/A 概率（用于投注）
- 最终晋级概率（用于后续淘汰赛推演）

### Step 7: 录入预测

```bash
python3 prediction_tracker.py record <match_id> <pH> <pD> <pA> --score X-Y
```

### Step 8: 写入 predictions.json

确认预测已写入 `02_data/predictions.json`。

### Step 9: 保存分析并生成面板

将本次每场比赛的详细分析写入 `02_data/analysis/M{id}.md`，包含：
- 对阵信息、阶段、日期
- 小组赛 xG 数据摘要
- 热身赛数据摘要
- 赔率隐含概率和 Edge
- 比分矩阵 Top 3
- 淘汰赛特殊因素（如适用）
- 最终预测（概率、比分、晋级方）

然后重新生成 dashboard：
```bash
python3 generate_dashboard.py
```

## 输出格式

### 概率表

| 对局 | 主胜 | 平(加时) | 客胜 | 预测比分 | 晋级方 | 简要原因 |
|------|------|---------|------|---------|--------|---------|
| M73 南非vs加拿大 | 15% | 25% | **60%** | 0-2 | 加拿大 | 加拿大小组赛xG碾压+热身赛6-0卡塔尔 |
| M74 巴西vs日本 | **45%** | 25% | 30% | 2-1 | 巴西 | 巴西xGD+6领先，日本防线在荷兰面前暴露 |
| ... | | | | | | |

### 每场详细分析

```
M73 南非 vs 加拿大 · 32强淘汰赛
─────────────────────────────────
小组赛xG: 南非 场均X.XX/xGA X.XX / 加拿大 场均X.XX/xGA X.XX
热身赛:   南非 X胜X平X负(含对XX) / 加拿大 X胜X平X负(含对XX)
赔率隐含: H XX% / D XX% / A XX%
比分矩阵: X-X(XX%) / X-X(XX%) / X-X(XX%)

舟车劳顿:
- 南非: 上场@XX → 本场@XX, XXXkm, 时区差Xh, 休息X天 [评级]
- 加拿大: 上场@XX → 本场@XX, XXXkm, 时区差Xh, 休息X天 [评级]

淘汰赛因素:
- 体力: [南非MD3主力出战/加拿大MD3轮换 + 旅途负担对比]
- 对位: [关键对位分析]
- 经验: [大赛淘汰赛经历]

→ 90分钟预测: 加拿大胜 60%，比分 0-2
→ 晋级概率: 加拿大 75% / 南非 25%
```

### 关键原则

- **热身赛数据必须纳入分析** — 3轮小组赛样本仍不够，需要热身赛补充
- **对强队热身赛权重高于对弱队** — 7-0弱队的参考价值远低于1-0强队
- **预测基于数据而非名气** — 不因球队历史声望改变概率判断
- **必须包含教练可能选什么和最佳策略** — 以教练选择为预测基准
- **比分格式：主队-客队** — 始终保持主队在前
- **淘汰赛平局 = 加时** — 90分钟的"平"不是最终结果，需额外给出晋级概率
- **不用"动机不对称"作为解释** — 淘汰赛双方都必须赢
