#!/usr/bin/env python3
"""Copy an existing exp/sigmoid shared-buffer source and add Task-only profiling.

This is mechanical, build-only preparation. It never runs a native binary or
asserts that the profiling method has passed hardware qualification.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import shutil

from qualify_shared_timing_v051 import exact, save_new, sha, source_files

ROOT = Path(__file__).resolve().parents[3]
HEADER = ROOT / "scaffolding/benchmarks/cannbench/harness/device_task_profile.h"
OPERATORS = ("exp", "sigmoid")


def adapt_host(text: str, operator: str) -> str:
    if operator not in OPERATORS:
        raise ValueError("unsupported native Task profiling operator")
    if '#include "device_task_profile.h"' in text or "aprof::TaskProfile" in text:
        raise ValueError("host already contains native Task profiling instrumentation")
    text = exact(text, '#include "device_shared_timing.h"',
                 '#include "device_shared_timing.h"\n#include "device_task_profile.h"')
    text = exact(text, '        Check(aclInit(nullptr), "aclInit");',
                 '        Check(aclInit(nullptr), "aclInit");\n        aprof::TaskProfile task_profile;')
    call = (f'        aprof::RunShared(stream, "{operator}", cycle_text[0] - \'0\', 1, 1, buffers,\n'
            '                         {"launch_baseline", "launch_candidate"}, launch_baseline, launch_candidate, snapshot);')
    return exact(text, call, '        task_profile.Start(static_cast<uint32_t>(device));\n' +
                 call + '\n        task_profile.Finish();')


def adapt_cmake(text: str, operator: str) -> str:
    if operator not in OPERATORS:
        raise ValueError("unsupported native Task profiling operator")
    line = (f"target_link_libraries({operator} PRIVATE tiling_api register platform unified_dlog "
            "dl m graph_base ascendcl ascendc_runtime)")
    return exact(text, line, line[:-1] + " msprofiler)")


def prepare(source: Path, output: Path, operator: str) -> dict:
    if operator not in OPERATORS:
        raise ValueError("unsupported native Task profiling operator")
    source, output = source.resolve(strict=True), output.resolve()
    before_files = source_files(source)
    new_header = "op_host/device_task_profile.h"
    if new_header in before_files:
        raise ValueError("source already has the native profiling adapter")
    if output.exists():
        raise FileExistsError("prospective preparation already exists: " + str(output))
    output.mkdir(parents=True)
    destination = output / "source"
    for relative in before_files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    patches = {}
    for relative, adapter in ((f"op_host/{operator}.asc", adapt_host), ("CMakeLists.txt", adapt_cmake)):
        before = (source / relative).read_text()
        after = adapter(before, operator)
        (destination / relative).write_text(after)
        patches[relative] = {
            "before_sha256": before_files[relative], "after_sha256": sha(destination / relative),
            "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                fromfile="original/" + relative, tofile="adapted/" + relative)),
        }
    shutil.copyfile(HEADER, destination / new_header)
    after_files = source_files(destination)
    unchanged = sorted(set(before_files) - patches.keys())
    if any(after_files[relative] != before_files[relative] for relative in unchanged):
        raise ValueError("mechanical instrumentation changed a protected source")
    if source_files(source) != before_files:
        raise ValueError("original source changed while preparing")
    proof = {
        "schema_version": "1.0.0", "operator": operator,
        "purpose": "prospective_native_task_profile_api_build_only",
        "original_source": str(source), "adapted_source": str(destination),
        "original_files": before_files, "adapted_files": after_files,
        "unchanged_files": unchanged, "patches": patches,
        "new_files": {new_header: sha(HEADER)},
        "producers": {str(Path(__file__).resolve()): sha(__file__), str(HEADER): sha(HEADER),
                      str(Path(source_files.__code__.co_filename).resolve()): sha(source_files.__code__.co_filename)},
        "api": {"output_environment": "APROF_TASK_PROFILE_DIR", "data_type": "ACL_PROF_TASK_TIME",
                "aicore_metrics": "ACL_AICORE_NONE", "aicore_events": None, "library": "msprofiler"},
        "preserved": ["RunShared call", "shared timing header", "kernel", "tiling", "oracle", "callback bodies"],
        "limits": "No NPU run or method admission is performed by this adapter.",
    }
    save_new(output / "source-review.json", proof)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operator", required=True, choices=OPERATORS)
    args = parser.parse_args()
    prepare(args.source, args.output, args.operator)


if __name__ == "__main__":
    main()
