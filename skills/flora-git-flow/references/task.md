# 单任务工作区

先读取[基线与路径](baseline.md)，确定基线并检查路径约束。

1. 读取仓库根目录、当前分支和工作区状态。
   - 运行 `git rev-parse --show-toplevel`、`git branch --show-current` 和 `git status --short`。
   - 当前目录不是 Git 仓库或基线无法确定时，报告受阻。
2. 确认目标分支和工作目录。
   - 调用方明确指定已有工作区时，核验后复用。
   - 只指定分支时，查询 worktree 登记，避免重复检出。
   - 没有可复用的工作区时，从确定的基线创建任务分支和独立 worktree。
   - 基线、目标和隔离方式已确定时，直接创建，不额外询问。
   - 按入口的统一目录规则，使用 `<workspace_root>/task`。
   - 复用工作区有未提交改动时，确认改动归属后再写入。
   - 新 worktree 只包含基线提交，原工作区的未提交改动保留原处。
   - 分支已创建而 worktree 创建失败时，报告残留分支，保留现场。
3. 核验工作区和基线。
   - 在目标目录读取 `pwd`、`git branch --show-current`、`git rev-parse HEAD` 和 `git status --short`。
   - 路径或分支不一致时，停止修改。
4. 返回工作区信息。
   - 返回 `workspace_root`、绝对工作目录、任务分支、基线 SHA 和基线选择记录。

任务完成后保留工作区和任务分支，不自动合并到 `main` 或 `master`。
