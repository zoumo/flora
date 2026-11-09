---
name: flora-flow
description: 按顺序执行需求澄清、本地规范、ticket 拆分和逐 ticket 独立实现。固定使用集成分支和独立 worktree。集成上下文处理简单协作，复杂实现和独立 review 委派给工作上下文。
disable-model-invocation: true
argument-hint: "[--fast | --strict]"
---

# Flora Flow

## Git Flow

- 当前分支是 `main` 或 `master` 时，创建集成分支 `<feature-slug>` 和集成 worktree `<repo>-worktrees/<feature-slug>/integration`。不询问确认。目标分支是集成分支。
- 当前分支不是 `main` 或 `master` 时，询问当前分支是否作为集成分支。回答“是”时，目标分支是当前分支，当前 worktree 是集成 worktree。回答“否”时，停止并询问方案。
- 当前目录不是 Git 仓库、工作区不干净或 HEAD 分离时，停止并询问用户。
- `<feature-slug>` 使用小写短横线格式。`<repo>` 是仓库根目录名。创建新分支或新 worktree 时，同名对象已存在则停止并询问用户。

## 运行模式

- 快速模式（推荐）：每张 ticket 只做必要测试，不做全量回归和验证。全部 ticket 合并后，由独立的 review 和验证上下文做一次全量 `code-review`、验证和完整测试。
- 严格模式：每张 ticket 由独立的 review 和验证上下文做完整测试和验证。
- 输入包含 `--fast` 时，选择快速模式。
- 输入包含 `--strict` 时，选择严格模式。
- 输入未提供模式时，默认选择快速模式。
- 仅当功能很复杂且改动量很大时，选择严格模式。
- 同时包含 `--fast` 和 `--strict` 时，停止并询问用户。

## 角色与职责

### 集成 thread 或 session

**工作模式**

- 负责流程决策、调度和汇总，并完成简单协作工作。
- 不执行复杂任务。需要修改实现、独立判断或长时间排查的工作必须委派。
- 不为每项操作新建上下文。能在当前 thread 连续完成的简单操作，直接完成。
- 不等待或轮询工作 thread。独立 thread 启动后结束当前 turn，收到回调再继续。

**职责**

- 确认 Git Flow 和运行模式。
- 检查 Git 状态，完成简单的规范整理、普通合并、聚焦检查和清理。
- 按依赖顺序委派复杂工作和独立 review，传递任务输入和返回要求。
- 接收结果并输出报告。普通合并、归档和清理只由集成 thread 完成。

**委派边界**

- coding、独立 `code-review`、完整测试和验证、复杂冲突处理、故障排查和多文件修改必须委派。
- 聚焦检查未通过时，不自行修复。交回 ticket 实现上下文，或委派新的修复上下文。
- 可以在集成 worktree 中编辑简单的规范、ticket 和流程状态。
- 不调用 `mcp__codex_app__wait_threads` 或 `wait_agent` 等待独立工作 thread。

### 工作 thread 或 subagent

工作上下文承接复杂规划、ticket 实现、复杂冲突处理、修复和独立 review 任务。

**工作模式**

- 需要独立观察、长时间执行或多个回调的工作，用 `mcp__codex_app__create_thread` 创建独立 thread。工具未加载时先加载。
- 短时、内部、完成后只需返回结果的委派，优先用 subagent。
- 工具不可用、集成 thread ID 不可得或创建失败时，改用 subagent。
- 每个上下文负责一个完整交付物。同一交付物的连续操作不拆给多个上下文。

**职责**

- 完成分配的工作，运行对应检查，并报告结果。
- 独立 thread 启动时接收集成 thread ID 和回调要求。集成 thread ID 从环境变量 `CODEX_THREAD_ID` 获取；变量为空时，由集成上下文询问用户。
- 独立 thread 在完成、失败或阻塞后，用 `mcp__codex_app__send_message_to_thread` 回调集成 thread，然后结束当前 turn。
- 回调写明任务、分支、提交 SHA、合并状态、检查结果和遗留风险。失败或阻塞时，另写原因和下一步。
- subagent 不发送回调，直接返回结果。
- ticket 实现上下文不合并到集成分支。

**授权**

- 调用本 skill 即授权创建独立 thread 和发送最终状态回调。

### review 和验证 thread 或 subagent

**工作模式**

- 必须新建独立上下文，不复用任何已有工作 thread 或 subagent。
- 创建方式、降级方式、回调和交接规则同工作 thread 或 subagent。

**职责**

- 执行 `code-review`、测试和验证，返回结论、测试结果和遗留风险。
- 不修改代码。严格模式下将缺陷交回原 ticket 实现上下文；原上下文不可用时，才新建修复上下文。

## 流程

1. **确认需求**（集成上下文）
   - 调用 `grill-with-docs` 确认范围、约束和验收标准。
2. **确定 Git Flow 和运行模式**（集成上下文）
   - 按 `Git Flow` 章节创建或确认集成分支、目标分支和集成 worktree。
   - 按 `运行模式` 章节确定运行模式。
3. **生成规范和 ticket**（集成上下文；复杂任务委派规划工作上下文）
   - 简单任务由集成上下文在集成 worktree 中调用 `to-spec` 和 `to-tickets`，跳过 `to-tickets` 的拆分确认。
   - 需求复杂、拆分复杂或当前上下文不足时，委派一个规划工作 thread 或 subagent。
   - 规划输入：需求、目标分支、运行模式、集成 worktree。
   - 规范：将运行模式和验收要求写入规范及每张 ticket。
   - 提交：规范目录 `<integration-worktree>/.scratch/<feature-slug>/` 未被 Git 忽略时提交到集成分支。
   - Tracker：本地规范返回绝对路径 `SPEC_DIR`；外部 tracker 返回 issue 标识或 URL。
   - 返回：`SPEC_DIR`、ticket 列表和总时长估算。
4. **输出执行前报告**（集成上下文）
   在启动 ticket 实现前，只输出以下 3 项：
   - 最终集成分支。
   - 执行模式：快速模式或严格模式。
   - 预估时间：从开始 ticket 到最终完成的总时长。无法可靠估算时写“待确认”。
5. **实现 ticket**（每张 ticket 一个 ticket 实现 thread 或 subagent）
   - 输入：ticket 引用、`SPEC_DIR`、目标分支、运行模式、ticket 分支 `<feature-slug>/<NN>-<slug>` 和 worktree `<repo>-worktrees/<feature-slug>/<NN>-<slug>`。外部 tracker 传 issue 标识或 URL。
   - 工作：从目标分支创建 ticket 分支和 worktree。
   - 约束：当前分支不等于 ticket 分支时停止并报告。
   - 工作：在 ticket worktree 中调用 `implement`，提交到 ticket 分支，将目标分支合并到 ticket 分支，运行必要检查。
   - 约束：ticket 实现上下文不合并到集成分支。
   - 返回：ticket 分支、worktree、提交 SHA、合并状态和检查结果。
6. **严格模式 review 和验证**（每张 ticket 一个 review 和验证 thread 或 subagent）
   - 条件：仅严格模式。
   - 输入：ticket 引用、`SPEC_DIR`、ticket 分支、worktree、提交 SHA 和必要检查结果。
   - 工作：运行 `code-review`、完整测试和验证。
   - 约束：不修改代码。发现缺陷时，交回原 ticket 实现上下文；原上下文不可用时，委派新的修复上下文。修复后创建新的 review 和验证上下文。
   - 返回：`code-review`、测试和验证结果。
7. **合并、归档和清理 ticket**（集成上下文）
   - 触发：快速模式收到 ticket 返回值；严格模式收到 review 和验证通过结果。
   - 输入：ticket 分支、worktree、提交 SHA 和 ticket 实现 thread ID（如果是独立 thread）。
   - 工作：在集成 worktree 中确认当前分支是目标分支，运行 `git merge --no-ff <ticket-branch>`，生成合并提交，运行既定的目标分支聚焦检查。
   - 收尾：检查通过后，标记 ticket 完成。
   - 归档：调用 `mcp__codex_app__set_thread_archived` 归档 ticket 实现 thread（如果存在）。
   - 清理：删除 ticket worktree 和 ticket 分支。
   - 约束：普通合并、归档和清理只在集成 thread 完成。
   - 约束：冲突、检查失败或需要修改代码时，保留 ticket worktree 和分支，交回原 ticket 上下文或委派修复上下文。
8. **快速模式最终 review 和验证**（review 和验证 thread 或 subagent）
   - 条件：仅快速模式，且全部 ticket 已合并。
   - 输入：目标分支、集成 worktree、`SPEC_DIR`、ticket 列表和合并提交。
   - 工作：运行全量 `code-review`、验证和完整测试。
   - 发现缺陷：委派修复工作上下文。修复后由集成上下文完成普通合并，再新建 review 和验证上下文。
   - 严格模式：每张 ticket 已完成独立的 review 和验证，不调度最终 review 和验证。
   - 返回：`code-review`、测试和验证结果。
9. **汇总结果**（集成上下文）
   - 输出目标分支、集成 worktree、规范位置或 tracker 标识、ticket 列表、合并提交，以及 review、测试和验证结果。
   - 输出归档和清理结果。
   - 保留集成分支和集成 worktree，不自动合并到 `main` 或 `master`。

## 规则

- 依赖未完成的 ticket 不启动。
- 禁止直接向 `main` 或 `master` 提交 ticket。
- 工作 thread 只回调。归档和清理由集成 thread 完成。
- 简单协作在集成上下文完成，复杂工作和独立 review 必须委派。
- 用户只要求规划时，完成步骤 1 至 4 后停止。
- skill 调用细节以各自说明为准。
