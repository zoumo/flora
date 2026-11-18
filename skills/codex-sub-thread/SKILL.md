---
name: codex-sub-thread
description: 创建独立 Codex sub-thread，选择同步等待或回调。创建工具不可用时回退到 subagent。也用于恢复、归档或迁移已有 thread。
---

# Codex Sub Thread

1. 检查 `mcp__codex_app__create_thread` 是否可用。工具未加载时，用 `tool_search` 查找。
   如果仍不可用，调用 `spawn_agent`，结束本流程。
2. 从环境变量 `CODEX_SESSION_ID` 读取父 thread ID。
3. 选择跟踪方式。如果当前轮需要结果，使用同步等待。如果父 thread 可以先继续，使用回调。
   使用回调前，确认父 thread ID 和回调工具可用。
4. 调用 `mcp__codex_app__create_thread` 创建 sub-thread。首条任务消息写明目标、工作目录和完成条件。
   如果使用回调，在首条消息中加入以下指令。

   > 目标完成或需要父 thread 介入时，调用 `mcp__codex_app__send_message_to_thread`。
   > 将 `threadId` 设为 `<父 thread ID>`。说明结果或需要父 thread 处理的事项。

   使用已准备的 worktree 时，选择 `local`，并在消息中写绝对路径。
   如果只返回 `clientThreadId`，用 `list_threads` 查找实际 `threadId`。如果仍在创建，报告创建中。

5. 按选定方式跟踪。
   - 如果使用同步等待，将 `threadId` 和 `hostId` 传给 `mcp__codex_app__wait_threads`。等待 sub-thread 完成或需要介入。
   - 如果使用回调，收到消息时处理结果或介入请求。

调用参数以当前工具定义为准。恢复、归档或迁移已有 thread 时，用 `tool_search` 查找对应工具。
