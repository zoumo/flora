# 报告结构

最终报告按下列顺序组织。
聊天回答可以压缩表格，但不能删除口径和异常说明。

## 1. 范围与口径

写明：

- 本地起止日期。
- `--as-of` UTC 快照。
- 索引时区。
- session 来源目录。
- 文件数、session 数和读取错误数。
- 人工 mapping 的 run 和 ticket 数。

必须解释：

- effort 是 active 区间之和。
- latency 是首尾日历时长。
- root wait 只扣 `wait_threads`。
- `model/edit/untimed` 不是纯编辑时间。

示例：

```text
分析窗口为 2026-11-03 至 2026-11-09（Asia/Shanghai），快照为 2026-11-09T14:29:00Z。
索引包含 544 个文件、540 个 session、0 个读取错误。
最终映射包含 23 个 run 和 114 张 ticket。
```

## 2. 结论摘要

先给 4 至 6 个可验证结论：

- run、ticket 和完成状态数量。
- ticket effort、ticket latency、root engaged、root wait。
- 主要阶段和主要时间归因。
- 最大长尾和等待来源。
- 数据限制。

不要在摘要中只列总时长。
说明 sum 和 union 的差异。

示例：

```text
113 张 ticket 已完成，1 张 running。
ticket effort 为 81.9 h，ticket latency 为 112.5 h。
root engaged 为 96.6 h，其中 66.2 h 是 wait_threads。
```

## 3. Run 总览

每行至少包含：

- run key
- ticket 数
- wall
- root engaged
- ticket effort
- ticket latency
- prep、implementation、closeout
- root wait
- root own
- flags

金额单位统一使用 `h`。
状态列为 `complete`、`partial`、`nested` 或 `handoff_merged`。

## 4. Ticket 明细

每行至少包含：

- run
- ticket label
- status
- effort
- latency
- attempt 数
- note

多个 attempt 时，note 写出接管、重试或 finish-gaps。
status 为 `completed_in_inferred_tail` 时，写出推断依据。

## 5. 分布与长尾

报告下列统计：

- effort 的 median、p75、p90、max。
- latency 的 median、p75、p90、max。
- effort 分桶。
- 每 run ticket 数。
- effort 最高 ticket。
- latency 最高 ticket。
- 最长命令。
- 长驻开发服务。

长尾必须从全部完成 ticket 排序后截取。
不能用输入顺序代替排序。

解释长尾时分别写：

- 高 effort：实际执行工作集中。
- 高 latency、低 effort：idle、外部等待或依赖等待。
- 高 effort、高 latency：单车 ticket 同时包含执行和等待。

## 6. 阶段分布

分别报告：

- 日历阶段合计。
- root active 阶段合计。
- 各 run 的日历阶段占比中位数。

写出阶段边界：

```text
prep = run start 到首个 ticket start
implementation = 首个 ticket start 到最后一个非 running ticket end
closeout = 最后一个非 running ticket end 到 run end
```

日历阶段可以远大于 root active。
不要把日历阶段解释为连续人工工作时间。

## 7. 时间归因

分别给出 ticket 和 root 表：

| 类别 | 小时 | 占比 |
| --- | ---: | ---: |

按小时降序。
保留全部类别，包括 `0.0` 小时类别。

必须说明：

- 归因依赖命令文本分类。
- 包装脚本可能改变测试和构建类别。
- `model/edit/untimed` 包含 reasoning 和其他未单独计时工作。
- `wait_agent` 归入 `subagent_wait`。

## 8. 异常核验

逐项列出实际发现的异常。
没有发现时写“无”。

### Inferred completion

写出：

- run
- ticket
- session ID
- 完成证据
- 为什么没有 `task_complete`

### Running

写出：

- run
- ticket
- session ID
- 快照时间
- `partial` 口径

### 嵌套 run

写出父 run、子 run 和 ticket 关系。
说明 effort 可能重叠。

### Handoff 或 finish-gaps

写出原线程、接管线程和完成的 ticket。
说明 attempt 是否合并。

### Remote-compact

写出失败的 attempt、接管 attempt 和最终核验结果。

### 跨夜和高 latency

写出 calendar gap、effort 和可能原因。
原因无法确认时写“无法从 session 确认”。

## 9. 项目分布

每行至少包含：

- 项目
- run 数
- ticket 数
- ticket effort
- 完成 ticket median

项目名称取自 root cwd 的末级目录。
项目名不明确时使用 `unknown`，并在映射中人工修正。

## 10. 结论与建议

建议必须由数据支持。
每项建议写：

- 证据数值。
- 影响对象。
- 可执行动作。

可用方向：

- 减少无效 root wait。
- 缩短 ticket latency 的 idle。
- 把测试命令包装成稳定入口。
- 把 remote-compact 后的接管规则写入 runbook。
- 对高 effort ticket 拆分验证和实现。
- 对嵌套 run 单独统计，避免重复解释日历时间。

不要建议删除数据、改写历史状态或隐藏长尾。

## 11. 限制

固定写出本窗口实际存在的限制。

常见限制：

- session JSONL 可能截断。
- 工具持续时间可能缺失。
- 命令分类是启发式。
- 不同 run 的 effort 可能重叠。
- 嵌套 run 会重复计工作量。
- 回归 fixture 只覆盖 2026-11 窗口。

如果 `--as-of` 缺失，停止报告并补建索引。
