# foreach_addcdiv_scalar Ascend C 实现

来源：cann-bench level1 `foreach_addcdiv_scalar` 的 desc/proto/golden/cases
来源类型：规格说明 + PyTorch golden
创建时间：2026-08-11
目标芯片：SocVersion=Ascend910_9362 / NpuArch=dav-2201（flash skill detector 实测）

## 规格与设计

- [x] 原始 schema 保持为三组 `Tensor[]` 输入、float scalar、`Tensor[]` 输出
- [x] 定义文档记录公式、dtype、特殊值和原始 case 范围
- [x] 设计文档记录 TensorList 承载、chunk、tiling、UB 预算、Cast 链与尾块

## 实现

- [x] 完整 AscendC device kernel
- [x] host tiling 与 ACL 直调入口
- [x] FP16/FP32/BF16 分发，FP16/BF16 使用 FP32 compute
- [x] `CMakeLists.txt` 产出可执行文件 `foreach_addcdiv_scalar`
- [x] `run.sh --case/--all/--device/--skip-build`
- [x] 原始 20 cases 数据生成、golden、精度校验和汇总

## 验证

- [x] bisheng/CMake 在 `dav-2201` 编译通过
- [x] 真实 Ascend 910 device 0 运行
- [x] 原始 20/20 cases 通过，无缩 shape、无缩 TensorList、无跳例
- [x] case 12 `scalar=inf` 特殊值分类通过
- [x] case 13 `scalar=nan` 特殊值分类通过
- [x] case 16 TensorList 长度 4 通过
- [x] `results.json` 保存逐 case MERE/MARE/阈值和总结果

## 门禁与范围

- [x] `harness.test_gate=off`，按配置跳过额外黑/白盒门禁
- [x] 按用户加速要求不做性能优化、profiling 或旧审查流程
- [x] 未提交 git：共享 worktree 开始时已有大量其他任务的 dirty changes，且本子任务要求保留 dirty worktree
