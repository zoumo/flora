---
name: spec-to-ship
description: 按顺序执行需求澄清、本地规范、ticket 拆分和逐 ticket 独立实现。用于从需求讨论推进到多张 ticket 的实现，或要求每一步使用独立上下文时。
---

# Spec to Ship

## 流程

1. 调用 `grill-with-docs` 询问需求。范围、约束、验收条件和未决事项全部确认后结束。
2. 调用 `to-spec` 写本地规范。项目没有配置 issue tracker 时，用本地文件作为 tracker。
3. 调用 `to-tickets` 拆分任务。拆分完成即视为确认，跳过 `to-tickets` 的同意询问。
4. 询问用户期望的 Git flow，等待两个问题的回答：
   - 目标分支：使用当前分支，或新建独立的 worktree 和分支。
   - 每张 ticket 的 commit 协作方式：在独立的 worktree 开发，完成后合并到目标分支，或直接在目标分支开发。
5. 按 ticket 依赖顺序执行。只有执行到对应 ticket 时，才创建独立实现上下文。
   先尝试 `mcp__codex_app__create_thread`。如果没有此工具，使用 subagent。
   将用户选择的 Git flow 传给每个实现上下文。
   每个实现上下文必须调用 `implement` skill 实现对应的 ticket。
   一张 ticket 只在一个上下文中实现。
   当 ticket 完成时，尝试使用 `mcp__codex_app__set_thread_archived` 归档 ticket 的 thread。
6. 报告规范路径、tracker 位置或标识、ticket 列表，以及每张 ticket 使用的上下文。

## 规则

- 上述 skill 的调用细节以其自身说明为准。本 skill 不复述其步骤。
- 主上下文只负责编排和汇总。主上下文不直接实现 ticket。
- 依赖未完成的 ticket 不启动实现。
- 用户只要求规划时，完成步骤 1 至 3 后停止。
