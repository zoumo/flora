# 集成与清理

调用方决定验证时机，并传入验证对应的分支头。
本文件使用本地目标分支当前 HEAD，不自行更新远端引用。

## 刷新子任务分支

前置条件：执行者已完成本轮写入。

1. 确认子任务工作区干净且分支头符合预期。
   - 核对子任务路径、当前分支和调用方传入的 SHA。
2. 将本地目标分支合入子任务分支。
   - 在子任务 worktree 中运行 `git merge <target-branch>`。
   - 发生冲突时，运行 `git merge --abort`。保留工作区，报告冲突。
3. 返回实际分支头。
   - 运行 `git rev-parse HEAD`。
   - 分支头变化时，通知调用方重新判断证据是否有效。

完成条件：目标提交已是子任务 HEAD 的祖先，且工作区干净。

## 合并子任务

前置条件：调用方已完成要求的验证，并允许合并。

1. 核验子任务分支头与通过验证的 SHA 一致。
   - SHA 不一致时停止，交回调用方安排重新验证。
2. 核验集成工作区干净且分支为目标分支。
3. 合并子任务分支。
   - 运行 `git merge --no-ff <task-branch>`。
   - 发生冲突时，运行 `git merge --abort`。保留资源，交回调用方。
4. 返回合并提交和实际状态。
   - 运行 `git rev-parse HEAD` 和 `git status --short`。
   - 调用方继续执行集成检查，不把合并成功当作验收通过。

完成条件：目标分支包含通过验证的 SHA，且集成工作区干净。

## 清理临时子任务资源

前置条件：调用方要求的验收通过，且执行者已停止写入临时工作区。

1. 确认临时资源属于本次任务。
2. 确认临时工作区没有待保留文件。
   - `git status --short --untracked-files=all --ignored` 必须为空。
3. 确认子任务分支已完全合入目标分支。
   - 运行 `git merge-base --is-ancestor <task-branch> <target-branch>`。
4. 删除临时 worktree。
   - 运行 `git worktree remove <task-worktree>`，禁止 `--force`。
5. 删除临时分支。
   - 运行 `git branch -d <task-branch>`，禁止 `-D`。
6. 读取清理后的实际状态。
   - 用 `git worktree list --porcelain` 和 `git branch --list <task-branch>` 确认资源已移除。

完成条件：临时 worktree 登记和分支都已移除。
默认保留集成分支和集成 worktree。
会话结束不能作为删除资源的依据。
