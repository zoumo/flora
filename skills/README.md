# 个人 Skills

本目录只存放个人编写、供外部使用的 skill。
每个 skill 使用独立目录：`skills/<name>/SKILL.md`。
目录名使用小写字母和连字符。
辅助脚本、模板和资源放在同一目录。

`SKILL.md` 说明用途、触发条件和操作步骤。
共享准则可引用 `principle/` 中的文档。

## 自有 Skill

- [super-flora](super-flora/SKILL.md)：所有工作的统一入口，按交付目标匹配调查、设计、修复、功能、重构、评审、操作或写作 playbook。
- [flora-git-flow](flora-git-flow/SKILL.md)：执行 Flora 的 Git 工作约定，管理任务分支和 worktree。
- [codex-sub-thread](codex-sub-thread/SKILL.md)：通过 Codex app MCP 创建、管理独立 sub-thread，并处理父子 thread 回调；MCP 不可用时回退到 subagent。
- [deepmodule-design](deepmodule-design/SKILL.md)：设计语言无关的深模块，用 TypeSpec 定义接口和数据结构。
- [harness-agent](harness-agent/SKILL.md)：初始化 harness、合并根入口，并配置后续 Agent 的文档与写入规则。
- [repo-harness-review](repo-harness-review/SKILL.md)：从 6 个维度评估仓库的 harness，给出证据和一项最小改进。
- [less-is-more](less-is-more/SKILL.md)：简化代码、接口和架构，减少不必要的概念与机制。

`super-flora` 负责意图匹配、分阶段执行和最终验收，按需调用 Git 和上下文管理 skill。
分支规则和上下文管理规则分别维护，流程文档只规定调用时机。

仓库内部的写作规范存放在 `.agent/skills/`。
