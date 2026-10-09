# apply_adam_w Ascend C 直调

该工程基于官方 `ascendc-direct-invoke-template/references/add_custom` 模板改造，提供四输入单 Kernel 直调实现。支持连续 `float32`、`float16`、`bfloat16` Tensor；半精度输入在 Kernel 内升为 FP32 计算。Host 动态查询 Vector Core 数量与每核 UB，不在 Host 上处理 Tensor 数据。

## 数学定义

```text
m_new = beta1*m + (1-beta1)*grad
v_new = beta2*v + (1-beta2)*grad*grad
m_hat = m_new / (1-beta1**step)
v_hat = v_new / (1-beta2**step)
update = m_hat / (sqrt(v_hat)+epsilon) + weight_decay*var
y = var + lr*update  (maximize=true)
y = var - lr*update  (maximize=false)
```

`epsilon` 位于 sqrt 外部；输入 `var/grad/m/v` 不会被更新。

## 构建

```bash
export ASCEND_HOME_PATH=/usr/local/Ascend/cann-9.0.0
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=ON
cmake --build build -j4
```

构建同时生成直调可执行文件 `build/apply_adam_w` 和 PyTorch 扩展 `build/libapply_adam_w_ops.so`。只需要主直调通路时可传 `-DBUILD_TORCH_EXTENSION=OFF`。

## 正确性

以下命令必须在可访问真实 NPU 设备节点的环境执行：

```bash
bash run.sh --case 1 --device 0
bash run.sh --all --device 0
python3 scripts/test_torch.py --all --device 0
bash run.sh --smoke --device 0
```

每个 case 的输入、golden、输出、metadata 和精度 JSON 位于 `build/cases/case_XX/`。数据生成器直接解析任务目录的权威 `cases.csv`，20 个 case 不做 shape 缩减。

## 性能与评分

```bash
python3 scripts/profile_cases.py --all --device 0 --warmup 3 --repeat 5 --output docs/perf/round_001
python3 scripts/score_cases.py --perf docs/perf/round_001 \
  --metadata ../../../../third_party/cann-bench/tasks/metadata/910b2.json --output results.json
```

性能脚本以 `msprof` 为每个 case 保存五次原始目录，只从包含 `apply_adam_w_kernel` 的 CSV 行提取 Task Duration，并以中位数作为 candidate 时间。`round_001` 是强制安全域修复前的 20-case 数据（旧综合分 `75.5839696285`）；修复后的代表数据位于 `round_002`。在修复版重新完成全 20-case profiling 前，`results.json` 不声明新的综合分。

## 文件结构

- `op_kernel/`：共享 TilingData 与 FP32/FP16/BF16 Ascend C Kernel。
- `op_host/`：ACL 直调 CLI、动态 tiling 和二进制 I/O。
- `op_extension/`：可选 PyTorch PrivateUse1 注册层，调用同一 Kernel。
- `scripts/`：case 解析、分块数据生成、精度验证、msprof 和 HAP 评分。
- `docs/`：设计、计划、环境与后续真实 NPU 证据。

## Kernel API 与约束

| 功能 | API | 关键约束及处理 |
|---|---|---|
| 非对齐 GM↔UB | `DataCopyPad` + 五字段 `DataCopyExtParams` | `blockLen` 为 uint32 字节且不超过 2097151；Host 按此上限与运行时 UB 动态推导 tile |
| 半精度计算 | `Cast` | FP16/BF16→FP32 使用 `CAST_NONE`，最终一次 `CAST_RINT` |
| 向量计算 | `Muls/Mul/Add/Adds/Div/Sqrt` | 只计算前 `validCount` 个元素；矩估计用显式 Muls+Add 匹配 golden 舍入 |
| 安全域 | `CompareScalar/Compare/Select/Duplicate` | Compare count 对齐到 64 个 FP32 元素；Select 模式 1/2 固定预留 8KB UB；Sqrt/Div 从不接收非正/零危险输入 |
| 特殊值恢复 | `Select` | 明确恢复 sqrt(0)、负 v_hat→NaN、0/0→NaN、非零/0→±Inf；NaN/Inf bit pattern 由 TilingData 传入 |

## 已知限制

- 仅支持连续、shape/dtype 完全一致、非空的 1～8 维 Tensor；Kernel 内按一维元素流处理。
- Host CLI 输入为原始二进制文件；部署接口不允许 Host cast、pad、transpose 或代算 Tensor。
- 当前采用单缓冲 Queue。曾在 DAV_2201 上尝试四输入双缓冲预取，但受 A2 Queue/event 资源约束发生 Kernel hang，因此未保留不安全实现。该限制影响峰值性能，不影响正确性；应在专门的 event 资源设计后再优化。
- `step>=1` 且 `0<=beta1,beta2<1`；不支持 float64 或空 Tensor。非法参数由 Host/PyTorch wrapper 拒绝。
