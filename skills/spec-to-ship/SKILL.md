---
name: spec-to-ship
description: 按顺序执行需求澄清、本地规范、ticket 拆分和逐 ticket 独立实现。用于从需求讨论推进到多张 ticket 的实现，或要求每一步使用独立上下文时。
---

# Spec to Ship

## 流程

1. 调用 `grill-with-docs` 询问需求。范围、约束、验收条件和未决事项全部确认后结束。
2. 调用 `to-spec` 写本地规范。项目没有配置 issue tracker 时，用本地文件作为 tracker。
3. 调用 `to-tickets` 拆分任务。
4. 为每张 ticket 建立独立实现上下文。优先使用 Codex thread/chat。thread/chat 不可用时，使用 subagent。
5. 按 ticket 依赖顺序执行。一张 ticket 只在一个上下文中实现。
6. 报告规范路径、tracker 位置或标识、ticket 列表，以及每张 ticket 使用的上下文。

## 规则

- 上述 skill 的调用细节以其自身说明为准。本 skill 不复述其步骤。
- 主上下文只负责编排和汇总。主上下文不直接实现 ticket。
- 依赖未完成的 ticket 不启动实现。
- 用户只要求规划时，完成步骤 1 至 3 后停止。
