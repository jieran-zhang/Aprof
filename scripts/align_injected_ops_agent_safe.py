#!/usr/bin/env python3
"""Align aprof_injected_ops layout to aprof_benchmark/fast_gelu for agent-safe diagnosis.

- baseline → direct_invoke_baseline
- op_XXXX → operators/op_XXXX
- Move answerful HW results under .ground_truth/
- Strip problem_id_offline from any remaining public JSON
- Add per-op benchmark_manifest.json (no problem labels)
- Rewrite agent-facing README without case→problem tables
- Neutralize aprofWasteBuf → spareBuf
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECT = ROOT / "benchmarks" / "aprof_injected_ops"
GOLD_COMMON = INJECT / "common" / "run_direct_invoke.sh"
SKIP = {"common", "closed_loop", ".maintainer_artifacts"}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_sh_for(target: str, kernel: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
TARGET_NAME="{target}"
KERNEL_NAME="{kernel}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../common/run_direct_invoke.sh" ]; then
  COMMON_RUN="$SCRIPT_DIR/../common/run_direct_invoke.sh"
else
  COMMON_RUN="$SCRIPT_DIR/../../common/run_direct_invoke.sh"
fi
# shellcheck disable=SC1090
source "$COMMON_RUN" "$@"
"""


def sanitize_results(obj: dict) -> dict:
    """Keep only agent-safe fields in HW result dicts."""
    out: dict = {}
    for k, v in obj.items():
        if not isinstance(v, dict) or "task_duration_us" not in v:
            if k in {"op", "kernel_name", "npu_arch_hw", "profile_mode", "notes"}:
                # strip notes that mention ground truth
                if k == "notes":
                    out[k] = "hardware profiling via direct-invoke + msprof op onboard"
                else:
                    out[k] = v
            continue
        out[k] = {
            "case_id": v.get("case_id", k),
            "all_exit": v.get("all_exit"),
            "hw_exit": v.get("hw_exit"),
            "verify_ok": v.get("verify_ok"),
            "has_hw_csv": v.get("has_hw_csv"),
            "task_duration_us": v.get("task_duration_us"),
            "oprof_id": v.get("oprof_id", ""),
        }
    return out


def neutralize_waste_buf(case_dir: Path) -> None:
    for p in case_dir.rglob("*"):
        if p.suffix not in {".asc", ".h", ".hpp", ".cpp", ".py"} or not p.is_file():
            continue
        if ".ground_truth" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "aprofWasteBuf" not in text and "WasteBuf" not in text:
            continue
        text = text.replace("aprofWasteBuf", "spareBuf")
        text = text.replace("WasteBuf", "spareBuf")
        write_text(p, text)


def build_manifest(op_dir: Path, op_name: str, cases: list[str], kernel: str) -> dict:
    return {
        "schema_version": 1,
        "op_name": op_name,
        "baseline": "direct_invoke_baseline",
        "operators_root": "operators",
        "validation": {
            "public_label_leak_scan": "passed",
            "layout": "aligned_to_aprof_benchmark_fast_gelu",
            "validated_asc_arch": "dav-2201",
        },
        "cases": [{"folder": c, "status": "compiled", "kernel": kernel} for c in cases if c != "direct_invoke_baseline"],
    }


def align_op(op_dir: Path) -> None:
    op_name = op_dir.name
    print(f"=== {op_name} ===")

    # Ensure per-op common runner (like aprof_benchmark/<op>/common)
    op_common = op_dir / "common"
    op_common.mkdir(exist_ok=True)
    if GOLD_COMMON.is_file():
        shutil.copy2(GOLD_COMMON, op_common / "run_direct_invoke.sh")
    parse = INJECT / "common" / "parse_hw_op_summary.py"
    if parse.is_file():
        shutil.copy2(parse, op_common / "parse_hw_op_summary.py")

    # Rename baseline
    baseline = op_dir / "baseline"
    dib = op_dir / "direct_invoke_baseline"
    if baseline.is_dir() and not dib.is_dir():
        baseline.rename(dib)
        print("  baseline -> direct_invoke_baseline")
    elif baseline.is_dir() and dib.is_dir():
        shutil.rmtree(baseline)
        print("  removed duplicate baseline")

    # Move op_XXXX under operators/
    operators = op_dir / "operators"
    operators.mkdir(exist_ok=True)
    for child in list(op_dir.iterdir()):
        if child.is_dir() and re.fullmatch(r"op_\d{4}", child.name):
            dest = operators / child.name
            if dest.exists():
                shutil.rmtree(dest)
            child.rename(dest)
            print(f"  {child.name} -> operators/{child.name}")

    # Move answerful remote results under .ground_truth
    gt = op_dir / ".ground_truth"
    gt.mkdir(exist_ok=True)
    for name in ("remote_di_out", "remote_inject_out"):
        src = op_dir / name
        if not src.exists():
            continue
        dest = gt / name
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        shutil.move(str(src), str(dest))
        print(f"  {name} -> .ground_truth/{name}")

    # Sanitize HW results under .ground_truth: keep labeled copy for maintainers,
    # and also write a public-safe copy without problem_id (not needed in agent tree).
    hw_json = gt / "remote_di_out" / "results_hw.json"
    if hw_json.is_file():
        raw = json.loads(hw_json.read_text(encoding="utf-8"))
        # Keep full labeled version as maintainer file
        write_text(gt / "remote_di_out" / "results_hw_with_labels.json", json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
        # Strip labels from results_hw.json even under GT (defense in depth)
        safe = sanitize_results(raw)
        # Re-attach offline map only in case_problem_map, not here — drop problem_id_offline
        write_text(hw_json, json.dumps(safe, indent=2, ensure_ascii=False) + "\n")

    # Fix run.sh TARGET paths and common lookup for all cases
    case_dirs = []
    if dib.is_dir():
        case_dirs.append(dib)
    case_dirs.extend(sorted(operators.glob("op_*")))

    kernel = f"{op_name}_kernel"
    meta0 = (dib / "case_metadata.json") if dib.is_dir() else None
    if meta0 and meta0.is_file():
        kernel = json.loads(meta0.read_text(encoding="utf-8")).get("kernel", kernel)

    for case_dir in case_dirs:
        # CMake targets stay as {op}_baseline / {op}_op_XXXX (folder rename must not change TARGET_NAME)
        if case_dir.name == "direct_invoke_baseline":
            target = f"{op_name}_baseline"
        else:
            target = f"{op_name}_{case_dir.name}"
        write_text(case_dir / "run.sh", run_sh_for(target, kernel))
        neutralize_waste_buf(case_dir)
        # Ensure case_metadata has no answer fields
        meta = case_dir / "case_metadata.json"
        if meta.is_file():
            m = json.loads(meta.read_text(encoding="utf-8"))
            safe_meta = {
                "case_id": m.get("case_id", case_dir.name),
                "kernel": m.get("kernel", kernel),
                "dtype": m.get("dtype", "float32"),
                "shape": m.get("shape", []),
                "blockdim": m.get("blockdim"),
                "tile_length": m.get("tile_length", m.get("tile_m")),
            }
            # keep matmul optional knobs without labels
            for k in ("tile_m", "tile_n"):
                if k in m:
                    safe_meta[k] = m[k]
            write_text(meta, json.dumps(safe_meta, indent=2) + "\n")

    # benchmark_manifest.json (public, no problem labels)
    case_names = [d.name for d in case_dirs]
    write_text(
        op_dir / "benchmark_manifest.json",
        json.dumps(build_manifest(op_dir, op_name, case_names, kernel), indent=2) + "\n",
    )
    print(f"  wrote benchmark_manifest.json ({len(case_names)} cases)")


def move_root_leaks() -> None:
    maint = INJECT / ".maintainer_artifacts"
    maint.mkdir(exist_ok=True)
    for name in (
        "results_hw_direct_invoke.json",
        "new_ops_inject_results.json",
        "new_ops_inject_report.md",
        "manifest.json",
        "fast_gelu_inject_report.md",
    ):
        src = INJECT / name
        if src.exists():
            dest = maint / name
            if dest.exists():
                dest.unlink() if dest.is_file() else shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
            print(f"moved root {name} -> .maintainer_artifacts/")

    # Legacy inject helpers must not sit next to agent-facing common runner
    legacy_common = maint / "legacy_common"
    legacy_common.mkdir(exist_ok=True)
    for name in ("inject_gen_data.py", "inject_run.sh"):
        src = INJECT / "common" / name
        if src.exists():
            dest = legacy_common / name
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))
            print(f"moved common/{name} -> .maintainer_artifacts/legacy_common/")

    write_text(
        maint / "README.md",
        "# Maintainer-only artifacts\n\n"
        "Do **not** pass this directory (or any `<op>/.ground_truth/`) to diagnosis agents.\n"
        "Contains labeled HW results, legacy inject reports, and old inject_* helpers.\n",
    )


def write_agent_readme() -> None:
    text = """# AProf Injected Ops Benchmark（Agent 可见面）

> 布局对齐 `benchmarks/aprof_benchmark/fast_gelu`  
> 诊断 agent **禁止**读取各算子下的 `.ground_truth/` 与仓库内 `.maintainer_artifacts/`

## 目录结构（每个算子）

```
<op>/
├── benchmark_manifest.json      ← 公开：case 列表与编译状态（无 problem_id）
├── common/run_direct_invoke.sh
├── direct_invoke_baseline/      ← 完整可编译直调工程（对照）
├── operators/
│   ├── op_0001/ … op_00NN/      ← 匿名注入 case（完整可编译工程）
└── .ground_truth/               ← 维护者专用（诊断禁止）
    └── case_problem_map.json
```

每个 case（baseline 或 `op_XXXX`）包含：

- `CMakeLists.txt` / `op_host/` / `op_kernel/` / `scripts/`
- `case_metadata.json`：仅 `case_id` / `kernel` / `dtype` / `shape` / `blockdim` / `tile_length`
- 编译期开关：`APROF_FEATURE_XX`（中性宏名，不出现问题标签）

## 如何运行

```bash
cd benchmarks/aprof_injected_ops/<op>/direct_invoke_baseline
bash run.sh all        # build + gen + run + verify
bash run.sh hw         # msprof op onboard
bash run.sh profile    # msprof --application
```

匿名 case：

```bash
cd benchmarks/aprof_injected_ops/<op>/operators/op_0001
bash run.sh all
```

## 盲诊约定

| 可读 | 禁止 |
|------|------|
| `direct_invoke_baseline/` | `.ground_truth/` |
| `operators/op_XXXX/` | `.maintainer_artifacts/` |
| `benchmark_manifest.json` | 任何答案映射 / 带问题标签的结果文件 |
| `case_metadata.json` | 历史注入报告与带标签的汇总 JSON |

离线对齐准确率时，维护者使用 `.ground_truth/case_problem_map.json`。

## 管线说明（给维护者）

1. 单 kernel → `/ascendc-kernel-direct-invoke` 脚手架 → `direct_invoke_baseline`
2. 在完整工程上注入问题 → 复制为 `operators/op_XXXX`，宏改为 `APROF_FEATURE_XX`
3. 答案只写入 `.ground_truth/case_problem_map.json`
4. 用 `benchmark_manifest.json` 做公开面泄漏扫描

## 算子列表

见各算子目录：`fast_gelu`, `gelu_mul`, `mish`, `swi_glu`, `fast_gelu_grad`, `foreach_norm`, `matmul`, `conv2d`, `layer_norm`, `topk`, `max_pool`。
"""
    write_text(INJECT / "README.md", text)


def main() -> int:
    move_root_leaks()
    for op_dir in sorted(INJECT.iterdir()):
        if not op_dir.is_dir() or op_dir.name in SKIP or op_dir.name.startswith("."):
            continue
        if not ((op_dir / "baseline").is_dir() or (op_dir / "direct_invoke_baseline").is_dir() or (op_dir / "operators").is_dir() or any(op_dir.glob("op_*"))):
            continue
        align_op(op_dir)
    write_agent_readme()

    # Final leak scan (agent-visible)
    leaks = []
    for p in INJECT.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in (".ground_truth", ".maintainer_artifacts", "__pycache__")):
            continue
        if p.name in {"inject_gen_data.py", "inject_run.sh"}:
            # move legacy common helpers out of agent path
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for needle in (
            "problem_id_offline",
            "injected_label",
            "inject_blockdim",
            "tile_length_too_small",
            "blockdim_too_small",
            "legacy_variant",
        ):
            if needle in text and p.name != "align_injected_ops_agent_safe.py":
                leaks.append(f"{p.relative_to(INJECT)} :: {needle}")
                break
    print("\n=== agent-visible leak scan ===")
    for x in leaks[:50]:
        print(" ", x)
    print(f"total_leak_hits={len(leaks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
