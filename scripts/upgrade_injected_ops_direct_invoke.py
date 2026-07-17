#!/usr/bin/env python3
"""Upgrade aprof_injected_ops cases in-place to full direct-invoke projects.

Changes per operator:
  - baseline + inject_* become complete CMake/op_host projects
  - inject_* renamed to anonymous op_XXXX
  - ground truth moved to <op>/.ground_truth/case_problem_map.json
  - APROF_INJECT_* macros rewritten to neutral APROF_FEATURE_XX
  - answer-leaking inject_manifest.json / metadata labels removed from case dirs
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECT_ROOT = ROOT / "benchmarks" / "aprof_injected_ops"
GOLD_COMMON = ROOT / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "common" / "run_direct_invoke.sh"
GOLD_DATA_UTILS = (
    ROOT / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "direct_invoke_baseline" / "op_host" / "data_utils.h"
)
GOLD_VERIFY = (
    ROOT / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "direct_invoke_baseline" / "scripts" / "verify_result.py"
)

INJECT_TO_FEATURE = {
    "APROF_INJECT_TAIL": "APROF_FEATURE_00",
    "APROF_INJECT_DYNSHAPE": "APROF_FEATURE_01",
    "APROF_INJECT_REDUNDANT_COPYIN": "APROF_FEATURE_02",
    "APROF_INJECT_DATA_MOVE": "APROF_FEATURE_02",
    "APROF_INJECT_EXTRA_COPYOUT": "APROF_FEATURE_03",
    "APROF_INJECT_PIPE_BREAK": "APROF_FEATURE_04",
    "APROF_INJECT_EXCESSIVE_BARRIER": "APROF_FEATURE_05",
    "APROF_INJECT_UB_OVERALLOC": "APROF_FEATURE_06",
    "APROF_INJECT_GM_SPILL": "APROF_FEATURE_07",
    "APROF_INJECT_SCALAR_LOOP": "APROF_FEATURE_08",
    "APROF_INJECT_API_RECOMPUTE": "APROF_FEATURE_08",
    "APROF_INJECT_REDUNDANT_VECTOR": "APROF_FEATURE_09",
}

FEATURE_IDS = [f"APROF_FEATURE_{i:02d}" for i in range(10)]

# Ops with vector tiling + single-input ABI identical to fast_gelu host template.
VECTOR_OPS = {
    "gelu_mul",
    "mish",
    "fast_gelu",
    "fast_gelu_grad",
    "layer_norm",
    "topk",
    "max_pool",
    "conv2d",
}

# swi_glu uses 2x input length; still vector tiling but different host/gen.
SWI_GLU_OPS = {"swi_glu"}

SKIP_DIRS = {"common", "closed_loop"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def neutralize_source(text: str) -> str:
    for old, new in INJECT_TO_FEATURE.items():
        text = text.replace(old, new)
    # Neutralize answer-leaking comments.
    text = re.sub(r"//.*[Ii]nject.*", "// feature toggle block", text)
    text = re.sub(r"//.*APROF_PATCH_.*", "// feature toggle block", text)
    text = re.sub(r"//.*[Pp]ipeline-break.*", "// optional sync helper", text)
    text = re.sub(r"//.*redundant.*", "// optional compute path", text)
    return text


def parse_flags_from_config(config_text: str) -> dict[str, int]:
    flags = {fid: 0 for fid in FEATURE_IDS}
    for line in config_text.splitlines():
        m = re.match(r"\s*#define\s+(APROF_INJECT_\w+|APROF_FEATURE_\d+)\s+(\d+)", line)
        if not m:
            continue
        name, val = m.group(1), int(m.group(2))
        feat = INJECT_TO_FEATURE.get(name, name if name.startswith("APROF_FEATURE_") else None)
        if feat in flags:
            flags[feat] = val
    return flags


def write_variant_config(path: Path, flags: dict[str, int]) -> None:
    lines = [
        "#ifndef APROF_VARIANT_CONFIG_H",
        "#define APROF_VARIANT_CONFIG_H",
        "",
    ]
    for fid in FEATURE_IDS:
        lines.append(f"#define {fid} {flags.get(fid, 0)}")
    lines.extend(["", "#endif", ""])
    write_text(path, "\n".join(lines))


def cmake_text(target: str) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project({target} LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_ASC_ARCHITECTURES "dav-2201" CACHE STRING "NPU architecture")

if(NOT DEFINED ENV{{ASCEND_HOME_PATH}})
    message(FATAL_ERROR "ASCEND_HOME_PATH is not set")
endif()

set(ASCEND_PATH "$ENV{{ASCEND_HOME_PATH}}")
set(ACL_INCLUDE_DIR "${{ASCEND_PATH}}/x86_64-linux/include")
if(NOT EXISTS "${{ACL_INCLUDE_DIR}}")
    set(ACL_INCLUDE_DIR "${{ASCEND_PATH}}/include")
endif()

add_executable({target} op_host/main.asc)
target_include_directories({target} PRIVATE
    ${{CMAKE_CURRENT_SOURCE_DIR}}/op_kernel
    ${{CMAKE_CURRENT_SOURCE_DIR}}/op_host
    ${{ACL_INCLUDE_DIR}}
)
target_link_directories({target} PRIVATE
    ${{ASCEND_PATH}}/lib64
    ${{ASCEND_PATH}}/x86_64-linux/lib64
    ${{ASCEND_PATH}}/aarch64-linux/lib64
)
target_link_libraries({target} PRIVATE ascendcl tiling_api register platform unified_dlog dl m pthread graph_base)
target_compile_options({target} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${{CMAKE_ASC_ARCHITECTURES}}>)
"""


def host_main_text(op_name: str, kernel_name: str, target: str, knobs: dict, input_mul: int = 1) -> str:
    n = int(knobs["output_elements"])
    blockdim = int(knobs["blockdim"])
    tile = int(knobs["tile_length"])
    tile_mul = int(knobs.get("tile_num_multiplier", knobs.get("tile_num_mul", 1)))
    return f"""#include "acl/acl.h"
#include "kernel_operator.h"
#include "data_utils.h"
#include "../op_kernel/aprof_vector_tiling.h"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

#include "../op_kernel/{kernel_name}.asc"

namespace {{
constexpr uint32_t kTotalElements = {n}U;
constexpr uint32_t kBlockDim = {blockdim}U;
constexpr uint32_t kTileLength = {tile}U;
constexpr uint32_t kTileNumMul = {tile_mul}U;
constexpr uint32_t kInputMul = {input_mul}U;
constexpr uint32_t kFp32Align = 8U;

uint32_t AlignUp(uint32_t value, uint32_t align)
{{
    return ((value + align - 1) / align) * align;
}}

void CheckAcl(aclError ret, const char *what)
{{
    if (ret != ACL_SUCCESS) {{
        std::cerr << what << " failed: " << ret << std::endl;
        throw std::runtime_error(what);
    }}
}}

AprofVectorTilingData BuildTiling()
{{
    AprofVectorTilingData tiling{{}};
    const uint32_t inputLogical = kTotalElements * kInputMul;
    tiling.inputElements = inputLogical;
    tiling.outputElements = kTotalElements;
    tiling.inputStride = AlignUp(inputLogical, kFp32Align);
    tiling.outputStride = AlignUp(kTotalElements, kFp32Align);
    tiling.elemsPerCore = (kTotalElements + kBlockDim - 1) / kBlockDim;
    tiling.tileLength = AlignUp(kTileLength, kFp32Align);
    tiling.tileLengthAligned = AlignUp(tiling.tileLength, kFp32Align);
    uint32_t baseTileNum = (tiling.elemsPerCore + tiling.tileLength - 1) / tiling.tileLength;
    tiling.tileNum = baseTileNum * kTileNumMul;
    tiling.tailLength = kTotalElements % tiling.tileLength;
    tiling.variantFlags = 0;
    return tiling;
}}
}} // namespace

int main()
{{
    const auto tiling = BuildTiling();
    const size_t inputBytes = static_cast<size_t>(tiling.inputStride) * sizeof(float);
    const size_t outputBytes = static_cast<size_t>(tiling.outputStride) * sizeof(float);
    const size_t tilingBytes = sizeof(AprofVectorTilingData);

    aclrtStream stream = nullptr;
    void* inputDev = nullptr;
    void* outputDev = nullptr;
    void* tilingDev = nullptr;
    int ret = 0;
    try {{
        auto inputHost = ReadBinaryFile("../data/input.bin", inputBytes);
        CheckAcl(aclInit(nullptr), "aclInit");
        CheckAcl(aclrtSetDevice(0), "aclrtSetDevice");
        CheckAcl(aclrtCreateStream(&stream), "aclrtCreateStream");
        CheckAcl(aclrtMalloc(&inputDev, inputBytes, ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc input");
        CheckAcl(aclrtMalloc(&outputDev, outputBytes, ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc output");
        CheckAcl(aclrtMalloc(&tilingDev, tilingBytes, ACL_MEM_MALLOC_HUGE_FIRST), "aclrtMalloc tiling");
        CheckAcl(aclrtMemcpy(inputDev, inputBytes, inputHost.data(), inputBytes, ACL_MEMCPY_HOST_TO_DEVICE), "copy input");
        CheckAcl(aclrtMemcpy(tilingDev, tilingBytes, &tiling, tilingBytes, ACL_MEMCPY_HOST_TO_DEVICE), "copy tiling");
        {kernel_name}<<<kBlockDim, nullptr, stream>>>(static_cast<uint8_t*>(inputDev), static_cast<uint8_t*>(outputDev), static_cast<uint8_t*>(tilingDev));
        CheckAcl(aclrtSynchronizeStream(stream), "sync");
        std::vector<uint8_t> outputHost(outputBytes);
        CheckAcl(aclrtMemcpy(outputHost.data(), outputBytes, outputDev, outputBytes, ACL_MEMCPY_DEVICE_TO_HOST), "copy output");
        WriteBinaryFile("output/output.bin", outputHost);
        std::cout << "{target} run completed" << std::endl;
    }} catch (const std::exception &ex) {{
        std::cerr << ex.what() << std::endl;
        ret = 1;
    }}
    if (tilingDev != nullptr) {{ aclrtFree(tilingDev); }}
    if (outputDev != nullptr) {{ aclrtFree(outputDev); }}
    if (inputDev != nullptr) {{ aclrtFree(inputDev); }}
    if (stream != nullptr) {{ aclrtDestroyStream(stream); }}
    aclrtResetDevice(0);
    aclFinalize();
    return ret;
}}
"""


def golden_expr(op_name: str) -> str:
    if op_name == "gelu_mul":
        return "y = [v * v / (1.0 + math.exp(-1.702 * v)) for v in x[:n]] + [0.0] * (stride - n)"
    if op_name == "mish":
        return "y = [v * math.tanh(math.log1p(math.exp(v))) for v in x[:n]] + [0.0] * (stride - n)"
    if op_name == "fast_gelu":
        return "y = [v / (1.0 + math.exp(-1.702 * v)) for v in x[:n]] + [0.0] * (stride - n)"
    if op_name == "fast_gelu_grad":
        return (
            "s = 1.702\n"
            "    y = []\n"
            "    for v in x[:n]:\n"
            "        e = math.exp(-s * v)\n"
            "        dydx = (1.0 + e * (1.0 - s * v)) / ((1.0 + e) ** 2)\n"
            "        y.append(v * dydx)\n"
            "    y = y + [0.0] * (stride - n)"
        )
    if op_name == "layer_norm":
        return "y = [(v - 1.0) / 2.0 for v in x[:n]] + [0.0] * (stride - n)"
    if op_name in {"topk", "max_pool", "conv2d"}:
        # Placeholder identity-like golden used by current inject baselines.
        return "y = list(x[:n]) + [0.0] * (stride - n)"
    if op_name == "swi_glu":
        return (
            "y = []\n"
            "    for i in range(n):\n"
            "        a = x[i]\n"
            "        b = x[n + i]\n"
            "        y.append((a / (1.0 + math.exp(-a))) * b)\n"
            "    y = y + [0.0] * (out_stride - n)"
        )
    raise ValueError(f"no golden for {op_name}")


def gen_data_text(op_name: str, kernel_name: str, case_id: str, knobs: dict, input_mul: int = 1) -> str:
    n = int(knobs["output_elements"])
    blockdim = int(knobs["blockdim"])
    tile = int(knobs["tile_length"])
    tile_mul = int(knobs.get("tile_num_multiplier", knobs.get("tile_num_mul", 1)))
    golden = golden_expr(op_name)
    if op_name == "swi_glu":
        body = f"""
    n = int(SPEC["output_elements"])
    in_logical = n * {input_mul}
    in_stride = align_up(in_logical, 8)
    out_stride = align_up(n, 8)
    blockdim = int(SPEC["blockdim"])
    tile_len = align_up(int(SPEC["tile_length"]), 8)
    elems_per_core = (n + blockdim - 1) // blockdim
    base_tile_num = (elems_per_core + tile_len - 1) // tile_len
    tile_num = max(1, base_tile_num * int(SPEC["tile_num_mul"]))
    rng = random.Random(20260709)
    x = [rng.uniform(-3.0, 3.0) for _ in range(in_logical)] + [0.0] * (in_stride - in_logical)
    {golden}
    blob_x = struct.pack(f"{{len(x)}}f", *x)
    blob_y = struct.pack(f"{{len(y)}}f", *y)
    (data / "input.bin").write_bytes(blob_x)
    (data / "golden.bin").write_bytes(blob_y)
    (build_sim / "input.bin").write_bytes(blob_x)
    tiling = (in_logical, n, in_stride, out_stride, elems_per_core, tile_len, align_up(tile_len, 8), tile_num, n % tile_len, 0)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))
    shape_in = in_stride
    shape_out = out_stride
"""
    else:
        body = f"""
    n = int(SPEC["output_elements"])
    stride = align_up(n, 8)
    blockdim = int(SPEC["blockdim"])
    tile_len = align_up(int(SPEC["tile_length"]), 8)
    elems_per_core = (n + blockdim - 1) // blockdim
    base_tile_num = (elems_per_core + tile_len - 1) // tile_len
    tile_num = max(1, base_tile_num * int(SPEC["tile_num_mul"]))
    rng = random.Random(20260709)
    x = [rng.uniform(-3.0, 3.0) for _ in range(n)] + [0.0] * (stride - n)
    {golden}
    blob_x = struct.pack(f"{{len(x)}}f", *x)
    blob_y = struct.pack(f"{{len(y)}}f", *y)
    (data / "input.bin").write_bytes(blob_x)
    (data / "golden.bin").write_bytes(blob_y)
    (build_sim / "input.bin").write_bytes(blob_x)
    tiling = (n, n, stride, stride, elems_per_core, tile_len, align_up(tile_len, 8), tile_num, n % tile_len, 0)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))
    shape_in = stride
    shape_out = stride
"""
    return f"""#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {{
  "output_elements": {n},
  "blockdim": {blockdim},
  "tile_length": {tile},
  "tile_num_mul": {tile_mul}
}}

def align_up(value: int, align: int) -> int:
    return ((value + align - 1) // align) * align

def main() -> int:
    root = Path.cwd()
    data = root / "data"
    build_sim = root / "build_sim"
    data.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)
{body}
    op_config = {{
        "kernel_name": "{kernel_name}",
        "kernel_path": "./{kernel_name}.o",
        "blockdim": blockdim,
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{{
            "case_name": "{case_id}_case0",
            "param_desc": [
                {{"param_type": "input", "type": "float32", "shape": [shape_in], "data_path": "./input.bin", "name": "x"}},
                {{"param_type": "output", "type": "float32", "shape": [shape_out], "name": "y"}},
                {{"param_type": "tiling", "tiling_data_size": 40, "tiling_data_path": "./tiling.bin"}}
            ]
        }}]
    }}
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {{
        "case_id": "{case_id}",
        "kernel": "{kernel_name}",
        "dtype": "float32",
        "shape": [n],
        "blockdim": blockdim,
        "tile_length": tile_len
    }}
    (root / "case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def run_sh_text(target: str, kernel_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
TARGET_NAME="{target}"
KERNEL_NAME="{kernel_name}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../common/run_direct_invoke.sh" ]; then
  COMMON_RUN="$SCRIPT_DIR/../common/run_direct_invoke.sh"
else
  COMMON_RUN="$SCRIPT_DIR/../../common/run_direct_invoke.sh"
fi
# shellcheck disable=SC1090
source "$COMMON_RUN" "$@"
"""


def ensure_common_runner() -> None:
    dest = INJECT_ROOT / "common" / "run_direct_invoke.sh"
    text = GOLD_COMMON.read_text(encoding="utf-8")
    # Point tmp root at aprof_injected_ops instead of aprof_benchmark.
    text = text.replace(
        'APROF_CASE_TMP="${APROF_CASE_TMP:-$APROF_TMP_ROOT/aprof_benchmark/$bench_name/$case_id}"',
        'APROF_CASE_TMP="${APROF_CASE_TMP:-$APROF_TMP_ROOT/aprof_injected_ops/$bench_name/$case_id}"',
    )
    write_text(dest, text)


def collect_knobs(case_dir: Path, op_name: str) -> dict:
    meta = case_dir / "metadata.json"
    if meta.is_file():
        data = load_json(meta)
        return {
            "output_elements": int(data.get("output_elements", 2048)),
            "blockdim": int(data.get("blockdim", 1)),
            "tile_length": int(data.get("tile_length", 256)),
            "tile_num_multiplier": int(data.get("tile_num_multiplier", data.get("tile_num_mul", 1))),
        }
    # Fallback defaults
    defaults = {
        "gelu_mul": {"output_elements": 2048, "blockdim": 4, "tile_length": 256, "tile_num_multiplier": 1},
        "mish": {"output_elements": 2048, "blockdim": 1, "tile_length": 256, "tile_num_multiplier": 1},
        "swi_glu": {"output_elements": 2048, "blockdim": 1, "tile_length": 256, "tile_num_multiplier": 1},
        "fast_gelu": {"output_elements": 2048, "blockdim": 1, "tile_length": 256, "tile_num_multiplier": 1},
    }
    return defaults.get(op_name, {"output_elements": 2048, "blockdim": 1, "tile_length": 256, "tile_num_multiplier": 1})


def collect_gt(case_dir: Path, folder: str) -> dict | None:
    if folder == "baseline":
        return None
    mf = case_dir / "inject_manifest.json"
    if mf.is_file():
        gt = load_json(mf).get("ground_truth", {})
        return {
            "folder": folder,  # will be rewritten to op_XXXX
            "problem_family": gt.get("problem_family", "unknown"),
            "problem_id": gt.get("problem_id", gt.get("injected_label", "unknown")),
            "legacy_variant": case_dir.name,
        }
    meta = case_dir / "metadata.json"
    if meta.is_file():
        data = load_json(meta)
        label = data.get("injected_label", "unknown")
        return {
            "folder": folder,
            "problem_family": "unknown",
            "problem_id": label,
            "legacy_variant": case_dir.name,
        }
    return {
        "folder": folder,
        "problem_family": "unknown",
        "problem_id": "unknown",
        "legacy_variant": case_dir.name,
    }


def upgrade_case(
    case_dir: Path,
    op_name: str,
    case_id: str,
    target: str,
    knobs: dict,
    input_mul: int,
) -> None:
    kernel_name = f"{op_name}_kernel"
    kernel_path = case_dir / "op_kernel" / f"{kernel_name}.asc"
    if not kernel_path.is_file():
        # Some ops may use different naming; keep existing .asc
        asc_files = list((case_dir / "op_kernel").glob("*_kernel.asc"))
        if not asc_files:
            raise FileNotFoundError(f"no kernel in {case_dir}")
        kernel_path = asc_files[0]
        kernel_name = kernel_path.stem

    # Neutralize kernel + headers
    for src in (case_dir / "op_kernel").glob("*"):
        if src.suffix in {".asc", ".h", ".hpp"} and src.name != "aprof_variant_config.h":
            write_text(src, neutralize_source(src.read_text(encoding="utf-8")))

    config_path = case_dir / "op_kernel" / "aprof_variant_config.h"
    if config_path.is_file():
        flags = parse_flags_from_config(config_path.read_text(encoding="utf-8"))
    else:
        flags = {fid: 0 for fid in FEATURE_IDS}
    write_variant_config(config_path, flags)

    write_text(case_dir / "CMakeLists.txt", cmake_text(target))
    write_text(case_dir / "op_host" / "data_utils.h", GOLD_DATA_UTILS.read_text(encoding="utf-8"))
    write_text(
        case_dir / "op_host" / "main.asc",
        host_main_text(op_name, kernel_name, target, knobs, input_mul=input_mul),
    )
    write_text(case_dir / "scripts" / "verify_result.py", GOLD_VERIFY.read_text(encoding="utf-8"))
    write_text(
        case_dir / "scripts" / "gen_data.py",
        gen_data_text(op_name, kernel_name, case_id, knobs, input_mul=input_mul),
    )
    write_text(case_dir / "run.sh", run_sh_text(target, kernel_name))

    # Neutral case metadata only
    case_meta = {
        "case_id": case_id,
        "kernel": kernel_name,
        "dtype": "float32",
        "shape": [int(knobs["output_elements"])],
        "blockdim": int(knobs["blockdim"]),
        "tile_length": int(knobs["tile_length"]),
    }
    write_text(case_dir / "case_metadata.json", json.dumps(case_meta, indent=2) + "\n")

    # Remove answer-leaking artifacts from agent-visible case tree
    for name in (
        "inject_manifest.json",
        "metadata.json",
        "blind_input.json",
        "profiling_plan.json",
        "label_alignment_report.json",
        "label_alignment_report.md",
    ):
        p = case_dir / name
        if p.exists():
            p.unlink()


def upgrade_op(op_name: str, dry_run: bool = False) -> None:
    op_dir = INJECT_ROOT / op_name
    if not op_dir.is_dir():
        raise SystemExit(f"missing op: {op_dir}")

    input_mul = 2 if op_name in SWI_GLU_OPS else 1
    variants = sorted(
        d.name
        for d in op_dir.iterdir()
        if d.is_dir() and (d.name == "baseline" or d.name.startswith("inject_"))
    )
    if "baseline" not in variants:
        raise SystemExit(f"{op_name}: no baseline")

    injects = [v for v in variants if v.startswith("inject_")]
    mapping: list[tuple[str, str]] = [("baseline", "baseline")]
    for i, old in enumerate(sorted(injects), start=1):
        mapping.append((old, f"op_{i:04d}"))

    print(f"=== {op_name} ===")
    for old, new in mapping:
        print(f"  {old} -> {new}")
    if dry_run:
        return

    ensure_common_runner()
    gt_cases = []
    tmp_root = op_dir / ".upgrade_tmp"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir()

    for old, new in mapping:
        src = op_dir / old
        dst = tmp_root / new
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "build", "build_sim", "msprof_*", "remote_inject_out", "data", "__pycache__", "*.o", "*.obj"
        ))
        knobs = collect_knobs(src, op_name)
        # Prefer knobs from original metadata before we wipe it
        if (src / "metadata.json").is_file():
            knobs = collect_knobs(src, op_name)
        target = f"{op_name}_{new}"
        case_id = new
        upgrade_case(dst, op_name, case_id, target, knobs, input_mul)
        if old != "baseline":
            gt = collect_gt(src, new)
            if gt:
                gt["folder"] = new
                gt_cases.append(gt)

    # Replace case dirs
    for old, _ in mapping:
        shutil.rmtree(op_dir / old)
    for _, new in mapping:
        shutil.move(str(tmp_root / new), str(op_dir / new))
    shutil.rmtree(tmp_root)

    # Ground truth (maintainer only)
    gt_dir = op_dir / ".ground_truth"
    gt_dir.mkdir(exist_ok=True)
    gt_doc = {
        "schema_version": 1,
        "note": "Ground truth for benchmark maintainers. Case directories and case metadata are intentionally anonymous. Diagnosis agents must not read this file.",
        "baseline": "baseline",
        "cases": [
            {
                "folder": c["folder"],
                "problem_family": c["problem_family"],
                "problem_id": c["problem_id"],
                "legacy_variant": c.get("legacy_variant"),
            }
            for c in gt_cases
        ],
    }
    write_text(gt_dir / "case_problem_map.json", json.dumps(gt_doc, indent=2) + "\n")

    # Move maintainer-only artifacts that leak labels out of agent-visible tree
    archive = gt_dir / "legacy_artifacts"
    archive.mkdir(exist_ok=True)
    for name in (
        "label_alignment_report.json",
        "label_alignment_report.md",
        "inject_deploy_manifest.json",
        "diagnosis_predictions.json",
        "remote_inject_out",
        "blind_inputs",
        "inject_tilelen_small_v2",
        "inject_tiling_unreasonable",
        "inject_data_move_bottleneck",
    ):
        p = op_dir / name
        if not p.exists():
            continue
        dest = archive / name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(p), str(dest))

    print(f"[ok] upgraded {op_name}: baseline + {len(gt_cases)} anonymous cases")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ops", nargs="+", default=["gelu_mul"], help="operators to upgrade")
    parser.add_argument("--all-vector", action="store_true", help="upgrade all supported vector ops")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ops = sorted(VECTOR_OPS | SWI_GLU_OPS) if args.all_vector else args.ops
    for op in ops:
        if op not in VECTOR_OPS and op not in SWI_GLU_OPS:
            print(f"[skip] {op}: not in supported vector template set yet")
            continue
        upgrade_op(op, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
