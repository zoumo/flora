# 个人 Skills

本目录只存放个人编写、供外部使用的 skill。
每个 skill 使用独立目录：`skills/<name>/SKILL.md`。
目录名使用小写字母和连字符。
辅助脚本、模板和资源放在同一目录。

`SKILL.md` 说明用途、触发条件和操作步骤。
共享准则可引用 `principle/` 中的文档。

## 自有 Skill

- [deepmodule-design](deepmodule-design/SKILL.md)：设计语言无关的深模块，用 TypeSpec 定义接口和数据结构。
- [harness-agent](harness-agent/SKILL.md)：初始化 harness、合并根入口，并配置后续 Agent 的文档与写入规则。
- [less-is-more](less-is-more/SKILL.md)：简化代码、接口和架构，减少不必要的概念与机制。
- [spec-to-ship](spec-to-ship/SKILL.md)：从需求澄清推进到规范、ticket 拆分和逐 ticket 独立实现。

仓库内部的写作规范存放在 `.agent/skills/`。
