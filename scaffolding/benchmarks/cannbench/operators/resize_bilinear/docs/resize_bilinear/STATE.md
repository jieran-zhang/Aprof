# resize_bilinear Ascend C 实现

来源：`third_party/cann-bench/tasks/level2/resize_bilinear`
目标芯片：Ascend910 / dav-2201

## 定义与设计
- [x] 分析 PyTorch 语义和原始 20 cases
- [x] 完成定义、设计和故障记录
- [x] correctness-first 跳过性能优化与重型评审

## 实现
- [x] CMake、ACL host、tiling、kernel
- [x] FP16/FP32/BF16 与 align true/false
- [x] output_size/scale_factor 解析
- [x] CANN 9.0.0 编译通过

## 验证
- [x] 20-case 数据生成、PyTorch golden、MERE/MARE/special verifier
- [x] 真实 Ascend 910 原始 20/20 cases 通过
- [x] `results.json` 为 `all_passed=true`

## 门禁与收尾
- [x] harness.test_gate=off，按配置跳过
- [x] README/definition/design/STATE/troubleshooting
- [x] 不 commit，不修改共享 JSON
