# 世界杯日历 Skill — Claude Code 插件

将 2026 FIFA 世界杯 72 场小组赛一键添加到 macOS 系统日历，支持三色标注。

## 安装

1. 将本文件夹放到任意位置（如 `~/worldcup-calendar/`）
2. 在 Claude Code 中 `cd` 到该目录
3. 输入 `/worldcup-calendar` 即可使用

## 使用

```
/worldcup-calendar                    # 默认：黄色(热门) + 绿色(其余)
/worldcup-calendar 我喜欢德国和法国    # 德国法国标红 + 其余热门黄色
/worldcup-calendar 先预览一下          # 仅预览不写入日历
```

也可以直接命令行运行：

```bash
python3 add_to_calendar.py groups                              # 默认模式
python3 add_to_calendar.py groups --my-teams Germany France    # 指定红色球队
python3 add_to_calendar.py groups --dry-run                    # 预览模式
```

## 颜色规则

| 颜色 | 含义 | 规则 |
|------|------|------|
| 红色 | 我的主队 | 用户指定的球队，不限时间 |
| 黄色 | 热门场次 | 阿根廷/巴西/葡萄牙/荷兰/日本/摩洛哥，北京时间 ≥ 07:00，每天最多 3 场 |
| 绿色 | 一般场次 | 其余所有比赛 |

## 系统要求

- macOS（使用 Calendar.app）
- Python 3.10+
- Claude Code（使用 skill 功能时）

## 文件说明

```
.claude/commands/worldcup-calendar.md  # Skill 指令定义
add_to_calendar.py                     # CLI 入口
match_data.py                          # 比赛数据 + 球队中英文映射
calendar_engine.py                     # macOS 日历操作引擎
```
