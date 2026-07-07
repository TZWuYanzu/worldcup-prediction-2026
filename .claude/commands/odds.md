---
description: "赔率分析：获取体彩赔率、计算隐含概率、标记value bet。当用户提到「赔率」「odds」「盘口」「体彩」时使用。"
allowed-tools:
  - Bash
  - Read
---

# 赔率分析

获取 Sporttery 体彩赔率，计算隐含概率，与模型预测对比找出 value bet。

## 解析用户意图

从 `$ARGUMENTS` 中提取：
- 无参数 → 分析所有当前在售比赛
- `59 60 65` → 只分析指定 match_id 的比赛
- `J` 或 `K` → 分析该小组的比赛
- `all` → 获取 HAD + HHAD + CRS + TTG 全部赔率类型

## 执行步骤

### Step 1: 获取赔率

```bash
python3 sporttery_odds.py fetch
```

如需全部赔率类型：
```bash
python3 sporttery_odds.py all
```

如需比分赔率：
```bash
python3 sporttery_odds.py crs
```

如需让球赔率：
```bash
python3 sporttery_odds.py hhad
```

### Step 2: 读取模型预测

```bash
python3 -c "
import json
with open('02_data/predictions.json') as f:
    preds = json.load(f)['predictions']
for p in preds:
    mid = p['matchId']
    print(f'M{mid}: model H={p[\"probH\"]:.0%} D={p[\"probD\"]:.0%} A={p[\"probA\"]:.0%}')
"
```

### Step 3: 计算 Edge

对每场比赛，计算：
- **隐含概率** = 1/赔率（去除overround后标准化）
- **Edge** = 模型概率 - 隐含概率
- Edge > +5% 标记为 ✅ value bet
- Edge < -5% 标记为 ⚠️ 市场不认同

### Step 4: 运行赔率预测分析

```bash
python3 sporttery_odds.py predict
```

## 输出格式

```
================================================================
  赔率分析 (6月28日，6场)
================================================================

  HAD 胜平负赔率:
  ─────────────────────────────────────────────────────────
  对局              赔率(H/D/A)    隐含概率        模型概率        Edge
  M59 阿尔及利亚vs奥地利  3.50/3.10/2.20  28%/31%/42%   25%/33%/42%   A: 0%
  M60 约旦vs阿根廷     12.0/7.50/1.20   8%/12%/80%    3%/10%/87%   A: +7% ✅
  ...

  Value Bet 汇总:
  ─────────────────────────────────────────────────────────
  ✅ M60 阿根廷客胜 @1.20 — 模型87% vs 赔率80% (+7%)
  ✅ ...

  ⚠️ 分歧较大:
  M59 平局 — 模型33% vs 赔率31% (分歧2%，可忽略)
================================================================
```

### Step 5: 写入投注看板

分析完成后，将赔率+Edge数据写入 `02_data/betting_rounds.json` 的对应轮次。如果该日期已有数据则覆盖 matches 部分。然后运行 `python3 generate_dashboard.py` 重新生成看板。

### 关键原则

- **Edge > 5% 才有投注价值** — 低于5%被overround吃掉
- **同时展示 HAD 和 HHAD** — 让球盘可能有不同的 edge
- **标注赔率变动方向** — 如果有历史赔率，标注升/降趋势
