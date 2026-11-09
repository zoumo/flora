---
name: spec-to-ship
description: 按顺序执行需求澄清、本地规范、ticket 拆分和逐 ticket 独立实现。固定使用集成分支和独立 worktree。用于从需求讨论推进到多张 ticket 的实现，或要求每一步使用独立上下文时。
disable-model-invocation: true
argument-hint: "[--fast | --strict]"
---

# Spec to Ship

## Git Flow

- 当前分支是 `main` 或 `master` 时，创建集成分支 `<feature-slug>` 和集成 worktree `<repo>-worktrees/<feature-slug>/integration`。不询问确认。目标分支是集成分支。
- 当前分支不是 `main` 或 `master` 时，询问当前分支是否作为集成分支。回答“是”时，目标分支是当前分支，当前 worktree 是集成 worktree。回答“否”时，停止并询问方案。
- 当前目录不是 Git 仓库、工作区不干净或 HEAD 分离时，停止并询问用户。
- `<feature-slug>` 使用小写短横线格式。`<repo>` 是仓库根目录名。创建新分支或新 worktree 时，同名对象已存在则停止并询问用户。

## 运行模式

- 快速模式（推荐）：每张 ticket 只做必要测试，不做全量回归和验证。全部 ticket 合并后，做一次全量 `code-review`、验证和完整测试。
- 严格模式：每张 ticket 做完整测试和验证。
- 输入包含 `--fast` 时，选择快速模式。
- 输入包含 `--strict` 时，选择严格模式。
- 输入未提供模式时，普通任务选择快速模式。
- 输入未提供模式时，高风险合同、迁移、发布或跨仓库真实联调选择严格模式。
- 同时包含 `--fast` 和 `--strict` 时，停止并询问用户。

## Ticket 协作

- 独立 thread（默认）：用 `mcp__codex_app__create_thread` 创建 ticket thread。工具未加载时先加载。只有工具加载或调用失败时，才使用 subagent。
- 启动 ticket thread 时，传入集成 thread ID 和回调要求。集成 thread ID 从环境变量 `CODEX_THREAD_ID` 获取；变量为空时询问用户。
- ticket thread 完成实现和提交后，将目标分支合并到 ticket 分支，重新运行检查。
- ticket thread 完成、失败或阻塞时，用 `mcp__codex_app__send_message_to_thread` 回调集成 thread，然后结束当前 turn。ticket thread 不合并到集成分支。
- 回调写明 ticket、分支、worktree、提交 SHA、检查结果、合并状态和遗留风险。
- 集成 thread 不调用 `mcp__codex_app__wait_threads`、`wait_agent` 等待 ticket thread。它可以启动其他 ticket，或结束当前 turn 等待回调。
- subagent（备用）：ticket 完成实现、提交、目标分支合并和检查后，直接返回最终结果，不发送回调。
- 调用本 skill 即授权创建 ticket thread，并授权 ticket thread 发送最终状态回调。

## 流程

1. 调用 `grill-with-docs` 确认需求。
2. 按 Git Flow 章节确定集成分支和目标分支。
3. 按运行模式章节确定运行模式。
4. 在集成 worktree 中调用 `to-spec` 和 `to-tickets`，跳过 `to-tickets` 的拆分确认。
   - 将运行模式和对应要求写入规范及 ticket 验收标准。
   - 本地 tracker 的规范目录是 `<integration-worktree>/.scratch/<feature-slug>/`。记录绝对路径 `SPEC_DIR`。
   - 规范目录被 Git 忽略时不提交；未被忽略时提交到集成分支。
   - 外部 tracker 记录 issue 标识或 URL。
5. 在启动 ticket 实现前，向用户输出简短执行前报告，只包含：
   - 最终集成分支。
   - 执行模式：快速模式或严格模式。
   - 预估时间：从开始 ticket 到最终完成的总时长。无法可靠估算时写“待确认”。
6. 按依赖顺序执行 ticket。每张 ticket 使用独立 worktree，并按 Ticket 协作章节选择独立 thread 或 subagent。从目标分支创建分支 `<feature-slug>/<NN>-<slug>` 和 worktree `<repo>-worktrees/<feature-slug>/<NN>-<slug>`。
   - 启动 ticket 上下文。
   - 传入 ticket worktree、ticket 分支、目标分支、ticket 引用和 `SPEC_DIR`。外部 tracker 传 issue 标识或 URL。
   - 上下文以 ticket worktree 为工作目录，确认当前分支等于 ticket 分支。
   - 分支不一致时停止。分支一致时调用 `implement`，提交到 ticket 分支，运行检查。
7. 合并 ticket。
   - 收到独立 thread 完成回调或 subagent 返回结果后，确认 ticket 已提交，目标分支已合并到 ticket 分支，检查通过。
   - 确认集成 worktree 当前分支是目标分支。不一致时停止，一致时运行 `git merge --no-ff <ticket-branch>`。
   - 目标分支检查通过后，标记 ticket 完成。独立 thread 尝试使用 `mcp__codex_app__set_thread_archived` 归档 thread。删除 ticket worktree 和 ticket 分支。
   - 检查失败时保留 ticket worktree 和分支，停止。冲突交回同一上下文，不在主上下文解决。
8. 报告最终结果：目标分支、集成 worktree、规范位置或 tracker 标识、ticket 列表和合并提交。保留集成分支和集成 worktree，不自动合并到 `main` 或 `master`。

## 规则

- 主上下文只编排和汇总，不实现 ticket。
- 依赖未完成的 ticket 不启动。
- 禁止直接向 `main` 或 `master` 提交 ticket。
- 用户只要求规划时，完成步骤 1 至 5 后停止。
- skill 调用细节以各自说明为准。
