#!/usr/bin/env python3
"""CPU-only source/input/command preparation for all five frozen validation ops.

The adapter never treats generated plans as correctness or performance receipts.
Builds, baseline qualification and the formal evaluator are separate stages.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys

from run_aprof_job import dump, sha

ROOT = Path(__file__).resolve().parents[3]
OPERATORS = ("dynamic_quant", "gelu", "gqa", "group_norm", "weight_quant_batch_matmul")
TRAIN_CONTROLS = ("exp", "sigmoid")
SUPPORTED_OPERATORS = OPERATORS + TRAIN_CONTROLS
HEADER = ROOT / "scaffolding/benchmarks/cannbench/harness/device_timer_v2.h"
BEGIN, END = "// APROF_EVAL_OPERATOR_BEGIN\n", "// APROF_EVAL_OPERATOR_END\n"
WRAPPERS = {
    "exp": ("        exp_kernel<<<", '        Check(aclrtSynchronizeStream(stream), "kernel synchronize");', "stream", "device", "1"),
    "sigmoid": ("        sigmoid_kernel<<<", '        Check(aclrtSynchronizeStream(stream), "kernel synchronize");', "stream", "device", "1"),
    "gelu": ("        gelu_kernel<<<", '        Check(aclrtSynchronizeStream(stream), "kernel synchronize");', "stream", "device", "1"),
    "dynamic_quant": ("        dynamic_quant_kernel<<<", '        Check(aclrtSynchronizeStream(stream), "kernel synchronize");', "stream", "device", "1"),
    "group_norm": ("group_norm_kernel<<<", 'C(aclrtSynchronizeStream(st),"kernel");', "st", "dev", "1"),
    "gqa": ("gqa_reorder<<<", 'C(aclrtSynchronizeStream(st),"scatter");', "st", "dev", "3 + 2 * t.B * t.Nkv"),
    "weight_quant_batch_matmul": ("if(bf16)wq_dequant_bf16<<<", 'Check(aclrtSynchronizeStream(stream),"post sync");', "stream", "dev", "3"),
}
EXTERNAL_CASES = {"gqa": "level4/gqa/cases.yaml", "weight_quant_batch_matmul": "level3/weight_quant_batch_matmul/cases.yaml"}


def instrument_text(original, operator):
    if "aprof::Run(" in original or "aprof_device_timer.h" in original:
        raise ValueError("instrumentation must start from the pristine benchmark host")
    start, finish, stream, device, launches = WRAPPERS[operator]
    if original.count(start) != 1 or original.count(finish) != 1 or original.count('#include "acl/acl.h"') != 1:
        raise ValueError(f"{operator} host changed; review its complete operator boundary before instrumenting")
    first, last = original.index(start), original.index(finish) + len(finish)
    if last <= first or "<<<" in original[:first] + original[last:]:
        raise ValueError("not all host launch sites belong to the complete operator interval")
    body = original[first:last]
    wrapped = f'\n{BEGIN}aprof::Run({stream}, {device}, "{operator}", {launches}, [&]() {{\n{body}\n}});\n{END}'
    modified = original[:first] + wrapped + original[last:]
    return modified.replace('#include "acl/acl.h"', '#include "acl/acl.h"\n#include "aprof_device_timer.h"', 1)


def check_instrumentation(tree, operator):
    text = (tree / "op_host" / f"{operator}.asc").read_text()
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.count("aprof::Run(") != 1:
        raise ValueError("candidate removed or duplicated the protected complete-operator timer")
    prefix, rest = text.split(BEGIN)
    interval, suffix = rest.split(END)
    if "<<<" in prefix + suffix or "<<<" not in interval:
        raise ValueError("kernel launches escaped the complete-operator timing interval")
    if (tree / "op_host/aprof_device_timer.h").read_bytes() != HEADER.read_bytes():
        raise ValueError("candidate changed the frozen timer header")
    expected = WRAPPERS[operator][2:]
    opening = f'aprof::Run({expected[0]}, {expected[1]}, "{operator}", {expected[2]}, [&]() {{'
    if not interval.startswith(opening):
        raise ValueError("candidate changed stream/device/launch-count timer binding")
    return {"host_launch_sites": interval.count("<<<"), "launches_per_call": expected[2],
            "scope": "all operator launches, required stage synchronization and inter-stage work; preparation and final D2H excluded"}


def check_candidate_scope(baseline, candidate, operator):
    """Conservative host-scope attestation shared by every evaluation arm."""
    for tree in (baseline, candidate):
        check_instrumentation(tree, operator)
    host = Path("op_host") / (operator + ".asc")
    old, new = (baseline / host).read_text(), (candidate / host).read_text()
    old_prefix, old_rest = old.split(BEGIN)
    new_prefix, new_rest = new.split(BEGIN)
    if old_prefix != new_prefix or old_rest.split(END)[1] != new_rest.split(END)[1]:
        raise ValueError("cannot attest full timing scope: host code outside the timed body changed")
    old_body, new_body = old_rest.split(END)[0], new_rest.split(END)[0]
    loop_headers = lambda body: re.findall(r"\b(?:for|while)\s*\([^)]*\)", body)
    if old_body.count("<<<") != new_body.count("<<<") or loop_headers(old_body) != loop_headers(new_body):
        raise ValueError("cannot attest the frozen launch multiplicity after host launch/loop restructuring")
    if (baseline / "CMakeLists.txt").read_bytes() != (candidate / "CMakeLists.txt").read_bytes():
        raise ValueError("cannot attest frozen instrumentation with changed compiler/CMake controls")
    for path in candidate.rglob("*"):
        if not path.is_file() or path.suffix not in (".asc", ".h", ".cpp") or path.relative_to(candidate) == host:
            continue
        old_path = baseline / path.relative_to(candidate)
        before = old_path.read_text() if old_path.exists() else ""
        after = path.read_text()
        if after == before:
            continue
        # Do not admit a newly introduced launch or host runtime helper in an
        # include that might be invoked before the protected timing interval.
        for token in ("<<<", "aclrt", "aclInit", "aclFinalize"):
            if after.count(token) != before.count(token):
                raise ValueError("cannot attest a host launch/runtime helper introduced outside the protected host body")
    return {"outside_host_identical": True, "compiler_controls_identical": True,
            "new_external_launch_helpers": False, "scope": "conservative static attestation; required work remains in the instrumented operator body"}


def relocate_cases(tree, operator, upstream_tasks):
    if operator not in EXTERNAL_CASES:
        return None
    source = upstream_tasks / EXTERNAL_CASES[operator]
    if not source.is_file():
        raise ValueError(f"exact upstream case specification is unavailable: {source}")
    cases = tree / "scripts/cases.py"
    original = cases.read_text()
    pattern = r"Path\(__file__\)\.resolve\(\)\.parents\[5\]\s*/\s*['\"]third_party/cann-bench/tasks/" + re.escape(EXTERNAL_CASES[operator]) + r"['\"]"
    relocated, count = re.subn(pattern, 'Path(__file__).with_name("cases.yaml")', original)
    if count != 1:
        raise ValueError("case resolver changed; refusing an unreviewed oracle relocation")
    shutil.copy2(source, tree / "scripts/cases.yaml")
    cases.write_text(relocated)
    return {"case_spec": {"path": str(source.resolve()), "sha256": sha(source)},
            "resolver_before_sha256": "sha256:" + hashlib.sha256(original.encode()).hexdigest(),
            "resolver_after_sha256": sha(cases), "change": "exact YAML copied; only its lookup path relocated"}


def case_contracts(tree):
    specification = importlib.util.spec_from_file_location("aprof_validation_cases", tree / "scripts/cases.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return [module.get_case(case_id) for case_id in range(1, 21)]


def json_contract(value):
    # Workload fingerprints must use strict JSON even for declared NaN/Inf cases.
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {key: json_contract(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_contract(item) for item in value]
    return value


def prepare(operator, destination, upstream_tasks):
    if operator not in SUPPORTED_OPERATORS:
        raise ValueError("operator is outside the frozen validation and train-control sets")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    canonical = ROOT / "scaffolding/benchmarks/cannbench/operators" / operator
    tree = destination / "baseline"
    tree.mkdir()
    # Outcome docs/results and historical profiles never enter model inputs.
    for name in ("op_host", "op_kernel", "scripts"):
        shutil.copytree(canonical / name, tree / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(canonical / "CMakeLists.txt", tree / "CMakeLists.txt")
    oracle_relocation = relocate_cases(tree, operator, upstream_tasks)
    host = tree / "op_host" / f"{operator}.asc"
    original = host.read_text()
    host.write_text(instrument_text(original, operator))
    shutil.copy2(HEADER, tree / "op_host/aprof_device_timer.h")
    patch = "".join(difflib.unified_diff(original.splitlines(True), host.read_text().splitlines(True),
                                       fromfile=f"a/op_host/{operator}.asc", tofile=f"b/op_host/{operator}.asc"))
    (destination / "instrumentation.patch").write_text(patch)
    contract = {"operator": operator, "hardware_scope": "910C/A3", "case_ids": list(range(1, 21)),
                "cases": json_contract(case_contracts(tree)), "timing": check_instrumentation(tree, operator),
                "seed_semantics": "4101/4102/4103 are order/repetition labels; original generators retain their fixed RNG seeds"}
    dump(destination / "context.json", contract)
    source_files = {p.relative_to(tree).as_posix(): sha(p) for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    preparation = {"schema_version": 1, "state": "cpu_prepared_awaiting_baseline_qualification", "operator": operator,
        "source_files": source_files, "producer_sha256": sha(Path(__file__)), "timer_sha256": sha(HEADER),
        "original_host_sha256": sha(canonical / "op_host" / f"{operator}.asc"),
        "instrumentation_patch_sha256": sha(destination / "instrumentation.patch"), "oracle_relocation": oracle_relocation,
        "hardware_executed": False, "model_executed": False, "input_generation_executed": False,
        "required_before_evaluation": ["generate and hash all declared inputs with unchanged generators",
            "baseline build and full correctness", "baseline timing/control calibration and repeat freeze",
            "source-bound baseline profiles", "accepted skill rule and frozen model/library/toolchain/evaluator"],
        "commands": {"generate_inputs": [[sys.executable, str(tree / "scripts/gen_data.py"), "--case", str(case),
                                           "--output", str(destination / "inputs")] for case in range(1, 21)],
            "configure": ["cmake", "-S", str(tree), "-B", str(destination / "baseline-build"), "-DCMAKE_BUILD_TYPE=Release"],
            "build": ["cmake", "--build", str(destination / "baseline-build"), "-j4"]}}
    dump(destination / "preparation.json", preparation)
    return preparation


def case_command(operator, binary, metadata, device, outputs):
    m = metadata
    csv = lambda value: ",".join(map(str, value))
    if operator in TRAIN_CONTROLS:
        fields = {"numel": m["numel"], "dtype": m["dtype"], "input": m["input"], "output": outputs["output"]}
        if operator == "exp":
            fields.update({name: m[name] for name in ("base", "scale", "shift")})
    elif operator == "gelu":
        fields = {"numel": m["numel"], "dtype": m["dtype"], "approximate": m["approximate"], "input": m["input"], "output": outputs["output"]}
    elif operator == "dynamic_quant":
        fields = {"shape": csv(m["shape"]), "dtype": m["dtype"], "input": m["input"], "y": outputs["output_y"], "scale": outputs["output_scale"]}
    elif operator == "group_norm":
        fields = {"shape": csv(m["shape"]), "dtype": m["dtype"], "groups": m["num_groups"], "epsilon": m["epsilon"],
                  "x": m["x"], "gamma": m["gamma"], "beta": m["beta"], "output": outputs["output"]}
    elif operator == "gqa":
        fields = {"query-shape": csv(m["query_shape"]), "key-shape": csv(m["key_shape"]), "dtype": m["dtype"],
                  "scale": m["scaleValue"], "causal": int(m["is_causal"]), "query": m["query"], "key": m["key"],
                  "value": m["value"], "output": outputs["output"]}
    elif operator == "weight_quant_batch_matmul":
        fields = {"m": m["m"], "k": m["k"], "n": m["n"], "dtype": m["dtype"][0],
                  **{name: m["paths"].get(name, "-") for name in ("x", "weight", "scale", "offset", "bias")}, "output": outputs["output"]}
    else:
        raise ValueError("unsupported validation operator")
    argv = [str(binary)]
    for key, value in fields.items():
        argv.extend(["--" + key, str(value)])
    return argv + ["--device", str(device)]


def launches_per_call(operator, metadata):
    if operator == "gqa":
        return 3 + 2 * int(metadata["query_shape"][0]) * int(metadata["key_shape"][2])
    return 3 if operator == "weight_quant_batch_matmul" else 1


def timing_config(operator, sources, binaries, prepared_inputs, destination, *, repeat, physical_device, mode="formal", case_ids=None):
    """Bind existing inputs only; neither launches commands nor creates outputs."""
    if operator not in SUPPORTED_OPERATORS or mode not in ("formal", "explore") or type(repeat) is not int or repeat < 1:
        raise ValueError("operator, collection phase and calibrated repeat count must be explicit")
    case_ids = list(range(1, 21)) if case_ids is None else list(case_ids)
    if not case_ids or len(set(case_ids)) != len(case_ids) or any(type(case) is not int or not 1 <= case <= 20 for case in case_ids):
        raise ValueError("timing cases must be a frozen subset of the declared workload")
    destination.mkdir(parents=True, exist_ok=False)
    config = {"schema_version": "2.0.0", "operator": operator, "device": 0, "physical_device": physical_device,
              "expected_case_ids": case_ids, "mode": mode, "pairs": 30 if mode == "formal" else 6,
              "warmup": 10, "repeat": repeat, "timeout_seconds": 180, "cases": []}
    for role in ("baseline", "candidate"):
        check_instrumentation(sources[role], operator)
        config[role] = {"cwd": str(sources[role]), "source_dir": str(sources[role]), "binary": str(binaries[role])}
    output_keys = ("output_y", "output_scale") if operator == "dynamic_quant" else ("output",)
    for case_id in config["expected_case_ids"]:
        metadata_path = prepared_inputs / f"case_{case_id:02d}/metadata.json"
        metadata = json.loads(metadata_path.read_text())
        paths = []

        def input_files(value, key=""):
            if key in output_keys:
                return
            if isinstance(value, dict):
                for child_key, child in value.items():
                    input_files(child, child_key)
            elif isinstance(value, str) and Path(value).is_absolute() and Path(value).is_file():
                paths.append(value)

        input_files(metadata)
        case = {"case_id": case_id, "workload": json_contract({k: v for k, v in metadata.items() if k not in output_keys}),
                "prepared_files": [str(metadata_path), *sorted(set(paths))], "epochs": []}
        for epoch in range(2):
            roles = {}
            for role in ("baseline", "candidate"):
                where = destination / f"case_{case_id:02d}" / f"epoch-{epoch}" / role
                where.mkdir(parents=True)
                outputs = {key: str(destination / "outputs" / f"case_{case_id:02d}" / f"epoch-{epoch}" / role / (key + ".bin")) for key in output_keys}
                bound = where / "metadata.json"
                # Keep special numeric values exactly as the unchanged verifier expects.
                bound.write_text(json.dumps({**metadata, **outputs}, indent=2, allow_nan=True) + "\n")
                case["prepared_files"].append(str(bound))
                roles[role] = {"command": case_command(operator, binaries[role], metadata, 0, outputs),
                              "verify_command": [sys.executable, str(sources[role] / "scripts/verify_result.py"), "--metadata", str(bound)],
                              "output_files": list(outputs.values()), "launches_per_operator": launches_per_call(operator, metadata)}
            case["epochs"].append(roles)
        config["cases"].append(case)
    dump(destination / "timing-config.json", config)
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operator", choices=SUPPORTED_OPERATORS)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--upstream-tasks", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.operator, args.destination, args.upstream_tasks.resolve()), indent=2))
