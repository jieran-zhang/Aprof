# msprof Simulator Setup Notes

The MVP can analyze local fixtures without CANN. To collect real data, run the workload in a Linux environment with the Ascend CANN toolkit and simulator libraries installed.

## Expected Command

```bash
export LD_LIBRARY_PATH=${ASCEND_TOOLKIT_HOME}/tools/simulator/Ascend910B1/lib:$LD_LIBRARY_PATH
msprof op simulator --soc-version=Ascend910B1 --output=./prof --core-id=0 ./ascendc_kernels_bbit
```

AProf's harness wraps the same command and keeps the raw artifacts, analysis
reports, and model-facing problem summary together:

```bash
source scripts/env_cann.sh
python3 -m aprof diagnose \
  --executable ./ascendc_kernels_bbit \
  --source-root benchmarks/reference_ops/reduce_sum \
  --arch configs/architectures/ascend910b1.yaml \
  --out reports/poc_msprof_sample/diagnose \
  --soc-version Ascend910B1 \
  --operator-name VectorAdd \
  --shape 'float16[262144]' \
  --data-type float16 \
  --run
```

Useful simulator outputs for AProf:

- `simulator/trace.json`: instruction or pipeline timeline, usable as time-window evidence.
- `simulator/core*.veccore*/core*_code_exe.csv`: code-line hotspot data with `code`, `call_count`, `cycles`, and `running_time(us)`.
- `visualize_data.bin`: MindStudio Insight visualization data, not parsed by the MVP.

## Driver/Runtime Libraries

`msprof op simulator` still launches the compiled workload and may require
driver/runtime libraries outside the toolkit. Before collecting real benchmark
evidence, verify that these libraries are visible:

```bash
source scripts/env_cann.sh
ldd benchmarks/msprof_simulator_real/cases/official_vector_add_baseline/workload/ascendc_kernels_bbit
```

The output must not contain `libascend_hal.so => not found`. If the driver or
runtime is mounted outside the default locations, set one or both overrides
before sourcing the environment script:

```bash
export ASCEND_DRIVER_PATH=/path/to/Ascend/driver
export ASCEND_RUNTIME_PATH=/path/to/Ascend/runtime
source scripts/env_cann.sh
```

`scripts/env_cann.sh` checks common paths such as
`/usr/local/Ascend/driver/lib64`, `/usr/local/Ascend/driver/lib64/driver`, and
`/usr/local/Ascend/driver/tools/dcmi`. If it still warns about
`libascend_hal.so` or `libdcmi.so`, the current machine cannot produce accurate
real profiling data until the Ascend driver/runtime is installed or mounted.

## Constraints To Preserve

- Simulator mode is single-card oriented; use card id 0.
- Compile with simulator support and include `-g` when source hotspot data is needed.
- Keep profiling runs short, ideally under about 5 minutes.
- Prefer an environment with at least 20 GB memory for collection.
- Record `soc-version`, compile flags, input shape, data type, and kernel version for every run.

## Real Benchmark Suite

AProf's real benchmark definitions are tracked in
`benchmarks/msprof_simulator_real/manifest.json`. The suite separates workload
definitions from completed captures:

- `cases/<case_id>/workload`: official sample or custom AscendC source.
- `cases/<case_id>/raw`: real `msprof op simulator` output.
- `cases/<case_id>/diagnose`: frozen AProf golden diagnosis.

Use the manifest-driven runner for repeatable collection:

```bash
python3 scripts/collect_msprof_benchmarks.py \
  --case official_vector_add_baseline \
  --prepare-sources \
  --build \
  --run \
  --verify
```

Fallback captures are disabled by default. For CI or method-loop testing without
driver/runtime libraries, use the explicit fallback flag:

```bash
python3 scripts/collect_msprof_benchmarks.py --run --verify --allow-fallback-capture
```

Fallback captures are not real profiling evidence and must not be reported as
`captured_real_msprof`.

Offline verification is safe in CI and does not require CANN:

```bash
python3 scripts/collect_msprof_benchmarks.py --verify --allow-incomplete
```

A case should only be used as real evaluation evidence when `raw/` contains a
simulator `trace.json` and at least one `*_code_exe.csv`. A run that only
contains `msprof_stdout.log`, `msprof_stderr.log`, and an
`insufficient_evidence` diagnosis records an attempted collection, not a
completed benchmark.

## Current Machine Status

The current workspace is Linux x86_64. A user-local CANN toolkit install is available at `/rshome/jieran.zhang/Ascend/ascend-toolkit`; source `scripts/env_cann.sh` before running `msprof` commands so `ASCEND_TOOLKIT_HOME`, `ASCEND_HOME_PATH`, and the simulator library path are configured. Set `ASCEND_SOC_VERSION` before sourcing the script when using a SoC other than `Ascend910B1`.
