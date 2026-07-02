# 2026 FIFA 世界杯 预测分析

**赛事**：2026 年 6 月 11 日 – 7 月 19 日
**主办**：美国（11 城）、墨西哥（3 城）、加拿大（2 城）
**规模**：48 队，12 个小组，每组 4 队；每组前 2 + 8 个最佳第 3 = 32 进入淘汰赛
**揭幕战**：2026/06/11 墨西哥 vs 南非（墨西哥城阿兹特克体育场）
**决赛**：2026/07/19 美国新泽西 MetLife 体育场

## 文件结构

```
worldcup_prediction/
├─ README.md              本文件
├─ 00_groups.md           12 个小组分组、赛程、强弱定性
├─ 01_teams/              16 支重点球队中等深度分析
│  ├─ argentina.md        阿根廷
│  ├─ belgium.md          比利时
│  ├─ brazil.md           巴西
│  ├─ canada.md           加拿大
│  ├─ colombia.md         哥伦比亚
│  ├─ croatia.md          克罗地亚
│  ├─ england.md          英格兰
│  ├─ france.md           法国
│  ├─ germany.md          德国
│  ├─ japan.md            日本
│  ├─ mexico.md           墨西哥
│  ├─ morocco.md          摩洛哥
│  ├─ netherlands.md      荷兰
│  ├─ norway.md           挪威
│  ├─ portugal.md         葡萄牙
│  ├─ senegal.md          塞内加尔
│  ├─ south_korea.md      韩国
│  ├─ spain.md            西班牙
│  ├─ switzerland.md      瑞士（B 组隐形种子）
│  ├─ uruguay.md          乌拉圭
│  └─ usa.md              美国
├─ 02_data/
│  ├─ teams.csv           一队一行的综合指标（FIFA 排名、主帅、阵式、近期 W/D/L、夺冠赔率推测）
│  ├─ friendlies.csv      逐场比赛记录（2025/06 - 2026/06，含预选赛与友谊赛）
│  └─ rosters/            26 人大名单（能完整拿到的几队）
│     ├─ mexico.csv
│     └─ south_korea.csv
├─ 03_prediction.md       综合预测：死亡之组、各组出线推测、淘汰赛走势、冠军预测（v2，赛前）
└─ 04_matchday1_review.md 第一轮战报与预测修正（v3，2026/06/16）
```

## 数据源与方法说明

- **主要来源**：英文 Wikipedia 各队主页 + 12 个小组独立页面（截至 2026/06/04 抓取）
- **限制**：
  - WebSearch 在本环境被禁用，无法搜索中文媒体（虎扑、直播吧等）。如需补充，可后续手动贴 URL。
  - Wikipedia `2026_FIFA_World_Cup_squads` 页面单次抓取被截断，**仅墨西哥、韩国拿到完整 26 人名单**；其他队仅列核心 6-10 人。
  - 2026 年 6 月初的最后一批热身赛（多在 6/4-6/10）部分尚未发生，仅记录截至 6/4 已发生的比赛。
- **数据置信度**：分组、主帅、近一年战绩 = 高；战术阵式 = 中（部分队 Wikipedia 未明确写）；完整 26 人名单 = 低（除墨韩外不全）。

## 复用方式

- 后续分析单场比赛 / 淘汰赛对阵：直接读 `01_teams/<队>.md` 查战术与核心球员，`02_data/friendlies.csv` grep 比分。
- 想加新队：在 `01_teams/` 下新增 md，更新 `02_data/teams.csv` 和 `00_groups.md`。
