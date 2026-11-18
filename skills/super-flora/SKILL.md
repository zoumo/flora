---
name: super-flora
description: 所有工作的统一入口。按交付目标匹配调查、设计、修复、功能、重构、评审、操作或写作 playbook，只读取选中的流程并按任务核验完成证据。
disable-model-invocation: true
argument-hint: "[--investigation | --design | --bug-fix | --feature | --refactoring | --review | --operations | --writing] <任务>"
---

# Super Flora

## 选择当前阶段

先从完整请求确定交付物、顺序和停止点。“继续”时，先核对已有产物和进度。
用户明确指定流程时，在本次范围内采用指定项。
按当前阶段要交付的结果选择 playbook，只读取选中的文件。

| Playbook | 匹配规则 | 默认停止点 |
| --- | --- | --- |
| [调查](playbooks/investigation.md) | 要解释、诊断结论、事实核对或方案输入 | 输出有依据的结论 |
| [设计](playbooks/design.md) | 要方案、规范、计划或取舍 | 输出本次要求的设计产物 |
| [缺陷修复](playbooks/bug-fix.md) | 要修复代码或系统故障，恢复预期行为 | 原故障修复并验证 |
| [功能](playbooks/feature.md) | 要新增或改变产品、代码的行为 | 验收条件通过 |
| [重构](playbooks/refactoring.md) | 要保持代码行为并改变结构 | 行为一致且结构达到目标 |
| [评审](playbooks/review.md) | 要 finding、风险或验收结论 | 输出结论和必要证据 |
| [操作](playbooks/operations.md) | 要系统操作、状态更新或持续跟进结果 | 达到目标、确认失败或阻塞 |
| [写作](playbooks/writing.md) | 要文档、报告、图表或其他表达产物 | 目标产物可读取 |

“看看原因”走只读调查。“检查并修复”走修复，诊断属于修复步骤。
“设计后给我看”停在方案。“写好并同步本地”先写作，再操作。
报告只是调查结果的呈现形式时，留在调查流程。

目标明确但表中没有对应项时，直接采用最短可行步骤。
意图不清时先做只读检查，只询问仍阻止交付的问题。

## 执行到交付

单项结果可以直接核验时，在当前上下文完成，给出结果和依据。
例如查询一次 CI 状态，读取指定流水线并报告状态。
命令数量不决定是否需要待办。

主 Agent 负责整项请求。涉及依赖、等待或交接时，用待办记录剩余工作。
阶段完成后，带着产物位置、已确认决定和有效证据进入下一个已授权阶段。
到达用户指定的停止点，或全部交付物齐备时，交付结果。
受阻时说明缺少什么，以及影响哪项交付。

分工前核对宿主的创建条件，允许时优先使用独立 thread。
管理工作区时调用 `flora-git-flow`，管理独立上下文时调用 `codex-sub-thread`。
选择辅助 skill 前，按需查阅[调用边界](references/skill-usage.md)。
判断验证范围或证据能否复用时，查阅[完成证据](references/completion-evidence.md)。
