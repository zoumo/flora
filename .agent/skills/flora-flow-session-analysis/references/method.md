# 指标与计算口径

## 数据单位

### Session

一个 Codex JSONL 线程。
索引从文件名读取线程 ID。同一线程 ID 有多个文件时，读取最大的文件。
不同 fork 线程保留为不同 session。

### Run

一次正式执行 `flora-flow` 的编排范围。
旧名 `spec-to-ship` 也归入同一 run 定义。
一个 run 包含至少一个 root session，以及人工分配的 ticket。
讨论、维护和当前分析 session 不属于 run。

### Ticket

`flora-flow` 产生的一张实现 ticket。
一个 ticket 包含一个或多个 attempt session。
`primary` 是报告代表线程，不改变 attempt 的统计范围。

### Attempt

同一 ticket 的一次执行线程。
下列情况会产生多个 attempt：

- 失败后重试。
- remote-compact 后接管。
- finish-gaps 补齐。
- handoff 到新线程。
- 同一实现被 fork 到多个线程。

## Session 关系

索引按下列证据建立父子关系：

- `session_meta.forked_from_id`
- `source.subagent.thread_spawn.parent_thread_id`
- `turn_attribution.parent_turn_id`
- collaboration 调用的 delegation 输出
- `create_thread` prompt 哈希和子线程起始时间

关系只用于候选发现和人工核验。
最终统计以 mapping 的 `root_sessions`、`tickets[].sessions` 和
`tickets[].primary` 为准。

## 相关 turn

session 可能有多个 turn。
脚本按下列优先级选择相关 turn：

1. trigger 为 `app_tool_create_thread`、`app_tool_send_message`
   或 `resume_interrupted_task` 的 turn。
2. 父 turn 触发的 `send_user_message_async_question` turn。
3. session 的全部 turn。

`resume_interrupted_task` 默认不进入相关 turn。
如果人工确认该恢复 turn 属于同一实现工作，把 session ID 写入
`overrides.json` 的 `analysis.attempt_include_resume`。

## Active 区间

### 事件点

脚本收集下列时间点：

- `task_started`
- `task_complete`
- `item_completed`
- user message

相邻事件点间隔不超过 `--gap-seconds` 时，脚本合并为 active 区间。
默认值是 `600` 秒。
跨夜 idle 和不连续对话因此不会扩大 effort。

### 工具区间

脚本使用工具事件的持续时间。
缺少持续时间时，脚本使用 function call 请求到输出的时间差。
工具区间与事件区间取并集。

命中开发服务的 `CommandExecution` 不计入 active。
当前识别项包括：

- `npm run dev`
- `pnpm dev`
- `yarn dev`
- `vite --host`
- `webpack serve`
- `run.sh`
- `dev:local`

长驻服务仍保留在 `long_tail.dev_services`，供人工检查。

### Effort

`ticket effort` 等于该 ticket 全部 attempt 的 active 区间之和。
多个 attempt 同时活动时，attempt 之间不去重。

`ticket latency` 等于首个 attempt 开始到最后一个 attempt 结束的日历时长。
latency 包含 idle、等待和 attempt 间隔。

## Root 指标

### task span

root 的 `task_started` 到 `task_complete` 区间并集。
未完成的 turn 截到 run 结束时间或 session 最后事件。

### engaged

root session 在 run 窗口内的 active 区间并集。
算法与 ticket effort 相同。

### wait

root wait 只统计 `wait_threads`。
`wait_agent` 和 collaboration 的 `wait` 归入 `subagent_wait`，不从 root own 扣除。

### own active

```text
root own = root engaged - root wait
```

own active 表示排除子线程等待后的根线程活动。

## 时间归因

归因按下列优先级扣除已识别工具区间。
每个区间只归入第一个匹配类别。

1. `thread_wait`
2. `subagent_wait`
3. `tests_verification`
4. `build_lint`
5. `git_pr_ci`
6. `ci_wait`
7. `browser_e2e`
8. `network_install`
9. `inspect_search`
10. `other_commands`
11. `extension`
12. `other_tools`
13. `mcp_app`
14. `orchestration`
15. `web_search`

剩余 active 时间记为 `model/edit/untimed`。

`model/edit/untimed` 包含：

- reasoning
- AgentMessage
- FileChange
- 未单独记录持续时间的模型工作
- 工具分类规则未覆盖的模型工作

不能把 `model/edit/untimed` 解释为纯编辑时间。

`tests_verification` 和 `build_lint` 使用命令文本分类。
包装脚本、make target 和别名可能改变类别。
长命令必须人工抽查。

## Run 阶段

### Prep

run 开始到首个 ticket 开始。

### Implementation

首个 ticket 开始到最后一个非 running ticket 结束。

### Closeout

最后一个非 running ticket 结束到 run 结束。

阶段报告两类时间：

- 日历时间：包含夜间 idle 和依赖等待。
- root active：root 在阶段窗口中的 engaged 区间。

ticket latency 窗口和 ticket active 窗口同时写入 JSON，供进一步核验。

`flags` 含 `partial` 的 run 不进入阶段占比和阶段汇总。
partial run 的结束时间会延长到已观察的 root 或 ticket 最后活动。

## 聚合指标

### 总和

下列指标可以在 run 之间求和：

- run wall
- ticket effort
- ticket latency
- root engaged
- root wait
- root own

同一 run 内，多个 ticket 可能并行。
不同 run 也可能重叠。
sum 表示工作量，不表示唯一日历时间。

### 并集

下列指标使用区间并集：

- `run_window_union_hours`
- `root_engaged_union_hours`
- `ticket_engaged_union_hours`
- `active_union_hours`

`active_union_hours` 是 root active 与全部 ticket active 的去重并集。
跨 run、嵌套 run 和并发 ticket 不会重复计时。

## Ticket 状态

### completed

至少一个 attempt 有已完成的 relevant turn。

### completed_in_inferred_tail

没有正式 `task_complete`，但后续证据和停止点支持完成。
该状态必须由人工写入 override。

### unclosed

全部 attempt 都没有完成的 relevant turn。
如果没有显式状态，脚本使用此默认值。

### running

快照时仍在执行。
该状态必须由人工写入 override。

## Run flags

### partial

run 或 ticket 集合未完整采集。
此 flag 改变阶段统计范围。

### nested

该 run 是另一个 `flora-flow` 执行的一部分。
此 flag 用于提醒重叠。脚本不自动删除嵌套双重计时。

### handoff_merged

run 合并了 handoff、finish-gaps 或接管线程。
脚本不据此自动改变时间。root 和 ticket 仍按 mapping 计算。

### remote_compact

执行中有 remote-compact 或接管。
此 flag 是核验证据。attempt 合并由 `sessions` 决定。

## 已知边界

- Codex JSONL schema 可能变化。schema 未识别时，先更新索引器。
- 工具事件可能缺少 duration。缺少时使用请求到响应时间。
- 命令分类是文本启发式，不是语义解析。
- 同一 worktree 的依赖等待可能出现在多个 session。
- 嵌套 run 的工时可以重叠。报告必须说明。
- 归档时间不等于完成时间。完成状态以 turn 和人工证据为准。
- 回归 fixture 依赖本机原始 session。fixture 不证明任意窗口可复现。
