---
name: spec-to-ship
description: 按顺序执行需求澄清、本地规范、ticket 拆分和逐 ticket 独立实现。固定使用集成分支和独立 worktree。用于从需求讨论推进到多张 ticket 的实现，或要求每一步使用独立上下文时。
---

# Spec to Ship

## 流程

1. 调用 `grill-with-docs` 确认需求。
2. 确定集成分支和目标分支。
   - 当前分支是 `main` 或 `master` 时，创建集成分支 `<feature-slug>` 和集成 worktree `<repo>-worktrees/<feature-slug>/integration`。不询问确认。目标分支是集成分支。
   - 当前分支不是 `main` 或 `master` 时，询问当前分支是否作为集成分支。回答“是”时，目标分支是当前分支，当前 worktree 是集成 worktree。回答“否”时，停止并询问方案。
   - 当前目录不是 Git 仓库、工作区不干净或 HEAD 分离时，停止并询问用户。
   - `<feature-slug>` 使用小写短横线格式。`<repo>` 是仓库根目录名。创建新分支或新 worktree 时，同名对象已存在则停止并询问用户。
3. 在集成 worktree 中调用 `to-spec` 和 `to-tickets`，跳过 `to-tickets` 的拆分确认。
   - 本地 tracker 的规范目录是 `<integration-worktree>/.scratch/<feature-slug>/`。记录绝对路径 `SPEC_DIR`。
   - 规范目录被 Git 忽略时不提交；未被忽略时提交到集成分支。
   - 外部 tracker 记录 issue 标识或 URL。
4. 按依赖顺序执行 ticket。每张 ticket 使用独立 worktree 和独立上下文，并从目标分支创建分支 `<feature-slug>/<NN>-<slug>` 和 worktree `<repo>-worktrees/<feature-slug>/<NN>-<slug>`。
   - 创建独立实现上下文。优先使用 `mcp__codex_app__create_thread`，否则使用 subagent。
   - 传入 ticket worktree、ticket 分支、目标分支、ticket 引用和 `SPEC_DIR`。外部 tracker 传 issue 标识或 URL。
   - 上下文以 ticket worktree 为工作目录，确认当前分支等于 ticket 分支。
   - 分支不一致时停止。分支一致时调用 `implement`，提交到 ticket 分支，运行检查。
5. 合并 ticket。
   - 上下文先合并目标分支到 ticket 分支，解决冲突，重新运行检查。
   - 确认集成 worktree 当前分支是目标分支。不一致时停止，一致时运行 `git merge --no-ff <ticket-branch>`。
   - 目标分支检查通过后，标记 ticket 完成，尝试使用 `mcp__codex_app__set_thread_archived` 归档 thread，删除 ticket worktree 和 ticket 分支。
   - 检查失败时保留 ticket worktree 和分支，停止。冲突交回同一上下文，不在主上下文解决。
6. 报告目标分支、集成 worktree、规范位置或 tracker 标识、ticket 列表和合并提交。保留集成分支和集成 worktree，不自动合并到 `main` 或 `master`。

## 规则

- 主上下文只编排和汇总，不实现 ticket。
- 依赖未完成的 ticket 不启动。
- 禁止直接向 `main` 或 `master` 提交 ticket。
- 用户只要求规划时，完成步骤 1 至 3 后停止。
- skill 调用细节以各自说明为准。
