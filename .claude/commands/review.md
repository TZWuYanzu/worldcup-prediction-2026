---
description: "复盘已完赛比赛：xG分析 + 预测对比 + 日历同步。当用户提到「复盘」「回顾」「review」「昨天的比赛」时使用。"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - WebFetch
---

# 比赛复盘

对已完赛但尚未复盘的比赛进行全面复盘：获取xG数据、录入比分、与赛前预测对比、分析偏差原因、同步日历。

## 解析用户意图

从 `$ARGUMENTS` 中提取：
- 无参数 → **自动模式**（见 Step 0）
- `6-27` 或 `06-27` 或 `2026-06-27` → 指定日期
- `今天` / `today` → 当天
- `昨天` / `yesterday` → 昨天
- match_id（如 `74 75`）→ 直接复盘指定比赛

## 执行步骤

### Step 0: 确定复盘范围（自动模式）

无参数时的默认逻辑：

```bash
python3 -c "
from datetime import datetime, timezone, timedelta
from match_data import ALL_MATCHES, TEAM_CN

now = datetime.now(timezone(timedelta(hours=8)))  # 北京时间
today_str = now.strftime('2026-%m-%d')

# 找出所有「比赛日期 <= 今天 且 无比分」的比赛 = 待复盘
unreviewed = []
for m in ALL_MATCHES:
    if m.date_str <= today_str and not m.score:
        unreviewed.append(m)

if unreviewed:
    print(f'待复盘: {len(unreviewed)} 场（已完赛但未录入比分）')
    for m in sorted(unreviewed, key=lambda x: (x.date_str, x.match_id)):
        t1cn = TEAM_CN.get(m.team1, m.team1)
        t2cn = TEAM_CN.get(m.team2, m.team2)
        stage = f'{m.group}组' if m.group else m.stage
        print(f'  M{m.match_id}: {t1cn} vs {t2cn} ({stage}) {m.date_str}')
else:
    # 所有历史比赛已复盘，看今天是否有已完赛比赛
    today_matches = [m for m in ALL_MATCHES if m.date_str == today_str and m.score]
    if today_matches:
        print(f'所有历史比赛已复盘。今天已完赛: {len(today_matches)} 场')
        for m in today_matches:
            t1cn = TEAM_CN.get(m.team1, m.team1)
            t2cn = TEAM_CN.get(m.team2, m.team2)
            print(f'  M{m.match_id}: {t1cn} {m.score} {t2cn}')
    else:
        print('所有比赛已复盘完毕，今天暂无已完赛比赛。')
"
```

**优先级：**
1. 有「日期已过但无比分」的比赛 → 先获取比分并复盘这些比赛
2. 所有历史比赛都已有比分 → 看今天是否有新完赛的比赛
3. 全部已复盘且今天无新比赛 → 告知用户无需复盘

**指定日期时：** 直接查该日期的比赛（无论是否已有比分），已有比分的直接复盘，无比分的先获取。

### Step 1: 获取缺失比分并更新 match_data.py

对每场无比分的比赛：
1. 用 WebFetch 从 TheSportsDB 获取比分：
   ```
   https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e=<Team1>_vs_<Team2>&s=2026
   ```
   或从 FIFA 官网获取
2. 更新 `match_data.py` 中的 `_RESULTS`（小组赛）或 `_KNOCKOUT_RESULTS`（淘汰赛）字典
3. 运行 `python3 add_to_calendar.py update-scores <id:score ...>` 同步日历

### Step 2: 逐场 xG 分析

对每场比赛运行：
```bash
python3 xg_model.py match <match_id>
```

记录每场的关键数据：xG、xGA、射门数、分阶段xG。

### Step 3: 提取赛前预测对比

```bash
python3 -c "
import json
with open('02_data/predictions.json') as f:
    preds = json.load(f)['predictions']
for p in preds:
    if p['matchId'] in [目标match_id列表]:
        print(f'M{p[\"matchId\"]}: H={p[\"probH\"]:.0%} D={p[\"probD\"]:.0%} A={p[\"probA\"]:.0%} score={p.get(\"predScore\",\"?\")}')
"
```

### Step 4: 预测评分

```bash
python3 prediction_tracker.py score
python3 prediction_tracker.py trend
```

### Step 5: 同步日历

```bash
python3 add_to_calendar.py update-scores <id1:score1> <id2:score2> ...
```

### Step 6: 更新分析文件（含场景推演对比）

对每场已复盘的比赛，在 `02_data/analysis/M{id}.md` 末尾追加实际比分和复盘摘要。

**必须包含「场景推演对比」**：将赛前分析中的每个战术场景（场景A/B/C/D）逐一与实际比赛过程对比。重点不是"最终比分是否吻合"，而是"过程是否吻合"。

对比方法：
1. 回顾赛前的分阶段 xG 预测和战术场景推演
2. 用实际 xG 射门时间线重建比赛叙事（谁在哪个时段主导、关键转折点）
3. 逐个场景打分：
   - ✅ 吻合 — 过程和结果都与场景描述一致
   - ◐ 部分吻合 — 结果类似但关键过程不同（如"挪威前30分钟破门"vs"挪威39'破门"）
   - ✗ 不吻合 — 实际走势与场景描述相反
4. 识别"场景盲区" — 实际发生了但所有场景都没覆盖的关键情况

示例：
```
场景推演对比:
- 场景A(30%): 挪威前30'Haaland破门 → ✗ 实际前30'科特迪瓦xG碾压(0.75 vs 0.20)
- 场景B(25%): 科特迪瓦防反先进球 → ✗ 挪威先进球(Nusa 39')
- 场景C(25%): 0-0僵持到60'后挪威破门 → ◐ 挪威确实赢了，但39'就进球非60'后
- 场景D(20%): 科特迪瓦偷鸡 → ✗ 科特迪瓦输了
- 场景盲区: 没预料到挪威30-45'爆发(5射/1.40xG)，以及最终绝杀而非控制型胜利
```

**结论谨慎性原则**：单场或少量样本不足以得出系统性结论（如"替补效应在淘汰赛失效"）。仅当≥5场样本出现一致趋势时才提升为方法论教训。3场以下仅标注为"待观察信号"。

### Step 6.5: 重新生成看板并部署【必做】

复盘完成后，重新生成 dashboard（包含 bracket 更新）：
```bash
python3 generate_dashboard.py
```

bracket 视图会自动根据已完赛淘汰赛比分（含 aet/pen）将晋级球队传播到下一轮对阵中。确认 bracket 中已完赛比赛的晋级方正确显示后，部署到线上：
```bash
npx netlify deploy --prod --dir=. --message="Review: update bracket + match results"
```

### Step 7: 汇总输出

## 输出格式

```
================================================================
  比赛复盘（N场待复盘）
================================================================

  M74: 巴西 2-1 日本 (R32)
  ────────────────────────────────
  xG:     巴西 2.15 - 1.87 日本
  赛前预测: 巴西 47% / 平 29% / 日本 24%  预测比分: 2-1
  实际结果: 巴西胜 → 预测方向正确

  偏差归因:
  - [具体原因]
  - [热身赛/小组赛已有的信号是否被忽略]

  ────────────────────────────────
  M75: 德国 ... (类似格式)
  ...

================================================================
  整体评估
================================================================
  方向正确: X/N 场
  Brier Score: 当轮 0.xxx / 累计 0.xxx
  
  方法论教训:
  1. [可改进的点]
  2. [需要调整的预测框架]
================================================================
```

### 关键原则

- **不用"动机不对称"解释预测偏差** — 运动员上场都想赢，预测错误归因于实力判断
- **区分"可改进"与"不可控"偏差** — 信息不足/逻辑错误 vs 纯随机性
- **乌龙球和点球纳入防线评估** — 它们反映禁区压力下的抗压极限
- **已有比分的比赛不重复复盘** — 无参数时只处理未录入比分的比赛
