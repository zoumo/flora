---
name: spec-to-ship-session-analysis
description: 分析 Codex 本地 session JSONL 中实际执行 spec-to-ship 的 run，按时间窗口统计 run、ticket、阶段、effort、latency、等待和时间归因。用于历史运行统计、长尾定位、未收尾线程核验和 handoff 合并；不用于执行 spec-to-ship，也不分析 Claude 或其他 agent 的 session。
---

# spec-to-ship Session 分析

本 skill 分析 Codex 实际执行 `spec-to-ship` 的历史运行。
本 skill 不执行 `spec-to-ship`，不修改 ticket，也不把讨论、维护和分析 session 算作运行。

## 适用条件

用户要求完成下列任务之一时，使用本 skill：

- 统计指定时间窗内的 `spec-to-ship` run 和 ticket。
- 计算 ticket effort、ticket latency、阶段时长和时间归因。
- 分析长尾 ticket、等待、重试、嵌套 run 或 handoff。
- 核验运行快照中未收尾的 session。

输入必须来自 Codex 的本地 JSONL：

- `~/.codex/sessions`
- `~/.codex/archived_sessions`

## 固定规则

1. 使用 `--as-of` 冻结 UTC 快照。分析仍在运行的 ticket 时，不冻结快照会多算 effort 和 latency。
2. 自动发现只生成候选。最终统计只读取人工核验后的 mapping 和 overrides。
3. 同一 run 的根线程和 ticket 线程分开计权。root 表示编排时间，ticket 表示实现工作。
4. 多 attempt 合并到同一 ticket。`primary` 表示代表 session，不表示丢弃其他 attempt。
5. 当前分析 session、skill 维护 session 和只讨论方法的 session 必须排除。
6. 报告公开前，检查嵌套 run、共享 worktree、跨夜 idle、remote-compact 和未正式收尾线程。
7. 原始 session 可能包含私有内容。默认只输出聚合结果和必要 session ID。

时间、状态和归因的定义见
[references/method.md](references/method.md)。

## 工作流

### 1. 固定输入

设置目录、时间窗和快照。

```bash
SKILL_DIR=.agent/skills/spec-to-ship-session-analysis
OUT=/tmp/spec-to-ship-analysis
mkdir -p "$OUT"

SINCE=2026-11-03
UNTIL=2026-11-09
AS_OF=2026-11-09T14:29:00Z
```

本仓库的 shell 命令使用 `rtk` 前缀。
其他环境没有 `rtk` 时，删除该前缀。

`SINCE` 和 `UNTIL` 使用索引时区的本地日期。
`AS_OF` 使用 UTC ISO 8601 时间。

### 2. 建立索引

```bash
rtk python3 "$SKILL_DIR/scripts/index_sessions.py" \
  --since "$SINCE" \
  --until "$UNTIL" \
  --as-of "$AS_OF" \
  --out "$OUT/index.json.gz"
```

读取命令输出。
如果 `errors` 大于 `0`，先检查 JSONL 读取错误。

索引保留 2 天回看和 1 天前瞻。
子线程跨出窗口时，用 `--lookback-days` 或 `--lookahead-days` 扩大范围。

### 3. 生成候选

```bash
rtk python3 "$SKILL_DIR/scripts/discover_runs.py" \
  --index "$OUT/index.json.gz" \
  --out-mapping "$OUT/discovered.json" \
  --out-review-json "$OUT/discovery-review.json" \
  --out-review-md "$OUT/discovery-review.md" \
  --exclude-session SESSION_ID
```

按需要重复 `--exclude-session`。
排除当前分析 session 和已确认的维护 session。

候选数通常大于最终 run 数。
检查 `discovery-review.md` 中的证据、父线程和重复指纹。

### 4. 人工核验并编写 mapping

从 `discovered.json` 复制候选，逐项核验：

- 删除弱提及、讨论、维护和当前分析 session。
- 确认 root session 属于正式 `spec-to-ship` 执行。
- 把 root、ticket、attempt 和状态写入 canonical mapping。
- 拆分嵌套 run。
- 合并 handoff、finish-gaps 和接管线程。
- 每个 ticket 的 `primary` 必须属于 `sessions`。

核验清单见 [references/manual-review.md](references/manual-review.md)。
字段格式见 [references/mapping-schema.md](references/mapping-schema.md)。

把通用关系写入 `mapping.json`。
把本次数据特有的状态、合并、排除和 `partial` 标记写入 `overrides.json`。
不要把本窗口的异常硬编码进脚本。

### 5. 计算报告

```bash
rtk python3 "$SKILL_DIR/scripts/analyze_sessions.py" \
  --index "$OUT/index.json.gz" \
  --mapping "$OUT/mapping.json" \
  --overrides "$OUT/overrides.json" \
  --out-json "$OUT/report.json" \
  --out-md "$OUT/report.md"
```

默认活跃空档阈值为 `600` 秒。
只有用户明确更换口径时才修改 `--gap-seconds`。

### 6. 检查结果

至少检查下列项目：

- `report.json.scope.as_of` 等于冻结时间。
- `summary.runs` 和 `summary.tickets_allocated` 等于人工 mapping 结果。
- `finished + running + unclosed` 等于全部 ticket。
- `warnings` 已解释 inferred completion、running、嵌套 run、handoff 和多个 attempt。
- 长尾 ticket 与原始 session 抽查结果一致。
- root wait 只来自 `wait_threads`。
- dev server 区间未进入 effort。

使用 [references/report-template.md](references/report-template.md)
组织最终回答或 Markdown 报告。

## 输出内容

最终结果至少包含：

- 时间窗、`--as-of`、来源目录和索引统计。
- run、ticket、完成状态、effort、latency、root wait 和 active union。
- 逐 run 和逐 ticket 表。
- effort 分布、阶段分布、时间归因和长尾。
- 人工核验过的异常及其影响。
- 口径边界和不能从数据确认的事实。

报告必须区分：

- 日历时间与活跃时间。
- effort 总和与去重后的 active union。
- 已确认完成与由尾段推断的完成。
- 自动候选与人工 canonical mapping。

## 回归

本 skill 包含 2026-11 的回归 fixture。
复现命令和预期结果见
[references/regression-2026-11/README.md](references/regression-2026-11/README.md)。

只有本机仍有对应 Codex session 时，回归才能复现。
fixture 不包含原始 JSONL。

完成真实分析后运行：

```bash
rtk python3 "$SKILL_DIR/scripts/check_regression.py" \
  --report "$OUT/report.json" \
  --expected "$SKILL_DIR/references/regression-2026-11/expected.json"
```

`check_regression.py` 只用于该固定窗口，不用于任意报告。

## 参考文档

- [references/method.md](references/method.md)：指标、区间、阶段、归因和边界。
- [references/manual-review.md](references/manual-review.md)：候选核验清单。
- [references/mapping-schema.md](references/mapping-schema.md)：mapping 和 overrides 格式。
- [references/report-template.md](references/report-template.md)：报告章节和结论写法。
- [references/regression-2026-11/README.md](references/regression-2026-11/README.md)：固定回归基线。
