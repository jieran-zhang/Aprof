# GLM 盲诊 Demo（fast_gelu）

用 `benchmarks/aprof_benchmark/fast_gelu` 的匿名 case，走一遍：

**盲诊输入 → GLM-5.2 → `single_case_diagnosis.json`**

不把 `.ground_truth/` 交给模型；可选在本地做 offline 对齐。

## 前置

1. 配置 API Key（已 gitignore）：

```bash
cp configs/secrets/glm.env.example configs/secrets/glm.env
# 编辑写入 ZHIPU_API_KEY=...
```

或：

```bash
export ZHIPU_API_KEY=...
```

2. 默认 case：`benchmarks/aprof_benchmark/fast_gelu/operators/op_0001`  
   （完整可编译直调工程：`CMakeLists` + `op_host` + `op_kernel`）

## 一键跑通（源码盲诊，不上板）

在仓库根目录：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py
```

只生成盲诊输入、不调 API：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py --dry-run
```

换 case：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py \
  --case-dir benchmarks/aprof_benchmark/fast_gelu/operators/op_0002
```

## 产物（`demo/out/`，已 gitignore）

| 文件 | 说明 |
|------|------|
| `blind_input.json` | 发给模型的脱敏输入 |
| `single_case_diagnosis.json` | 模型诊断（契约见 `skills/aprof/references/contracts.md`） |
| `final_diagnosis.md` | 人类可读摘要 |
| `offline_alignment.json` | **仅维护者**：与 `.ground_truth` 对比（未发给模型） |
| `glm_raw_response.json` | 原始 API 响应 |

## 与 plugin workflow 的关系

```text
@aprof-performance-workflow          ← Cursor 内编排（可走完整 diagnosis↔profiling）
demo/run_glm_diagnosis_demo.py       ← 最小 API 闭环：源码盲诊 → GLM → JSON
```

完整状态机见 `../workflows/aprof-performance-workflow.md`。本 demo 对应 Step 1（源码诊断）；若要接 910B msprof，可：

1. 在 case 目录执行 `bash run.sh hw`（本机或远程）
2. 把 CSV / OpBasicInfo 摘要并入盲诊输入后再调 GLM
3. 可选模板：`upload_case_for_hw.example.sh`（需自行填 SSH 凭据）

## 安全约定

- 诊断输入路径禁止包含 `.ground_truth/`、`.maintainer_artifacts/`
- `case_metadata.json` 只含 shape / blockdim / tile_length 等中性字段
- API Key 只放 `configs/secrets/glm.env`，勿写入 README / commit
