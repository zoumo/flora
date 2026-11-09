# 人工核验清单

自动发现只提供两类候选：

- 有强 `flora-flow` 证据的 session。
- 可由标签和父子关系推断的 ticket session。

发现逻辑同时接受旧名 `spec-to-ship`。
自动发现不判断正式运行范围。
下列项目必须人工确认。

## 1. 核验 run 边界

- 确认用户明确启动或继续 `flora-flow`。
- 确认 root session 执行 ticket 拆分或编排，不只讨论方法。
- 确认 run 的首个有效证据早于或等于 `start`。
- 确认 run 的 `end` 覆盖最后一个有效 root 或 ticket 事件。
- 保留跨夜 idle 为 latency，不加入 effort。

删除下列候选：

- 询问 `flora-flow` 用法。
- 修改或维护 skill。
- 讨论历史统计。
- 当前分析 session。
- 只读取 skill 文档的 session。
- 同一 prompt 的重复 fork 副本。

## 2. 核验 root

- 确认 `root_sessions` 包含实际编排线程。
- 确认 planning、handoff 和 finish-gaps 线程属于同一 run。
- 检查同一 run 是否被候选发现拆成两个 root。
- 检查父线程是否只发送初始 prompt，没有参与后续编排。
- 检查子线程是否独立执行了另一套 `flora-flow`。

独立执行的子线程写入新 run。
共享同一 ticket 集合的接管线程写入同一 run。

## 3. 核验 ticket

- 确认 ticket label 来自正式 ticket 列表或 issue 文件。
- 确认 `primary` 是最终实现或最终核验线程。
- 确认 `sessions` 包含全部有效 attempt。
- 检查是否把父线程或另一个 ticket 的线程误挂到当前 ticket。
- 检查 ticket 开始时间是否早于同 run 的首个 ticket 边界。
- 检查 ticket 结束时间是否包含后续 finish-gaps。

同一 label 的失败重试加入同一 ticket。
不同 label 的实现线程不能只按 target 关系合并。

## 4. 未正式收尾线程

检查 `task_started` 后是否缺少 `task_complete`。

按证据选择状态：

- 后续有完成证据，但无正式收尾：`completed_in_inferred_tail`。
- 快照时仍在执行：`running`。
- 没有完成证据：`unclosed`。
- 被后续 attempt 完成：ticket 记 `completed`，旧 attempt 保留在 `sessions`。

不要仅因 session 文件结束就标记完成。

## 5. Inferred completion

只有同时满足下列条件才写入 `completed_in_inferred_tail`：

- 目标工作已经产出。
- 后续消息或工具结果显示核验完成。
- 没有发现新的执行 turn。
- 停止点不是 context 中断或工具错误。

在 `note` 写出证据类型。
在最终报告说明 inferred completion 的数量和 session ID。

## 6. 快照时 running

检查 `--as-of` 前最后一个相关 turn。

如果 turn 没有完成，且工作仍在继续：

- ticket 状态写 `running`。
- run 写 `partial`。
- 报告使用快照时间说明截断。

重新运行前使用同一 `--as-of`。
变更快照后不能直接比较 effort 和 latency。

## 7. 跨夜 idle

当 ticket latency 明显大于 effort 时，检查原因。

常见原因：

- 夜间停止。
- 人工等待。
- 外部 CI。
- 共享 worktree 锁。
- 子线程未唤醒。

保留 latency。
不要把 idle 加入 effort。
在报告中解释长 latency 的原因。

## 8. 共享 worktree 和 dependency wait

检查多个 ticket 是否等待同一构建、测试或 worktree。

确认等待类型：

- `wait_threads`：等待其他 Codex 子线程。
- `wait_agent`：等待子代理。
- CI 或 shell 命令：按命令归因。

root wait 只扣除 `wait_threads`。
共享依赖造成的 ticket latency 保留。
不要从 ticket effort 删除 dependency wait，除非工具区间已单独识别。

## 9. Remote-compact 和 retry

检查同一 ticket 是否有下列 session：

- 首轮失败线程。
- remote-compact 后接管线程。
- 修复和最终核验线程。

合并规则：

1. 全部有效 session 写入 `sessions`。
2. 最终完成或核验线程写入 `primary`。
3. 在 `note` 记录失败原因和接管关系。
4. run flag 增加 `remote_compact`。
5. 检查两个 session 是否重复计入同一事件。

## 10. 嵌套 run

出现下列证据时检查嵌套：

- root 在一个 `flora-flow` ticket 中启动另一个 `flora-flow`。
- 子 run 有独立 ticket 集合。
- 父子 run 同时有 active 区间。

独立 ticket 集合写入新 run。
父子 run 都保留，并写 `nested` flag。
报告不能把两个 run 的 effort 当作唯一日历时间。

## 11. Handoff 和 finish-gaps

检查新线程是否补做同一 run 的未完成 ticket。

合并条件：

- 同一 ticket 集合或明确的剩余 ticket。
- 新线程引用原 run 的 root、计划或 ticket。
- 新线程的工作与前序 run 连续。

处理方法：

- 新线程加入 `root_sessions`。
- 补齐 ticket 或加入新的 attempt。
- 写 `handoff_merged` flag。
- 在 ticket `note` 说明哪个线程完成剩余工作。

## 12. 重复 fork 和 subagent 副本

检查相同 prompt 指纹和相近起始时间。

常见重复：

- root 的 fork 快照。
- 同一 `create_thread` prompt 的多个 evidence 副本。
- fork 后的实现线程。

选一个 canonical session。
不同 ticket 的 fork 不能仅因 prompt 相同而合并。
逐项检查父线程、ticket label 和 worktree。

## 13. 排除当前分析 session

当前分析 session 可能出现下列强标记：

- user 要求分析 `flora-flow`。
- 读取本 skill。
- 运行 `discover_runs.py`。
- 讨论 ticket 统计。

按 session ID 加入 `--exclude-session`。
如果索引建立后才发现，从 canonical mapping 删除该 run 或错误候选。

## 14. 最终对照

提交报告前逐项确认：

- 每个 run key 唯一。
- 每个 ticket label 在 run 内唯一。
- `primary` 属于 `sessions`。
- 所有 session ID 存在于索引。
- `start <= end`。
- `finished + running + unclosed` 等于 ticket 总数。
- 所有 `partial` run 都有说明。
- 所有 `nested`、`handoff_merged` 和 `remote_compact` 都有证据。
- 报告中的异常 session ID 与 mapping 一致。
