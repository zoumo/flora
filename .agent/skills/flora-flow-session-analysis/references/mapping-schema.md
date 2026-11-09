# Mapping 和 Override 格式

## 文件分工

`mapping.json` 保存人工核验后的通用 run/ticket 关系。
`overrides.json` 保存本次时间窗特有的状态、合并和标记。

脚本不自动读取 discovered draft。
`analyze_sessions.py` 必须先读取 mapping，再应用 overrides。

## Mapping

最小结构：

```json
{
  "schema_version": 1,
  "name": "2026-11 reviewed runs",
  "analysis": {},
  "runs": [
    {
      "key": "11/09 example-run",
      "project": "example",
      "start": "2026-11-09T07:00:00Z",
      "end": "2026-11-09T10:00:00Z",
      "root_sessions": [
        "01a1..."
      ],
      "tickets": [
        {
          "label": "01",
          "primary": "01a1...",
          "sessions": [
            "01a1..."
          ],
          "status": "completed",
          "note": "final verification thread"
        }
      ],
      "notes": "",
      "flags": []
    }
  ]
}
```

### Run 字段

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `key` | 是 | 报告中的唯一 run 名称 |
| `project` | 否 | 项目名，默认 `unknown` |
| `start` | 是 | UTC ISO 8601 开始时间 |
| `end` | 是 | UTC ISO 8601 结束时间 |
| `root_sessions` | 是 | 至少一个编排 session |
| `tickets` | 是 | ticket 数组，可以为空并产生警告 |
| `notes` | 否 | run 级核验说明 |
| `flags` | 否 | 口径和异常标记 |

推荐 flags：

- `partial`
- `nested`
- `handoff_merged`
- `remote_compact`

`partial` 会改变阶段统计范围。
其他 flags 主要产生报告警告，不自动改变时间。

### Ticket 字段

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `label` | 是 | run 内唯一 ticket 标签 |
| `primary` | 否 | 代表 session，默认取 `sessions[0]` |
| `sessions` | 是 | 全部有效 attempt session |
| `status` | 否 | 人工确认状态 |
| `note` | 否 | attempt、接管和完成证据 |

`primary` 必须属于 `sessions`。
同一 ticket 的全部有效 attempt 都必须进入 `sessions`。

允许的 status：

- `completed`
- `completed_in_inferred_tail`
- `running`
- `unclosed`

省略 status 时：

- 任一 attempt 有完成 turn：`completed`
- 全部 attempt 未完成：`unclosed`

`running` 和 `completed_in_inferred_tail` 应显式写入。

## Overrides

示例：

```json
{
  "analysis": {
    "attempt_include_resume": [
      "01a1..."
    ]
  },
  "add_runs": [
    {
      "key": "11/09 added-run",
      "project": "example",
      "start": "2026-11-09T11:00:00Z",
      "end": "2026-11-09T12:00:00Z",
      "root_sessions": [
        "01a1..."
      ],
      "tickets": [
        {
          "label": "01",
          "primary": "01a1...",
          "sessions": [
            "01a1..."
          ],
          "status": "completed"
        }
      ],
      "notes": "",
      "flags": []
    }
  ],
  "runs": {
    "11/09 existing-run": {
      "flags": [
        "nested",
        "handoff_merged"
      ],
      "notes": "merged the finish-gaps thread",
      "root_sessions": [
        "01a1...",
        "01a1..."
      ],
      "tickets": {
        "06": {
          "primary": "01a1...",
          "sessions": [
            "01a1...",
            "01a1..."
          ],
          "status": "completed",
          "note": "first thread did not close; finish-gaps thread completed T06"
        }
      },
      "remove_tickets": [
        "99"
      ]
    }
  }
}
```

### 应用顺序

1. 深拷贝 mapping。
2. 合并 `overrides.analysis`。
3. 把 `add_runs` 追加到 runs。
4. 按 run key 应用普通 run 字段。
5. 更新已有 ticket 或新增 ticket。
6. 按 `remove_tickets` 删除 ticket。

`add_runs` 的 key 不能与 mapping 重复。
override 的 run key 必须已存在。

### Analysis 字段

`analysis.attempt_include_resume` 列出允许
`resume_interrupted_task` 进入相关 turn 的 session。

只在人工确认恢复 turn 属于同一 ticket 时写入。
该字段属于数据修正，不写入通用脚本。

## 常见修改

### 合并 attempt

在 ticket patch 中写入完整 `sessions`。
把最终实现或核验线程写入 `primary`。
在 `note` 写出 attempt 顺序和完成关系。

### 标记 inferred completion

```json
{
  "status": "completed_in_inferred_tail",
  "note": "no task_complete; later evidence shows verification finished"
}
```

### 标记 running 和 partial

在 run patch 写：

```json
{
  "flags": [
    "partial"
  ]
}
```

在 ticket patch 写：

```json
{
  "status": "running"
}
```

### 合并 handoff

在 run patch 更新 `root_sessions` 和 ticket `sessions`。
添加 `handoff_merged` flag。
用 `note` 说明新线程完成的范围。

### 标记嵌套

在独立子 run 和父 run 都添加 `nested` flag。
保留两套 ticket。
在最终报告说明 effort 可能重叠。

## 校验规则

`validate_mapping` 检查：

- run key 唯一。
- run 有 root session。
- ticket label 在 run 内唯一。
- ticket 有 session。
- `primary` 属于 `sessions`。
- status 在允许集合内。

脚本还会检查所有 session ID 是否存在于索引。
未知 ID 返回错误。

## 禁止项

- 不把本窗口的 session ID 写入通用算法。
- 不按 `meta.session_id` 去重 fork 线程。
- 不把 `primary` 当作唯一统计 attempt。
- 不用 `notes` 代替 `flags`。
- 不把 `partial`、`running` 或 inferred 完成当作自动推断结果。
