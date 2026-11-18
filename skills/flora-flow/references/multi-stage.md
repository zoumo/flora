# 多阶段交付状态

仅在选中的 playbook 要求准备或恢复多阶段交付时，读取本文件。
本文件只规定 run 状态和任务交接，不规定 Git 或 thread 操作。
执行顺序以选中的 playbook 为准。

## 能力边界

| 责任 | 归属 |
| --- | --- |
| 分支、worktree、刷新、合并和清理 | `flora-git-flow` |
| 上下文创建、回调、观察、恢复和归档 | `codex-sub-thread` |
| 流程顺序、调度、验收时机和完成证据 | 选中的 playbook |
| run 记录、依赖和结果归属 | 本文件 |

集成上下文亲自执行 playbook，负责调度、状态和汇总。
集成上下文是 Git 资源负责人。
复杂规划、实现、故障排查和独立 review 委派工作上下文。
聚焦检查失败时，交回实现上下文，不在集成上下文修复。
工作上下文只完成分配的交付物，不重新匹配流程。

本流程委派默认优先独立 sub-thread。
沿用用户已明确指定的上下文类型，不重复确认。
平台要求用户明确请求新 thread 时，本流程的默认偏好不能替代用户请求。

只有用户指定 subagent、平台要求或独立 thread 能力不可用时，才按 `codex-sub-thread` 回退。
回退前说明具体原因，并记录到状态文件。
用户要求必须使用独立 thread 时，创建受阻就停止并报告，不回退。

独立 sub-thread 必须传入父 thread ID 并要求回调。
subagent 直接返回结果，无需父 thread ID 或跨 thread 回调。

独立工作上下文启动并登记后，按 `codex-sub-thread` 选择观察方式。
平台要求等待时，执行有界等待并保存 cursor。
平台允许结束 turn 且回调可用时，等待回调。

## 状态文件

`flora-git-flow` 返回 `workspace_root`。
`STATE_FILE` 是 `<workspace_root>/state.json`，不提交到 Git。
所有结果处理、合并、恢复和清理先读状态文件。
每次状态变化后立即写回。

最小字段：

```json
{
  "feature_slug": "<feature-slug>",
  "mode": "fast",
  "target_branch": "<target-branch>",
  "integration_worktree": "<absolute-path>",
  "base_sha": "<SHA>",
  "workflow": {
    "snapshot_dir": "<workspace_root>/workflow",
    "manifest": "<workspace_root>/workflow/manifest.json"
  },
  "baseline": {
    "source": "<用户指定提交、当前任务分支或远端分支>",
    "remote_ref": null,
    "remote_sha": null,
    "checked_at": null,
    "reason": "<基线选择或冻结原因>"
  },
  "final_review_thread_ids": [],
  "final_review_agent_ids": [],
  "tickets": [
    {
      "id": "<NN>",
      "status": "planned",
      "blocked_by": [],
      "ticket_branch": "<branch>",
      "worktree": "<absolute-path>",
      "thread_id": null,
      "thread_ids": [],
      "client_thread_id": null,
      "host_id": null,
      "agent_id": null,
      "agent_ids": [],
      "implementation_sha": null,
      "branch_head": null,
      "cleanup": {"status": "pending", "remaining": [], "completed": []},
      "review_thread_ids": [],
      "review_agent_ids": [],
      "last_callback": null
    }
  ]
}
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| `planned` | 尚未启动 |
| `starting` | 已准备资源，正在创建上下文 |
| `running` | 实现上下文已启动 |
| `callback_received` | 已收到并核验本轮结果 |
| `reviewing` | 独立 review 和验证中 |
| `merging` | 合并或目标分支检查中 |
| `merged` | 已合并且目标分支检查通过 |
| `blocked` | 受阻，已记录原因和剩余资源 |

清理状态独立使用 `pending`、`done`、`failed`。
清理失败保留 `status: merged`，只更新 `cleanup`。
缺陷影响后续依赖时，暂停受影响的 ticket。
用修复 ticket 记录解除阻塞的条件。

## 流程快照

初始化时，将 3 个 skill 的指令文件复制到快照目录。
这 3 个 skill 是 `flora-flow`、`flora-git-flow` 和 `codex-sub-thread`。
manifest 记录原路径、快照路径和内容 SHA-256。
其他执行 skill 首次使用时，也保存所用指令及哈希。
快照保存在 Git 外，不复制密钥、session 或工具输出。
按需读取快照中的文件，不预读所有 playbook。

恢复时沿用快照，不因已安装 skill 改变而切换规则。
用户要求升级流程时，保留旧快照并记录切换理由。
模式切换记录前后模式、时间和所用快照。
高优先级指令和当前工具 schema 始终优先于快照。

## 交接与结果核验

1. 创建前写入资源和 `starting` 状态。
2. 按 `codex-sub-thread` 记录创建结果。
   - 真实 `threadId` 追加到 `thread_ids`，更新 `thread_id`，写为 `running`。
   - 只有 `clientThreadId` 时，记录 `client_thread_id`，保留 `starting`。
   - subagent 记录 `agent_id` 和 `agent_ids`，结果直接返回。
   - review ID 追加到对应数组，不覆盖历史记录。
3. 核验返回结果的执行者和 ticket。
   - 结果必须来自当前 attempt 或本轮指定的 reviewer。
   - 从 Git 读取实际分支头，确认结果对应当前 SHA。
   - 新实现结果携带新 SHA 时，核验后更新 `implementation_sha` 和 `branch_head`。
   - review 结果必须对应已记录的 `branch_head`。
4. 记录结果和完成证据。
   - 按执行者 ID、ticket 和 `branch_head` 去重。
   - 旧 attempt、重复或旧 SHA 结果不能证明本轮完成。
   - `last_callback` 保存结果来源、分支头、结论和检查结果。
5. 按 playbook 继续验证或合并。
   - 回调只是唤醒信号，不能代替 Git 核验和完成证据。
   - blocker 全部为 `merged` 且无影响本 ticket 的未修复缺陷时，才允许启动依赖 ticket。

## 最终验收后的清理

1. 确认最终验收通过且执行者已停止写入。
2. 按资源路径和上下文 ID 去重。
3. 串行清理各 ticket 的 Git 临时资源。
4. 归档实现、规划和审查 thread。
   - subagent 按平台能力释放，不调用 thread 归档工具。
5. 读回结果，更新共享资源对应的每项 `cleanup`。

每项已完成操作写入 `cleanup.completed`。
剩余资源及失败原因写入 `cleanup.remaining`。
只有 Git 资源与上下文都已清理时，才记为 `done`。
恢复时只补做剩余操作，清理失败不撤销合并结果。
集成分支、集成工作区和证据继续保留。

最终验收前默认保留临时工作区。
资源不足时，先保存证据并核验合并归属，再清理闲置工作区。
保留实现上下文和恢复所需 SHA，记录提前清理原因。

复用原上下文修复时，先核验工作区并刷新到集成基线。
原工作区已清理时，资源负责人准备替代工作区。
替代工作区和当前执行者写入修复 ticket，保留原 ticket 历史。
复用资源时，原 ticket 的实现 SHA 和验收结果保留为历史。
清理共享资源前，确认所有使用者已停止写入。

## 恢复

1. 读取 `STATE_FILE`、流程快照和已记录模式。
2. 按 `codex-sub-thread` 恢复已记录的上下文。
3. 按本文件核验结果并更新状态。
4. 从未完成步骤继续，不重复创建资源或上下文。

保留全部 attempt、review ID 和已完成操作。
缺失回调不表示失败，不据此创建第二个上下文。
归档、清理失败或工具缺失时，记录未完成项。

旧 run 没有流程快照时，先查已记录的模式和规则证据。
记录版本未知与本次采用规则，不假称已恢复历史版本。
旧 `cleaned` 状态核验后映射为 `merged` 和 `cleanup: done`。
旧 `blocked` 若仅因清理失败，核验合并证据后恢复为 `merged`。
其他 `blocked` 保留业务阻塞，不能按清理失败放行。
