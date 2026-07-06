# AProf Agent Contracts

本文定义 AProf workflow 中三个 agent 之间传递的结构化契约。字段名必须保持稳定；未知信息使用 `null`、空数组或 `unknown`，不要编造。

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

由 `aprof-profiling-agent` 产出。输入是 `metrics[]` 及其描述，输出 msprof 采集方案、远程执行参数和 report 解析方案。

```json
{
  "plan_id": "P1",
  "input_metrics": [
    "single_copyin_bytes"
  ],
  "profile_mode": "hw-op",
  "mode_reason": "需要 Memory.csv 与 PipeUtilization.csv 中的真实硬件计数，simulator 无法直接产出 8 CSV",
  "msprof_command": {
    "preferred": "msprof op --warm-up=3 --output=../msprof_hw_output ./<binary> <args>",
    "fallback": "bash ../ops_profiling/scripts/msprof_profile_run.sh --warm-up=3 --output=../msprof_hw_output -- ./<binary> <args>",
    "simulator": "msprof op simulator --config=./op_config.json --output=../msprof_sim_output --timeout=8"
  },
  "required_artifacts": [
    {
      "path_pattern": "msprof_hw_output/OPPROF_*/Memory.csv",
      "reason": "读取 GM_to_UB_datas 与 MTE 指令数"
    }
  ],
  "optional_artifacts": [
    {
      "path_pattern": "msprof_hw_output/OPPROF_*/PipeUtilization.csv",
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
  "remote_deploy_args": {
    "profile_mode": "hw-op",
    "run_cmd": "./<binary> <args>",
    "gen_data_cmd": null,
    "warm_up": 3,
    "summarize": true,
    "steps": "upload,build,profile,summarize,download"
  },
  "handoff": {
    "next_agent": "aprof-remote-kernel-deploy",
    "after_remote": "aprof-diagnosis-agent"
  }
}
```

约束：

- 优先选择能直接产出所需 metric 的真实硬件模式：`hw-op` 或 `hw-msprof`。
- 只有 metric 可由 `trace.json`、`*_instr_exe_*.csv` 或 `*_code_exe_*.csv` 代理，或远端无 NPU 时，才选择 `sim`。
- `remote_deploy_args.profile_mode` 必须是 `sim`、`hw-msprof`、`hw-op` 之一，并与 `profile_mode` 一致。

## artifact_manifest.json

由 remote deploy 阶段在本地 `remote_out` 下生成，或由 workflow 根据 `deploy_results.json` 与下载文件列表补齐。用于判断 `profiling_plan.json` 是否已满足。

```json
{
  "profile_mode": "hw-op",
  "local_out": "benchmarks/example/remote_out",
  "deploy_results": "benchmarks/example/remote_out/deploy_results.json",
  "artifacts": [
    {
      "kind": "csv",
      "name": "Memory.csv",
      "path": "benchmarks/example/remote_out/msprof_hw_output/OPPROF_xxx/Memory.csv",
      "satisfies": [
        "single_copyin_bytes"
      ]
    }
  ],
  "missing_required_artifacts": [],
  "ready_for_diagnosis": true,
  "notes": []
}
```

约束：

- `ready_for_diagnosis` 只有在 `missing_required_artifacts` 为空时才能为 `true`。
- sim 模式至少需要 `trace.json` 或 `*_instr_exe_*.csv` 才能进入 sim-only 诊断。
- hw-op 模式优先确认 `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`。
- hw-msprof 模式优先确认 `PROF_GROUP_*` 下的 CSV、`aicore.db` 或 `remote_hw_summary.txt`。

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
  "diagnoses": [
    {
      "id": "D1",
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
