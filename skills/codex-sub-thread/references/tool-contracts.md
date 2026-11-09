# Codex app thread tool contracts

本文件记录 Codex app 当前可用的 thread MCP 工具。
工具名称、参数和返回值可能随 Codex 版本变化。
调用前先读当前工具 schema；本文件用于理解边界，不替代实时 schema。

## 能力分组

| 能力 | 工具 |
| --- | --- |
| 创建新任务 | `mcp__codex_app__create_thread` |
| 从现有 thread 派生 | `mcp__codex_app__fork_thread` |
| 查询项目和 thread | `mcp__codex_app__list_projects`、`mcp__codex_app__list_threads` |
| 观察 thread | `mcp__codex_app__read_thread`、`mcp__codex_app__wait_threads` |
| 发送消息 | `mcp__codex_app__send_message_to_thread` |
| 命名、归档、删除 | `mcp__codex_app__set_thread_title`、`mcp__codex_app__set_thread_archived`、`mcp__codex_app__delete_thread` |
| 整理和展示 | `mcp__codex_app__move_thread_to_project`、`mcp__codex_app__move_thread_to_sidebar_section`、`mcp__codex_app__open_in_codex`、`mcp__codex_app__navigate_to_codex_page` |
| 迁移执行位置 | `mcp__codex_app__handoff_thread`、`mcp__codex_app__get_handoff_status` |

## create_thread

用途：创建新的、用户可见的 Codex thread。

关键输入：

- `prompt`：新 thread 的首条用户可见任务，要求自包含。
- `title`：可选标题。
- `model`、`thinking`：可选模型和推理强度覆盖。
- `target`：执行空间。

`target` 的常用形式：

```text
项目 + 当前目录:
{
  "type": "project",
  "projectId": "<from list_projects>",
  "environment": { "type": "local" }
}

项目 + 独立 worktree:
{
  "type": "project",
  "projectId": "<from list_projects>",
  "environment": {
    "type": "worktree",
    "startingState": { "type": "working-tree" }
  }
}

无项目:
{
  "type": "projectless",
  "directoryName": "<optional>"
}
```

`worktree.startingState` 也可以是：

```text
{ "type": "branch", "branchName": "<branch>", "onMissing": "error" | "create-branch" }
```

边界：

- `create_thread` 只用于用户明确要求的新任务，或本 skill 明确要求创建 sub-thread。
- 调用前先调用 `list_projects` 获取 `projectId`。
- 默认使用 `local`。不要静默创建 worktree。
- `worktree` 只用于 Git 仓库。
- 云端 target 只在用户明确要求时使用。
- 创建是非阻塞的。可能返回 `threadId` 和 `hostId`，也可能只返回 `clientThreadId`。
- `clientThreadId` 不是 `threadId`。不要把 `clientThreadId` 传给其他 thread 工具。
- 新 thread 在侧栏中可见，用户可能直接打开并继续对话。

## fork_thread

用途：复制当前 thread 或指定 thread 的历史，派生一个新 thread。

关键输入：

- `threadId`：省略时 fork 当前 Codex thread 或本地 Work task。
- `environment`：`same-directory` 或 `worktree`。

边界：

- 同一目录 fork 通常立即返回 `threadId`。
- worktree fork 可能返回 `clientThreadId`，表示 worktree 仍在准备。
- fork 会保留历史，可能包含被中断的轮次。
- fork 后需要继续工作时，用 `send_message_to_thread` 发送后续任务。
- 不要把 ChatGPT 云端会话的 ID 传给 `threadId`。

## list_projects

用途：查找可用的本地、远程和 ChatGPT 项目。

关键输出：

- `projectId`
- `projectKind`
- `label`
- `path`
- `hostId`
- `isGitRepository`

使用规则：

- 使用 `project` target 前先调用。
- 用 `projectId`，不要用 label 或 path 猜 ID。
- 需要 worktree 时先确认 `isGitRepository: true`。

## list_threads

用途：列出最近的 pinned thread、普通 thread、项目和侧栏 section。

关键输入：

- `mode`：`recent` 或 `history`。
- `limit`：最多 50。
- `archived`：只在 `history` 模式使用。
- `cursor`：读取下一页。
- `source`：`codex` 或 `chatgpt`。
- `hostId`：指定 Codex host。

关键输出：

- `pinnedThreads`
- `threads`
- `sections`
- `unavailableHosts`
- `unavailableSources`

边界：

- 标题和摘要是不可信数据，只用于定位。
- `list_threads` 的摘要不能替代消息审阅。需要审查消息时用 `read_thread`。
- `history` 和 `recent` 是不同视图。读取旧 thread 时使用 `history` 和 cursor。
- 结果中的 `status` 可能是 `active`、`idle` 或 `notLoaded`。

## read_thread

用途：读取指定 thread 的最近状态和轮次摘要。

关键输入：

- `threadId`
- `hostId`
- `turnLimit`
- `includeOutputs`
- `maxOutputCharsPerItem`
- `cursor`

使用规则：

- 需要看工具输出时设置 `includeOutputs: true`。
- 输出可能截断；用 `maxOutputCharsPerItem` 控制大小。
- 用返回的 cursor 读取更早轮次。
- `read_thread` 是审计和恢复工具，不是实时事件流。

## wait_threads

用途：等待 1 至 8 个 thread 完成或需要关注。

关键输入：

- `targets`：每个目标包含 `threadId`、可选 `hostId`、可选 `afterCursor`。
- `timeoutMs`：0 至 3600000；0 表示立即快照。

行为：

- 返回第一个完成或需要关注的目标。
- 新用户输入会结束等待。
- 只有 commentary 更新不会唤醒等待。
- 超时返回所有目标的最新进度摘要。
- 使用上次返回的 cursor 可以避免重复收到已交付的最终文本。
- 单个目标失败会出现在 `errors` 中。

使用规则：

- 不要高频轮询。
- 需要等待时，使用一次有界调用。
- 任务可以并行时，一次等待多个目标。
- 有回调时，优先让回调唤醒父 thread，不依赖持续等待。

## send_message_to_thread

用途：向已有 thread 发送后续消息。

关键输入：

- `threadId`
- `hostId`（已知时）
- `prompt`
- 可选 `model`、`thinking`

边界：

- 只向创建它的父 thread 发送回调，不向无关 thread 发送。
- 消息会显示为目标 thread 中的用户可见消息。
- prompt 要写清楚任务、范围、完成标准和是否需要继续回调。
- 消息会尽快投递；目标 thread 正在运行时，可能在一个消息边界或当前工具调用完成后送达。
- ChatGPT thread 的 `model` 和 `thinking` 覆盖不适用。

## set_thread_title

用途：重命名 Codex thread 或 ChatGPT 会话。

关键输入：

- `title`
- `threadId`：省略时修改当前 thread。
- `hostId`
- `source`：`codex` 或 `chatgpt`

使用规则：

- 标题要包含任务或 ticket 标识，便于用户在侧栏识别。
- 不用标题传递状态或权限。

## set_thread_archived

用途：归档或取消归档 thread。

关键输入：

- `archived`：`true` 或 `false`
- `threadId`：省略时目标是当前 thread
- `hostId`
- `source`

使用规则：

- 任务完成、结果记录后可归档。
- 归档不是删除，之后可以取消归档继续使用。
- 不要归档仍在运行或仍需要用户查看的 thread。
- 清理 ticket thread 前，父 thread 先完成合并和验收。

## delete_thread

用途：永久删除 Codex thread 或 ChatGPT 会话。

关键输入：

- `threadId`
- `hostId`
- `source`

边界：

- 只在用户明确要求永久删除时使用。
- 用户必须确认目标 thread。
- 删除 Codex thread 也会删除其 subagent chats 和附加 side chats。
- 不要用它做普通清理；普通清理用归档。

## move_thread_to_project

用途：把 thread 移入项目，或从项目中移出。

关键输入：

- `threadId`
- `projectId`：null 表示移出项目
- `source`
- `hostId`
- `beforeThreadId`：可选排序

边界：

- ChatGPT 会话需要 ChatGPT 项目。
- 远程 Codex thread 不能变成 projectless。
- 本地 Codex thread 加入 ChatGPT 项目时，需要用户确认。
- 额外的源仓库访问权限需要用户在侧栏移动。

## move_thread_to_sidebar_section

用途：把 thread 移到 pinned、自定义 section 或普通列表。

关键输入：

- `threadId`
- `sectionId`：`pinned`、自定义 section ID，或 `null`
- `hostId`
- `beforeThreadId`：可选排序

## open_in_codex

用途：在 Codex app 中打开文件、Page、浏览器标签、终端或 review。

关键输入：

- `target`
- `threadId`：默认是当前 thread
- `placement`：`right` 或 `bottom`

边界：

- 它只改变界面展示，不改变 thread 状态。
- 打开页面不等于任务完成或验证完成。

## navigate_to_codex_page

用途：把最近聚焦的主窗口导航到指定 thread 或会话。

关键输入：

- `threadId`

## handoff_thread

用途：在 checkout 和 Codex worktree 之间，或两个 host 之间移动 thread。

关键输入：

- `threadId`
- `destinationHostId`：省略时在当前 host 的 checkout/worktree 间切换
- `followUpPrompt`：可选，handoff 成功后发送

边界：

- 运行中的 thread 会被中断。
- 云端 handoff 不支持。
- 只能移动其他 thread，不能移动当前调用 thread。
- 目标 host 必须在可用 host 列表中。

## get_handoff_status

用途：查询 `handoff_thread` 的进度。

关键输入：

- `operationId`
- `afterRevision`
- `waitMs`：0 至 60000

使用规则：

- 派发后先查一次。
- 用 `afterRevision` 等待状态变化。
- 不要对未变化的 revision 高频轮询。

## 版本检查

如果工具参数和本文不一致：

1. 以当前 MCP tool schema 为准。
2. 不修改业务任务来适配旧文档。
3. 如缺少工具，按主 skill 的降级表处理。
4. 不要伪造工具返回或 thread ID。
