#!/usr/bin/env python3
"""Upgrade matmul / foreach_norm in aprof_injected_ops to full direct-invoke layout."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECT_ROOT = ROOT / "benchmarks" / "aprof_injected_ops"
GOLD_DATA_UTILS = (
    ROOT / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "direct_invoke_baseline" / "op_host" / "data_utils.h"
)
GOLD_VERIFY = (
    ROOT / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "direct_invoke_baseline" / "scripts" / "verify_result.py"
)

# Reuse helpers from the main upgrade script.
import importlib.util

spec = importlib.util.spec_from_file_location(
    "upgrade_main", ROOT / "scripts" / "upgrade_injected_ops_direct_invoke.py"
)
um = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(um)


def parse_gen_defaults(gen_path: Path) -> dict[str, int]:
    text = gen_path.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for key in (
        "default_m",
        "default_n",
        "default_k",
        "default_tile_m",
        "default_tile_n",
        "default_blockdim",
        "default_num_tensors",
        "default_tensor_length",
        "default_tile_length",
        "variant_flags",
    ):
        m = re.search(rf"{key}\s*=\s*(\d+)", text)
        if m:
            out[key] = int(m.group(1))
    return out


def matmul_host(target: str, knobs: dict) -> str:
    m, n, k = knobs["default_m"], knobs["default_n"], knobs["default_k"]
    tm, tn = knobs["default_tile_m"], knobs["default_tile_n"]
    bd = knobs["default_blockdim"]
    return f"""#include "acl/acl.h"
#include "kernel_operator.h"
#include "data_utils.h"
#include "../op_kernel/aprof_matmul_tiling.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
#include "../op_kernel/matmul_kernel.asc"

namespace {{
constexpr uint32_t kM = {m}U;
constexpr uint32_t kN = {n}U;
constexpr uint32_t kK = {k}U;
constexpr uint32_t kTileM = {tm}U;
constexpr uint32_t kTileN = {tn}U;
constexpr uint32_t kBlockDim = {bd}U;
constexpr uint32_t kFp32Align = 8U;
uint32_t AlignUp(uint32_t v, uint32_t a) {{ return ((v + a - 1) / a) * a; }}
void CheckAcl(aclError ret, const char *what) {{
    if (ret != ACL_SUCCESS) {{ std::cerr << what << " failed: " << ret << std::endl; throw std::runtime_error(what); }}
}}
AprofMatmulTilingData BuildTiling() {{
    AprofMatmulTilingData t{{}};
    t.m = AlignUp(kM, kFp32Align); t.n = AlignUp(kN, kFp32Align); t.k = AlignUp(kK, kFp32Align);
    t.tileM = AlignUp(kTileM, kFp32Align); t.tileN = AlignUp(kTileN, kFp32Align);
    t.tileMAligned = t.tileM; t.tileNAligned = t.tileN;
    t.rowsPerCore = (t.m + kBlockDim - 1) / kBlockDim;
    t.inputStride = AlignUp(t.m * t.k + t.k * t.n, kFp32Align);
    t.outputStride = AlignUp(t.m * t.n, kFp32Align);
    t.blockdim = kBlockDim; t.variantFlags = 0;
    return t;
}}
}} // namespace

int main() {{
    const auto tiling = BuildTiling();
    const size_t inputBytes = static_cast<size_t>(tiling.inputStride) * sizeof(float);
    const size_t outputBytes = static_cast<size_t>(tiling.outputStride) * sizeof(float);
    const size_t tilingBytes = sizeof(AprofMatmulTilingData);
    aclrtStream stream = nullptr; void* inputDev=nullptr; void* outputDev=nullptr; void* tilingDev=nullptr; int ret=0;
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
        matmul_kernel<<<kBlockDim, nullptr, stream>>>(static_cast<uint8_t*>(inputDev), static_cast<uint8_t*>(outputDev), static_cast<uint8_t*>(tilingDev));
        CheckAcl(aclrtSynchronizeStream(stream), "sync");
        std::vector<uint8_t> outputHost(outputBytes);
        CheckAcl(aclrtMemcpy(outputHost.data(), outputBytes, outputDev, outputBytes, ACL_MEMCPY_DEVICE_TO_HOST), "copy output");
        WriteBinaryFile("output/output.bin", outputHost);
        std::cout << "{target} run completed" << std::endl;
    }} catch (const std::exception &ex) {{ std::cerr << ex.what() << std::endl; ret = 1; }}
    if (tilingDev) aclrtFree(tilingDev); if (outputDev) aclrtFree(outputDev); if (inputDev) aclrtFree(inputDev);
    if (stream) aclrtDestroyStream(stream); aclrtResetDevice(0); aclFinalize(); return ret;
}}
"""


def foreach_host(target: str, knobs: dict) -> str:
    nt, tl, tile, bd = (
        knobs["default_num_tensors"],
        knobs["default_tensor_length"],
        knobs["default_tile_length"],
        knobs["default_blockdim"],
    )
    return f"""#include "acl/acl.h"
#include "kernel_operator.h"
#include "data_utils.h"
#include "../op_kernel/aprof_foreach_tiling.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
#include "../op_kernel/foreach_norm_kernel.asc"

namespace {{
constexpr uint32_t kNumTensors = {nt}U;
constexpr uint32_t kTensorLength = {tl}U;
constexpr uint32_t kTileLength = {tile}U;
constexpr uint32_t kBlockDim = {bd}U;
constexpr uint32_t kFp32Align = 8U;
uint32_t AlignUp(uint32_t v, uint32_t a) {{ return ((v + a - 1) / a) * a; }}
void CheckAcl(aclError ret, const char *what) {{
    if (ret != ACL_SUCCESS) {{ std::cerr << what << " failed: " << ret << std::endl; throw std::runtime_error(what); }}
}}
AprofForeachTilingData BuildTiling() {{
    AprofForeachTilingData t{{}};
    t.numTensors = kNumTensors;
    t.tensorLength = AlignUp(kTensorLength, kFp32Align);
    t.tileLength = AlignUp(kTileLength, kFp32Align);
    if (t.tileLength > t.tensorLength) t.tileLength = t.tensorLength;
    t.tileLengthAligned = t.tileLength;
    t.tensorsPerCore = (t.numTensors + kBlockDim - 1) / kBlockDim;
    t.inputStride = AlignUp(t.numTensors * t.tensorLength, kFp32Align);
    t.outputStride = AlignUp(t.numTensors, kFp32Align);
    t.blockdim = kBlockDim; t.variantFlags = 0;
    return t;
}}
}} // namespace

int main() {{
    const auto tiling = BuildTiling();
    const size_t inputBytes = static_cast<size_t>(tiling.inputStride) * sizeof(float);
    const size_t outputBytes = static_cast<size_t>(tiling.outputStride) * sizeof(float);
    const size_t tilingBytes = sizeof(AprofForeachTilingData);
    aclrtStream stream = nullptr; void* inputDev=nullptr; void* outputDev=nullptr; void* tilingDev=nullptr; int ret=0;
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
        foreach_norm_kernel<<<kBlockDim, nullptr, stream>>>(static_cast<uint8_t*>(inputDev), static_cast<uint8_t*>(outputDev), static_cast<uint8_t*>(tilingDev));
        CheckAcl(aclrtSynchronizeStream(stream), "sync");
        std::vector<uint8_t> outputHost(outputBytes);
        CheckAcl(aclrtMemcpy(outputHost.data(), outputBytes, outputDev, outputBytes, ACL_MEMCPY_DEVICE_TO_HOST), "copy output");
        WriteBinaryFile("output/output.bin", outputHost);
        std::cout << "{target} run completed" << std::endl;
    }} catch (const std::exception &ex) {{ std::cerr << ex.what() << std::endl; ret = 1; }}
    if (tilingDev) aclrtFree(tilingDev); if (outputDev) aclrtFree(outputDev); if (inputDev) aclrtFree(inputDev);
    if (stream) aclrtDestroyStream(stream); aclrtResetDevice(0); aclFinalize(); return ret;
}}
"""


def matmul_gen(case_id: str, knobs: dict) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {{
  "m": {knobs['default_m']}, "n": {knobs['default_n']}, "k": {knobs['default_k']},
  "tile_m": {knobs['default_tile_m']}, "tile_n": {knobs['default_tile_n']},
  "blockdim": {knobs['default_blockdim']}
}}

def align_up(v, a): return ((v + a - 1) // a) * a

def matmul_golden(a, b, m, n, k):
    out = [0.0] * (m * n)
    for i in range(m):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += a[i * k + p] * b[p * n + j]
            out[i * n + j] = s
    return out

def main() -> int:
    root = Path.cwd(); data = root / "data"; build_sim = root / "build_sim"
    data.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)
    m = align_up(SPEC["m"], 8); n = align_up(SPEC["n"], 8); k = align_up(SPEC["k"], 8)
    tile_m = align_up(SPEC["tile_m"], 8); tile_n = align_up(SPEC["tile_n"], 8)
    blockdim = SPEC["blockdim"]
    a_elems, b_elems, c_elems = m*k, k*n, m*n
    in_stride = align_up(a_elems + b_elems, 8); out_stride = align_up(c_elems, 8)
    rows_per_core = (m + blockdim - 1) // blockdim
    rng = random.Random(20260709)
    a = [rng.uniform(-1.0, 1.0) for _ in range(a_elems)]
    b = [rng.uniform(-1.0, 1.0) for _ in range(b_elems)]
    c = matmul_golden(a, b, m, n, k)
    xin = [0.0]*in_stride; xin[:a_elems]=a; xin[a_elems:a_elems+b_elems]=b
    yout = [0.0]*out_stride; yout[:c_elems]=c
    (data/"input.bin").write_bytes(struct.pack(f"{{len(xin)}}f", *xin))
    (data/"golden.bin").write_bytes(struct.pack(f"{{len(yout)}}f", *yout))
    (build_sim/"input.bin").write_bytes(struct.pack(f"{{len(xin)}}f", *xin))
    tiling = (m,n,k,tile_m,tile_n,tile_m,tile_n,rows_per_core,in_stride,out_stride,blockdim,0)
    (build_sim/"tiling.bin").write_bytes(struct.pack("12I", *tiling))
    op_config = {{
        "kernel_name": "matmul_kernel", "kernel_path": "./matmul_kernel.o",
        "blockdim": blockdim, "mode": "ca", "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{{"case_name": "{case_id}_case0", "param_desc": [
            {{"param_type":"input","type":"float32","shape":[in_stride],"data_path":"./input.bin","name":"ab"}},
            {{"param_type":"output","type":"float32","shape":[out_stride],"name":"c"}},
            {{"param_type":"tiling","tiling_data_size":48,"tiling_data_path":"./tiling.bin"}}
        ]}}]
    }}
    (build_sim/"op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {{"case_id":"{case_id}","kernel":"matmul_kernel","dtype":"float32","shape":[m,n,k],"blockdim":blockdim,"tile_m":tile_m,"tile_n":tile_n}}
    (root/"case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def foreach_gen(case_id: str, knobs: dict) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {{
  "num_tensors": {knobs['default_num_tensors']},
  "tensor_length": {knobs['default_tensor_length']},
  "tile_length": {knobs['default_tile_length']},
  "blockdim": {knobs['default_blockdim']}
}}

def align_up(v, a): return ((v + a - 1) // a) * a

def main() -> int:
    root = Path.cwd(); data = root / "data"; build_sim = root / "build_sim"
    data.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)
    n = SPEC["num_tensors"]; L = align_up(SPEC["tensor_length"], 8)
    tile = align_up(SPEC["tile_length"], 8); tile = min(tile, L)
    blockdim = SPEC["blockdim"]
    tpc = (n + blockdim - 1) // blockdim
    in_stride = align_up(n * L, 8); out_stride = align_up(n, 8)
    rng = random.Random(20260709)
    x = [rng.uniform(-3.0, 3.0) for _ in range(n * L)] + [0.0] * (in_stride - n * L)
    y = []
    for i in range(n):
        s = sum(v*v for v in x[i*L:(i+1)*L])
        y.append(math.sqrt(s))
    y = y + [0.0] * (out_stride - n)
    (data/"input.bin").write_bytes(struct.pack(f"{{len(x)}}f", *x))
    (data/"golden.bin").write_bytes(struct.pack(f"{{len(y)}}f", *y))
    (build_sim/"input.bin").write_bytes(struct.pack(f"{{len(x)}}f", *x))
    tiling = (n, L, tile, tile, tpc, in_stride, out_stride, blockdim, 0)
    (build_sim/"tiling.bin").write_bytes(struct.pack("9I", *tiling))
    op_config = {{
        "kernel_name": "foreach_norm_kernel", "kernel_path": "./foreach_norm_kernel.o",
        "blockdim": blockdim, "mode": "ca", "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{{"case_name": "{case_id}_case0", "param_desc": [
            {{"param_type":"input","type":"float32","shape":[in_stride],"data_path":"./input.bin","name":"x"}},
            {{"param_type":"output","type":"float32","shape":[out_stride],"name":"y"}},
            {{"param_type":"tiling","tiling_data_size":36,"tiling_data_path":"./tiling.bin"}}
        ]}}]
    }}
    (build_sim/"op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {{"case_id":"{case_id}","kernel":"foreach_norm_kernel","dtype":"float32","shape":[n,L],"blockdim":blockdim,"tile_length":tile}}
    (root/"case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def upgrade_special(op_name: str) -> None:
    op_dir = INJECT_ROOT / op_name
    um.ensure_common_runner()
    variants = sorted(
        d.name for d in op_dir.iterdir() if d.is_dir() and (d.name == "baseline" or d.name.startswith("inject_"))
    )
    injects = [v for v in variants if v.startswith("inject_")]
    mapping = [("baseline", "baseline")] + [(old, f"op_{i:04d}") for i, old in enumerate(sorted(injects), 1)]
    print(f"=== {op_name} ===")
    for a, b in mapping:
        print(f"  {a} -> {b}")

    tmp = op_dir / ".upgrade_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    gt_cases = []

    for old, new in mapping:
        src = op_dir / old
        dst = tmp / new
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns(
                "build", "build_sim", "msprof_*", "remote_inject_out", "data", "__pycache__", "*.o", "*.obj"
            ),
        )
        knobs = parse_gen_defaults(src / "scripts" / "gen_data.py")
        target = f"{op_name}_{new}"
        # neutralize kernels
        for srcf in (dst / "op_kernel").glob("*"):
            if srcf.suffix in {".asc", ".h"} and srcf.name != "aprof_variant_config.h":
                um.write_text(srcf, um.neutralize_source(srcf.read_text(encoding="utf-8")))
        cfg = dst / "op_kernel" / "aprof_variant_config.h"
        flags = um.parse_flags_from_config(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {f: 0 for f in um.FEATURE_IDS}
        um.write_variant_config(cfg, flags)
        um.write_text(dst / "CMakeLists.txt", um.cmake_text(target))
        um.write_text(dst / "op_host" / "data_utils.h", GOLD_DATA_UTILS.read_text(encoding="utf-8"))
        if op_name == "matmul":
            um.write_text(dst / "op_host" / "main.asc", matmul_host(target, knobs))
            um.write_text(dst / "scripts" / "gen_data.py", matmul_gen(new, knobs))
            kernel_name = "matmul_kernel"
            case_meta = {
                "case_id": new,
                "kernel": kernel_name,
                "dtype": "float32",
                "shape": [knobs["default_m"], knobs["default_n"], knobs["default_k"]],
                "blockdim": knobs["default_blockdim"],
                "tile_m": knobs["default_tile_m"],
                "tile_n": knobs["default_tile_n"],
            }
        else:
            um.write_text(dst / "op_host" / "main.asc", foreach_host(target, knobs))
            um.write_text(dst / "scripts" / "gen_data.py", foreach_gen(new, knobs))
            kernel_name = "foreach_norm_kernel"
            case_meta = {
                "case_id": new,
                "kernel": kernel_name,
                "dtype": "float32",
                "shape": [knobs["default_num_tensors"], knobs["default_tensor_length"]],
                "blockdim": knobs["default_blockdim"],
                "tile_length": knobs["default_tile_length"],
            }
        um.write_text(dst / "scripts" / "verify_result.py", GOLD_VERIFY.read_text(encoding="utf-8"))
        um.write_text(dst / "run.sh", um.run_sh_text(target, kernel_name))
        um.write_text(dst / "case_metadata.json", json.dumps(case_meta, indent=2) + "\n")
        for name in ("inject_manifest.json", "metadata.json", "blind_input.json", "profiling_plan.json"):
            p = dst / name
            if p.exists():
                p.unlink()
        if old != "baseline":
            gt = um.collect_gt(src, new)
            if gt:
                gt["folder"] = new
                gt_cases.append(gt)

    for old, _ in mapping:
        shutil.rmtree(op_dir / old)
    for _, new in mapping:
        shutil.move(str(tmp / new), str(op_dir / new))
    shutil.rmtree(tmp)

    gt_dir = op_dir / ".ground_truth"
    gt_dir.mkdir(exist_ok=True)
    um.write_text(
        gt_dir / "case_problem_map.json",
        json.dumps(
            {
                "schema_version": 1,
                "note": "Ground truth for benchmark maintainers. Diagnosis agents must not read this file.",
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
            },
            indent=2,
        )
        + "\n",
    )
    archive = gt_dir / "legacy_artifacts"
    archive.mkdir(exist_ok=True)
    for name in (
        "label_alignment_report.json",
        "label_alignment_report.md",
        "inject_deploy_manifest.json",
        "diagnosis_predictions.json",
        "remote_inject_out",
        "blind_inputs",
        "inject_tiling_unreasonable",
        "inject_data_move_bottleneck",
    ):
        p = op_dir / name
        if p.exists():
            dest = archive / name
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            shutil.move(str(p), str(dest))
    print(f"[ok] upgraded {op_name}: baseline + {len(gt_cases)} cases")


if __name__ == "__main__":
    upgrade_special("matmul")
    upgrade_special("foreach_norm")
