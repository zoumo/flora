# 严格模式

集成上下文负责调度和合并，工作上下文负责实现。
每次只执行 1 张 ticket，验证通过后才合并并继续。
每张 ticket 都需要独立 review 和完整的 ticket 验证。
最终集成结果需要独立 review 和完整门禁。
验证分工、任务模板和复审按[审查与验证](../references/review-and-verification.md)执行。

已有 run 恢复时，读取[交付状态](../references/multi-stage.md)的恢复规则。
沿用现有工作区、ticket 和上下文，不重做初始化。

## 步骤

1. **准备集成工作区和持久状态**（集成上下文）
   - 读取[交付状态](../references/multi-stage.md)。
   - 调用 `flora-git-flow` 准备集成工作区。资源负责人是集成上下文。
   - 创建 `STATE_FILE`，将 `mode` 写为 `strict`。
   - 保存流程快照、基线选择和远端检查结果。

2. **确认需求**（集成上下文）
   - 读取[完成证据](../references/completion-evidence.md)。
   - 在集成 worktree 中确认范围、约束和完成证据。只询问阻止执行或验收的缺失信息。需要交互澄清时，调用 `grill-with-docs`。
   - ADR、术语表和其他澄清文档写入集成分支。

3. **生成规范和 ticket**（集成上下文；复杂任务委派规划工作上下文）
   - 如果目标仓库存在 `docs/agents/issue-tracker.md`，按该配置使用 tracker。
   - 如果 tracker 配置不存在，使用本地 Markdown tracker，并明确传给 `to-spec` 和 `to-tickets`。本地目录是 `<integration-worktree>/.scratch/<feature-slug>/issues/`。
   - 默认由集成上下文在集成 worktree 中调用 `to-spec` 和 `to-tickets`，跳过 `to-tickets` 的拆分确认。
   - 需求复杂、拆分复杂或当前上下文不足时，在规划开始前委派 1 个规划工作上下文。委派替代集成上下文规划，上下文类型按交付状态选择。
   - 规划输入：需求、目标分支、运行模式和集成 worktree。通过 `codex-sub-thread` 委派，按上下文类型接收结果。
   - 规范：将运行模式、验收要求和完成证据写入规范及每张 ticket。
   - 提交：规范目录 `<integration-worktree>/.scratch/<feature-slug>/` 未被 Git 忽略时提交到集成分支。
   - Tracker：本地规范返回绝对路径 `SPEC_DIR`；外部 tracker 返回 issue 标识或 URL。
   - 返回：`SPEC_DIR` 和 ticket 列表。存在可靠依据时，附总时长估算。
   - 结束：规范和 ticket 齐备后，进入执行前报告。不追加规划核对或规划 review。

4. **输出执行前报告**（集成上下文）
   - 输出目标分支、集成 worktree 和 ticket 列表。
   - 输出选定流程、选择依据和完成证据要求。
   - 存在可靠依据时，附总时长估算。报告后直接执行。

5. **实现 ticket**（每张 ticket 一个实现上下文）
   - 调度：每次只启动 1 张依赖已完成的 ticket。
   - 准备：调用 `flora-git-flow` 准备子任务工作区，记录资源，将状态写为 `starting`。
   - 输入：ticket 引用、`SPEC_DIR`、目标分支、运行模式、ticket 分支、ticket worktree 绝对路径、交付状态规定的结果返回方式。附验收条件和完成证据要求。外部 tracker 传 issue 标识或 URL。
   - 工作：调用 `codex-sub-thread` 创建实现上下文，传入已准备的工作区，按交付状态接收结果。
   - 执行约定：使用审查与验证中的实现任务模板。明确聚焦命令、用户要求的符号和例外。
   - 实现：按任务中的验证分工运行 `implement`，提交到 ticket 分支。
   - 状态：按交付状态记录创建结果和当前执行者。
   - 约束：ticket 实现上下文不合并到集成分支。
   - 返回：ticket 分支、worktree、实现提交 SHA、分支头 SHA 和完成证据。

6. **执行 ticket 独立 review 和验证**（每张 ticket 一个独立审查上下文）
   - 刷新：按交付状态核验实现结果。调用 `flora-git-flow` 刷新子任务分支，更新 `branch_head`。冲突交回实现上下文。
   - 输入：ticket 引用、`SPEC_DIR`、ticket 分支、worktree、实现提交 SHA、分支头 SHA、必要检查结果、交付状态规定的结果返回方式。
   - 工作：首次创建独立只读 review 上下文，按交付状态接收结果。使用 ticket worktree，运行 `code-review` 和完整的 ticket 验证。
   - 状态：记录 review 上下文，将状态写为 `reviewing`。
   - 约束：review 不修改代码。阻塞缺陷交回原实现上下文。原上下文不可用时，委派修复上下文并复用原工作区。
   - 复审：优先复用原审查者。按审查与验证确定范围，记录当前分支头的结论。
   - 返回：`code-review`、测试和验证结果，以及验收条件对应的完成证据。

7. **合并并保留 ticket**（集成上下文）
   - 触发：收到当前分支头的 review 和验证通过结果。
   - 前置检查：按交付状态核验结果归属和分支头。通过后写为 `callback_received`。
   - 前置检查：确认 ticket 分支头仍是已通过 review 的分支头。分支头变化时，返回本流程的 ticket review 步骤。
   - 工作：将状态写为 `merging`，调用 `flora-git-flow` 合并子任务。运行 ticket 既定的目标分支聚焦检查。
   - 收尾：检查通过后，将 ticket 状态写为 `merged`。
   - 保留：将 `cleanup.status` 写为 `pending`。最终验收前保留可恢复的实现、审查上下文和工作区。
   - 约束：冲突、检查失败或需要修改代码时，保留 ticket worktree 和分支，交回原 ticket 上下文或委派修复上下文。

8. **继续执行 ticket**（集成上下文）
   - 重复本流程的 ticket 实现、review 和合并步骤，直到全部 ticket 合并。

9. **最终 review 和验证**（独立审查上下文）
   - 条件：全部 ticket 已合并。
   - 输入：目标分支、集成 worktree、`SPEC_DIR`、ticket 列表、初始目标 SHA、合并提交、交付状态规定的结果返回方式。
   - 工作：调用 `codex-sub-thread` 创建新的只读 review 上下文，按交付状态接收结果。使用集成 worktree，运行全量 `code-review`、验证和完整测试。
   - 状态：记录最终 review 上下文、finding 和证据。
   - 发现阻塞缺陷：追加 `final-fix-<NN>` ticket。优先交给原实现上下文，刷新保留的工作区后修复。
   - 修复：完成 ticket review 和合并。按审查与验证确定最终复审范围，优先复用原独立审查者。
   - 结束：验收条件通过且没有阻塞项时，记录通过。非阻塞项列为后续项。
   - 返回：`code-review`、测试和验证结果，以及验收条件对应的完成证据。

10. **统一清理与归档**（集成上下文）
   - 条件：最终验收通过，执行者已停止写入。
   - 清理：按交付状态逐项调用 `flora-git-flow` 和 `codex-sub-thread`。
   - 状态：分别记录交付状态和清理结果。失败时保留剩余资源。

11. **汇总结果**（集成上下文）
   - 输出目标分支、集成 worktree、规范位置或 tracker 标识、ticket 列表、合并提交，以及 review、测试和验证结果。
   - 输出归档和清理结果。
   - 保留集成分支和集成 worktree，不自动合并到 `main` 或 `master`。
