# 多任务工作区

## 准备集成工作区

先读取[基线与路径](baseline.md)，确定基线并检查路径约束。

1. 读取仓库根目录、当前分支和工作区状态。
   - 运行 `git rev-parse --show-toplevel`、`git branch --show-current` 和 `git status --short`。
   - 当前目录不是 Git 仓库或基线无法确定时，报告受阻。
2. 确认集成分支和工作目录。
   - 用户已指定目标时，优先采用指定目标。
   - 未指定目标且当前是主分支或 detached HEAD 时，从确定的基线创建集成分支和独立 worktree。
   - 基线、目标和隔离方式已确定时，直接创建，不额外询问。
   - 原工作区存在未提交改动时，保留改动。报告新分支只包含所选提交。
   - 未指定目标且当前分支是任务分支时，将当前分支作为集成分支。
   - 复用的集成工作区不干净时，保留改动并报告隔离受阻。
   - 创建前核验目标路径、分支和 worktree 登记。
   - 分支已创建而 worktree 创建失败时，报告残留分支，保留现场。
3. 记录集成基线。
   - 在集成目录核对当前分支，运行 `git rev-parse HEAD`。
4. 返回集成工作区信息。
   - 返回 `target_branch`、`integration_worktree`、`base_sha` 和 `workspace_root`。
   - 返回基线来源、远端检查结果及同步或冻结理由。

`workspace_root` 按入口的统一目录规则确定。
`integration_worktree` 默认是 `<workspace_root>/integration`。

## 准备子任务工作区

准备前，读取[路径约束](baseline.md#路径约束)，检查创建路径。

1. 确认调用方已允许启动子任务。
2. 读取本地目标分支当前 HEAD。
   - 记录 `<target-sha>`，子任务只从这个提交派生。
   - 子任务不另选远端基线。
3. 从目标分支创建子任务分支。
   - 默认分支名为 `<target-branch>-<id>-<task-slug>`。
   - 创建前核验目标路径、分支和 worktree 登记。
   - 运行 `git branch <task-branch> <target-sha>`。
4. 创建子任务 worktree。
   - 默认路径为 `<workspace_root>/<id>-<task-slug>`。
   - 运行 `git worktree add <task-worktree> <task-branch>`。
   - worktree 创建失败时，报告残留分支，保留现场。
5. 返回子任务工作区信息。
   - 核对实际路径、当前分支和 HEAD。
   - 返回绝对工作目录、任务分支和分支头 SHA。

完成条件：实际路径、分支和分支头与分配结果一致。
资源负责人核验后，才把工作区交给执行者。
review 使用待验证的现有 worktree，不另建 checkout。
