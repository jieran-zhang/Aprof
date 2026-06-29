---
name: ascendc-msprof-simulator
description: 从用户提供的 Ascend C kernel 文件夹，端到端跑通 `msprof op simulator` 并采集到性能报告（trace.json / visualize_data.bin / instr_exe.csv）。覆盖两步：(1) 调用 ops-ascendc-direct-invoke-template 搭建并编译直调工程；(2) 用 `--config` 模式正确设置 msprof op simulator 跑出报告。触发：当用户已有 kernel.asc 想拿到 simulator profiling 报告、提及 "msprof op simulator"、"算子仿真性能"、"kernel-launcher"、"op_config.json" 时使用。参考验证工程：`benchmarks/reference_ops/reduce_sum/`。
---

# Ascend C Kernel → msprof op simulator 端到端 SOP

本 skill 把"我有一个写好的 kernel.asc，请帮我拿到 simulator 性能报告"这一整条链路固化成可复用流程。

- **输入**：用户给定一个 kernel 文件夹，至少包含一个 `*_kernel.asc`（或对应 tiling 头文件）。
- **输出**：`OPPROF_*/device0/<kernel>/0/simulator/` 下的 `trace.json`、`visualize_data.bin`、以及每核 `*_instr_exe_*.csv`、`*_code_exe_*.csv`。
- **验证基线**：`benchmarks/reference_ops/reduce_sum/` 是已跑通的参考样例，所有命令在该工程上经过实测。

> 平台：本 skill 在 `Ascend950PR_950x` simulator（CANN 9.1.0-beta.1，`dav-3510` 架构）上验证。其他 Ascend SoC 替换 `--npu-arch` 与 simulator 目录名即可。

---

## Step 0：前置检查

| 项 | 要求 | 验证命令 |
|---|---|---|
| CANN 环境 | 已 `source scripts/setup_env.sh`，`$ASCEND_HOME_PATH` 指向 CANN 安装根 | `echo $ASCEND_HOME_PATH` |
| Simulator 目录 | `$ASCEND_HOME_PATH/tools/simulator/Ascend950PR_950x/` 存在（或目标 SoC 同名目录） | `ls $ASCEND_HOME_PATH/tools/simulator/` |
| `LD_LIBRARY_PATH` | 已 prepend simulator lib（`setup_env.sh` 自动做了） | `echo $LD_LIBRARY_PATH \| tr : '\n' \| head -1` |
| 编译器 | `bisheng` 和 `ld.lld` 都在 `$ASCEND_HOME_PATH/bin/` 下 | `which bisheng ld.lld` |
| msprof 工具链 | `$ASCEND_HOME_PATH/tools/msopprof/bin/{msopprof,kernel-launcher}` 存在 | `ls $ASCEND_HOME_PATH/tools/msopprof/bin/` |

任一不满足，先去补环境，不要继续。

---

## Step 1：用 `ops-ascendc-direct-invoke-template` skill 搭直调框架并编译

**调用方式**：本 skill 不重复 direct-invoke 模板的内容，把 kernel 工程化的工作完全交给 `ops-ascendc-direct-invoke-template` skill。流程是：

1. 路由分支（vector / matmul / mxfp8 fusion）。参考路径：
   - Vector → `references/add_custom/`
   - Matmul / Cube（dav-3510）→ `references/matmul_custom/`
   - mxfp8 matmul+eltwise → `references/matmul_fusion_guide.md`
2. 复制模板、改名、按 `[MODIFY]` 标记填空：kernel 类、入口函数、tiling 结构体、IO 数量、CMake 目标名、`--npu-arch`。
3. 编译并跑通（host 版本，真机用）：
   ```bash
   cd <your_op>
   bash run.sh          # 全流程；--skip-build 可只跑测试
   ```
4. 编译验收：`build/<your_op>` 存在，并且 host 端 `aclInit` 成功（真机环境）。

> **注意**：host 可执行文件 **只能在真机上跑**。在没有 NPU 的机器上 `aclInit` 会失败，这是预期。本 skill 后续 simulator 路径**不依赖**这个可执行文件，所以即使 host 端跑不起来也不影响。

---

## Step 2：把 kernel 单独编成 device-side `.o`（simulator 用）

`msprof op simulator --config` 不接受整体 host ELF，需要的是单独的 device-side kernel `.o`。两步编译：

```bash
source scripts/setup_env.sh
cd <your_op>
mkdir -p build_sim
BISHENG=$ASCEND_HOME_PATH/bin/bisheng
LD=$ASCEND_HOME_PATH/bin/ld.lld

# 1) 编译 object（aicore-only + asc-aicore-lang）
"$BISHENG" -fPIC --aicore-only --npu-arch=dav-3510 -O2 \
    -I op_kernel -I op_host \
    -I "$ASCEND_HOME_PATH/include" \
    -I "$ASCEND_HOME_PATH/x86_64-linux/include" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
    --asc-aicore-lang -c op_kernel/<your_op>_kernel.asc \
    -o build_sim/<your_op>_kernel.obj

# 2) 链接成 device 端 final ELF
"$LD" -m aicorelinux -Ttext=0 build_sim/<your_op>_kernel.obj -static \
    -o build_sim/<your_op>_kernel.o

file build_sim/<your_op>_kernel.o
# 期望: ELF 64-bit LSB executable, *unknown arch 0x1029*, statically linked
```

完整可执行脚本见 [`references/build_kernel_o.sh`](references/build_kernel_o.sh)。

**Tips**：
- 想要 `*_code_exe_*.csv` 能映射回源码（代码热点），`bisheng` 命令加 `-g`。否则该 CSV 只有 header。
- 不同 SoC 改 `--npu-arch` 即可（dav-3510 = Ascend950）。

---

## Step 3：准备 `input.bin`、`tiling.bin`、`op_config.json`

### 3.1 输入数据 + tiling 二进制

按 kernel 期望的 layout 写 bin。模板见 [`references/gen_input_tiling.py`](references/gen_input_tiling.py)。最小例子（ReduceSum 1×8 fp32，单核）：

```python
import struct, numpy as np
np.arange(1*8, dtype=np.float32).tofile("build_sim/input.bin")
# 按 host 端 ComputeTiling 的输出顺序打包：m, n, inputStrideN, rowsPerCore, perLoopN, perLoopNAligned, loopCount, tailN
open("build_sim/tiling.bin", "wb").write(struct.pack("8I", 1, 8, 8, 1, 8, 8, 1, 0))
```

### 3.2 `op_config.json`（关键 schema，最容易写错的地方）

**顶层字段** vs **`test_cases` 内层字段** 不能搞错：

```json
{
  "kernel_name": "<your_op>_kernel",                       // 顶层！必须等于 kernel 入口函数名
  "kernel_path": "./<your_op>_kernel.o",                   // 顶层！指向 Step 2 编出来的 device ELF
  "blockdim": 1,                                            // 顶层！等于 host 端 <<<>>> 第一个参数
  "mode": "ca",                                             // 顶层！ca = cycle accurate
  "device_id": 0,                                           // 顶层！simulator 必须 0
  "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",                 // 顶层！vector 用 AIVEC，cube 用 AIC
  "test_cases": [
    {
      "case_name": "<your_op>_case0",                      // 自定义，会成为输出目录的一部分
      "param_desc": [
        {"param_type": "input",  "type": "float32", "shape": [1, 8], "data_path": "./input.bin", "name": "x"},
        {"param_type": "output", "type": "float32", "shape": [1],                                "name": "y"},
        {"param_type": "tiling", "tiling_data_size": 32, "tiling_data_path": "./tiling.bin"}
        // 可选：{"param_type": "workspace", "user_workspace_size": 4096}
      ]
    }
  ]
}
```

完整模板见 [`references/op_config.template.json`](references/op_config.template.json)。

| 字段位置 | 字段 | 说明 |
|---|---|---|
| 顶层 | `kernel_name` | 必须等于 `extern "C" __global__ __vector__ void <name>` 中的 name |
| 顶层 | `kernel_path` | Step 2 编出的 device `.o`，相对 cwd（即 `build_sim/`） |
| 顶层 | `blockdim` | 启动核数；不要写 `block_dim`（带下划线的是 kernel-launcher 内部用的，会被忽略） |
| 顶层 | `mode` | `ca`（cycle accurate）/ `fa`（fast）等，simulator 走 `ca` |
| 顶层 | `magic` | Vector kernel = `RT_DEV_BINARY_MAGIC_ELF_AIVEC`；Cube = `RT_DEV_BINARY_MAGIC_ELF_AIC` |
| `param_desc` | `param_type` | 必须是 `input` / `output` / `workspace` / `tiling` 之一 |
| `param_desc` | `shape` / `type` / `data_path` / `name` | input/output 必填 |
| `param_desc` | `tiling_data_size` / `tiling_data_path` | tiling 必填，size 单位字节 |

---

## Step 4：运行 `msprof op simulator --config`

**注意官方约束**（[官方文档](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/910beta1/devaids/optool/docs/zh/user_guide/msopprof_simulator_user_guide.md)）：

- `--config` 模式 **不支持 `--soc-version`**，必须用 `LD_LIBRARY_PATH` 指定 simulator（`scripts/setup_env.sh` 已做 prepend）。
- `--config` 模式 **不要 `--aic-metrics=PipeUtilization`**，simulator 模式根本不产 `pipe_utilization.csv`，加了反而可能干扰。
- `--timeout` 单位是分钟，范围 1..2880，**官方建议单次 ≤5 分钟**。

```bash
source scripts/setup_env.sh
cd <your_op>/build_sim
rm -rf ../msprof_sim_output/OPPROF_*

msprof op simulator \
    --config=./op_config.json \
    --output=../msprof_sim_output \
    --timeout=10
```

**预期 stdout 关键行**（表示 simulator 真的注入并跑了 kernel）：

```text
[INFO]  Running simulation task: Binary Simulation Running, use simulator in LD_LIBRARY_PATH
[INFO]  Top sim cfg file: .../dav_3510/lib/Ascend950pr_9599_sim.toml
[INFO]  AicWrapper attach AIC 0..N, num_vec_core=2, num_subcore=3
[INFO]  <ProfInit> Start profiling on kernel: <your_op>_kernel
[info]  [block_start] : AIV, task_id=0, core_id=0, block_id=0
[info]  [block_end]   : AIV, task_id=0, core_id=0, block_id=0
```

**耗时参考**（在本机 1×8 fp32 ReduceSum 单核）：
- Kernel 仿真（CA 模式）：~3 分钟
- kernel-launcher 解析 7000+ raw dump → trace.json + visualize_data.bin：~7 分钟
- **总计 ~10 分钟**

shape 越大 / blockdim 越多，时间几何级增长。第一次跑用最小 shape 验证链路是否通。

---

## Step 5：定位报告

成功后产物布局（已实测验证）：

```text
<your_op>/msprof_sim_output/OPPROF_<timestamp>_<id>/
└── device0/
    ├── tmp_dump/                              # 7000+ raw simulator dumps（中间产物）
    └── <kernel_name>/<launch_idx>/
        ├── dump/                              # per-launch raw dumps
        └── simulator/
            ├── trace.json                     # 全图 timeline（Chrome / MindStudio Insight）
            ├── visualize_data.bin             # MindStudio Insight 可视化
            └── <core>.<unit>/                 # 例: core0.veccore0
                ├── <core>_code_exe_*.csv      # 代码热点（需 -g 编译才有数据）
                ├── <core>_instr_exe_*.csv     # 指令级 cycles + pipe + detail
                └── trace.json                 # 单核 timeline
```

| 报告 | 内容 | 打开方式 |
|---|---|---|
| `trace.json`（全图） | 所有 PIPE 在 timeline 上的运行情况、依赖关系 | `chrome://tracing` 拖入 / MindStudio Insight |
| `trace.json`（单核） | 单核内每条指令的时间线 | 同上 |
| `visualize_data.bin` | 时间线 + 代码热点 + GM 带宽视图（全特性） | MindStudio Insight 专用 |
| `*_instr_exe_*.csv` | 每条指令的 `cycles` / `pipe` / `running_time(us)` / `detail` | 直接读 / `pandas` 按 cycles 排序找热点 |
| `*_code_exe_*.csv` | 每行源码对应的 cycles | 仅 `bisheng -g` 时有数据 |

**实测样本**（`core0.veccore0_instr_exe_*.csv` 真实片段）：
```text
instr,addr,pipe,call_count,cycles,running_time(us),detail
VF,282121064,PUSHQ,1,564,0.300000,"addr:0x10d0da00,instr_num:0x8,"
SET_FLAG,282121124,VECTOR,1,555,0.300000,"PIPE:VEC,TRIGGERPIPE:SCALAR,FLAGID:0xffffffff,"
ST_XD_XN,282120960,SCALAR,1,546,0.300000,"dtype:B32,XD:X24=0,XN:X7=0x1b94d800,..."
```

---

## 常见错误与对策（按出现频率排序）

| 报错 / 现象 | 真正原因 | 修复 |
|---|---|---|
| `Json config error, param:[xxx] is not exist` | `op_config.json` schema 错（最常见：把 `kernel_name`/`kernel_path` 写到 `test_cases` 里去了） | 严格按 Step 3.2 的顶层 vs 内层结构写 |
| `--soc-version is not effective in config mode` | 用了 `--soc-version` | 删掉这个参数，靠 `LD_LIBRARY_PATH` |
| `Top sim cfg` 加载不到 / `Failed to load ini ...PR_xxx.ini` | 用了 simulator 目录没有同名 ini 的 SoC（symlink + 缺 ini） | 换成天然成对的 SoC（如 Ascend950PR_9599），或者补 ini |
| 卡 10 分钟无输出，最终 timeout，`device0/` 空或只有 `tmp_dump/` | `msprof op simulator --application ./host_elf` 模式，simulator HAL `SetOverflowAddr` 失败导致 host 卡死 | **改用 `--config` 模式**，不要用 `--application` |
| `aclrtSetDevice failed: 107001` | 同上的 `--application` 模式 + 自己额外预 prepend 了 simulator lib 与 msprof 注入冲突 | 改用 `--config` 模式 |
| `*_code_exe_*.csv` 只有 header | `bisheng` 没加 `-g` | 编 kernel.obj 时加 `-g` |
| host `./reduce_sum` 单独跑 `aclInit failed: 500000` | 机器无真机 NPU，host 必须靠 msprof 包裹注入的 simulator HAL 才能跑 | 这是预期，simulator profiling 不依赖 host elf |

---

## 完整一键脚本

把 Step 2 ~ Step 4 串起来（针对一个已经按 direct-invoke 模板搭好的 `<your_op>/`）：

```bash
#!/usr/bin/env bash
set -euo pipefail
source scripts/setup_env.sh

OP_NAME=${1:?usage: $0 <your_op>}
OP_DIR=$(realpath "benchmarks/reference_ops/$OP_NAME")
cd "$OP_DIR"
mkdir -p build_sim msprof_sim_output

# 1) device-side kernel .o
bash "$(dirname "$(realpath "$0")")/references/build_kernel_o.sh" "$OP_NAME"

# 2) input / tiling bin（按算子自定义；ReduceSum 默认参数演示）
python3 "$(dirname "$(realpath "$0")")/references/gen_input_tiling.py" --op "$OP_NAME"

# 3) op_config.json（按算子手工准备一次即可，路径相对 build_sim/）
[ -f build_sim/op_config.json ] || cp "$(dirname "$(realpath "$0")")/references/op_config.template.json" build_sim/op_config.json

# 4) run msprof
cd build_sim
rm -rf ../msprof_sim_output/OPPROF_*
msprof op simulator --config=./op_config.json --output=../msprof_sim_output --timeout=10

# 5) 输出指向
latest=$(ls -td ../msprof_sim_output/OPPROF_* | head -1)
echo "Reports in: $latest/device0/${OP_NAME}_kernel/0/simulator/"
ls "$latest/device0/${OP_NAME}_kernel/0/simulator/"
```

---

## 进程清理 / 故障排查 quick commands

```bash
# 清残留进程（msopprof / kernel-launcher 跑久了可能挂住 build_sim/ 不让删）
pkill -9 -f "msopprof simulator" 2>/dev/null
pkill -9 -f "kernel-launcher"    2>/dev/null

# 看 simulator 失败时的真实日志
ls -t ~/ascend/log/debug/plog/ | head
tail -80 ~/ascend/log/debug/plog/$(ls -t ~/ascend/log/debug/plog/ | head -1)
```

---

## 参考材料

- 已跑通的样例：[`benchmarks/reference_ops/reduce_sum/`](../../../benchmarks/reference_ops/reduce_sum/)，含完整 `op_kernel/`、`op_host/`、`scripts/` 和 `docs/direct_invoke_msprof_sop.md`。
- direct-invoke 框架细节：`.cursor/skills/ops-ascendc-direct-invoke-template/SKILL.md`
- 仿真器整体概念：`.cursor/skills/ops-ops-simulator/SKILL.md`
- 官方 msopprof simulator 指南：<https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/910beta1/devaids/optool/docs/zh/user_guide/msopprof_simulator_user_guide.md>
- 官方 `op_config.json` schema 示例（CANN 8.0.RC3 alpha）：<https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/80RC3alpha003/devaids/auxiliarydevtool/atlasopdev_16_0104.html>
