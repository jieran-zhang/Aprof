# A16W16非量化矩阵乘算子

## 概述

本示例展示了A16W16非量化矩阵乘算子在昇腾AI处理器上的完整实现，包含基于SWAT模板和StreamK模板的高性能优化方案。A16W16支持Float16、BFloat16数据类型，是深度学习中最基础且最重要的计算操作，广泛应用于各种神经网络层，包括全连接层、注意力机制等。

当前目录提供以下能力：

- `matmul_a16w16_swat`：基于SWAT模板的实现。
- `matmul_a16w16_streamk`：基于StreamK模板的实现。
- `gen_data.py`：生成输入数据和CPU golden结果。
- `verify_result.py`：校验NPU输出与CPU golden是否一致。
- `matmul_a16w16_algorithm_recommend.py`：对当前目录下可执行算法进行兼容性筛选和耗时排序。

## 使用约束

当前样例支持以下场景：

- A的形状为`[M, K]`(非转置)或`[K, M]`(转置)
- B的形状为`[K, N]`(非转置)或`[N, K]`(转置)。
- 输出矩阵C的形状为`[M, N]`。
- 支持数据类型：Float16、BFloat16，矩阵A,B,C数据类型需保持一致。
- 默认数据类型为BFloat16，如果需要更改请同步修改以上代码文件。

### StreamK 输入范围限制

`matmul_a16w16_streamk` 对输入参数有特定的范围要求，需满足以下条件之一：

1. **SK 模式**：
   - K 维度需足够大（建议 K ≥ 8192）
   - M 和 N 的切分块数乘积不超过 AIC 核数的一半

2. **DPSK 模式**：
   - M 和 N 需为 256 的倍数
   - K 维度需足够大（建议 K ≥ 8192）
   - M 和 N 的总切分块数大于 AIC 核数，尾轮块数不超过 AIC 核数的一半

M 和 N 切分块数的计算：
$$
totalNum = \frac{N}{baseN} \times \frac{M}{baseM}
$$

如果输入参数不满足上述条件，直接运行 `matmul_a16w16_streamk` 将会报错退出，详细条件判断可以参考[具体tiling计算](../../include/tiling/matmul_tiling_streamk.h)。建议使用算法推荐脚本自动选择适合当前形状的算法。

## 支持架构

NPU ARCH 3510

## 性能优化指南

关于算子涉及的模板实现及优化策略，请参考[非量化矩阵乘算子性能优化指南](../../../docs/matmul_performance.md)

## API参考

[Ascend C API文档](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/850/API/ascendcopapi/atlasascendc_api_07_0003.html)

## 参数说明

两个可执行文件的命令行参数格式一致：

```text
<program> m k n [transA transB]
```

- `m`：矩阵A的行数。
- `k`：矩阵A的列数，同时也是矩阵B的归约维。
- `n`：矩阵B的列数，对应输出矩阵的列数。
- `transA`：矩阵A的转置信息（可选，默认为false）。
- `transB`：矩阵B的转置信息（可选，默认为true）。

在当前布局下，如果不传入转置信息，默认A矩阵非转置，B矩阵转置：

- A按`[M, K]`组织。
- B按`[N, K]`组织。
- 输出矩阵C的形状为`[M, N]`。

## 数据与校验

`gen_data.py`会在当前目录下生成以下文件：

- `input/input_a.bin`
- `input/input_b.bin`
- `output/cpu_output.bin`

样例执行完成后会额外生成：

- `output/npu_out.bin`

两个可执行文件在运行结束后都会自动调用`verify_result.py`，将NPU输出与CPU golden进行一致性校验。

## 一键运行（推荐）

仓库提供 `run.sh`（位于 `matmul_recipes/examples/matmul_a16w16/scripts/`），可一键串联 **构建 → 数据生成 → 算子执行 → 结果校验** 全流程。
推荐先进入样例目录再执行，命令更短：

```bash
cd Samples/2_Performance/matmul_story/matmul_recipes/examples/matmul_a16w16

# 自动构建 + 自动推荐最优算法 + 运行
bash scripts/run.sh 128 16384 128

# 带转置参数
bash scripts/run.sh 128 16384 128 false true

# 指定目标可执行文件，跳过重新构建
bash scripts/run.sh \
  --target matmul_a16w16_swat --skip-build 128 16384 128

# 查看完整帮助
bash scripts/run.sh --help
```

### run.sh 参数说明

| 参数 | 说明 |
|------|------|
| `m k n` | 矩阵维度（必填）。 |
| `transA transB` | 转置参数（可选）。默认 `false true`，即 A 不转置、B 转置。 |
| `--target <name>` | 指定要运行的可执行文件名。省略时自动调用推荐脚本选择最优目标。 |
| `--skip-build` | 跳过构建/安装阶段，复用已有 `build_out`。 |
| `-h, --help` | 显示帮助信息。 |

如需查看完整算法推荐排名（含耗时表格），请在安装目录下直接运行 `matmul_a16w16_algorithm_recommend.py`（见下文「手动构建与运行」）。

## 手动构建与运行

如需手动控制各步骤，可在仓库根目录下完成编译和安装后，进入当前样例目录：

```bash
cmake -S . -B build -DNPU_ARCH=dav-3510
cmake --build build --parallel
cmake --install build --prefix ./build_out
cd build_out/2_Performance/matmul_story/matmul_recipes/matmul_a16w16
```

### 1. 生成测试数据

```bash
python3 gen_data.py 128 16384 128 false true
```

### 2. 运行单个算法样例

```bash
./matmul_a16w16_swat 128 16384 128
```

或：

```bash
./matmul_a16w16_streamk 128 16384 128
```

带转置参数：

```bash
./matmul_a16w16_swat 128 16384 128 false true
```

### 3. 运行算法推荐脚本

```bash
python3 matmul_a16w16_algorithm_recommend.py 128 16384 128
```

或带转置参数：

```bash
python3 matmul_a16w16_algorithm_recommend.py 128 16384 128 false true
```

下图为推荐脚本输出的**结构示意**（数值为虚构，仅说明版式）：

```text
[Profile Breakdown]
+---------------------------+----------+---------+----------+---------+---------+------------+--------------+
| algorithm                 |kernel(us)| mac(us) |scalar(us)| mte1(us)| mte2(us)|fixpipe(us) |icache_miss(%)|
+===========================+==========+=========+==========+=========+=========+============+==============+
| matmul_a16w16_swat        |    12.345|   1.234 |     0.567|   0.123 |   0.456 |     0.789 |        0.100 |
| matmul_a16w16_streamk     |    15.678|   2.100 |     0.800|   0.200 |   0.300 |     0.500 |        0.250 |
+---------------------------+----------+---------+----------+---------+---------+------------+--------------+
```
