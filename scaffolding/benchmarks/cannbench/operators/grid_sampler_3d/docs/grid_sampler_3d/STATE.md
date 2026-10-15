# grid_sampler_3d Ascend C 实现

来源：`third_party/cann-bench/tasks/level2/grid_sampler_3d/{desc.md,proto.yaml,cases.yaml,golden.py}`
来源类型：PyTorch 算子规格与 20-case 矩阵
创建时间：2026-08-11
目标芯片：SocVersion=Ascend910 / NpuArch=dav-2201

## 阶段 2：可编译骨架
- [x] 创建 CMake、host、tiling 与 kernel 直调框架
- [x] `cmake/make` 在 CANN 9.0.0 下构建成功
- [x] binary 生成并记录 SHA256/mtime
- [x] 按用户要求不提交 dirty worktree

## 阶段 3：算子定义文档
- [x] 提取坐标、插值、padding、dtype 与特殊值语义
- [x] 编写 `grid_sampler_3d_definition.md`
- [x] correctness-first 快速路径下跳过重型双 Agent 评审

## 阶段 4：算子设计文档
- [x] 编写 `grid_sampler_3d_design.md`
- [x] 记录 GM 访问、64B 分核边界、FP32 计算与 Cast 链
- [x] 确认无 UB/DMA 路径
- [x] correctness-first 快速路径下跳过重型双 Agent 评审

## 阶段 5：测试套件
- [x] 原样录入 level2 全部 20 cases
- [x] 分块生成大输入，逐 batch 计算 PyTorch golden
- [x] 校验 MERE/MARE 和 NaN/Inf 掩码
- [x] 汇总真实 case result 到 `results.json`

## 阶段 6：核函数实现
- [x] FP16/FP32 dtype 分发
- [x] trilinear 与 nearest-even
- [x] zeros、border、reflection 和 align_corners
- [x] CCE 编译通过
- [x] host 采集同步 kernel wall-clock `kernel_us`

## 阶段 7：真实 NPU 验证
- [x] 源码确认不是空骨架
- [ ] Ascend 910 上 20/20 cases 通过
- [ ] `results.json` 显示 `all_passed=true`

## 阶段 7.5：黑/白盒测试门禁
Harness 配置：`harness.test_gate = off`
- [x] 按配置和用户 correctness-first 要求跳过

## 阶段 8：最终文档
- [x] README、定义、设计、STATE、troubleshooting 完整
- [ ] 根据真实 NPU 结果完成最终状态
