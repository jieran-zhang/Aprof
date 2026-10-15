#!/usr/bin/env python3
"""Prepare the one-attempt exp/sigmoid confirmation of the 0.5.1 timer.

Preparation and freezing are offline. Build is explicit. This script does not
launch the full confirmation campaign or infer diagnostic admission from a flag.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "skill-libs/graph-base/0.5.1"
PROFILE = Path("skills/ascendc-aprof-profiling")
OPERATORS = ("exp", "sigmoid")
LARGE_CASE = {"exp": 9, "sigmoid": 4}
PROTOCOL = "shared_buffer_acl_event_v2"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def workload_json(value):
    """Preserve non-finite descriptive metadata without invalid JSON numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        name = "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
        return {"__aprof_nonfinite_float__": name}
    if isinstance(value, list):
        return [workload_json(item) for item in value]
    if isinstance(value, dict):
        return {key: workload_json(item) for key, item in value.items()}
    return value


def strict_runtime_roundtrip(path):
    """Exercise the real CLI JSON parser in a clean candidate-runtime process."""
    program = ("import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
               "from aprof_runtime.profile_evidence import _json; p=Path(sys.argv[2]); "
               "value=_json(p.read_text()); assert _json(json.dumps(value,allow_nan=False))==value")
    result = subprocess.run([sys.executable, "-I", "-c", program, str(RELEASE / "runtime/src"), str(path)],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError("strict runtime JSON roundtrip failed: " + result.stderr[-3000:])


def exact(text, before, after):
    if text.count(before) != 1:
        raise ValueError("mechanical patch anchor must occur exactly once: " + before[:80])
    return text.replace(before, after, 1)


def adapt_host(text, operator):
    if operator not in OPERATORS:
        raise ValueError("unsupported operator")
    text = exact(text, '#include "aprof_device_timer.h"', '#include "device_shared_timing.h"')
    before = f'''        aprof::Run(stream, device, "{operator}", 1, [&]() {{
        {operator}_kernel<<<tiling.blockNum, nullptr, stream>>>(
            static_cast<uint8_t *>(devIn), static_cast<uint8_t *>(devOut), static_cast<uint8_t *>(devTiling));
        }});'''
    after = f'''        // A/A method qualification: both named callbacks invoke the unchanged baseline kernel.
        const char *cycle_text = std::getenv("APROF_SHARED_CYCLE");
        if (!cycle_text || std::string(cycle_text).size() != 1 || cycle_text[0] < '0' || cycle_text[0] > '5')
            throw std::invalid_argument("APROF_SHARED_CYCLE must be 0..5");
        const std::string baseline_output = Arg(argc, argv, "--baseline-output");
        const std::string candidate_output = Arg(argc, argv, "--candidate-output");
        if (baseline_output.empty() || candidate_output.empty() || baseline_output == candidate_output)
            throw std::invalid_argument("distinct callback output paths are required");
        const aprof::SharedBuffers buffers{{
            {{{{"input", devIn, bytes}}, {{"tiling", devTiling, sizeof(tiling)}}}},
            {{{{"output", devOut, bytes}}}}, {{}}
        }};
        auto launch_baseline = [&](aclrtStream selected_stream, const aprof::SharedBuffers &shared) {{
            {operator}_kernel<<<tiling.blockNum, nullptr, selected_stream>>>(
                static_cast<uint8_t *>(shared.inputs[0].data), static_cast<uint8_t *>(shared.outputs[0].data),
                static_cast<uint8_t *>(shared.inputs[1].data));
        }};
        auto launch_candidate = [&](aclrtStream selected_stream, const aprof::SharedBuffers &shared) {{
            {operator}_kernel<<<tiling.blockNum, nullptr, selected_stream>>>(
                static_cast<uint8_t *>(shared.inputs[0].data), static_cast<uint8_t *>(shared.outputs[0].data),
                static_cast<uint8_t *>(shared.inputs[1].data));
        }};
        auto snapshot = [&](const char *role, aclrtStream, const aprof::SharedBuffers &shared) {{
            const std::string path = std::string(role) == "baseline" ? baseline_output : candidate_output;
            Check(aclrtMemcpy(hostOut, bytes, shared.outputs[0].data, bytes, ACL_MEMCPY_DEVICE_TO_HOST),
                  "D2H independent callback output");
            if (!WriteFile(path, hostOut, bytes)) throw std::runtime_error("write callback output failed");
        }};
        aprof::RunShared(stream, "{operator}", cycle_text[0] - '0', 1, 1, buffers,
                         {{"launch_baseline", "launch_candidate"}}, launch_baseline, launch_candidate, snapshot);'''
    return exact(text, before, after)


def adapt_oracle(text, operator):
    """Change only CLI output/result routing; preserve the actual oracle code."""
    if operator == "exp":
        text = exact(text,
            "p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args()",
            "p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); "
            "p.add_argument('--output',required=True); p.add_argument('--result',required=True); a=p.parse_args()")
        text = exact(text, "open(m['output'],'rb')", "open(a.output,'rb')")
        return exact(text, "(mp.parent/'result.json').write_text", "Path(a.result).write_text")
    if operator == "sigmoid":
        text = exact(text, '    parser.add_argument("--metadata", required=True)',
            '    parser.add_argument("--metadata", required=True)\n'
            '    parser.add_argument("--output", required=True)\n'
            '    parser.add_argument("--result", required=True)')
        text = exact(text, 'open(metadata["output"], "rb")', 'open(args.output, "rb")')
        return exact(text, '(metadata_path.parent / "result.json").write_text', 'Path(args.result).write_text')
    raise ValueError("unsupported operator")


def source_files(source):
    source = Path(source)
    paths = [source / "CMakeLists.txt"]
    for folder in ("op_host", "op_kernel", "scripts"):
        paths.extend(p for p in (source / folder).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError("regular source files required: " + str(path))
    return {str(path.relative_to(source)): sha(path) for path in sorted(paths)}


def role_source_files(source):
    """Match the collector's full source bundle, including noncompiled provenance."""
    root = Path(source)
    excluded = {".git", ".aprof", "build", "__pycache__", ".pytest_cache"}
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in excluded)
        for name in dirs + names:
            if (Path(directory) / name).is_symlink():
                raise ValueError("source snapshots cannot contain symlinks")
        for name in sorted(names):
            path = Path(directory) / name
            if path.stat().st_size > 100 * 1024 * 1024:
                raise ValueError("source file exceeds collector's 100 MiB limit")
            files[str(path.relative_to(root))] = sha(path)
    return files


def verify_files(bindings):
    for filename, digest in bindings.items():
        path = Path(filename)
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise ValueError("frozen file changed: " + filename)


def protocol_commands():
    result = []
    for phase in ("aa_before", "formal", "aa_after"):
        result.append(f"prime {len(result)} {phase}")
        for pair in range(5):
            result.append(f"pair {len(result)} {phase} {pair}")
    result.append(f"finish {len(result)}")
    return result


def prepare(round2, output, diagnostic_anchor, method_transition=None):
    round2, output = Path(round2).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise FileExistsError("qualification plan already exists: " + str(output))
    output.mkdir(parents=True)
    header = RELEASE / PROFILE / "assets/device_shared_timing.h"
    plan = {"schema_version": "1.0.0", "protocol": PROTOCOL,
            "purpose": "independent_measurement_method_confirmation",
            "created_at": time.time(), "operators": {},
            "attempt_policy": "one_attempt_per_operator_no_resume_no_resampling",
            "failure_policy": "stop_failed_operator_preserve_costs_and_judge_both_operators",
            "diagnostic_anchor": str(Path(diagnostic_anchor).resolve(strict=True)),
            "diagnostic_admission": "replay_diagnosis_before_build_and_freeze",
            "cycles": 6, "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100,
            "repeat_source": "one_baseline_calibration_per_case",
            "controls": {"maximum_role_bias": 0.02, "maximum_cv": 0.05,
                         "maximum_before_after_shift": 0.02, "scope": "every_case_global_and_each_cycle"},
            "frozen_files": {str(Path(__file__).resolve()): sha(__file__), str(header): sha(header)}}
    plan["frozen_files"][plan["diagnostic_anchor"]] = sha(plan["diagnostic_anchor"])
    if method_transition is not None:
        from run_shared_timing_confirmation import binding
        from replay_measurement_transition import replay_transition
        plan["method_transition"] = binding(method_transition)
        plan["method_transition_admission"] = replay_transition(plan["method_transition"], qualification_dir=output)
        plan["frozen_files"][plan["method_transition"]["path"]] = sha(method_transition)
    for operator in OPERATORS:
        original = round2 / operator / "baseline"
        destination = output / operator / "source"
        before_files = source_files(original)
        role_files = role_source_files(original)
        destination.mkdir(parents=True)
        for relative in before_files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / relative, target)
        patches = {}
        for relative, adapter in ((f"op_host/{operator}.asc", adapt_host),
                                  ("scripts/verify_result.py", adapt_oracle)):
            before = (original / relative).read_text()
            after = adapter(before, operator)
            (destination / relative).write_text(after)
            patches[relative] = {"before_sha256": before_files[relative], "after_sha256": sha(destination / relative),
                "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                    fromfile="original/" + relative, tofile="adapted/" + relative))}
        shutil.copyfile(header, destination / "op_host/device_shared_timing.h")
        after_files = source_files(destination)
        unchanged = set(before_files) - set(patches)
        if any(after_files[p] != before_files[p] for p in unchanged):
            raise ValueError("mechanical adaptation changed a protected source")
        proof = {"operator": operator, "purpose": "AA_identical_baseline_kernel",
            "original_source": str(original), "adapted_source": str(destination),
            "original_files": before_files, "original_role_files": role_files,
            "adapted_files": after_files, "patches": patches,
            "unchanged_files": sorted(unchanged), "new_files": {"op_host/device_shared_timing.h": sha(header)},
            "roles": {"baseline": {"symbol": "launch_baseline", "implementation": "original_baseline"},
                      "candidate": {"symbol": "launch_candidate", "implementation": "original_baseline"}},
            "limits": "Mechanical instrumentation attestation; independent hardware confirmation is still required."}
        proof_path = output / operator / "source-review.json"
        save_new(proof_path, proof)
        cases = []
        for case_id in range(1, 21):
            metadata_path = round2 / operator / "prepared" / f"case_{case_id:02d}" / "metadata.json"
            metadata = read(metadata_path)
            if metadata["case_id"] != case_id:
                raise ValueError("prepared case ID mismatch")
            input_path = Path(metadata["input"]).resolve(strict=True)
            if input_path.stat().st_size != metadata["numel"] * (4 if metadata["dtype"] == "float32" else 2):
                raise ValueError("prepared input byte length mismatch")
            plan["frozen_files"].update({str(metadata_path): sha(metadata_path), str(input_path): sha(input_path)})
            cases.append({"case_id": case_id, "metadata": str(metadata_path), "input": str(input_path),
                          "workload": workload_json({k: v for k, v in metadata.items() if k not in {"input", "output"}})})
        for base, inventory in ((original, role_files), (destination, after_files)):
            plan["frozen_files"].update({str(base / p): digest for p, digest in inventory.items()})
        plan["frozen_files"][str(proof_path)] = sha(proof_path)
        plan["operators"][operator] = {"original_source": str(original), "source": str(destination),
            "source_review": str(proof_path), "cases": cases,
            "confirmation_output": str(output / operator / "confirmation"), "max_attempts": 1,
            "timeline": {"case_ids": [1, LARGE_CASE[operator]], "cycles_per_case": 1, "cycle_index": 0,
                "expected_kernel_tasks_formula": "1222+30*R", "repeat_source": "completed_confirmation_registration",
                "expected_event_samples": 30,
                "command_sequence": protocol_commands(), "included_in_formal_timing": False}}
    save_new(output / "plan.json", plan)
    strict_runtime_roundtrip(output / "plan.json")
    return plan


def load_plan(output):
    output = Path(output).resolve(strict=True)
    plan = read(output / "plan.json")
    if tuple(sorted(plan["operators"])) != OPERATORS or plan["protocol"] != PROTOCOL:
        raise ValueError("wrong qualification plan")
    verify_files(plan["frozen_files"])
    for operator in OPERATORS:
        item = plan["operators"][operator]
        proof = read(item["source_review"])
        if source_files(item["original_source"]) != proof["original_files"] or role_source_files(item["source"]) != proof["adapted_files"]:
            raise ValueError("source inventory changed")
        if role_source_files(item["original_source"]) != proof["original_role_files"]:
            raise ValueError("original role source bundle changed")
    return output, plan


def diagnostic_admission(plan):
    # This recomputes original diagnostic evidence; a caller-supplied summary is insufficient.
    from replay_timing_diagnosis import replay_diagnosis
    anchor = Path(plan["diagnostic_anchor"])
    report = replay_diagnosis(anchor)
    if report.get("shared_buffer_entry_qualified") is not True:
        raise ValueError("independent shared-buffer diagnostic replay did not qualify entry")
    from replay_measurement_transition import replay_transition
    if "method_transition" not in plan:
        raise ValueError("prospective duration-method transition is required before build")
    if replay_transition(plan["method_transition"]) != plan["method_transition_admission"]:
        raise ValueError("measurement-method transition evidence changed")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"anchor": str(anchor), "anchor_sha256": sha(anchor), "replay": report,
            "replay_sha256": hashlib.sha256(canonical).hexdigest()}


def build(output, operator):
    output, plan = load_plan(output)
    if operator not in OPERATORS:
        raise ValueError("unknown operator")
    item = plan["operators"][operator]
    source = Path(item["source"])
    receipt_path = output / operator / "build-receipt.json"
    receipt = {"schema_version": "1.0.0", "operator": operator, "plan_sha256": sha(output / "plan.json"),
               "source_review_sha256": sha(item["source_review"]), "started_at": time.time(),
               "environment": {k: os.environ.get(k) for k in ("PATH", "ASCEND_HOME_PATH", "ASCEND_OPP_PATH", "LD_LIBRARY_PATH")},
               "commands": [], "status": "started"}
    save_new(output / operator / "build-started.json", receipt)
    try:
        receipt["diagnostic_admission"] = diagnostic_admission(plan)
        for index, command in enumerate((
            ["cmake", "-S", str(source), "-B", str(source / "build"), "-DCMAKE_BUILD_TYPE=Release"],
            ["cmake", "--build", str(source / "build"), "-j2"],
        )):
            log_path = output / operator / f"build-{index}.log"
            execution = {"argv": command, "cwd": str(source), "started_at": time.time()}
            receipt["commands"].append(execution)
            with log_path.open("xb") as log:
                result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            execution.update(exit_status=result.returncode, finished_at=time.time(), log=str(log_path), log_sha256=sha(log_path))
            if result.returncode:
                raise RuntimeError("build command failed")
        load_plan(output)
        binary = source / "build" / operator
        if not binary.is_file() or binary.is_symlink():
            raise ValueError("expected executable absent")
        receipt.update(status="passed", binary=str(binary), binary_sha256=sha(binary))
    except BaseException as error:
        receipt.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        receipt["finished_at"] = time.time()
        save_new(receipt_path, receipt)
    return receipt


def make_config(plan, output, operator, device, physical_device):
    item = plan["operators"][operator]
    source = Path(item["source"])
    binary = str(source / "build" / operator)
    cases = []
    for item_case in item["cases"]:
        metadata = read(item_case["metadata"])
        command = [binary, "--numel", str(metadata["numel"]), "--dtype", metadata["dtype"],
                   "--input", item_case["input"], "--device", str(device),
                   "--baseline-output", "{cycle_dir}/baseline.bin", "--candidate-output", "{cycle_dir}/candidate.bin",
                   "--output", "{cycle_dir}/final.bin"]
        if operator == "exp":
            for key in ("base", "scale", "shift"):
                command += ["--" + key, str(metadata[key])]
        cases.append({"case_id": item_case["case_id"], "workload": item_case["workload"],
            "prepared_files": [item_case["metadata"], item_case["input"]], "command": command,
            "verify_commands": {role: [str(Path(sys.executable).resolve(strict=True)), str(source / "scripts/verify_result.py"),
                "--metadata", item_case["metadata"], "--output", "{cycle_dir}/" + role + ".bin",
                "--result", "{cycle_dir}/" + role + "-result.json"] for role in ("baseline", "candidate")},
            "output_files": {role: ["{cycle_dir}/" + role + ".bin"] for role in ("baseline", "candidate")}})
    return {"schema_version": "1.0.0", "operator": operator,
        "run_id": output.name, "session_id": output.name + "-" + operator,
        "candidate_id": operator + "-identical-baseline-aa", "device": device, "physical_device": physical_device,
        "expected_case_ids": list(range(1, 21)),
        "roles": {role: {"source_dir": item["original_source"], "symbol": "launch_" + role,
                         "launches_per_operator": 1} for role in ("baseline", "candidate")},
        "build": {"source_dir": str(source), "binary": binary,
                  "receipt_files": [str(output / operator / "build-receipt.json"), item["source_review"], str(output / "plan.json")]},
        "cases": cases}


def freeze(output, device=0, physical_device=0):
    output, plan = load_plan(output)
    if (output / "freeze.json").exists():
        raise FileExistsError("freeze already exists")
    admission = diagnostic_admission(plan)
    files = {str(output / "plan.json"): sha(output / "plan.json")}
    configs = {}
    for operator in OPERATORS:
        receipt_path = output / operator / "build-receipt.json"
        receipt = read(receipt_path)
        if (receipt["status"] != "passed" or receipt["plan_sha256"] != files[str(output / "plan.json")]
                or sha(receipt["binary"]) != receipt["binary_sha256"]):
            raise ValueError("both immutable successful builds are required")
        files[str(receipt_path)] = sha(receipt_path)
        files[receipt["binary"]] = receipt["binary_sha256"]
        for command in receipt["commands"]:
            files[command["log"]] = command["log_sha256"]
        config_path = output / operator / "config.json"
        save_new(config_path, make_config(plan, output, operator, device, physical_device))
        strict_runtime_roundtrip(config_path)
        files[str(config_path)] = sha(config_path)
        configs[operator] = str(config_path)
    collector = RELEASE / PROFILE / "scripts/device_shared_timing.py"
    assignments = [node for node in ast.parse(collector.read_text()).body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PRODUCERS" for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError("collector must declare exactly one literal producer inventory")
    producer_paths = [RELEASE / relative for relative in ast.literal_eval(assignments[0].value)]
    producer_paths.append(Path(__file__).with_name("replay_timing_diagnosis.py"))
    producer_paths.append(Path(__file__).with_name("run_shared_timing_confirmation.py"))
    producer_paths.append(ROOT / "scaffolding/tools/verify_measurement_publication.py")
    producer_paths.extend(Path(__file__).with_name(name) for name in (
        "measurement_source_archive.py", "replay_measurement_transition.py", "run_event_duration_study.py"))
    files.update({str(p): sha(p) for p in producer_paths})
    timeline = {"protocol": PROTOCOL, "included_in_formal_timing": False, "runs": []}
    for operator in OPERATORS:
        for case_id in plan["operators"][operator]["timeline"]["case_ids"]:
            directory = output / operator / f"timeline-case-{case_id:02d}"
            command_file = output / "timeline-commands" / f"{operator}-{case_id:02d}.txt"
            command_file.parent.mkdir(exist_ok=True)
            with command_file.open("x") as stream:
                stream.write("\n".join(protocol_commands()) + "\n")
            files[str(command_file)] = sha(command_file)
            case = next(c for c in read(configs[operator])["cases"] if c["case_id"] == case_id)
            timeline["runs"].append({"operator": operator, "case_id": case_id, "cycle_index": 0,
                "max_attempts": 1, "expected_kernel_tasks_formula": "1222+30*R", "expected_event_samples": 30,
                "repeat_source": "completed_confirmation_registration",
                "application": [token.replace("{cycle_dir}", str(directory)) for token in case["command"]],
                "command_file": {"path": str(command_file), "sha256": files[str(command_file)]},
                "environment": {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": "0", "APROF_SHARED_COMMANDS": str(command_file),
                                "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "{confirmation_repeat}"},
                "output": str(directory),
                "requirements": ["export all 1222+30*R kernel task timestamps", "match each ACL event to its frozen R ordered kernel tasks",
                    "report each task sum and first-start to last-end span", "never merge profiler timing into formal samples"]})
    timeline_path = output / "timeline-plan.json"
    save_new(timeline_path, timeline)
    files[str(timeline_path)] = sha(timeline_path)
    verify_files(files)
    result = {"schema_version": "1.0.0", "created_at": time.time(), "plan_sha256": sha(output / "plan.json"),
              "frozen_files": files, "configs": configs, "accepted": False,
              "diagnostic_admission": admission,
              "status": "diagnostic_qualified_ready_for_one_attempt_confirmation",
              "authority": "freeze_only_not_hardware_or_publication_acceptance"}
    save_new(output / "freeze.json", result)
    strict_runtime_roundtrip(output / "freeze.json")
    return result


def timeline_driver(output, operator, case_id):
    """Dedicated msprof application; production header, one complete cycle.

    The external profiling controller owns the device lock and trace export.
    This receipt alone cannot qualify a timeline or the measurement method.
    """
    output, plan = load_plan(output)
    frozen = read(output / "freeze.json")
    verify_files(frozen["frozen_files"])
    if operator not in OPERATORS or case_id not in plan["operators"][operator]["timeline"]["case_ids"]:
        raise ValueError("timeline workload was not preregistered")
    config = read(frozen["configs"][operator])
    case = next(c for c in config["cases"] if c["case_id"] == case_id)
    directory = output / operator / f"timeline-case-{case_id:02d}"
    directory.mkdir(exist_ok=False)
    expand = lambda argv: [token.replace("{cycle_dir}", str(directory)) for token in argv]
    env = {key: value for key, value in os.environ.items() if not key.startswith("APROF_")}
    from run_shared_timing_confirmation import confirmation_repeat
    repeat = confirmation_repeat(output, operator, case_id)
    env.update(APROF_SHARED_CYCLE="0", APROF_SHARED_TIMING="1", APROF_SHARED_MODE="confirmation",
               APROF_SHARED_REPEAT=str(repeat))
    command = expand(case["command"])
    receipt = {"purpose": "timeline_only_not_formal_samples", "operator": operator, "case_id": case_id,
        "started_at": time.time(), "freeze_sha256": sha(output / "freeze.json"), "argv": command,
        "binary_sha256": sha(command[0]), "commands": protocol_commands(), "verifications": {},
        "repeat": repeat, "accepted": False, "status": "started", "requires_external_trace_review": True}
    save_new(directory / "started.json", receipt)
    try:
        with (directory / "stdout.log").open("xb") as log:
            result = subprocess.run(command, cwd=config["build"]["source_dir"], env=env,
                input=("\n".join(protocol_commands()) + "\n").encode(), stdout=log, stderr=subprocess.STDOUT, timeout=900)
        receipt["exit_status"] = result.returncode
        if result.returncode:
            raise ValueError("timeline native process failed")
        prefix = "APROF_SHARED_TIMING_JSON:"
        messages = [json.loads(line[len(prefix):]) for line in (directory / "stdout.log").read_text().splitlines()
                    if line.startswith(prefix)]
        expected_kinds = ["ready"] + ["prime" if c.startswith("prime") else "pair" if c.startswith("pair") else "complete"
                                      for c in protocol_commands()]
        if [m.get("kind") for m in messages] != expected_kinds:
            raise ValueError("timeline native transcript is incomplete")
        if (any(m.get("protocol") != PROTOCOL or m.get("operator") != operator or m.get("cycle_index") != 0 for m in messages)
                or [m.get("command_index") for m in messages[1:]] != list(range(19))
                or messages[-1].get("input_bytes_unchanged") is not True):
            raise ValueError("timeline native identity or command order differs")
        receipt["messages"] = messages
        for role in ("baseline", "candidate"):
            binary_output = directory / (role + ".bin")
            if not binary_output.is_file() or binary_output.is_symlink():
                raise ValueError("callback snapshot missing")
            output_hash = sha(binary_output)
            command = expand(case["verify_commands"][role])
            started = time.time()
            log_path = directory / (role + "-verify.log")
            with log_path.open("xb") as log:
                result = subprocess.run(command, cwd=config["build"]["source_dir"], stdout=log, stderr=subprocess.STDOUT, timeout=180)
            receipt["verifications"][role] = {"argv": command, "started_at": started, "finished_at": time.time(),
                "exit_status": result.returncode, "output_sha256": output_hash, "log_sha256": sha(log_path)}
            if result.returncode or sha(binary_output) != output_hash:
                raise ValueError("timeline callback oracle failed or modified output")
        load_plan(output)
        verify_files(frozen["frozen_files"])
        receipt["status"] = "native_complete_pending_external_trace_review"
    except BaseException as error:
        receipt.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        receipt["finished_at"] = time.time()
        if (directory / "stdout.log").is_file():
            receipt["stdout_sha256"] = sha(directory / "stdout.log")
        save_new(directory / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--round2", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--diagnostic-anchor", type=Path, required=True)
    prepare_parser.add_argument("--method-transition", type=Path, required=True,
                                help="root-registered method change with retained failures and duration study")
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--operator", choices=OPERATORS, required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--output", type=Path, required=True)
    freeze_parser.add_argument("--device", type=int, default=0)
    freeze_parser.add_argument("--physical-device", type=int, default=0)
    timeline_parser = sub.add_parser("timeline-driver")
    timeline_parser.add_argument("--output", type=Path, required=True)
    timeline_parser.add_argument("--operator", choices=OPERATORS, required=True)
    timeline_parser.add_argument("--case-id", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        value = prepare(args.round2, args.output, args.diagnostic_anchor, args.method_transition)
    elif args.command == "build":
        value = build(args.output, args.operator)
    elif args.command == "freeze":
        value = freeze(args.output, args.device, args.physical_device)
    else:
        value = timeline_driver(args.output, args.operator, args.case_id)
    print(json.dumps({"command": args.command, "output": str(args.output), "accepted": False,
                      "operators": list(value.get("operators", {}))}))


if __name__ == "__main__":
    main()
