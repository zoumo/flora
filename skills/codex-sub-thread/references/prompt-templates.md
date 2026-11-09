# Prompt templates

替换尖括号中的内容。
不要复制不适用的段落。
所有 prompt 都会显示给用户或目标 thread，不能包含密钥。

## 1. 创建 sub-thread，带回调

```text
你是独立 sub-thread，负责一个完整交付物。

父 thread ID: <父 thread ID>
回调目标: 创建它的父 thread
回调规则: 完成、失败、阻塞或需要决策时，向父 thread 发送消息。
工作目录: <绝对路径>
任务: <目标、范围、约束、验收标准>
交付物: <文件、提交、报告或测试结果>
禁止事项: <不要合并、不要推送、不要修改指定目录等>

回报规则:
1. 完成、失败、阻塞或需要父 thread 决策时，调用 mcp__codex_app__send_message_to_thread。
2. threadId 使用父 thread ID: <父 thread ID>。
3. 消息格式:
   状态: completed | failed | blocked
   任务: <一句话>
   threadId: <你的 threadId>
   工作区: <绝对路径>
   分支: <branch>
   提交: <SHA>
   检查: <命令> -> <结果>
   产物或变更: <文件或行为>
   风险: <未验证项、兼容性、已知缺陷>
   需要父 thread: <合并、决策、重试或无需操作>
4. 发送成功后结束当前 turn。
5. 无法发送时，停止并报告本地错误。不要猜父 thread ID。
```

## 2. 创建 sub-thread，不带回调

只在父 thread 可以用 `wait_threads` 或 `read_thread` 观察结果时使用。

```text
你是独立 sub-thread，负责一个完整交付物。

工作目录: <绝对路径>
任务: <目标、范围、约束、验收标准>
交付物: <文件、提交、报告或测试结果>
禁止事项: <不要合并、不要推送、不要修改指定目录等>

完成后在最终回答中报告:
状态、分支、提交 SHA、检查命令和结果、遗留风险、需要父 thread 做什么。
不要向其他 thread 发送消息。
```

## 3. sub-thread 完成回调

```text
状态: completed
任务: <任务名>
threadId: <sub-thread ID>
工作区: <绝对路径>
分支: <branch>
提交: <SHA>
检查: <命令> -> <结果>
产物或变更: <文件或行为>
风险: <未验证项、兼容性、已知缺陷>
需要父 thread: 合并并清理 worktree；无需决策。
```

## 4. sub-thread 失败回调

```text
状态: failed
任务: <任务名>
threadId: <sub-thread ID>
工作区: <绝对路径>
分支: <branch>
提交: <SHA 或 none>
失败点: <命令或步骤>
错误: <关键错误文本，不含密钥>
已尝试: <1 至 3 条>
需要父 thread: <重试、换方案、补充权限或终止任务>。
```

## 5. sub-thread 阻塞回调

```text
状态: blocked
任务: <任务名>
threadId: <sub-thread ID>
工作区: <绝对路径>
分支: <branch>
阻塞原因: <缺少权限、需要选择方案、外部系统不可用、需求冲突>
可选方案: <A / B / C>
建议: <推荐方案和理由>
需要父 thread: 请用户决策后回复本 thread。
```

## 6. 父 thread 发起修复

```text
继续原任务，不要新建上下文。

检查发现: <问题>
影响: <为什么必须修复>
请在原工作区 <绝对路径> 修复。
完成标准: <测试、行为或输出>
提交到原分支: <branch>

修复后按原回调规则回报父 thread ID: <父 thread ID>。
```

## 7. 父 thread 询问状态

```text
请报告当前状态，不要开始新的范围。

请回答:
1. 当前进行到哪一步？
2. 是否遇到阻塞？
3. 已完成哪些检查？
4. 预计还需要哪些操作？

如果已经完成或阻塞，按原回调规则回报父 thread ID: <父 thread ID>。
```

## 8. 父 thread 接收结果后的确认

```text
已收到结果。不要继续修改。

请确认:
- 分支: <branch>
- 提交: <SHA>
- 检查: <命令和结果>

父 thread 将执行合并、归档和清理。你不合并共享分支。
```

## 9. handoff 后继续

```text
thread 已迁移到 <目标 host 或 worktree>。
请先确认当前工作目录和分支，再继续原任务。

不要重复已完成的步骤。
完成后按原回调规则回报父 thread ID: <父 thread ID>。
```

## 10. MCP 不可用时改用 subagent

```text
你是父 thread 的 subagent。当前环境没有可用的 Codex app thread MCP。
你没有独立 thread ID，不要尝试调用 send_message_to_thread 或其他 thread MCP。

父 thread ID: <父 thread ID，仅用于记录>
工作目录: <绝对路径>
任务: <目标、范围、约束、验收标准>
交付物: <文件、提交、报告或测试结果>
禁止事项: <不要合并、不要推送、不要修改指定目录等>

完成后直接返回:
状态、分支、提交 SHA、检查命令和结果、遗留风险、需要父 thread 做什么。
```

## 11. thread 登记表

父 thread 在本地工作记录中维护：

| threadId | clientThreadId | hostId | 工作目录 | 任务 | 分支 | 状态 | 回调 | 最后检查 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `<id>` | `<pending>` | `local` | `<path>` | `<task>` | `<branch>` | active | yes | `<command/result>` |

规则：

- `clientThreadId` 只用于等待创建完成，不传给 thread 工具。
- 用 `threadId` 发消息、读取和等待。
- 状态变化后更新表。
- 归档和清理后保留最终状态，便于审计。
