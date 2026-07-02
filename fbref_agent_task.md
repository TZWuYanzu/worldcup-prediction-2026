# 任务：从 FBref 抓取 2026 世界杯球员数据

## 环境准备

```bash
pip install requests lxml
```

## 脚本

将下面的 Python 脚本保存为 `fbref_fetch_standalone.py`，内容见同目录文件。

## 执行步骤

### 方式一：自动发现（推荐先试）

```bash
python3 fbref_fetch_standalone.py --auto
```

这会自动从 FBref 赛程页找到所有已完赛比赛的 Match Report 链接并逐一抓取。每场间隔 4 秒避免被限速。

### 方式二：手动指定（如果自动发现失败）

1. 打开浏览器访问 FBref 世界杯赛程页：
   - https://fbref.com/en/comps/1/schedule/FIFA-World-Cup-Scores-and-Fixtures
   - 或 https://fbref.com/en/comps/1/2025-2026/schedule/2025-2026-FIFA-World-Cup-Scores-and-Fixtures

2. 找到以下比赛的 "Match Report" 链接（点击进入后复制 URL）：

**优先级高（淘汰赛，已完赛）：**
- M73: South Africa vs Canada (6月29日)
- M74: Brazil vs Japan (6月29日)
- M75: Germany vs Paraguay (6月30日)
- M76: Netherlands vs Morocco (6月30日)
- M77: Ivory Coast vs Norway (7月1日)
- M78: France vs Sweden (7月1日)
- M79: Mexico vs Ecuador (7月1日)

**优先级中（小组赛第三轮）：**
- M67: England vs Croatia
- M69: England vs Ghana
- M71: Panama vs England
- M42: New Zealand vs Belgium
- M37: Belgium vs Egypt
- M49: France vs Senegal

3. 创建 `urls.txt`，每行格式 `match_id url`：

```
78 https://fbref.com/en/matches/xxxxx/France-Sweden-June-30-2026-FIFA-World-Cup
79 https://fbref.com/en/matches/xxxxx/Mexico-Ecuador-July-1-2026-FIFA-World-Cup
...
```

4. 批量抓取：

```bash
python3 fbref_fetch_standalone.py --batch urls.txt
```

### 方式三：单场抓取

```bash
python3 fbref_fetch_standalone.py 78 "https://fbref.com/en/matches/xxxxx/..."
```

## 输出

所有数据写入当前目录的 `fbref_results.json`。

## 完成后

将 `fbref_results.json` 文件内容发回给我。
