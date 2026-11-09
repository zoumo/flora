# 2026-11 回归基线

## 范围

- 本地窗口：2026-11-03 至 2026-11-09
- 时区：`Asia/Shanghai`
- 快照：`2026-11-09T14:29:00Z`
- 来源：`~/.codex/sessions` 和 `~/.codex/archived_sessions`
- 索引：544 个文件、540 个 session、0 个错误

## 文件

- `mapping.json`：22 个已核验 run，103 张 ticket
- `overrides.json`：1 个新增 run，11 张 ticket，以及本窗口修正
- `expected.json`：核心指标、23 个 run 和 4 个异常 ticket 的断言

fixture 不包含原始 JSONL。
本机 session 改变后，旧 fixture 仍可用于检查算法口径，但不能代替新的抽样核验。
fixture 覆盖旧名 `spec-to-ship` 时期，发现逻辑必须同时识别两个名称。

## 预期结果

- run：23
- ticket：114
- finished：113
- completed：112
- inferred completion：1
- running：1
- unclosed：0
- ticket effort：81.895 h
- ticket latency：112.510 h
- root engaged：96.605 h
- root wait：66.213 h
- root own active：30.392 h
- run window union：102.424 h
- root + ticket active union：60.147 h

`expected.json` 检查 379 个断言。

## 复现

在工作区根目录运行：

```bash
SKILL_DIR=.agent/skills/flora-flow-session-analysis
FIXTURE="$SKILL_DIR/references/regression-2026-11"
OUT=/tmp/flora-regression-2026-11
mkdir -p "$OUT"

rtk python3 "$SKILL_DIR/scripts/index_sessions.py" \
  --since 2026-11-03 \
  --until 2026-11-09 \
  --as-of 2026-11-09T14:29:00Z \
  --out "$OUT/index.json.gz"

rtk python3 "$SKILL_DIR/scripts/analyze_sessions.py" \
  --index "$OUT/index.json.gz" \
  --mapping "$FIXTURE/mapping.json" \
  --overrides "$FIXTURE/overrides.json" \
  --out-json "$OUT/report.json" \
  --out-md "$OUT/report.md"

rtk python3 "$SKILL_DIR/scripts/check_regression.py" \
  --report "$OUT/report.json" \
  --expected "$FIXTURE/expected.json"
```

检查器成功时输出：

```json
{
  "ok": true,
  "checks": 379,
  "failures": []
}
```

## 覆盖的异常

### Inferred completion

`11/08 testify in-process` T03：

- session：`01a1be3f-9bf9-7bc1-970f-31b2778489e1`
- 状态：`completed_in_inferred_tail`
- effort：61.482 min
- latency：61.482 min

### Running

`11/09 agent-sdk execution options` T05：

- session：`01a1c083-6acb-7433-aa7a-d828da875593`
- 状态：`running`
- effort：55.388 min
- run flag：`partial`

### Nested

下列 run 标记 `nested`：

- `11/04 testify tests refactor`
- `11/05 Mindpowers FE`
- `11/09 agent-sdk remove-testify-cli`

### Handoff

`11/06 MASS idle close` T06：

- `01a1b284-45ee-7e93-b10e-02ec443e7ab2`
- `01a1b5a2-e953-7751-b55d-53363778b11e`

首轮线程未正式收尾。
同一编排根的 finish-gaps 线程完成 T06。
run flag 为 `handoff_merged`。

### Remote-compact

`11/09 agent-sdk remove-testify-cli` T01 有 3 个 attempt：

- `01a1bf50-c365-73f1-933e-28e94200a4ba`
- `01a1bf6b-a592-7b92-871e-058f3f609900`
- `01a1bfa3-152e-7c01-81ac-6236c20d2248`

首轮 remote-compact 失败。
后续线程接管修复并完成最终核验。

### Resume turn

下列 session 的 `resume_interrupted_task` turn 经人工确认进入 effort：

- `01a1ac8a-a745-7280-88a7-2040f236f9ee`
- `01a1ac7e-75f4-7933-a47b-b25dcc139287`

### 长尾

最高 effort ticket 为：

- run：`11/06 MASS idle close`
- ticket：`02`
- effort：232.201 min

最高 latency ticket 为：

- run：`11/06 MASS idle close`
- ticket：`06`
- latency：927.340 min

长尾断言可以防止“先截断再排序”的错误再次出现。
