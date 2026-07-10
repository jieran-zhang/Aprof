---
name: ascendc-remote-kernel-deploy
description: 通过 SSH 将本地 Ascend C 算子工程同步到远程 CANN 主机，在远端完成 kernel 编译、msprof 采集（simulator / 上板 msprof / msprof op），并把 trace.json、instr_exe.csv、op_summary CSV 等报告拉回本地。触发：远程部署算子、远程 msprof 仿真或上板 profiling、SSH/SFTP 拉取报告时使用。深度指标解读见 ops-profiling skill。
---

# 远程 Kernel 编译、msprof 采集与报告拉取

本 skill 覆盖**远程部署与采集**链路：上传源码 → 远端编译 → 远端 msprof（多模式）→ SFTP 下载报告。

- **输入**：本地算子目录（simulator 用 `run.sh build/sim`；上板用 cmake 直调可执行文件）
- **输出**：本地 `{op_dir}/remote_out/` 下的 profiling 产物 + `deploy_results.json`
- **上游计划**：可接收 `/ascendc-aprof-profiling` 生成的 `profiling_plan.json`
- **直调 / simulator 细节**：`skills/aprof/benchmark/ascendc-kernel-direct-invoke/SKILL.md`
- **上板采集 / 解析细节**：`ops-profiling` skill（`msprof_profile_run.sh`、`msprof_perf_summary.py`）
- **工具**：`skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py`
- **Agent 编排**：`skills/aprof/remote-kernel-deploy/AGENTS.md`（安装：`bash skills/aprof/remote-kernel-deploy/init.sh`）

---

## msprof 命令选型（远程）

远程主机**有真机 NPU** 与**仅做 simulator** 时，选用不同命令链：

```
远程主机有 NPU 且要上板数据？
├── 否 / 仅验证 kernel 逻辑 → 【sim】msprof op simulator --config
└── 是
    ├── 需要 7 组 aic-metrics + 逐核 sample / 主 Bound 判定
    │   → 【hw-msprof】msprof_profile_run.sh 包裹可执行文件
    └── 需要 msopprof 8 CSV + PipeUtilization 闭环
        → 【hw-op】msprof op [--warm-up=N] [--launch-count=N] ./binary
```

| 模式 | 适用 | 远端核心命令 | 典型产物目录 | 解析脚本 |
|------|------|-------------|-------------|----------|
| **sim** | 无 NPU 或只要仿真 timeline | `msprof op simulator --config=./op_config.json` | `msprof_sim_output/OPPROF_*/simulator/` | 直接读 `trace.json`、`*_instr_exe_*.csv` |
| **hw-msprof** | 上板深度瓶颈（PipeUtilization 等 7 组 + sample） | `msprof_profile_run.sh --warm-up=N --output=... -- ./binary args` | `msprof_hw_output/PROF_GROUP_*/` | `msprof_perf_summary.py $PROF_GROUP ops_dir` |
| **hw-op** | 上板 msopprof 标准 8 CSV | `msprof op --warm-up=N --output=... ./binary args` | `msprof_hw_output/OPPROF_*/` | `perf_summary.py $OPPROF ops_dir` |

**环境探测**（SSH 登录后）：

```bash
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
which msprof msopprof bisheng 2>/dev/null
npu-smi info 2>/dev/null | head -5    # 有输出 → 可走上板
ls $ASCEND_HOME_PATH/tools/simulator/*/lib 2>/dev/null | head -3  # simulator lib
```

仅 `msprof` 可用 → `hw-msprof`；仅 `msopprof` / `msprof op` 语义 → `hw-op`；两者皆有 → 按项目约定或用户指定（与 `ops-profiling` 决策树一致）。


## Step 0：本地与远程前置条件

| 项 | 本地 | 远程 |
|---|---|---|
| Python | `paramiko` 已安装（如 `conda activate cann && pip install paramiko`） | `python3` 可用 |
| SSH | 私钥或密码可登录 | 用户 home 可写 |
| CANN | 无需安装 | 已安装，`source .../set_env.sh` 后 `bisheng`、`msprof` 在 PATH |
| 算子目录 | sim：`run.sh` 支持 `build`/`sim`；上板：含 `CMakeLists.txt` 的直调工程 | 上板需 `npu-smi` 可用 |

### 服务器配置

复制并填写 `scripts/server_config.json`（模板见 `scripts/server_config.example.json`）：

```json
{
  "host": "your.remote.host",
  "port": 22,
  "user": "your_user",
  "private_key": "~/.ssh/id_ed25519",
  "env": "source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh",
  "remote_root": "",
  "asc_arch": "dav-3510"
}
```

`remote_root` 留空时默认为 `/home/{user}/aprof_remote_ops/{目录名}`。

环境变量可覆盖 JSON（优先级更高）：

| 变量 | 含义 |
|---|---|
| `APROF_REMOTE_HOST` / `PORT` / `USER` / `PASS` | SSH 连接 |
| `APROF_REMOTE_PRIVATE_KEY` | 私钥路径 |
| `APROF_REMOTE_ENV` | 远端 source CANN 的命令 |
| `APROF_REMOTE_ROOT` | 远端根目录（工具会在此下建子目录） |
| `ASC_ARCH` | bisheng `--npu-arch`，如 `dav-3510` |
| `MSPROF_TIMEOUT` | msprof `--timeout`（分钟） |

### Profiling plan 输入

当上游 `aprof-profiling-agent` 已生成 `profiling_plan.json` 时，执行工具可附带：

```bash
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir <op_dir> \
  --profile-mode <sim|hw-msprof|hw-op> \
  --profiling-plan <path/to/profiling_plan.json> \
  [--run-cmd "./<binary> <args>"] \
  [--gen-data-cmd "python3 scripts/gen_data.py ..."] \
  [--summarize]
```

工具会校验 `profiling_plan.json.profile_mode` 与 `--profile-mode` 一致，并在 `{local_out}/artifact_manifest.json` 中记录已下载产物、缺失必需产物和 `ready_for_diagnosis`。

Inject benchmark 的 sim-only case 可额外传入公共脚本目录：

```bash
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir benchmarks/aprof_injected_ops/fast_gelu/inject_tail \
  --profile-mode sim \
  --profiling-plan benchmarks/aprof_injected_ops/fast_gelu/inject_tail/profiling_plan.json \
  --inject-common-dir benchmarks/aprof_injected_ops/common
```

若 `profiling_plan.json.remote_deploy_args.remote_env_exports` 包含 `APROF_INJECT_COMMON` / `APROF_INJECT_RUN`，工具会在远端 build/sim 命令前自动导出这些环境变量。

连通性自检：

```bash
ssh -p <port> -i ~/.ssh/id_ed25519 <user>@<host> \
  'source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh && \
   which bisheng msprof msopprof && npu-smi info 2>/dev/null | head -3 && \
   ls $ASCEND_HOME_PATH/tools/simulator/*/lib 2>/dev/null | head -3'
```

---

## Step 1：本地算子目录要求

### 模式 sim（simulator）

`run.sh` 需支持：

```bash
bash run.sh build   # bisheng + ld.lld → build_sim/<op>_kernel.o
bash run.sh sim     # msprof op simulator --config=./op_config.json
```

典型目录（上传时**跳过**已有产物）：

```text
<op_dir>/
├── run.sh
├── op_kernel/*_kernel.asc
├── scripts/gen_data.py
├── build_sim/             # 不上传
└── msprof_sim_output/     # 不上传
```

### 模式 hw-msprof / hw-op（上板）

cmake 直调工程，远端编译出 host 可执行文件（在 NPU 机器上 `aclInit` 成功）：

```text
<op_dir>/
├── CMakeLists.txt
├── run.sh                  # 可选，本地一键 build+run
├── op_kernel/ op_host/
├── scripts/gen_data.py
├── build/                  # 不上传，远端 cmake 重建
└── msprof_hw_output/       # 不上传
```

上板采集前通常需生成输入数据，例如：

```bash
python3 scripts/gen_data.py <args>
mkdir -p build/output msprof_hw_output
```

`ops-profiling` 脚本随上传放到远端 `<op>/ops_profiling/scripts/`（工具自动同步）。

---

## Step 2：上传到远程

通过 SFTP 上传文本类源码（`.sh` `.asc` `.h` `.py` `.json` `.md` `.cpp` 等），自动递归建目录。

远端布局：

```text
$APROF_REMOTE_ROOT/<op_name>/
├── run.sh
├── op_kernel/
├── scripts/
├── build_sim/          # 远端 build 时生成
└── msprof_sim_output/  # 远端 sim 时生成
```

**注意**：SFTP 默认权限常为 `664`/`775`，msprof 会拒绝组/其他用户可写路径（见 Step 4）。

---

## Step 3：远端编译（build）

### sim：device-side `.o`

```bash
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd $REMOTE_OP_DIR
export ASC_ARCH=dav-3510
bash run.sh build 2>&1
```

等价核心命令：

```bash
BISHENG=$ASCEND_HOME_PATH/bin/bisheng
LD_LLD=$ASCEND_HOME_PATH/bin/ld.lld
"$BISHENG" -fPIC --aicore-only --npu-arch="$ASC_ARCH" -O2 -g \
  -I op_kernel -I "$ASCEND_HOME_PATH/include" \
  --asc-aicore-lang -c op_kernel/<op>_kernel.asc \
  -o build_sim/<op>_kernel.obj
"$LD_LLD" -m aicorelinux -Ttext=0 build_sim/<op>_kernel.obj -static \
  -o build_sim/<op>_kernel.o
```

验收：`build_sim/<op>_kernel.o` 存在（`unknown arch 0x1029`）。

### hw-msprof / hw-op：cmake 直调可执行文件

```bash
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd $REMOTE_OP_DIR
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_ASC_ARCHITECTURES=dav-3510
cmake --build build -j$(nproc)
# 验收：build/<binary> 可执行，例如 build/fast_gelu
```

---

## Step 4：远端 msprof 采集

### 4a. sim — `msprof op simulator`

sim 前**必须**收紧权限（SFTP 上传后常见）：

```bash
chmod 700 msprof_sim_output build_sim
chmod u=rw,go= build_sim/* 2>/dev/null || true
ulimit -n 65536 2>/dev/null || ulimit -n 4096 || true
export ASC_ARCH=dav-3510 MSPROF_TIMEOUT=8
cd $REMOTE_OP_DIR && bash run.sh sim 2>&1
```

或直接：

```bash
cd build_sim
msprof op simulator \
  --config=./op_config.json \
  --output=../msprof_sim_output \
  --timeout="${MSPROF_TIMEOUT:-5}"
```

成功标志：`[INFO] <ProfInit> Start profiling on kernel:`、`Profiling results saved in .../OPPROF_*`

产物：

```text
msprof_sim_output/OPPROF_*/simulator/trace.json
msprof_sim_output/OPPROF_*/simulator/core0.veccore0/*_instr_exe_*.csv
```

### 4b. hw-msprof — `msprof_profile_run.sh`（上板深度采集）

对应 `ops-profiling` 标准采集模式：warm-up + 7 组 `--aic-metrics` + sample-based。

```bash
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd $REMOTE_OP_DIR
python3 scripts/gen_data.py <case_args>   # 按算子自定
mkdir -p build/output msprof_hw_output

cd build
bash ../ops_profiling/scripts/msprof_profile_run.sh \
  --warm-up=3 \
  --output=../msprof_hw_output \
  -- ./<binary> <run_args>
```

解析摘要（可选，仍在远端跑完后拉回 `remote_hw_summary.txt`）：

```bash
PROFILE_DIR=$(ls -d msprof_hw_output/PROF_GROUP_* | head -1)
python3 ops_profiling/scripts/msprof_perf_summary.py "$PROFILE_DIR" . \
  > remote_hw_summary.txt 2>&1
```

产物：

```text
msprof_hw_output/PROF_GROUP_*/PROF_*/*.csv
msprof_hw_output/PROF_GROUP_*/PROF_Sample/.../aicore.db
remote_hw_summary.txt   # 含逐核负载、主 Bound 线索
```

### 4c. hw-op — `msprof op`（上板 msopprof）

```bash
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd $REMOTE_OP_DIR/build
msprof op --warm-up=10 --launch-count=1 --output=../msprof_hw_output \
  ./<binary> <run_args>
```

可选归档：

```bash
OPPROF_DIR=$(ls -td ../msprof_hw_output/OPPROF_* | head -1)
python3 ../ops_profiling/scripts/perf_summary.py "$OPPROF_DIR" ..
```

产物：

```text
msprof_hw_output/OPPROF_*/OpBasicInfo.csv
msprof_hw_output/OPPROF_*/PipeUtilization.csv
msprof_hw_output/OPPROF_*/...（共 8 份 CSV）
```

### 4d. 对比 / 批量（上板，ops-profiling 扩展）

在**已部署的算子目录**上，还可直接 SSH 执行（无需本 tool 封装）：

```bash
# 对比：model.py vs model_new_ascendc.py
bash ops_profiling/scripts/msprof_profile_run.sh \
  --compare --output-dir=./compare_out --warm-up=3 --device=0

# 批量多算子
bash ops_profiling/scripts/msprof_profile_run.sh \
  --batch --base-dir=./output_performance --max-jobs=7 --device-start=0
```

输出：`performance.json`、`perf_report.md`、`batch_summary.json` 等（见 `ops-profiling` skill）。

### 常见错误（sim + 上板通用）

| 现象 | 原因 | 修复 |
|---|---|---|
| `msprof_sim_output is writable by any other users` | 目录权限过宽 | sim 前 `chmod 700` |
| `op_config.json is writable by any other users` | SFTP 后 `build_sim/*` 过宽 | `chmod u=rw,go= build_sim/*` |
| `aclrtSetDevice failed` / `aclInit failed` | 在无 NPU 机器跑 host 直调 | 改走 **sim** 或换有 NPU 的远程机 |
| `has_artifacts: false` 但 exit 0 | msprof 报错未导致 shell 失败 | 查 stdout `[ERROR]`；`find msprof_*_output` |
| 上板耗时过长 | DVFS / 多组 metrics | 先 `--warm-up`；缩小 shape；SSH timeout ≥3600s |

---

## Step 5：拉取报告到本地

用 SFTP `get` 下载；`find` 路径类输出取**整行路径**，`cat` 多行 JSON 取**全文**（不要只取最后一行）。

建议拉取：

| 模式 | 远端路径模式 | 本地位置 |
|---|---|---|
| sim | `msprof_sim_output/.../trace.json`、`*_instr_exe_*.csv` | `{local_out}/msprof_sim_output/...` |
| hw-msprof | `msprof_hw_output/PROF_GROUP_*/**/*.csv`、`remote_hw_summary.txt` | `{local_out}/msprof_hw_output/...` |
| hw-op | `msprof_hw_output/OPPROF_*/*.csv` | `{local_out}/msprof_hw_output/...` |

验收清单：

```text
- [ ] deploy_results.json 中 has_artifacts == true
- [ ] artifact_manifest.json 中 ready_for_diagnosis == true（若传入 profiling_plan.json）
- [ ] sim：至少一个 trace.json
- [ ] hw-msprof：存在 PROF_GROUP_* 且含 op_summary 或 sample aicore.db
- [ ] hw-op：存在 OPPROF_* 且含 PipeUtilization.csv
```

---

## 一键工具

从仓库根目录执行：

```bash
# sim：上传 → build → simulator → 下载
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir benchmarks/aprof_injected_ops/fast_gelu/baseline \
  --profile-mode sim

# 上板 msprof（7 组 metrics + sample）
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir benchmarks/reference_ops/fast_gelu \
  --profile-mode hw-msprof \
  --run-cmd "./fast_gelu 8 2048 fp32 1" \
  --gen-data-cmd "python3 scripts/gen_data.py 8 2048 fp32" \
  --summarize

# 上板 msprof op（8 CSV）
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir benchmarks/reference_ops/fast_gelu \
  --profile-mode hw-op \
  --run-cmd "./fast_gelu 8 2048 fp32 1" \
  --profiling-plan remote_out/profiling_plan.json

# 仅重跑采集 + 下载（源码已在远端）
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir benchmarks/reference_ops/fast_gelu \
  --profile-mode hw-msprof \
  --run-cmd "./fast_gelu 8 2048 fp32 1" \
  --steps profile,download
```

`--steps`：`upload,build,profile,download`（`sim` 为 `profile` 别名）。依赖 `pip install paramiko`；配置见 `scripts/server_config.json`。

---

## 与 inject skill 的边界

| 本 skill | `ascendc-aprof-inject-problems` |
|---|---|
| SSH 部署、编译、msprof、下载 | 如何构造 baseline / inject 变体与 `injected_label` |
| 任意带 `run.sh build/sim` 的算子目录 | `metadata.json` 语义与多 case 批量对比 |
| 通用 `remote_msprof_deploy.py` | 批量 inject runner（如 `scripts/run_remote_*_inject*.py`） |

批量跑多个 inject case 时：先用 inject skill 准备目录，再对本 skill 的 tool **逐目录**调用，或写薄封装脚本循环 `--local-dir`。

---

## 相关资源

- Direct-invoke / Simulator SOP：`skills/aprof/benchmark/ascendc-kernel-direct-invoke/SKILL.md`
- 上板采集 / 解析 / 对比批量：`ops-profiling` skill（`references/msprof-guide.md`、`references/msprof-op-guide.md`）
- SSH 配置：`scripts/remote_server_config.py`
- 参考：`benchmarks/reference_ops/fast_gelu/`（上板）、`benchmarks/aprof_injected_ops/fast_gelu/baseline`（sim）
