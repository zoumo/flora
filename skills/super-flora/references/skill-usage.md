# Skill 使用

先核对辅助 skill 的实际动作是否符合本次交付范围。
只需聊天草案时，直接给出内容。创建文件、发布 ticket 或委派沿用已有授权。
调用前只传任务、已有决定、允许产物和停止点。
不重复已经完成的规划或确认。

## Matt skills

| Skill | 调用条件 |
| --- | --- |
| `grill-with-docs` | 通过交互澄清设计，并允许同时维护 ADR 和术语表 |
| `grilling` | 只需压力测试方案或决定，不要求设计文档 |
| `tdd` | 行为改动适合测试先行，测试位置已确认 |
| `to-spec` | 用户要求正式规范，且规范可以保存或发布 |
| `to-tickets` | 用户要求 ticket 或需要依赖拆分，且已有授权写入的目标位置 |
| `diagnosing-bugs` | 故障难以定位，需要建立反馈回路和根因证据 |
| `research` | 要求独立研究并允许委派和写入 Markdown 报告 |
| `implement` | 任务明确需要提交、完整测试和独立审查 |
| `code-review` | 评审代码改动与规范的一致性 |
| `codebase-design` | 需要模块、接口和 seam 设计词汇 |
| `prototype` | 用一次性产物回答设计问题 |

## 其他常用 skills

| Skill | 调用条件 |
| --- | --- |
| `less-is-more` | 需要减少概念、接口或机制 |
| `deepmodule-design` | 需要语言无关模块合同或 TypeSpec 设计 |
| `harness-agent` | 需要初始化或补充仓库 harness |
| `skill-creator` | 创建、修改或测试 skill |
| `writing-for-agents` | 编写 skill、AGENTS 或 Agent 文档 |
| `manage-skills` | 安装、更新、部署或检查 skill |

按任务选择所需项，不把本表作为每次任务的固定清单。

## 调用边界

辅助 skill 的步骤只补充当前 playbook。
辅助 skill 要求与用户停止点冲突时，保留用户边界。
不能完整遵守下游 skill 时，明确写出受限步骤。
不声称已经完成未实际执行的步骤。

