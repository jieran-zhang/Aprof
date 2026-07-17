# GLM 盲诊 Demo 说明

对应实现：`plugins/aprof-performance-workflow/demo/`。

## 目标

在不依赖 Cursor 会话的情况下，用智谱 **GLM-5.2** 对 `aprof_benchmark/fast_gelu` 匿名 case 做源码级盲诊，验证：

1. 输入是完整可编译直调工程（`op_host` + `CMakeLists` + `op_kernel`）
2. 不向模型暴露 `.ground_truth`
3. 输出符合 `single_case_diagnosis.json` 契约

## 数据流

```text
operators/op_XXXX
    → build_blind_diagnosis_input.py
    → blind_input.json
    → GLM-5.2 (system prompt = diagnosis agent 规则)
    → single_case_diagnosis.json
    → (optional) offline_alignment.json  ← 仅本地读 GT
```

## 配置

- Key：`configs/secrets/glm.env`（gitignore）
- 模板：`configs/secrets/glm.env.example`
- 模型默认：`glm-5.2`，endpoint：`https://open.bigmodel.cn/api/paas/v4/chat/completions`

## 与 910B

本 demo **默认不上板**。若要加硬件证据：

1. 本机或远程 `bash run.sh hw`
2. 把 `OpBasicInfo.csv` 等摘要并入盲诊输入后再调 API
3. 可选上传脚本模板：`plugins/aprof-performance-workflow/demo/upload_case_for_hw.example.sh`

远程凭据仍使用 gitignored 的 `scripts/run_remote_*.py` / `scripts/server_config.json`。
