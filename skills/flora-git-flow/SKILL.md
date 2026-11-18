---
name: flora-git-flow
description: 创建、刷新、合并和清理 Flora 任务的 Git 分支和 worktree。
---

# Flora Git Flow

## 职责与路由

调用方指定资源负责人、仓库、任务标识和本次操作。
资源负责人统一创建、合并和清理分支及 worktree。
执行者使用分配的工作区。
调用方负责会话、实现和验收，并记录资源归属。
已有资源传入绝对路径、分支和预期分支头。

| 操作 | 读取文件 |
| --- | --- |
| 准备单个任务工作区 | [单任务工作区](references/task.md) |
| 准备集成或子任务工作区 | [多任务工作区](references/delivery.md) |
| 刷新、合并或清理分支和 worktree | [集成与清理](references/integration.md) |

只读取本次操作对应的文件。

## 目录与命名

新建 worktree 统一使用以下默认路径：
`workspace_root` 是 `~/.worktrees/<repo-key>/<slug>`。
单任务使用 `<workspace_root>/task`。
集成工作区使用 `<workspace_root>/integration`。
子任务使用 `<workspace_root>/<id>-<task-slug>`。
调用工具和返回路径前，将 `~` 展开为绝对路径。

`<repo-key>` 默认取 `git worktree list --porcelain` 中主工作区的目录名。
同一仓库的所有 worktree 沿用同一标识。
核验仓库归属时，将 `git rev-parse --git-common-dir` 解析为绝对路径后比较。
同名仓库冲突时，追加来源标识，分开存放。

用户指定的路径和分支优先，其次采用仓库命名约定。
没有命名约定时，新建目标分支使用 `codex-<slug>`。
`<slug>` 使用小写字母、数字和短横线。
已有资源沿用记录的绝对路径，不自动搬迁。

## 操作与完成条件

1. 核验仓库、资源归属和操作前提。
   - 同名路径或分支已存在时，核验 worktree 登记和归属后复用。
   - 归属不明、分支头不符或隔离受阻时，停止操作并保留现场。
2. 按选中的参考文件执行本次操作。
   - 保留已有改动，禁止自动 stash、reset 或覆盖。
   - 任务改动提交到任务分支，禁止直接提交到 `main` 或 `master`。
   - 资源负责人串行执行刷新、合并和清理。
3. 从 Git 读回操作后的实际状态。
   - 工作区操作核对路径、分支和 HEAD。
   - 删除操作核对 worktree 登记和分支是否已移除。
4. 返回结果和未完成项。
   - 返回绝对路径、分支、提交 SHA 和本次操作的完成证据。
   - 部分成功时，列出已完成操作、剩余资源和失败原因。
   - 保留剩余资源，恢复时只补做未完成项。
