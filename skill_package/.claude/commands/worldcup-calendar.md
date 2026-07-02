---
description: "管理2026世界杯日历：添加小组赛到macOS日历，支持标记关注球队。当用户提到「世界杯日历」「添加赛程」「比赛日程」「worldcup calendar」时使用。"
allowed-tools:
  - Bash
  - Read
---

# 世界杯日历管理 Skill

你负责将 2026 FIFA 世界杯比赛添加到用户的 macOS 系统日历中。

## 脚本位置

项目根目录下的 `add_to_calendar.py`，需要在该目录下运行。

## 解析用户意图

从 `$ARGUMENTS` 中提取以下信息：

### 1. 球队名识别

如果用户提到了球队名（中文或英文），提取为 `--my-teams` 参数。参考下表：

| 中文 | English | 中文 | English |
|------|---------|------|---------|
| 阿根廷 | Argentina | 墨西哥 | Mexico |
| 巴西 | Brazil | 摩洛哥 | Morocco |
| 法国 | France | 荷兰 | Netherlands |
| 德国 | Germany | 挪威 | Norway |
| 西班牙 | Spain | 葡萄牙 | Portugal |
| 英格兰 | England | 日本 | Japan |
| 比利时 | Belgium | 韩国 | South Korea |
| 克罗地亚 | Croatia | 瑞士 | Switzerland |
| 哥伦比亚 | Colombia | 乌拉圭 | Uruguay |
| 加拿大 | Canada | 美国 | United States |
| 塞内加尔 | Senegal | 澳大利亚 | Australia |

### 2. 意图路由

- 用户要添加比赛到日历 / 无特殊指令 → `groups` action
- 用户提到比分、结果、更新分数 → `update-scores` action
- 用户提到淘汰赛 → `add-knockout` action（告知用户此功能即将上线）
- 用户提到晋级、对阵更新 → `update-bracket` action（告知用户此功能即将上线）

## 执行命令

### 默认（仅绿色 + 黄色，无红色标注）：

```bash
python3 add_to_calendar.py groups
```

### 用户指定关注球队（加红色标注）：

```bash
python3 add_to_calendar.py groups --my-teams Germany France Spain England
```

注意：`--my-teams` 后面使用 **英文球队名**（即使用户用中文说的）。

### 预览模式（不写入日历）：

```bash
python3 add_to_calendar.py groups --dry-run --my-teams Germany France
```

### 其他可选参数

- `--yellow-max N`：每天最多 N 场黄色标注（默认 3）
- `--timezone N`：UTC 偏移量（默认 8，即北京时间）
- `--dry-run`：仅预览不写入

## 颜色规则说明

向用户解释结果时使用：

- **红色（我的主队）**：用户指定的关注球队，不受时间限制
- **黄色（热门场次）**：阿根廷/巴西/葡萄牙/荷兰/日本/摩洛哥的比赛，且本地时间 ≥ 07:00，每天最多 3 场
- **绿色（一般场次）**：其余所有比赛

## 错误处理

- 如果球队名无法识别，运行 `python3 -c "from match_data import get_all_team_names; [print(f'{cn} / {en}') for en,cn in get_all_team_names()]"` 展示完整球队列表让用户选择
- 如果 Calendar.app 权限被拒绝，提示用户前往「系统设置 > 隐私与安全 > 自动化」授权

## 示例对话

用户: `/worldcup-calendar`
→ 执行: `python3 add_to_calendar.py groups`

用户: `/worldcup-calendar 我喜欢德国和法国`
→ 执行: `python3 add_to_calendar.py groups --my-teams Germany France`

用户: `/worldcup-calendar 标记阿根廷、西班牙、英格兰、巴西`
→ 执行: `python3 add_to_calendar.py groups --my-teams Argentina Spain England Brazil`

用户: `/worldcup-calendar 先预览一下效果，关注葡萄牙`
→ 执行: `python3 add_to_calendar.py groups --dry-run --my-teams Portugal`

## 更新比分

`update-scores` 已完整实现，用于将已完赛比分写入日历事件标题和备注。

### 用法

通过 CLI 参数直接传入比分（格式 `match_id:score`）：

```bash
python3 add_to_calendar.py update-scores 1:2-0 2:2-1 13:1-1
```

或通过文件传入（每行一个 `match_id:score`）：

```bash
python3 add_to_calendar.py update-scores --file scores.txt
```

预览模式：

```bash
python3 add_to_calendar.py update-scores 1:2-0 --dry-run
```

### 注意事项

- 需要先运行 `groups` 命令生成 `calendar_state.json`
- 事件标题会从 "⚽ A队 vs B队" 变为 "⚽ A队 2-0 B队"
- 备注中会追加比分信息
- 支持先按 UID 查找事件，找不到时按球队名模糊匹配

### 示例对话

用户: `/worldcup-calendar 更新比分 墨西哥2-0南非 韩国1-1捷克`
→ 解析 match_id，执行: `python3 add_to_calendar.py update-scores 1:2-0 2:1-1`

用户: `/worldcup-calendar 把今天的比分更新一下`
→ 先确认今天比赛的 match_id 和比分，再执行 update-scores
