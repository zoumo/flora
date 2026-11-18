# 集成与清理

使用本地目标分支当前 `HEAD`。调用方决定验证时机。

## 刷新和合并

| 操作 | 前提 | 执行 | 核验 |
| --- | --- | --- | --- |
| 刷新子任务分支 | 执行者已停止本轮写入。子任务工作区干净，`HEAD` 符合预期 | 在子任务 worktree 中执行 `git merge <target-branch>` | 子任务 `HEAD` 包含目标提交，且工作区干净 |
| 合并子任务 | 验证通过，且调用方已授权合并。子任务 `HEAD` 等于通过验证的 SHA。集成工作区干净，且已检出目标分支 | 在集成 worktree 中执行 `git merge --no-ff <task-branch>` | 目标分支包含通过验证的 SHA，且集成工作区干净 |

如果合并产生冲突，执行 `git merge --abort`，保留工作区和分支并报告冲突。
如果刷新改变 `HEAD`，交回调用方确认验证结果是否仍有效。
合并成功后，调用方继续执行集成检查。

## 清理临时子任务资源

清理前，调用方须确认验收通过。执行者须停止写入临时工作区。

1. 确认临时工作区无待保留文件。
   `git status --short --untracked-files=all --ignored` 的输出必须为空。
2. 确认子任务分支已合入目标分支。
   `git merge-base --is-ancestor <task-branch> <target-branch>` 必须成功。
3. 用 `git worktree remove <task-worktree>` 删除临时 worktree。
4. 用 `git branch -d <task-branch>` 删除临时分支。
5. 核对 worktree 登记和分支是否已移除。

禁止强制删除。默认保留集成分支和集成 worktree。
