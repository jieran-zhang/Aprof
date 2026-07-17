# AProf Injected Ops Benchmark（Agent 可见面）

> 布局对齐 `benchmarks/aprof_benchmark/fast_gelu`  
> 诊断 agent **禁止**读取各算子下的 `.ground_truth/` 与仓库内 `.maintainer_artifacts/`

## 目录结构（每个算子）

```
<op>/
├── benchmark_manifest.json      ← 公开：case 列表与编译状态（无 problem_id）
├── common/run_direct_invoke.sh
├── direct_invoke_baseline/      ← 完整可编译直调工程（对照）
├── operators/
│   ├── op_0001/ … op_00NN/      ← 匿名注入 case（完整可编译工程）
└── .ground_truth/               ← 维护者专用（诊断禁止）
    └── case_problem_map.json
```

每个 case（baseline 或 `op_XXXX`）包含：

- `CMakeLists.txt` / `op_host/` / `op_kernel/` / `scripts/`
- `case_metadata.json`：仅 `case_id` / `kernel` / `dtype` / `shape` / `blockdim` / `tile_length`
- 编译期开关：`APROF_FEATURE_XX`（中性宏名，不出现问题标签）

## 如何运行

```bash
cd benchmarks/aprof_injected_ops/<op>/direct_invoke_baseline
bash run.sh all        # build + gen + run + verify
bash run.sh hw         # msprof op onboard
bash run.sh profile    # msprof --application
```

匿名 case：

```bash
cd benchmarks/aprof_injected_ops/<op>/operators/op_0001
bash run.sh all
```

## 盲诊约定

| 可读 | 禁止 |
|------|------|
| `direct_invoke_baseline/` | `.ground_truth/` |
| `operators/op_XXXX/` | `.maintainer_artifacts/` |
| `benchmark_manifest.json` | 任何答案映射 / 带问题标签的结果文件 |
| `case_metadata.json` | 历史注入报告与带标签的汇总 JSON |

离线对齐准确率时，维护者使用 `.ground_truth/case_problem_map.json`。

## GLM 盲诊（可选）

金标准 demo 在 `aprof_benchmark/fast_gelu`；同一套盲诊脚本也可指向本目录下的 case：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py \
  --case-dir benchmarks/aprof_injected_ops/mish/operators/op_0005
```

详见 `plugins/aprof-performance-workflow/demo/README.md` 与 `docs/glm_diagnosis_demo.md`。

## 管线说明（给维护者）

1. 单 kernel → `/ascendc-kernel-direct-invoke` 脚手架 → `direct_invoke_baseline`
2. 在完整工程上注入问题 → 复制为 `operators/op_XXXX`，宏改为 `APROF_FEATURE_XX`
3. 答案只写入 `.ground_truth/case_problem_map.json`
4. 用 `benchmark_manifest.json` 做公开面泄漏扫描

## 算子列表

见各算子目录：`fast_gelu`, `gelu_mul`, `mish`, `swi_glu`, `fast_gelu_grad`, `foreach_norm`, `matmul`, `conv2d`, `layer_norm`, `topk`, `max_pool`。
