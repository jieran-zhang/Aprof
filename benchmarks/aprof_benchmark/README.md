# aprof_benchmark

Agent 可见的性能诊断 benchmark 金标准布局。当前样例算子：`fast_gelu`。

## 布局

```text
fast_gelu/
├── fast_gelu_kernel.asc           # 单 kernel 源（脚手架输入）
├── direct_invoke_baseline/        # ascendc-kernel-direct-invoke 生成的完整可编译工程
├── operators/op_XXXX/             # 在完整工程上注入问题后的匿名 case
├── common/run_direct_invoke.sh
├── benchmark_manifest.json        # 公开 case 列表（无 problem_id）
└── .ground_truth/                 # 维护者专用；诊断 agent 禁止读取
    └── case_problem_map.json
```

管线：

1. 单 kernel → `/ascendc-kernel-direct-invoke` → `direct_invoke_baseline`
2. 在完整工程内注入问题 → `operators/op_XXXX`
3. 答案只写 `.ground_truth/case_problem_map.json`

## 跑一个 case

```bash
cd benchmarks/aprof_benchmark/fast_gelu/direct_invoke_baseline
bash run.sh all

cd ../operators/op_0001
bash run.sh all
```

## 给诊断 agent 的输入约定

| 可读 | 禁止 |
|------|------|
| `direct_invoke_baseline/` | `.ground_truth/` |
| `operators/op_XXXX/` | 任何答案映射 / 带问题标签的报告 |
| `benchmark_manifest.json` / `case_metadata.json` | |

GLM API 盲诊 demo（源码 → `single_case_diagnosis.json`）：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py
```

详见 `plugins/aprof-performance-workflow/demo/README.md`。

更大规模的注入集（同布局）见 `benchmarks/aprof_injected_ops/`。
