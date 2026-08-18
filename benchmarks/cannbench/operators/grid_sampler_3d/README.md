# grid_sampler_3d Ascend C 直调框架

面向 Ascend 910（`dav-2201`）的 5D `grid_sample` 直调实现，覆盖 cann-bench level2
定义的 20 个原始 cases。支持 FP16/FP32、trilinear/nearest、zeros/border/reflection
和 `align_corners=true/false`。

```bash
source /usr/local/Ascend/cann-9.0.0/set_env.sh
./run.sh --case 1 --device 0
./run.sh --all --device 0
```

单 case 产物位于 `build/cases/case_XX/result.json`；全量通过后由
`scripts/summarize.py` 生成仓库内的 `results.json`。运行脚本在验证后删除大体积
输入/输出 `.bin`，保留 metadata 与评测结果。

目录结构：

- `op_kernel/`：tiling 数据与 Ascend C kernel
- `op_host/`：ACL 初始化、内存管理、kernel launch 与端到端耗时采集
- `scripts/`：20 cases、流式数据生成、PyTorch golden 校验、结果汇总
- `docs/grid_sampler_3d/`：定义、设计、状态和故障排查记录
