#!/usr/bin/env python3
"""Scaffold an AscendC direct-invoke project from a kernel file.

The tool is deliberately conservative. It can parse the kernel entry and emit a
standard project layout, but it marks the result as non-runnable until IO sizes,
dtype, blockDim and tiling data are known.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Any


DTYPE_TO_CPP = {
    "float32": "float",
    "fp32": "float",
    "float": "float",
    "float16": "uint16_t",
    "fp16": "uint16_t",
    "half": "uint16_t",
    "int32": "int32_t",
    "uint32": "uint32_t",
    "int8": "int8_t",
    "uint8": "uint8_t",
}

DTYPE_TO_BYTES = {
    "float32": 4,
    "fp32": 4,
    "float": 4,
    "float16": 2,
    "fp16": 2,
    "half": 2,
    "int32": 4,
    "uint32": 4,
    "int8": 1,
    "uint8": 1,
}

DTYPE_TO_MSPROF = {
    "fp32": "float32",
    "float": "float32",
    "float32": "float32",
    "fp16": "float16",
    "half": "float16",
    "float16": "float16",
    "int32": "int32",
    "uint32": "uint32",
    "int8": "int8",
    "uint8": "uint8",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an AscendC direct-invoke scaffold")
    parser.add_argument("--kernel-file", required=True, help="Source AscendC kernel file")
    parser.add_argument("--out-dir", required=True, help="Output direct-invoke project directory")
    parser.add_argument("--op-name", required=True, help="Operator/project name")
    parser.add_argument("--kernel-name", default="", help="Kernel entry name; inferred when omitted")
    parser.add_argument("--io-spec-json", default="", help="JSON file describing launch params and IO sizes")
    parser.add_argument("--soc", default="dav-2201", help="CANN npu arch, for example dav-2201 or dav-3510")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing out-dir")
    args = parser.parse_args()

    kernel_file = Path(args.kernel_file).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not kernel_file.is_file():
        raise SystemExit(f"kernel file not found: {kernel_file}")
    if out_dir.exists():
        if not args.force:
            raise SystemExit(f"out-dir already exists: {out_dir} (use --force to overwrite)")
        shutil.rmtree(out_dir)

    kernel_text = kernel_file.read_text(encoding="utf-8")
    entry = parse_kernel_entry(kernel_text, args.kernel_name)
    io_spec = read_json(Path(args.io_spec_json)) if args.io_spec_json else {}
    params = build_param_model(entry["params"], io_spec)
    missing = find_missing(params, io_spec)
    runnable = not missing

    write_project(
        out_dir=out_dir,
        kernel_file=kernel_file,
        kernel_text=kernel_text,
        op_name=args.op_name,
        kernel_name=entry["name"],
        params=params,
        io_spec=io_spec,
        soc=args.soc,
        runnable=runnable,
        missing=missing,
    )

    report = {
        "schema_version": 1,
        "status": "runnable" if runnable else "needs_io_spec",
        "op_name": args.op_name,
        "kernel_name": entry["name"],
        "source_kernel": str(kernel_file),
        "out_dir": str(out_dir),
        "soc": args.soc,
        "params": params,
        "missing_fields": missing,
        "notes": [] if runnable else ["Fill --io-spec-json and rerun before claiming build/run support."],
    }
    write_json(out_dir / "scaffold_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if runnable else 2


def parse_kernel_entry(text: str, kernel_name: str) -> dict[str, Any]:
    pattern = re.compile(
        r'(?:extern\s+"C"\s+)?__global__\s+(?:(?:__\w+__|KERNEL_TASK_TYPE_\w+\([^)]*\))\s+)*'
        r'void\s+([A-Za-z_]\w*)\s*\((.*?)\)',
        re.S,
    )
    matches = list(pattern.finditer(text))
    if kernel_name:
        matches = [m for m in matches if m.group(1) == kernel_name]
    if not matches:
        raise SystemExit("could not find a matching __global__ void kernel entry")
    if len(matches) > 1 and not kernel_name:
        names = ", ".join(m.group(1) for m in matches)
        raise SystemExit(f"multiple kernel entries found ({names}); pass --kernel-name")
    params = [parse_param(p) for p in split_params(matches[0].group(2))]
    return {"name": matches[0].group(1), "params": params}


def split_params(raw: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in raw:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            item = "".join(cur).strip()
            if item and item != "void":
                out.append(item)
            cur = []
        else:
            cur.append(ch)
    item = "".join(cur).strip()
    if item and item != "void":
        out.append(item)
    return out


def parse_param(raw: str) -> dict[str, Any]:
    cleaned = raw.split("=")[0].strip()
    m = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$", cleaned)
    if not m:
        raise SystemExit(f"could not parse kernel parameter: {raw}")
    name = m.group(1)
    type_text = cleaned[: m.start(1)].strip()
    return {"name": name, "type": type_text, "raw": raw.strip()}


def build_param_model(entry_params: list[dict[str, Any]], io_spec: dict[str, Any]) -> list[dict[str, Any]]:
    if "params" in io_spec:
        by_name = {str(p.get("name", "")): p for p in io_spec.get("params", [])}
        by_index = list(io_spec.get("params", []))
        result = []
        for idx, entry in enumerate(entry_params):
            spec = by_name.get(entry["name"]) or (by_index[idx] if idx < len(by_index) else {})
            merged = dict(entry)
            merged.update(normalize_param_spec(spec, entry, idx, io_spec))
            result.append(merged)
        return result

    inputs = list(io_spec.get("inputs", []))
    outputs = list(io_spec.get("outputs", []))
    result = []
    input_i = 0
    output_i = 0
    for idx, entry in enumerate(entry_params):
        inferred_kind = infer_kind(entry["name"], idx, len(entry_params), len(inputs), len(outputs))
        source: dict[str, Any] = {}
        if inferred_kind == "input" and input_i < len(inputs):
            source = inputs[input_i]
            input_i += 1
        elif inferred_kind == "output" and output_i < len(outputs):
            source = outputs[output_i]
            output_i += 1
        elif inferred_kind == "tiling":
            source = io_spec.get("tiling", {})
        merged = dict(entry)
        merged.update(normalize_param_spec(source, entry, idx, io_spec, inferred_kind))
        result.append(merged)
    return result


def infer_kind(name: str, idx: int, total: int, input_count: int, output_count: int) -> str:
    lower = name.lower()
    if "tiling" in lower:
        return "tiling"
    if "workspace" in lower or lower in {"work", "workspacegm"}:
        return "workspace"
    if "output" in lower or lower.startswith("y") or lower.startswith("z"):
        return "output"
    if input_count or output_count:
        if idx < input_count:
            return "input"
        if idx < input_count + output_count:
            return "output"
    if idx == total - 1 and "gm" in lower:
        return "tiling"
    return "input"


def normalize_param_spec(
    spec: dict[str, Any],
    entry: dict[str, Any],
    idx: int,
    io_spec: dict[str, Any],
    fallback_kind: str | None = None,
) -> dict[str, Any]:
    kind = str(spec.get("kind") or spec.get("param_type") or fallback_kind or infer_kind(entry["name"], idx, 0, 0, 0))
    dtype = str(spec.get("dtype") or spec.get("type") or io_spec.get("dtype") or "float32")
    shape = spec.get("shape")
    elem_count = int(spec.get("elements") or (product(shape) if shape else 0))
    size = int(spec.get("size") or spec.get("bytes") or (elem_count * DTYPE_TO_BYTES.get(dtype, 0)))
    file_name = str(spec.get("file") or spec.get("data_path") or default_file(entry["name"], kind))
    model = {
        "kind": kind,
        "dtype": dtype,
        "shape": shape or [],
        "elements": elem_count,
        "size": size,
        "file": file_name,
    }
    if "golden_file" in spec:
        model["golden_file"] = str(spec["golden_file"])
    if "fill" in spec:
        model["fill"] = spec["fill"]
    return model


def default_file(name: str, kind: str) -> str:
    if kind == "tiling":
        return "tiling.bin"
    if kind == "output":
        return f"{name}.bin"
    if kind == "workspace":
        return f"{name}.workspace.bin"
    return f"{name}.bin"


def product(shape: Any) -> int:
    if not isinstance(shape, list) or not shape:
        return 0
    value = 1
    for item in shape:
        value *= int(item)
    return value


def find_missing(params: list[dict[str, Any]], io_spec: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not io_spec:
        missing.append("io_spec_json")
    if not int(io_spec.get("blockdim", 0)):
        missing.append("blockdim")
    for p in params:
        kind = p["kind"]
        prefix = f"params.{p['name']}"
        if kind in {"input", "output"}:
            if not p.get("shape") and not p.get("elements"):
                missing.append(f"{prefix}.shape")
            if not p.get("dtype"):
                missing.append(f"{prefix}.dtype")
            if not int(p.get("size", 0)):
                missing.append(f"{prefix}.size")
        elif kind == "workspace":
            if "size" not in p or int(p.get("size", 0)) < 0:
                missing.append(f"{prefix}.size")
        elif kind == "tiling":
            if not int(p.get("size", 0)):
                missing.append(f"{prefix}.size")
    return missing


def write_project(
    *,
    out_dir: Path,
    kernel_file: Path,
    kernel_text: str,
    op_name: str,
    kernel_name: str,
    params: list[dict[str, Any]],
    io_spec: dict[str, Any],
    soc: str,
    runnable: bool,
    missing: list[str],
) -> None:
    for rel in ("op_kernel", "op_host", "scripts", "data", "build_sim"):
        (out_dir / rel).mkdir(parents=True, exist_ok=True)
    copy_kernel_tree(kernel_file, out_dir / "op_kernel")
    (out_dir / "op_kernel" / f"{op_name}_kernel.asc").write_text(kernel_text, encoding="utf-8")
    write_text(out_dir / "CMakeLists.txt", render_cmake(op_name, soc))
    write_text(out_dir / "run.sh", render_run_sh(op_name, runnable, soc))
    make_executable(out_dir / "run.sh")
    write_text(out_dir / "op_host" / "data_utils.h", render_data_utils())
    write_text(
        out_dir / "op_host" / "main.cpp",
        render_main_cpp(op_name, kernel_name, params, int(io_spec.get("blockdim", 1) or 1), runnable),
    )
    write_text(out_dir / "scripts" / "gen_data.py", render_gen_data(op_name, kernel_name, params, io_spec, runnable, missing))
    make_executable(out_dir / "scripts" / "gen_data.py")
    write_text(out_dir / "scripts" / "verify_result.py", render_verify_result(params, io_spec, runnable, missing))
    make_executable(out_dir / "scripts" / "verify_result.py")


def copy_kernel_tree(kernel_file: Path, target: Path) -> None:
    for sibling in kernel_file.parent.iterdir():
        if sibling.is_file() and sibling.suffix in {".h", ".hpp", ".inc"}:
            shutil.copy2(sibling, target / sibling.name)


def render_cmake(op_name: str, soc: str) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project({op_name} LANGUAGES ASC CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_ASC_ARCHITECTURES "{soc}" CACHE STRING "NPU architecture")

if(NOT DEFINED ENV{{ASCEND_HOME_PATH}})
    message(FATAL_ERROR "ASCEND_HOME_PATH is not set. Source the CANN set_env.sh first.")
endif()

set(ASCEND_PATH "$ENV{{ASCEND_HOME_PATH}}")
set(ACL_INCLUDE_DIR "${{ASCEND_PATH}}/x86_64-linux/include")
if(NOT EXISTS "${{ACL_INCLUDE_DIR}}")
    set(ACL_INCLUDE_DIR "${{ASCEND_PATH}}/include")
endif()

add_executable({op_name} op_host/main.cpp)

target_include_directories({op_name} PRIVATE
    ${{CMAKE_CURRENT_SOURCE_DIR}}/op_kernel
    ${{CMAKE_CURRENT_SOURCE_DIR}}/op_host
    ${{ACL_INCLUDE_DIR}}
)

target_link_directories({op_name} PRIVATE
    ${{ASCEND_PATH}}/lib64
    ${{ASCEND_PATH}}/x86_64-linux/lib64
    ${{ASCEND_PATH}}/aarch64-linux/lib64
)

target_link_libraries({op_name} PRIVATE
    ascendcl
    tiling_api
    register
    platform
    unified_dlog
    dl
    m
    pthread
    graph_base
)

target_compile_options({op_name} PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${{CMAKE_ASC_ARCHITECTURES}}>
)
"""


def render_run_sh(op_name: str, runnable: bool, soc: str) -> str:
    runnable_guard = "" if runnable else """if [ ! -f scaffold_report.json ] || grep -q '"status": "needs_io_spec"' scaffold_report.json; then
  echo "[ERROR] scaffold is missing IO information. See scaffold_report.json and rerun scaffold_direct_invoke.py with --io-spec-json."
  exit 2
fi
"""
    return f"""#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${{1:-all}}"
shift || true

{runnable_guard}

export ASCEND_HOME_PATH="${{ASCEND_HOME_PATH:-/usr/local/Ascend/ascend-toolkit/latest}}"
export ASCEND_TOOLKIT_HOME="${{ASCEND_TOOLKIT_HOME:-$ASCEND_HOME_PATH}}"
export PATH="$ASCEND_HOME_PATH/bin:$ASCEND_HOME_PATH/tools/msopprof/bin:$PATH"

if [ "$(uname -m)" = "aarch64" ]; then
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/aarch64-linux"
else
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/x86_64-linux"
fi
export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/lib64:$CANN_ARCH_DIR/lib64:${{LD_LIBRARY_PATH:-}}"
ASC_ARCH="${{ASC_ARCH:-{soc}}}"

find_repo_root() {{
  local dir="$SCRIPT_DIR"
  while [ "$dir" != "/" ]; do
    if [ -d "$dir/.git" ] || [ -d "$dir/skills/aprof" ]; then
      printf "%s\\n" "$dir"
      return
    fi
    dir="$(dirname "$dir")"
  done
  printf "%s\\n" "$SCRIPT_DIR"
}}

APROF_REPO_ROOT="${{APROF_REPO_ROOT:-$(find_repo_root)}}"
APROF_TMP_ROOT="${{APROF_TMP_ROOT:-$APROF_REPO_ROOT/tmp/aprof}}"
APROF_CASE_TMP="${{APROF_CASE_TMP:-$APROF_TMP_ROOT/direct_invoke/$(basename "$SCRIPT_DIR")}}"
APROF_MSPROF_OUTPUT="${{APROF_MSPROF_OUTPUT:-$APROF_CASE_TMP/msprof_hw_output}}"
APROF_MSPROF_SIM_OUTPUT="${{APROF_MSPROF_SIM_OUTPUT:-$APROF_CASE_TMP/msprof_sim_output}}"
APROF_WARMUP="${{APROF_WARMUP:-10}}"
APROF_REPEAT="${{APROF_REPEAT:-5}}"
APROF_PROFILE_MODE="${{APROF_PROFILE_MODE:-legacy}}"

case "$MODE" in
  gen)
    python3 scripts/gen_data.py "$@"
    ;;
  build)
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_ASC_ARCHITECTURES="$ASC_ARCH"
    cmake --build build -j"$(nproc)"
    ;;
  run)
    mkdir -p build/output
    ./build/{op_name} "$@"
    ;;
  verify)
    python3 scripts/verify_result.py "$@"
    ;;
  sim-build)
    python3 scripts/gen_data.py "$@"
    mkdir -p build_sim
    BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
    LD_LLD="$ASCEND_HOME_PATH/bin/ld.lld"
    "$BISHENG" -fPIC --aicore-only --npu-arch="$ASC_ARCH" -O2 -g \\
      -I op_kernel \\
      -I "$ASCEND_HOME_PATH/include" \\
      -I "$CANN_ARCH_DIR/include" \\
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \\
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \\
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \\
      --asc-aicore-lang -c "op_kernel/{op_name}_kernel.asc" \\
      -o "build_sim/{op_name}_kernel.obj"
    "$LD_LLD" -m aicorelinux -Ttext=0 "build_sim/{op_name}_kernel.obj" -static -o "build_sim/{op_name}_kernel.o"
    if command -v file >/dev/null 2>&1; then file "build_sim/{op_name}_kernel.o"; fi
    ;;
  sim)
    mkdir -p "$APROF_MSPROF_SIM_OUTPUT" build_sim
    rm -rf "$APROF_MSPROF_SIM_OUTPUT"/OPPROF_*
    chmod 700 "$APROF_MSPROF_SIM_OUTPUT" build_sim
    chmod u=rw,go= build_sim/* 2>/dev/null || true
    cd build_sim
    msprof op simulator --config=./op_config.json --output="$APROF_MSPROF_SIM_OUTPUT" --timeout="${{MSPROF_TIMEOUT:-5}}"
    ;;
  profile)
    bash "$0" build
    bash "$0" gen "$@"
    APROF_PROFILE_RUN_ROOT="${{APROF_PROFILE_RUN_ROOT:-$APROF_MSPROF_OUTPUT/$(date +%Y%m%d_%H%M%S)}}"
    mkdir -p "$APROF_PROFILE_RUN_ROOT"
    if [ "$APROF_PROFILE_MODE" != "hw-op" ] && [ "$APROF_WARMUP" -gt 0 ]; then
      warm_i=1
      while [ "$warm_i" -le "$APROF_WARMUP" ]; do
        (cd build && "./{op_name}" >/dev/null)
        warm_i=$((warm_i + 1))
      done
    fi
    if [ "$APROF_PROFILE_MODE" = "hw-op" ]; then
      (cd build && msprof op --warm-up="$APROF_WARMUP" --launch-count="$APROF_REPEAT" \\
        --output="$APROF_PROFILE_RUN_ROOT/hw_op" "./{op_name}")
    else
      i=1
      while [ "$i" -le "$APROF_REPEAT" ]; do
        run_dir="$APROF_PROFILE_RUN_ROOT/legacy_run_$i"
        mkdir -p "$run_dir"
        (cd build && msprof --application="./{op_name}" --output="$run_dir" \\
          --aic-metrics="${{APROF_AIC_METRICS:-PipeUtilization}}" --task-time=on --runtime-api=on)
        i=$((i + 1))
      done
      printf '{{"profile_mode":"legacy","warm_up":%s,"repeat":%s,"run_root":"%s","note":"legacy msprof --application has no launch-count; runs are repeated externally"}}\\n' \\
        "$APROF_WARMUP" "$APROF_REPEAT" "$APROF_PROFILE_RUN_ROOT" > "$APROF_PROFILE_RUN_ROOT/profiling_summary.json"
    fi
    ;;
  all)
    bash "$0" build
    bash "$0" gen "$@"
    bash "$0" run
    bash "$0" verify
    ;;
  *)
    echo "usage: $0 [gen|build|run|verify|sim-build|sim|profile|all]"
    exit 2
    ;;
esac
"""


def render_data_utils() -> str:
    return r"""#ifndef APROF_DIRECT_INVOKE_DATA_UTILS_H
#define APROF_DIRECT_INVOKE_DATA_UTILS_H

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

inline std::vector<uint8_t> ReadBinaryFile(const std::string& path, size_t expectedSize)
{
    FILE* fp = fopen(path.c_str(), "rb");
    if (fp == nullptr) {
        throw std::runtime_error("failed to open " + path);
    }
    std::vector<uint8_t> data(expectedSize);
    const size_t got = fread(data.data(), 1, expectedSize, fp);
    fclose(fp);
    if (got != expectedSize) {
        throw std::runtime_error("short read from " + path);
    }
    return data;
}

inline void WriteBinaryFile(const std::string& path, const std::vector<uint8_t>& data)
{
    FILE* fp = fopen(path.c_str(), "wb");
    if (fp == nullptr) {
        throw std::runtime_error("failed to open " + path);
    }
    const size_t wrote = fwrite(data.data(), 1, data.size(), fp);
    fclose(fp);
    if (wrote != data.size()) {
        throw std::runtime_error("short write to " + path);
    }
}

#endif
"""


def render_main_cpp(op_name: str, kernel_name: str, params: list[dict[str, Any]], blockdim: int, runnable: bool) -> str:
    if not runnable:
        return f"""#include <iostream>

int main()
{{
    std::cerr << "This scaffold is missing IO metadata. See scaffold_report.json." << std::endl;
    return 2;
}}
"""
    allocs = []
    launch_args = []
    cleanup = []
    copy_back = []
    for idx, p in enumerate(params):
        var = f"dev{idx}"
        size = int(p["size"])
        kind = p["kind"]
        launch_args.append(f"static_cast<uint8_t*>({var})")
        if kind == "workspace":
            allocs.append(
                f'    void* {var} = nullptr;\n'
                f'    CheckAcl(aclrtMalloc(&{var}, {size}, ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc {p["name"]}");'
            )
        else:
            file_path = f"../data/{p['file']}"
            allocs.append(
                f'    void* {var} = nullptr;\n'
                f'    CheckAcl(aclrtMalloc(&{var}, {size}, ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc {p["name"]}");\n'
                f'    auto host{idx} = ReadBinaryFile("{file_path}", {size});\n'
                f'    CheckAcl(aclrtMemcpy({var}, {size}, host{idx}.data(), {size}, ACL_MEMCPY_HOST_TO_DEVICE), "aclrtMemcpy {p["name"]} H2D");'
            )
        cleanup.append(f"    if ({var} != nullptr) {{ aclrtFree({var}); }}")
        if kind == "output":
            out_path = f"output/{p['file']}"
            copy_back.append(
                f'    std::vector<uint8_t> out{idx}({size});\n'
                f'    CheckAcl(aclrtMemcpy(out{idx}.data(), {size}, {var}, {size}, ACL_MEMCPY_DEVICE_TO_HOST), "aclrtMemcpy {p["name"]} D2H");\n'
                f'    WriteBinaryFile("{out_path}", out{idx});'
            )
    launch = ", ".join(launch_args)
    alloc_text = "\n".join(allocs)
    cleanup_text = "\n".join(reversed(cleanup))
    copy_back_text = "\n".join(copy_back)
    return f"""#include "acl/acl.h"
#include "kernel_operator.h"
#include "data_utils.h"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

#include "../op_kernel/{op_name}_kernel.asc"

namespace {{

constexpr uint32_t kBlockDim = {blockdim};

void CheckAcl(aclError ret, const char* what)
{{
    if (ret != ACL_SUCCESS) {{
        std::cerr << what << " failed, aclError=" << ret << std::endl;
        throw std::runtime_error(what);
    }}
}}

}} // namespace

int main()
{{
    int32_t deviceId = 0;
    aclrtStream stream = nullptr;
    int ret = 0;
    try {{
        CheckAcl(aclInit(nullptr), "aclInit");
        CheckAcl(aclrtSetDevice(deviceId), "aclrtSetDevice");
        CheckAcl(aclrtCreateStream(&stream), "aclrtCreateStream");

{alloc_text}

        {kernel_name}<<<kBlockDim, nullptr, stream>>>({launch});
        CheckAcl(aclrtSynchronizeStream(stream), "aclrtSynchronizeStream");

{copy_back_text}
        std::cout << "{op_name} direct-invoke run succeeded" << std::endl;
{cleanup_text}
    }} catch (const std::exception& ex) {{
        std::cerr << ex.what() << std::endl;
        ret = 1;
    }}
    if (stream != nullptr) {{ aclrtDestroyStream(stream); }}
    aclrtResetDevice(deviceId);
    aclFinalize();
    return ret;
}}
"""

def render_gen_data(
    op_name: str,
    kernel_name: str,
    params: list[dict[str, Any]],
    io_spec: dict[str, Any],
    runnable: bool,
    missing: list[str],
) -> str:
    payload = {"op_name": op_name, "kernel_name": kernel_name, "params": params, "io_spec": io_spec, "missing": missing}
    blockdim = int(io_spec.get("blockdim", 1) or 1)
    source = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import struct
from pathlib import Path

SPEC = {source}


def main() -> int:
    if SPEC["missing"]:
        raise SystemExit("scaffold is missing IO metadata: " + ", ".join(SPEC["missing"]))
    root = Path.cwd()
    data = root / "data"
    build_sim = root / "build_sim"
    data.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)
    rng = random.Random(20260709)
    for param in SPEC["params"]:
        kind = param["kind"]
        path = data / param["file"]
        sim_path = build_sim / param["file"]
        if kind == "workspace":
            continue
        blob = make_blob(param, rng)
        path.write_bytes(blob)
        sim_path.write_bytes(blob)
    op_config = {{
        "kernel_name": SPEC["kernel_name"],
        "kernel_path": f"./{{SPEC['op_name']}}_kernel.o",
        "blockdim": {blockdim},
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{{"case_name": f"{{SPEC['op_name']}}_case0", "param_desc": build_param_desc()}}],
    }}
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    print(json.dumps({{"generated": True, "op_config": str(build_sim / "op_config.json")}}, indent=2))
    return 0


def make_blob(param: dict, rng: random.Random) -> bytes:
    kind = param["kind"]
    size = int(param["size"])
    if kind == "output":
        return bytes(size)
    if kind == "tiling":
        values = SPEC["io_spec"].get("tiling_values_u32")
        if values:
            blob = struct.pack(f"{{len(values)}}I", *[int(v) for v in values])
            return blob + bytes(max(0, size - len(blob)))
        return bytes(size)
    dtype = canonical_dtype(param.get("dtype", "float32"))
    elements = int(param.get("elements") or 0)
    if dtype == "float32":
        vals = [rng.uniform(-1.0, 1.0) for _ in range(elements)]
        blob = struct.pack(f"{{len(vals)}}f", *vals)
    elif dtype in {{"float16", "uint16"}}:
        vals = [rng.randrange(0, 65535) for _ in range(elements)]
        blob = struct.pack(f"{{len(vals)}}H", *vals)
    elif dtype == "int32":
        vals = [rng.randrange(-128, 128) for _ in range(elements)]
        blob = struct.pack(f"{{len(vals)}}i", *vals)
    else:
        blob = bytes((i % 251 for i in range(size)))
    return blob + bytes(max(0, size - len(blob)))


def build_param_desc() -> list[dict]:
    desc = []
    for param in SPEC["params"]:
        kind = param["kind"]
        if kind == "workspace":
            desc.append({{"param_type": "workspace", "user_workspace_size": int(param["size"])}})
        elif kind == "tiling":
            desc.append({{"param_type": "tiling", "tiling_data_size": int(param["size"]), "tiling_data_path": f"./{{param['file']}}"}})
        elif kind in {{"input", "output"}}:
            item = {{
                "param_type": kind,
                "type": msprof_dtype(param.get("dtype", "float32")),
                "shape": param.get("shape") or [int(param.get("elements", 0))],
                "name": param["name"],
            }}
            if kind == "input":
                item["data_path"] = f"./{{param['file']}}"
            desc.append(item)
    return desc


def canonical_dtype(dtype: str) -> str:
    aliases = {{"fp32": "float32", "float": "float32", "half": "float16", "fp16": "float16", "uint32": "int32"}}
    return aliases.get(dtype, dtype)


def msprof_dtype(dtype: str) -> str:
    aliases = {{"fp32": "float32", "float": "float32", "half": "float16", "fp16": "float16"}}
    return aliases.get(dtype, dtype)


if __name__ == "__main__":
    raise SystemExit(main())
"""


def render_verify_result(params: list[dict[str, Any]], io_spec: dict[str, Any], runnable: bool, missing: list[str]) -> str:
    outputs = [p for p in params if p.get("kind") == "output"]
    output_payload = json.dumps(outputs, indent=2, ensure_ascii=False)
    missing_payload = json.dumps(missing, ensure_ascii=False)
    mode = io_spec.get("verification", {}).get("mode", "exists") if io_spec else "exists"
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

OUTPUTS = {output_payload}
MISSING = {missing_payload}
MODE = {mode!r}


def main() -> int:
    if MISSING:
        raise SystemExit("scaffold is missing IO metadata: " + ", ".join(MISSING))
    missing = []
    for out in OUTPUTS:
        path = Path("build/output") / out["file"]
        if not path.is_file():
            missing.append(str(path))
        elif path.stat().st_size != int(out["size"]):
            raise SystemExit(f"size mismatch for {{path}}: got {{path.stat().st_size}}, expected {{out['size']}}")
    if missing:
        raise SystemExit("missing output files: " + ", ".join(missing))
    if MODE == "exists":
        print(json.dumps({{"verification": "skipped", "reason": "exists-only generic scaffold", "outputs": len(OUTPUTS)}}, indent=2))
        return 0
    raise SystemExit(f"unsupported verification mode: {{MODE}}")


if __name__ == "__main__":
    raise SystemExit(main())
"""


def get_blockdim_from_text(text: str) -> str:
    return text


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"io spec json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    raise SystemExit(main())
