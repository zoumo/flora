# flora

个人 Agent skills、工作流、开发准则和角色说明的集中存放地。

## 目录

| 路径 | 用途 |
| --- | --- |
| [skills/](skills/) | 个人编写、供外部使用的 skill |
| [.agent/skills/](.agent/skills/) | 仓库内部使用的规范 skill |
| `.codex/skills/`、`.claude/skills/` | 指向内部规范 skill 的符号链接 |
| [principle/](principle/) | 开发准则、工程约定和协作原则 |
| [agents/](agents/) | 预定义 Agent 角色、职责和工作方式 |
| [scripts/](scripts/) | 安装与维护脚本 |

工作流先随所属 skill 或角色维护，出现独立的复用需求后再扩展目录。

## Skill 管理

使用 Skills Manager 统一管理 skill，flora 保存维护源和安装清单。

- 自有 skill：放在 `skills/<name>/SKILL.md`，辅助脚本和资源放在同一目录。
- 开源 skill：在 [skill-manager.yaml](skill-manager.yaml) 记录来源，由 Skills Manager 获取和更新。
- 本机中央库、数据库、部署副本由 Skills Manager 管理，不提交到本仓库。

脚本使用 Bun 1.3.14 或更新版本。

安装开发依赖：

```bash
bun install --frozen-lockfile
```

检查 TypeScript 类型并运行测试：

```bash
bun run typecheck
bun test
```

清单只保存元数据。
顶层 `deploy_to` 指定全部 skill 共享的部署目标。
`sources` 按 `ref` 分组，每组列出来源包含的 skill。
Git 来源的 `ref` 使用仓库 URL。
子目录 skill 使用相对 `path`，`branch` 指定分支。

`presets` 单独列出每个分组包含的 skill 名称。
删除 skill 时，脚本也会删除 preset 中的引用。

添加 marketplace skill：

```bash
bun scripts/skill-manager.ts add owner/repo@skill
```

添加 Git 来源时，用 `--name` 指定 skill 名称：

```bash
bun scripts/skill-manager.ts add https://github.com/owner/repo/tree/main/skills/example --name example
```

`--preset` 记录分组，支持重复使用。

删除清单条目：

```bash
bun scripts/skill-manager.ts remove example
```

`add` 同步安装、分组和部署后保存清单。
`remove` 同步删除中央库条目和部署后保存清单。
`sync` 删除清单外的第三方 skill，并同步清单中的 skill。
本地或内部来源的 skill 保留。
`--dry-run` 只展示清单，不修改文件或本机状态。

预览第三方 skill 安装计划（不安装、不部署）：

```bash
bun scripts/skill-manager.ts sync --dry-run
```

安装清单中的 skill，按清单中的 `deploy_to` 部署：

```bash
bun scripts/skill-manager.ts sync
```

脚本可从任意工作目录执行。
CLI 缺失时优先使用 Cargo 安装。
否则按系统和架构通过 `gh-proxy.org` 下载发行版。
已有中央库条目会保留；重复执行仍会部署。部署冲突由 Skills Manager 拒绝覆盖，需根据报告处理。

## 输出语言

[AGENTS.md](AGENTS.md) 指引 Agent 按输出语言选用规则。
中文遵循[简明技术中文](.agent/skills/simplified-technical-chinese/SKILL.md)。
英文遵循 [ASD-STE100](.agent/skills/asd-ste100/SKILL.md)。
两个 skill 存放在 `.agent/skills/`。
`.codex/skills/` 和 `.claude/skills/` 通过符号链接引用它们。

参见[个人 skill 说明](skills/README.md)。
