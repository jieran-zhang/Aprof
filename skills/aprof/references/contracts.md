# AProf Agent Contracts

本文定义 AProf workflow 中 diagnosis、profiling 与 optimization agent 之间传递的结构化契约。字段名必须保持稳定；未知信息使用 `null`、空数组或 `unknown`，不要编造。

全局约束：

- 性能证据必须区分 `single_run_exploration` 与 `stable_metric_evidence`。最终性能提升只能引用带 warmup、repeat 和稳定性统计的 evidence。
- 诊断结论必须先经过 workload / roofline feasibility 判断；低利用率不是独立问题，只有和可达上限、算法工作量和硬件分母对齐后才能定性。
- 优化默认 `production_safe`。`benchmark_specialized` 候选可以报告性能，但不能默认成为 `final output` 或 `best_op`。

## diagnosis_hypotheses.json

由 `aprof-diagnosis-agent` 产出。输入是 kernel 源码、源码路径或工程路径，输出源码静态分析得到的性能问题假设与最多 3 个硬件 metric。

```json
{
  "kernel": {
    "name": "unknown",
    "source_path": "op_kernel/example_kernel.asc",
    "operator_family": "elementwise",
    "shape_context": [],
    "dtype_context": []
  },
  "hypotheses": [
    {
      "id": "H1",
      "problem_family": "tiling",
      "summary": "tileLength 可能过小导致 DataCopy 粒度偏小",
      "source_evidence": [
        "循环内频繁 DataCopy",
        "每个 tile 只处理很少元素"
      ],
      "confidence": "medium",
      "evidence_level": "source-hypothesis",
      "related_references": [
        "diagnosis/references/tiling-diagnosis-metrics.md",
        "diagnosis/references/data-movement-diagnosis-metrics.md"
      ]
    }
  ],
  "metrics": [
    {
      "name": "single_copyin_bytes",
      "description": "单次搬入粒度",
      "diagnosis_use": "验证 tileLength 过小或非连续搬运是否导致 MTE setup 成本放大",
      "source": "Memory.csv",
      "fields": [
        "GM_to_UB_datas(KB)",
        "ai*_mte2_instructions"
      ],
      "formula": "GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions",
      "evidence_level": "derived",
      "linked_hypotheses": [
        "H1"
      ],
      "priority": 1
    }
  ],
  "limits": [
    "源码静态诊断只产生假设，最终结论必须等待 profiling 数据验证"
  ]
}
```

约束：

- `hypotheses` 最多 3 条。
- `metrics` 最多 3 条，并按 `priority` 从高到低排序。
- `problem_family` 只能使用 `tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`。
- `confidence` 使用 `high`、`medium`、`low`。

## profiling_plan.json

由 `aprof-profiling-agent` 产出。输入是 `metrics[]` 及其描述，输出 msprof 采集方案、执行计划和 report 解析方案。

```json
{
  "plan_id": "P1",
  "input_metrics": [
    "single_copyin_bytes"
  ],
  "profile_mode": "hw-op",
  "mode_reason": "需要 Memory.csv 与 PipeUtilization.csv 中的真实硬件计数，simulator 无法直接产出 8 CSV",
  "msprof_command": {
    "preferred": "msprof op --warm-up=10 --launch-count=5 --output=profiling_out/msprof_hw_output ./<binary> <args>",
    "fallback": "bash ../ops_profiling/scripts/msprof_profile_run.sh --warm-up=10 --output=profiling_out/msprof_hw_output -- ./<binary> <args>",
    "simulator": "msprof op simulator --config=./op_config.json --output=profiling_out/msprof_sim_output --timeout=8"
  },
  "required_artifacts": [
    {
      "path_pattern": "profiling_out/msprof_hw_output/OPPROF_*/Memory.csv",
      "reason": "读取 GM_to_UB_datas 与 MTE 指令数"
    }
  ],
  "optional_artifacts": [
    {
      "path_pattern": "profiling_out/msprof_hw_output/OPPROF_*/PipeUtilization.csv",
      "reason": "辅助判断 MTE2/MTE3 是否为主 bound"
    }
  ],
  "parser_plan": [
    {
      "metric": "single_copyin_bytes",
      "artifact": "Memory.csv",
      "fields": [
        "GM_to_UB_datas(KB)",
        "ai*_mte2_instructions"
      ],
      "formula": "GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions",
      "output_key": "single_copyin_bytes"
    }
  ],
  "execution_plan": {
    "profile_mode": "hw-op",
    "run_cmd": "./<binary> <args>",
    "gen_data_cmd": null,
    "warm_up": 10,
    "repeat": 5,
    "statistic": "median",
    "stability_cv_threshold": 0.05,
    "min_effect_pct": 3.0,
    "output_dir": "profiling_out/msprof_hw_output",
    "summarize": true,
    "steps": "prepare,profile,summarize,parse"
  },
  "handoff": {
    "after_profiling": "aprof-diagnosis-agent"
  }
}
```

约束：

- 优先选择能直接产出所需 metric 的真实硬件模式：`hw-op` 或 `hw-msprof`。
- 只有 metric 可由 `trace.json`、`*_instr_exe_*.csv` 或 `*_code_exe_*.csv` 代理，或当前 profiling 环境无 NPU 时，才选择 `sim`。
- `execution_plan.profile_mode` 必须是 `sim`、`hw-msprof`、`hw-op` 之一，并与 `profile_mode` 一致。
- 真实硬件最终证据默认 `warm_up >= 10`、`repeat >= 5`；如环境只能单次采集，必须标记为 `single_run_exploration`，不得用于最终提升声明。
- `hw-op` 优先使用 `msprof op --warm-up=<warm_up> --launch-count=<repeat>`；普通 `msprof --application` 没有 launch-count 时必须外层 repeat，并保存独立 run 目录。
- `stability_cv_threshold` 默认 0.05；超过阈值时 `profiling_results.measurement_status` 只能是 `unstable` 或 `measurement_limited`。

## profiling_results.json

由 `aprof-profiling-agent` 在执行 msprof 或读取用户提供 report 后生成。用于判断 `profiling_plan.json` 是否已满足，并把 report 中解析出的 metric 值交回 diagnosis。

```json
{
  "profile_mode": "hw-op",
  "output_dir": "benchmarks/example/profiling_out",
  "has_artifacts": true,
  "artifacts": [
    {
      "kind": "csv",
      "name": "Memory.csv",
      "path": "benchmarks/example/profiling_out/msprof_hw_output/OPPROF_xxx/Memory.csv",
      "satisfies": [
        "single_copyin_bytes"
      ]
    }
  ],
  "metric_values": [
    {
      "metric": "single_copyin_bytes",
      "value": 256.0,
      "selected_value": 256.0,
      "unit": "bytes",
      "source_path": "benchmarks/example/profiling_out/msprof_hw_output/OPPROF_xxx/Memory.csv",
      "samples": [
        254.0,
        256.0,
        257.0,
        255.0,
        256.0
      ],
      "statistics": {
        "count": 5,
        "mean": 255.6,
        "median": 256.0,
        "min": 254.0,
        "max": 257.0,
        "std": 1.14,
        "cv": 0.0045,
        "selected": "median"
      },
      "fields": {
        "GM_to_UB_datas(KB)": 128,
        "ai*_mte2_instructions": 512
      },
      "formula": "GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions",
      "linked_hypotheses": [
        "H1"
      ]
    }
  ],
  "missing_required_artifacts": [],
  "measurement_policy": {
    "warm_up": 10,
    "repeat": 5,
    "statistic": "median",
    "stability_cv_threshold": 0.05,
    "min_effect_pct": 3.0
  },
  "measurement_status": "stable",
  "ready_for_diagnosis": true,
  "notes": []
}
```

约束：

- `ready_for_diagnosis` 只有在 `missing_required_artifacts` 为空时才能为 `true`。
- sim 模式至少需要 `trace.json` 或 `*_instr_exe_*.csv` 才能进入 sim-only 诊断。
- hw-op 模式优先确认 `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`。
- hw-msprof 模式优先确认 `PROF_GROUP_*` 下的 CSV、`aicore.db` 或 `hw_summary.txt`。
- `metric_values[]` 必须保留 `samples` 和 `statistics`。只有 `measurement_status=stable` 且样本数满足 plan 时，才允许作为 `stable_metric_evidence`。
- 以 duration 计算优化收益时，使用同一 `statistic` 比较 baseline 与 candidate；提升小于 `min_effect_pct` 或 CV 超阈值时，结论降级为 `measurement_limited`。

## single_case_diagnosis.json

由 `aprof-diagnosis-agent` 在**单 kernel 独立诊断**时产出。该契约不依赖 baseline；每个问题必须有独立 metric 佐证。可使用源码、tiling、shape、report 和硬件参数，但禁止使用 ground-truth label、inject metadata 或 variant 名。

```json
{
  "case_id": "anonymous_case",
  "kernel": {
    "name": "fast_gelu",
    "operator_family": "elementwise",
    "source_visible": true
  },
  "hardware_context": {
    "soc_version": "dav-3510",
    "aiv_core_num": 32,
    "aic_core_num": null,
    "ub_bytes_per_core": 253952,
    "l1_bytes_per_core": null,
    "l0c_bytes_per_core": null,
    "frequency_hz": 1650000000,
    "vector_peak_flops": null,
    "cube_peak_flops": null,
    "gm_bandwidth_bytes_per_s": null,
    "source": "npu-arch / PlatformAscendC / user-provided"
  },
  "roofline": {
    "work_bytes": {
      "read_bytes_min": 9220,
      "write_bytes_min": 9220,
      "actual_read_bytes": null,
      "actual_write_bytes": null,
      "source": "shape/dtype or Memory.csv"
    },
    "work_ops": {
      "estimated_vector_ops": null,
      "actual_vector_flops": null,
      "source": "algorithm estimate or ArithmeticUtilization.csv"
    },
    "arithmetic_intensity_ops_per_byte": null,
    "achieved_ops_per_s": null,
    "achieved_bandwidth_bytes_per_s": null,
    "roofline_bound": "unknown",
    "limits": [
      "缺少真实 Memory.csv / ArithmeticUtilization.csv 时只能做 proxy roofline"
    ]
  },
  "workload_model": {
    "total_elements": 2048,
    "dtype_bytes": 4,
    "operator_family": "elementwise",
    "ops_per_element_estimate": 12,
    "min_read_bytes": 8192,
    "min_write_bytes": 8192,
    "block_dim": 1,
    "available_aiv_cores": 32,
    "elements_per_active_core": 2048,
    "workload_class": "tiny",
    "attainable_utilization_note": "tiny workload cannot fill all cores or UB; low absolute utilization alone is not a bottleneck"
  },
  "attainable_utilization": {
    "ai_core": {
      "observed_pct": 3.0,
      "attainable_pct": 5.0,
      "status": "near_attainable",
      "source": "workload_model + OpBasicInfo.csv"
    },
    "ub": {
      "observed_pct": 1.0,
      "attainable_pct": 2.0,
      "status": "workload_limited",
      "source": "workload_model"
    }
  },
  "diagnoses": [
    {
      "id": "D1",
      "diagnosis_type": "true_bottleneck",
      "problem": "partial tile extra reload",
      "problem_family": "tiling/data_movement",
      "confidence": "high",
      "evidence_level": "source+trace+tiling",
      "metrics": [
        {
          "name": "tail_length",
          "value": 1,
          "unit": "elements",
          "source": "tiling_context",
          "supports": "存在 partial tile"
        },
        {
          "name": "extra_reload_path",
          "value": "enabled when curN < tileLength",
          "unit": "source fact",
          "source": "kernel_source",
          "supports": "partial tile 额外 GM reload"
        },
        {
          "name": "mte_like_trace_duration",
          "value": 5.8629,
          "unit": "sim trace duration units",
          "source": "trace.json",
          "supports": "搬运相关指令为主导耗时"
        }
      ],
      "roofline_interpretation": "缺少真实带宽/流量字段，当前只支持 trace proxy 判断为搬运/同步开销主导",
      "workload_interpretation": "问题来自 partial tile 额外 reload，而不是低 UB 绝对利用率",
      "recommendation": "避免 tail 重复 reload，tail 复用主路径或只搬运有效数据"
    }
  ],
  "missing_evidence": [
    "Memory.csv",
    "ArithmeticUtilization.csv",
    "PipeUtilization.csv",
    "PlatformAscendC runtime hardware denominators"
  ],
  "leakage_guard": {
    "forbidden_inputs": [
      "injected_label",
      "injected_problem",
      "variant name",
      "inject_manifest.json",
      "inject_audit_report.json"
    ]
  }
}
```

约束：

- 不使用 baseline 作为必要输入；如用户提供 baseline，只能作为可选附录，不得作为主判断依据。
- `diagnoses[]` 中每个问题至少包含 2 个 metric，推荐 3 个：源码 metric、tiling/shape metric、report/trace metric。
- `roofline` 必须说明硬件参数来源；缺失真实硬件分母时，必须把结论降级为 proxy。
- `workload_model` 必须在最终诊断前存在。至少包含总元素数、dtype bytes、理论最小读写量、blockDim、可用 core 数、每核工作量和 `workload_class`。
- `diagnosis_type` 只能使用 `true_bottleneck`、`workload_limited`、`measurement_limited`、`code_quality_risk`、`optimization_not_recommended`。
- 对 tiny/small workload，低 UB/AI Core 利用率默认解释为 `workload_limited`；只有额外 evidence 指向错误 tiling、额外 GM 流量、bank conflict 或 pipeline stall，才可上升为 `true_bottleneck`。
- 注入评估时禁止读取包含 ground-truth 的文件：`metadata.json.injected_label`、`inject_manifest.json`、`inject_audit_report.json`、`label_alignment_report.json`。

## final_diagnosis.md

最终 workflow 输出使用 Markdown，但必须能追溯到上述 JSON。

```markdown
## 诊断结论

- 最可能问题：...
- 证据等级：直接 / 派生 / Trace / source-hypothesis

## 硬件数据支撑

| Metric | 值 | 来源 | 支撑的假设 |
| ------ | -- | ---- | ---------- |

## 缺口与下一步

- ...
```

## optimization_plan.json

由 `aprof-optimization-agent` 产出。输入是完整 `op_dir`、诊断 JSON、profiling JSON 和可选执行命令；输出多算子族候选策略与本地验证命令。

```json
{
  "schema_version": 1,
  "op_dir": "benchmarks/reference_ops/fast_gelu",
  "operator_family": "elementwise",
  "strategies": [
    {
      "strategy_id": "data_movement_traffic_rewrite",
      "problem_family": "data_movement",
      "summary": "Use DataCopyPad for uncertain alignment and coalesce repeated small DataCopy operations.",
      "source_anchors": [
        "op_kernel/* DataCopy/DataCopyPad",
        "profiling_results metric_values for MTE2/MTE3"
      ],
      "expected_benefit": "Reduce MTE setup cost and avoid non-aligned transfer penalties.",
      "risk": "Padding values may affect math if padded elements are consumed by compute.",
      "references": [
        "skills/aprof/optimization/references/optimization-candidate-design.md",
        "skills/aprof/optimization/references/data-movement-optimization-strategies.md",
        "skills/aprof/optimization/references/optimization-cannbot-knowledge-index.md"
      ],
      "verification_focus": [
        "non-aligned shapes",
        "MTE2/MTE3 before/after"
      ],
      "structural_edits": [
        "Coalesce adjacent small DataCopy operations by changing loop structure and offset formulas.",
        "Keep intermediate vector/reduce/cast chains in UB when lifetime and capacity allow."
      ],
      "capacity_model": [
        "Compare actual GM bytes against theoretical minimum bytes.",
        "Record useful bytes per MTE instruction and UB capacity impact."
      ],
      "abort_conditions": [
        "Padding elements may enter math or comparison paths.",
        "DataCopyPad overload or alignment requirement is unknown."
      ],
      "linked_hypotheses": [
        "H2"
      ],
      "linked_metrics": [
        "single_copyin_bytes",
        "mte2_utilization"
      ],
      "bound_type": "memory",
      "optimization_scope": "production_safe",
      "semantic_requirements": [
        "preserve operator math and dtype precision",
        "preserve dynamic shape/tiling support unless user explicitly requests benchmark-only specialization",
        "preserve tail and boundary safety"
      ],
      "required_evidence": [
        "DataCopy/DataCopyPad call sites and copy lengths",
        "alignment facts for GM/UB addresses and valid element count",
        "Memory.csv or profiling metric_values for GM_to_UB/UB_to_GM bytes"
      ],
      "expected_metric_delta": [
        "MTE instruction count decreases for the same useful bytes",
        "GM round trips and redundant copy-in/out paths decrease"
      ],
      "pre_patch_checks": [
        "Run ascendc-env-check if local build/profile will execute.",
        "Use ascendc-docs-search for risky DataCopyPad overloads or padding parameters."
      ],
      "post_patch_checks": [
        "Run ascendc-code-review for DataCopy alignment, padding, and lifetime clauses.",
        "Verify aligned and non-aligned shapes."
      ],
      "failure_handoff": {
        "build_failure": "ascendc-code-review",
        "accuracy_failure": "ascendc-precision-debug",
        "runtime_failure": "ascendc-runtime-debug",
        "timeout_or_crash": "ascendc-crash-debug",
        "metric_regression": "optimization_memory_next_candidate",
        "profile_unavailable": "ops-profiling",
        "api_uncertainty": "ascendc-docs-search",
        "static_review_failure": "ascendc-code-review"
      },
      "requires_agent_patch": true
    }
  ],
  "commands": {
    "build_cmd": "bash run.sh",
    "verify_cmd": "true",
    "profile_cmd": "bash scripts/profile_hw.sh",
    "metric_source": "auto",
    "notes": []
  },
  "memory_path": "benchmarks/reference_ops/fast_gelu/aprof_opt/optimization_memory.jsonl",
  "dry_run": true,
  "notes": []
}
```

约束：

- `op_dir` 必须是完整 direct-invoke 工程；raw kernel 需要先通过 direct-invoke scaffold。
- `strategies[]` 只描述候选修改，不直接修改 baseline。
- 每个 candidate 只能应用一个 `strategy_id`。
- 每个 strategy 必须保留诊断链接：`problem_family`、`linked_hypotheses`、`linked_metrics`、`bound_type`。
- 每个 strategy 必须包含执行前后门禁：`required_evidence`、`expected_metric_delta`、`pre_patch_checks`、`post_patch_checks`、`failure_handoff`。
- 新生成的 strategy 应包含 `structural_edits`、`capacity_model`、`abort_conditions`；旧 plan 缺失这些字段时仍可按保守候选处理。
- 深层 candidate 仍不新增 schema 字段；把 `decision_gate` 映射到 `required_evidence`，`capacity_formula` 映射到
  `capacity_model`，`structural_patch_shape` 映射到 `structural_edits`，`metric_delta` 映射到
  `expected_metric_delta`，停止条件映射到 `abort_conditions`。
- 策略选择顺序为 diagnosis problem family 优先、profiling bound 次之、source scan 兜底。
- `profile_cmd` 缺失时仍可生成计划，但不得声称完成性能优化。
- 默认 `optimization_scope=production_safe`。硬编码 shape/core/UB、删除动态 tiling、降低精度或缩小算法适用范围的策略必须标为 `benchmark_specialized`，并在 final report 中单独列为非默认产物。
- 选择 best 前必须通过 Correctness & Generality Gate：语义保持、边界/tail 测试、代码审查和 portability risk 均可接受。

复杂候选示例：

- MatMul StreamK candidate 使用同一个 `ai_core_task_parallelism` strategy，`structural_edits` 写 Host Tiling K split、
  FP32 partial workspace、AIV reduce+cast 与 AIC/AIV flag；`capacity_model` 写 `baseM*baseN*sizeof(float)*kCnt`
  workspace 和 L1/L0/Fixpipe 分母；`abort_conditions` 写 partial combine、输出顺序或平台边界不明确时停止。
- Softmax online candidate 使用同一个 `api_algorithm_vector_scalar_rewrite` strategy，`structural_edits` 写 S2 tile loop、
  running max/sum/O_acc 和 final normalize；`capacity_model` 写 `score_tile + Q/K/V + state <= UB`；
  `expected_metric_delta` 写 GM traffic 从完整 score/prob staging 降为 state/workspace traffic。

## candidate_result.json

由每个候选的本地 gate 产出，记录 build、精度、profiling 和 before/after metric。

```json
{
  "schema_version": 1,
  "candidate_id": "candidate_01",
  "strategy_id": "tiling_task_tile_shape_rewrite",
  "candidate_op_dir": "benchmarks/reference_ops/fast_gelu/aprof_opt/candidates/candidate_01/op",
  "changed_files": [
    "op_kernel/fast_gelu_kernel.asc"
  ],
  "build_status": "passed",
  "accuracy_status": "passed",
  "profile_status": "passed",
  "metric_before": 10.8,
  "metric_after": 8.9,
  "metric_name": "kernel_duration_us",
  "speedup": 1.213,
  "selected_as_best": true,
  "semantic_status": "preserved",
  "scope_status": "production_safe",
  "portability_risk": "low",
  "accepted_for": [
    "production"
  ],
  "measurement_evidence": {
    "metric_name": "kernel_duration_us",
    "baseline_samples": [
      10.7,
      10.8,
      10.9,
      10.8,
      10.8
    ],
    "candidate_samples": [
      8.8,
      8.9,
      9.0,
      8.9,
      8.9
    ],
    "statistic": "median",
    "baseline_selected": 10.8,
    "candidate_selected": 8.9,
    "baseline_cv": 0.006,
    "candidate_cv": 0.007,
    "measurement_status": "stable"
  },
  "failure_reason": null,
  "failure_handoff": null,
  "artifacts": {
    "profile_dir": "msprof_hw_output/PROF_GROUP_xxx"
  }
}
```

约束：

- 状态字段只能是 `not_run`、`passed`、`failed`、`skipped`。
- `accuracy_status != passed` 时不得选择为 best。
- `metric_after >= metric_before` 或 metric 缺失时不得选择为 best。
- `semantic_status` 必须是 `unknown`、`preserved`、`changed`、`failed`；只有 `preserved` 可选 best。
- `scope_status` 必须是 `production_safe`、`benchmark_specialized`、`rejected`；默认 final output 只允许 `production_safe`。
- `portability_risk=high` 或 `accepted_for` 不含 `production` 时，不得选择为 `best_op`，即使 duration 更低。
- `measurement_evidence.measurement_status` 必须为 `stable` 才能声明确定性性能提升；否则只能报告探索性结果。
- gate 失败必须写入 `failure_handoff`：accuracy -> `ascendc-precision-debug`；runtime -> `ascendc-runtime-debug`；timeout/crash/AIC -> `ascendc-crash-debug`；profile 缺失 -> `ops-profiling`；metric regression -> `optimization_memory_next_candidate`。
- simulator-only metric 必须在报告中标注为 proxy。

## optimization_memory.jsonl

长期 memory，每行一个 JSON record。用于避免重复尝试已知失败补丁和复用已成功策略。

```json
{
  "created_at": "2026-07-16T00:00:00Z",
  "op_name": "FastGelu",
  "shape": "float32[8, 2048]",
  "dtype": "float32",
  "soc": "Ascend910B1",
  "problem_family": "tiling",
  "strategy_id": "tiling_task_tile_shape_rewrite",
  "status": "success",
  "metric_before": 10.8,
  "metric_after": 8.9,
  "speedup": 1.213,
  "failure_reason": null,
  "failure_handoff": null,
  "changed_files": [
    "op_kernel/fast_gelu_kernel.asc"
  ]
}
```

约束：

- `status` 使用 `success`、`failed`、`skipped`、`manual_required`。
- 记录维度必须包含 `op_name + shape + dtype + soc + problem_family + strategy_id`。
- 编译错误、API 限制、精度失败、runtime/crash 和性能回退都要记录，失败原因与 `failure_handoff` 应简短可搜索。
