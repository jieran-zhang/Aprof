#!/usr/bin/env python3
"""Trusted one-candidate controller and baseline qualification for five operators.

This module is inert on import. Both CLI commands execute hardware work. The
release runner must freeze this file, its task plans and baseline receipts before
using ``evaluate``; source preparation alone is never an execution receipt.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from run_aprof_job import dump, sha
from validation_operator_adapter import (OPERATORS, TRAIN_CONTROLS, SUPPORTED_OPERATORS, case_command, check_instrumentation, check_candidate_scope,
                                         json_contract, timing_config)


def read(path):
    return json.loads(Path(path).read_text())


def ref(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(Path(path))}


def checked(value):
    path = Path(value["path"]).resolve(strict=True)
    if sha(path) != value["sha256"]:
        raise ValueError(f"frozen evaluator input changed: {path}")
    return path


def imports(release):
    sys.path[:0] = [str(release / "runtime/src"), str(release / "skills/ascendc-aprof-profiling/scripts")]
    import aprof_runtime
    if Path(aprof_runtime.__file__).resolve().parent != (release / "runtime/src/aprof_runtime").resolve():
        raise ValueError("controller requires the frozen candidate runtime in a fresh process")
    import device_paired_timing_v2 as timing
    import profile_capture as profiler
    from aprof_runtime.exploration import ExplorationGate, freeze_exploration_manifest, verify_exploration
    from aprof_runtime.profile_evidence import load_capture_manifest, normalize_profile
    from aprof_runtime.store import EpisodeStore
    from aprof_runtime.traces import TraceWriter, make_optimization_trace, register_json_artifact, validate_optimization_trace
    from normalize_profile import expand_specs
    return locals()


def prepare_task(preparation, prepared_inputs, release, profile, repeat, physical_device, destination, admitted_parameters=None):
    """Freeze already-generated inputs and CPU-only plan metadata, without launch."""
    api = imports(release)
    prepared = read(preparation / "preparation.json")
    if prepared["state"] != "cpu_prepared_awaiting_baseline_qualification":
        raise ValueError("source preparation must precede task freeze")
    destination.mkdir(parents=True, exist_ok=False)
    source = preparation / "baseline"
    dump(destination / "source-inventory.json", api["profiler"].source_inventory(source))
    dump(destination / "input-inventory.json", inputs_inventory(prepared_inputs))
    context = read(preparation / "context.json")
    context["profile"] = profile
    context["publication_source_scope"] = {"admitted_parameters": admitted_parameters or [],
        "rule": "automatic production scope requires only these independently predeclared integer tiling/buffer edits; arithmetic, precision, branches and dynamic tails must remain byte-identical; broader edits require independent source review"}
    dump(destination / "context.json", context)
    plan = dict(schema_version=1, operator=prepared["operator"], split="train" if prepared["operator"] in TRAIN_CONTROLS else "validation",
        case_ids=list(range(1, 21)), release=str(release.resolve()),
        baseline_source=str(source.resolve()), prepared_inputs=str(prepared_inputs.resolve()),
        source_inventory=ref(destination / "source-inventory.json"), input_inventory=ref(destination / "input-inventory.json"),
        repeat=repeat, physical_device=physical_device, profile=profile,
        control_case_ids=[1, 3, 8, 14, 16, 20], timing_protocol="two-epoch-symmetric-prime-v2",
        admitted_parameters=admitted_parameters or [],
        cpu_reference_environment={key: "32" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
        preparation_receipt=ref(preparation / "preparation.json"), context=ref(destination / "context.json"))
    dump(destination / "task-plan.json", plan)
    return plan


def inputs_inventory(directory):
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("prepared input symlinks are not admitted")
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = sha(path)
    if not files:
        raise ValueError("all declared inputs must be prepared before qualification")
    return files


def validate_plan(plan, api):
    if (plan.get("schema_version") != 1 or plan.get("operator") not in SUPPORTED_OPERATORS
            or plan.get("case_ids") != list(range(1, 21))):
        raise ValueError("task plan must bind the complete declared validation or train-control workload")
    if plan.get("split") != ("train" if plan["operator"] in TRAIN_CONTROLS else "validation"):
        raise ValueError("controller task split disagrees with the frozen operator membership")
    if (plan.get("timing_protocol") != "two-epoch-symmetric-prime-v2"
            or plan.get("control_case_ids") != [1, 3, 8, 14, 16, 20]):
        raise ValueError("controller timing controls differ from the preregistered protocol")
    if type(plan.get("repeat")) is not int or not 1 <= plan["repeat"] <= 1000000:
        raise ValueError("a calibrated and frozen repeat count is required")
    if type(plan.get("physical_device")) is not int or not 0 <= plan["physical_device"] < 16:
        raise ValueError("physical device mapping is required")
    if str(plan["physical_device"]) != os.environ.get("ASCEND_RT_VISIBLE_DEVICES"):
        raise ValueError("launch with the frozen physical device visible as logical device zero")
    if any(name in os.environ for name in ("APROF_TIMING", "APROF_TIMING_INTERACTIVE", "APROF_TIMING_V2",
            "APROF_CAPTURE_REPLAY", "APROF_WARMUP", "APROF_REPEAT", "APROF_PRIME_REPEAT", "APROF_SAMPLES")):
        raise ValueError("inherited timing/capture controls are not allowed")
    if not isinstance(plan.get("profile"), dict) or plan["profile"].get("case_id") not in plan["case_ids"]:
        raise ValueError("profile sentinel must be frozen before candidate construction")
    profile = plan["profile"]
    if not profile.get("kernels") or not profile.get("metrics"):
        raise ValueError("named-kernel and metric choices must be frozen in the task context")
    if any(not isinstance(kernel, str) or not kernel or kernel == "*" for kernel in profile["kernels"]):
        raise ValueError("profiling requires concrete named kernels")
    for name, spec in profile["metrics"].items():
        if (not isinstance(name, str) or not name or set(spec) != {"unit", "file", "format", "field", "row_aggregation", "aggregation"}
                or spec["format"] != "csv" or spec["row_aggregation"] != "median" or spec["aggregation"] != "median"):
            raise ValueError("metrics require exact frozen CSV cells and median reducers")
    source = Path(plan["baseline_source"]).resolve(strict=True)
    check_instrumentation(source, plan["operator"])
    expected_source = read(checked(plan["source_inventory"]))
    if api["profiler"].source_inventory(source) != expected_source:
        raise ValueError("qualified baseline source changed")
    expected_inputs = read(checked(plan["input_inventory"]))
    prepared = Path(plan["prepared_inputs"]).resolve(strict=True)
    if inputs_inventory(prepared) != expected_inputs:
        raise ValueError("shared frozen workload inputs changed")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        if str(plan["cpu_reference_environment"][name]) != os.environ.get(name):
            raise ValueError("CPU oracle thread environment differs from the frozen task")
    return source, prepared


def _checked_seconds(seconds):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds:
        raise ValueError("controller seconds must be finite and positive")
    return seconds


def _inherited_deadline(started, seconds):
    seconds = _checked_seconds(seconds)
    launch_path = os.environ.get('APROF_TASK_LAUNCH_PATH')
    if launch_path:
        from evaluate_skill_release import _load_launch
        path = Path(launch_path)
        launch, _ = _load_launch(path.parents[2], path.parent.name, path,
                                 os.environ['APROF_TASK_LAUNCH_SHA256'])
        deadline = float(os.environ['APROF_TASK_DEADLINE_MONOTONIC'])
        if (deadline != launch['deadline_monotonic'] or seconds > launch['child_timeout_seconds']
                or deadline <= started):
            raise ValueError('controller changed or exhausted the original parent allowance')
        return deadline
    # Preserve only the old standalone <=3600 entry; larger tasks need a parent.
    if seconds > 3600:
        raise ValueError('larger standalone budget requires the original dispatcher launch')
    return started + seconds


class Commands:
    def __init__(self, directory, deadline):
        self.directory, self.deadline = directory, deadline
        self.executions = []

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 1:
            raise TimeoutError("controller exhausted its wall-time budget")
        return seconds

    def run(self, label, argv, cwd, *, timeout=600, environment=None):
        directory = self.directory / label
        directory.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        process, error = None, None
        try:
            with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
                process = subprocess.Popen([str(x) for x in argv], cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True, env=environment)
                process.wait(timeout=min(timeout, self.remaining()))
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            receipt = {"argv": [str(x) for x in argv], "cwd": str(cwd), "duration_seconds": time.monotonic() - started,
                       "exit_status": None if process is None else process.returncode, "error": error,
                       "stdout": ref(directory / "stdout.log"), "stderr": ref(directory / "stderr.log")}
            if environment is not None:
                receipt["environment"] = dict(environment)
            dump(directory / "execution.json", receipt)
            self.executions.append(ref(directory / "execution.json"))
        return receipt


def build(source, destination, commands, operator):
    configure = commands.run("configure", ["cmake", "-S", source, "-B", destination, "-DCMAKE_BUILD_TYPE=Release"], source)
    if configure["exit_status"] != 0 or configure["error"]:
        raise RuntimeError("candidate CMake configure failed")
    compile_result = commands.run("build", ["cmake", "--build", destination, "-j4"], source)
    if compile_result["exit_status"] != 0 or compile_result["error"]:
        raise RuntimeError("candidate build failed")
    binary = destination / operator
    if not binary.is_file():
        raise RuntimeError("build did not produce the declared operator binary")
    return binary


def correctness(operator, source, binary, prepared, destination, commands, timing, physical_device):
    rows = []
    keys = ("output_y", "output_scale") if operator == "dynamic_quant" else ("output",)
    with timing.device_lock(physical_device, min(180, commands.remaining())):
        for case_id in range(1, 21):
            directory = destination / f"case_{case_id:02d}"
            directory.mkdir(parents=True)
            metadata = read(prepared / f"case_{case_id:02d}/metadata.json")
            outputs = {key: str(directory / (key + ".bin")) for key in keys}
            bound = directory / "metadata.json"
            bound.write_text(json.dumps({**metadata, **outputs}, allow_nan=True, indent=2) + "\n")
            execution = commands.run(f"correctness/{case_id:02d}/kernel", case_command(operator, binary, metadata, 0, outputs), source, timeout=180)
            verification = None
            if execution["exit_status"] == 0 and not execution["error"]:
                verification = commands.run(f"correctness/{case_id:02d}/verify", [sys.executable, source / "scripts/verify_result.py", "--metadata", bound], source, timeout=300)
            result = directory / "result.json"
            passed = bool(verification and verification["exit_status"] == 0 and not verification["error"]
                          and result.is_file() and read(result).get("passed") is True)
            rows.append({"case_id": case_id, "correct": passed, "metadata": ref(bound),
                         "verification": ref(result) if result.is_file() else None,
                         "outputs": [ref(Path(path)) for path in outputs.values() if Path(path).is_file()],
                         "kernel_execution": commands.executions[-2 if verification else -1],
                         "verifier_execution": commands.executions[-1] if verification else None})
            dump(destination / "report.json", {"case_ids": list(range(1, 21)), "rows": rows, "complete": len(rows) == 20})
            if commands.deadline - time.monotonic() <= 1:
                raise TimeoutError("correctness stage exhausted the controller budget")
    return rows


def verify_correctness_report(reference):
    report = read(checked(reference))
    if report.get("case_ids") != list(range(1, 21)) or not report.get("complete") or [row["case_id"] for row in report["rows"]] != list(range(1, 21)):
        raise ValueError("baseline full correctness report is incomplete")
    for row in report["rows"]:
        checked(row["metadata"])
        result = read(checked(row["verification"]))
        if row["correct"] is not True or result.get("passed") is not True:
            raise ValueError("baseline correctness failed")
        for key in ("kernel_execution", "verifier_execution"):
            execution = read(checked(row[key]))
            if execution["exit_status"] != 0 or execution["error"]:
                raise ValueError("baseline correctness execution failed")
            stdout = checked(execution["stdout"])
            checked(execution["stderr"])
            if key == "verifier_execution":
                emitted = []
                for line in stdout.read_text().splitlines():
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict) and "passed" in value:
                        emitted.append(value)
                if emitted != [result]:
                    raise ValueError("baseline correctness JSON differs from actual verifier stdout")
        for output in row["outputs"]:
            checked(output)
    return report


def aa_verdict(report):
    rows = []
    for case in report["per_case"]:
        bias = abs(1 / case["speedup"] - 1) if case["speedup"] else None
        rows.append({"case_id": case["case_id"], "role_bias": bias,
                     "passed": bias is not None and bias <= 0.02 and max(case["baseline_cv"], case["candidate_cv"]) <= 0.05})
    return {"passed": report["stable"] and len(rows) == 20 and all(row["passed"] for row in rows),
            "rows": rows, "max_role_bias": 0.02, "max_cv": 0.05, "resampling": "none"}


def verify_timing_raw(raw, config, report, sources, api):
    """Replay raw sample/log/source bindings, without running a command."""
    from aprof_runtime.jsonio import content_hash
    if (not raw.get("complete") or raw["config_hash"] != content_hash(config)
            or raw["producer_hash"] != sha(Path(api["timing"].__file__))
            or raw["case_ids"] != list(range(1, 21))
            or api["timing"].summarize(raw, config) != report):
        raise ValueError("formal timing producer, completeness or arithmetic does not replay")
    if [item["case_id"] for item in raw["case_executions"]] != list(range(1, 21)):
        raise ValueError("formal timing execution inventory differs")
    for case, execution in zip(config["cases"], raw["case_executions"], strict=True):
        case_id = case["case_id"]
        identity = raw["case_identities"][str(case_id)]
        if (execution["exit_status"] != 0 or execution["identity_before"] != identity or execution["identity_after"] != identity
                or identity["workload_hash"] != content_hash(case["workload"])):
            raise ValueError("timing workload/source identity changed during measurement")
        for path, digest in identity["prepared_files"].items():
            checked({"path": path, "sha256": digest})
        for role in ("baseline", "candidate"):
            if identity[role]["source_files"] != sources[role] or identity[role]["binary_hash"] != sha(Path(config[role]["binary"])):
                raise ValueError("timed source/binary differs from frozen candidate")
            for path, digest in identity[role]["verifier_files"].items():
                checked({"path": path, "sha256": digest})
            command = execution["commands"][role]
            verification = execution["verifications"][role]
            for record, expected in ((command, case[role]["command"]), (verification, case[role]["verify_command"])):
                if record["exit_status"] != 0 or record["argv"] != expected:
                    raise ValueError("timing command/oracle execution differs")
                checked({"path": record["log_path"], "sha256": record["log_hash"]})
            lines = Path(command["log_path"]).read_text().splitlines()
            samples = [json.loads(line[len(api["timing"].PREFIX):]) for line in lines if line.startswith(api["timing"].PREFIX)]
            expected_samples = [row[role] for row in raw["records"] if row["case_id"] == case_id]
            if samples != expected_samples or len(samples) != config["pairs"]:
                raise ValueError("paired samples differ from original device stdout")
        for path, digest in execution["output_hashes"].items():
            checked({"path": path, "sha256": digest})
    return report


def qualification(plan_path, output, seconds):
    started = time.monotonic()
    deadline = _inherited_deadline(started, seconds)
    from controller_admission import AdmissionRecorder
    plan = read(plan_path)
    api = imports(Path(plan["release"]).resolve())
    source, prepared = validate_plan(plan, api)
    output.mkdir(parents=True, exist_ok=False)
    commands = Commands(output / "commands", deadline)
    commands.remaining()
    database = output / "evidence.sqlite"
    result = {"schema_version": 1, "status": "failed", "task_plan": ref(plan_path), "operator": plan["operator"]}
    admission = None
    try:
        binary = build(source, output / "build", commands, plan["operator"])
        with api["EpisodeStore"](database) as store:
            bundle_dir = output / "source-bundle"
            bundle_dir.mkdir()
            source_hash = api["profiler"].source_bundle(source, bundle_dir, store)
            source_hashes = {role: source_hash for role in ("baseline", "candidate")}
            run_id = plan["operator"] + "-baseline-qualification"
            admission = AdmissionRecorder(api, store, output, plan,
                {role: source for role in source_hashes}, {role: binary for role in source_hashes}, prepared,
                source_hashes, run_id, run_id + "-control", "baseline_qualification")
            try:
                admission.start("correctness")
                rows = correctness(plan["operator"], source, binary, prepared, output / "correctness", commands, api["timing"], plan["physical_device"])
                accuracy_ref = store.register_artifact(output / "correctness/report.json")
                passed = all(row["correct"] for row in rows)
                admission.complete("correctness", [accuracy_ref], passed=passed)
                if not passed:
                    raise RuntimeError("original baseline failed declared correctness")
                for phase in ("aa_before", "formal", "aa_after"):
                    commands.remaining()
                    admission.collect(phase)
                admission.start("profile")
                baseline_profiles = []
                case_id = plan["profile"]["case_id"]
                metadata = read(prepared / f"case_{case_id:02d}/metadata.json")
                output_keys = ("output_y", "output_scale") if plan["operator"] == "dynamic_quant" else ("output",)
                profile_refs = []
                for index, kernel in enumerate(plan["profile"]["kernels"]):
                    folder = output / "profiles" / f"kernel-{index:02d}"
                    folder.mkdir(parents=True)
                    outputs = {key: str(folder / (key + ".bin")) for key in output_keys}
                    config = dict(backend="auto", architecture="Ascend910C", soc="Ascend910_9392", device=0,
                        physical_device=plan["physical_device"], chip=0, case_id=case_id, kernel=kernel, role="baseline",
                        source_dir=str(source), binary=str(binary), cwd=str(source),
                        workload=json_contract({key: value for key, value in metadata.items() if key not in output_keys}),
                        command=case_command(plan["operator"], binary, metadata, 0, outputs), warmups=10, repeats=5,
                        timeout_seconds=min(180, commands.remaining()))
                    dump(folder / "config.json", config)
                    with api["timing"].device_lock(plan["physical_device"], min(180, commands.remaining())):
                        captured = api["profiler"].capture(config, folder / "capture", database)
                    manifest = api["load_capture_manifest"](store, captured["manifest_hash"])
                    normalized = api["normalize_profile"](store, captured["manifest_hash"],
                        api["expand_specs"](manifest, plan["profile"]["metrics"]))
                    if any(metric["status"] != "available" for metric in normalized["metrics"].values()):
                        raise ValueError("a predeclared named-kernel metric is unavailable on this baseline/toolchain")
                    dump(folder / "normalized-profile.json", normalized)
                    profile_refs.extend([captured["manifest_hash"], store.register_artifact(folder / "normalized-profile.json")])
                    baseline_profiles.append({"kernel": kernel, "normalized": ref(folder / "normalized-profile.json"),
                                              "capture": ref(folder / "capture/capture-manifest.json")})
                admission.complete("profile", profile_refs)
                artifacts = admission.finish(capture_refs=[read(checked(item["normalized"]))["capture_manifest_hash"]
                                                           for item in baseline_profiles])
                result.update(status="passed", binary=ref(binary), correctness=ref(output / "correctness/report.json"),
                    control_report_ref=artifacts["control_report"], registration_ref=artifacts["qualification_registration"],
                    registration=ref(output / "registration.json"), source_hashes=source_hashes,
                    run_id=run_id, candidate_id=run_id + "-control",
                    baseline_profiles=baseline_profiles, profile_store=ref(database))
            except Exception as error:
                admission.fail_active(error)
                raise
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    result["executions"] = commands.executions
    # SQLite may write its final commit while the store exits; bind those bytes.
    if database.is_file():
        result["profile_store"] = ref(database)
    dump(output / "qualification.json", result)
    return result


def verify_qualification(plan_path, reference, api):
    qualification = read(checked(reference))
    if qualification["status"] != "passed" or qualification["task_plan"] != ref(plan_path):
        raise ValueError("baseline qualification must bind this exact frozen task plan")
    verify_correctness_report(qualification["correctness"])
    for pointer in qualification["executions"]:
        execution = read(checked(pointer))
        checked(execution["stdout"])
        checked(execution["stderr"])
        if execution["exit_status"] != 0 or execution["error"]:
            raise ValueError("baseline build/correctness command failed")
    if [item["kernel"] for item in qualification["baseline_profiles"]] != read(plan_path)["profile"]["kernels"]:
        raise ValueError("baseline named-kernel profile inventory differs from frozen choices")
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory, verify_store_connection
    import sqlite3
    database = checked(qualification["profile_store"])
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        objects = default_object_directory(database)
        verify_store_connection(connection, objects)
        store = _ReadOnlyArtifacts(connection, objects)
        from timing_admission import verify_timing_admission
        if sha(checked(qualification["registration"])) != qualification["registration_ref"]:
            raise ValueError("baseline control registration differs")
        source_inventory = read(checked(read(plan_path)["source_inventory"]))
        for source_ref in qualification["source_hashes"].values():
            if read(store.verify_artifact(source_ref))["files"] != source_inventory:
                raise ValueError("baseline control source differs from frozen task")
        admission = verify_timing_admission(store, qualification["control_report_ref"], expected={
            key: qualification[key] for key in ("run_id", "candidate_id", "operator", "source_hashes", "registration_ref")}
            | {"purpose": "baseline_qualification"})
        return verify_qualification_bindings(store, qualification, read(plan_path), admission, api)


def verify_qualification_bindings(store, qualification, plan, admission, api):
    """Join already-replayed controls/profile evidence to the frozen task inputs."""
    from timing_admission import verify_capture_window
    protocol = read(store.verify_artifact(admission["protocol_ref"]))
    control = read(store.verify_artifact(qualification["control_report_ref"]))
    binary = checked(qualification["binary"])
    binary_hash = sha(binary)
    if (qualification["operator"] != plan["operator"] or protocol["operator"] != plan["operator"]
            or protocol["measurement_policy"]["repeat"] != plan["repeat"]
            or any(value != binary_hash for value in protocol["binary_hashes"].values())
            or set(protocol["binary_hashes"]) != {"baseline", "candidate"}):
        raise ValueError("baseline binary/operator/repeat differs from its qualified protocol")
    for phase in ("aa_before", "aa_after"):
        config = read(store.verify_artifact(protocol["phases"][phase]["config_ref"]))
        if config["expected_case_ids"] != plan["control_case_ids"]:
            raise ValueError("baseline control coverage differs from the frozen task")
    roster = read(store.verify_artifact(control["attempt_roster_ref"]))
    completed = {}
    for reference in roster["events"]:
        event = read(store.verify_artifact(reference))
        if event["state"] == "completed":
            completed[event["stage"]] = set(event["evidence_refs"])
    if sha(checked(qualification["correctness"])) not in completed.get("correctness", set()):
        raise ValueError("baseline correctness report differs from its registered stage")
    raw = read(store.verify_artifact(control["formal"]["raw_ref"]))
    if raw["device"] != 0 or raw["physical_device"] != plan["physical_device"]:
        raise ValueError("baseline timing device differs from the frozen task")
    metadata = read(Path(plan["prepared_inputs"]) / f"case_{plan['profile']['case_id']:02d}/metadata.json")
    output_keys = ("output_y", "output_scale") if plan["operator"] == "dynamic_quant" else ("output",)
    workload = json_contract({key: value for key, value in metadata.items() if key not in output_keys})
    for item in qualification["baseline_profiles"]:
        normalized = read(checked(item["normalized"]))
        manifest_ref = normalized["capture_manifest_hash"]
        if (sha(checked(item["capture"])) != manifest_ref
                or {manifest_ref, sha(checked(item["normalized"]))} - completed.get("profile", set())):
            raise ValueError("baseline profile attachments differ from their registered stage")
        manifest = api["load_capture_manifest"](store, manifest_ref)
        if (manifest["role"] != "baseline" or manifest["case_id"] != plan["profile"]["case_id"]
                or manifest["kernel"] != item["kernel"] or normalized["kernel"] != item["kernel"]
                or normalized["case_id"] != plan["profile"]["case_id"]
                or manifest["source_hash"] != protocol["source_hashes"]["baseline"]
                or manifest["binary_hash"] != binary_hash
                or read(store.verify_artifact(manifest["workload_hash"])) != workload):
            raise ValueError("baseline profile scope/source/binary differs from the frozen task")
        hardware = read(store.verify_artifact(manifest["hardware_hash"]))
        if (hardware.get("host") != raw["host"]
                or any(str(hardware.get(key)) != str(raw[key]) for key in ("device", "physical_device"))):
            raise ValueError("baseline profile hardware differs from qualified timing")
        verify_capture_window(store, manifest_ref, window=admission["stage_windows"]["profile"],
                              control_report_ref=qualification["control_report_ref"], role="baseline")
        replay = api["normalize_profile"](store, manifest_ref, api["expand_specs"](manifest, plan["profile"]["metrics"]))
        if (normalized != replay or set(normalized["metrics"]) != set(plan["profile"]["metrics"])
                or any(metric["status"] != "available" for metric in normalized["metrics"].values())):
            raise ValueError("baseline profile metrics differ from frozen choices or raw replay")
    return binary



def mechanism_choice(proposal, profile):
    choice = proposal.get("mechanism")
    if (not isinstance(choice, dict) or set(choice) != {"case_id", "kernel", "metric", "expected_direction"}
            or choice["case_id"] != profile["case_id"] or choice["kernel"] not in profile["kernels"]
            or choice["metric"] not in profile["metrics"] or choice["expected_direction"] not in ("increase", "decrease")):
        raise ValueError("candidate must predeclare one permitted named-kernel metric and direction")
    return choice


def attest_parameter_scope(baseline, candidate, admitted):
    """Narrow source proof, independent of which benchmark cases happened to pass.

The trusted task author must review parameter meanings and safe bounds before
the model runs. This function proves only that the patch stays within that
reviewed class; it never infers generality from twenty correctness samples.
"""
    before = {path.relative_to(baseline).as_posix(): path.read_bytes() for path in baseline.rglob("*")
              if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    after = {path.relative_to(candidate).as_posix(): path.read_bytes() for path in candidate.rglob("*")
             if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    result = {"passed": False, "policy": "predeclared integer tiling/buffer edits with unchanged semantic and tail code",
              "limitation": "broader algorithm/host rewrites require independent source review; full20 accuracy alone is insufficient",
              "changes": []}
    if not admitted or set(before) != set(after):
        return {**result, "reason": "no reviewed parameter scope or source file inventory changed"}
    for entry in admitted:
        if (set(entry) != {"path", "symbol", "kind", "minimum", "maximum", "multiple_of"}
                or entry["kind"] not in ("tile_elements", "buffer_depth", "block_count")
                or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", entry["symbol"])
                or not all(type(entry[key]) is int and entry[key] >= 1 for key in ("minimum", "maximum", "multiple_of"))
                or entry["minimum"] > entry["maximum"] or entry["path"] not in before):
            raise ValueError("malformed independently reviewed parameter scope")
        pattern = rb"\b" + entry["symbol"].encode() + rb"\s*=\s*(\d+)(?:[uUlL]*)(?=\s*[;,)])"
        old, new = list(re.finditer(pattern, before[entry["path"]])), list(re.finditer(pattern, after[entry["path"]]))
        if len(old) != 1 or len(new) != 1:
            return {**result, "reason": "reviewed parameter declaration changed or became ambiguous"}
        old_value, new_value = int(old[0][1]), int(new[0][1])
        if not entry["minimum"] <= new_value <= entry["maximum"] or new_value % entry["multiple_of"]:
            return {**result, "reason": "candidate parameter exceeds independently reviewed resource bounds"}
        if old_value != new_value:
            result["changes"].append({"path": entry["path"], "symbol": entry["symbol"], "before": old_value, "after": new_value})
        for mapping, match in ((before, old[0]), (after, new[0])):
            contents = mapping[entry["path"]]
            mapping[entry["path"]] = contents[:match.start(1)] + b"<reviewed-integer>" + contents[match.end(1):]
    if before != after or not result["changes"]:
        return {**result, "reason": "patch changes unreviewed code, arithmetic, precision, control flow or tails"}
    return {**result, "passed": True, "reason": "only independently reviewed resource parameters changed"}


def freeze_candidate(api, store, workspace, output, operator, run_id, choice, split="validation", *,
                     handler_id="validation.single_candidate", coverage_gap=None):
    from evaluate_skill_release import validate_candidate
    changed = validate_candidate(workspace / "baseline", workspace / "candidate")
    if not changed:
        raise ValueError("no source intervention was submitted")
    proposal = read(workspace / "candidate_plan.json")
    if proposal.get("actual_parent") != "original baseline" or not isinstance(proposal.get("intent"), str) or not proposal["intent"].strip():
        raise ValueError("candidate plan must name its original baseline and concrete intent")
    anchors = proposal.get("source_anchors")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("candidate must freeze concrete mechanism source anchors before measurement")
    for anchor in anchors:
        if not isinstance(anchor, dict) or set(anchor) != {"path", "line", "why"}:
            raise ValueError("source anchor requires relative path, line and rationale")
        path = (workspace / "candidate" / anchor["path"]).resolve()
        if (not path.is_relative_to((workspace / "candidate").resolve()) or not path.is_file()
                or type(anchor["line"]) is not int or not 1 <= anchor["line"] <= len(path.read_text().splitlines())
                or not isinstance(anchor["why"], str) or not anchor["why"].strip()):
            raise ValueError("source anchor does not identify a real candidate line")
    sources = {}
    for role in ("baseline", "candidate"):
        directory = output / "source-bundles" / role
        directory.mkdir(parents=True)
        sources[role] = api["profiler"].source_bundle(workspace / role, directory, store)
    patch = ""
    for relative in changed:
        old, new = workspace / "baseline" / relative, workspace / "candidate" / relative
        patch += "".join(difflib.unified_diff(old.read_text().splitlines(True) if old.exists() else [],
            new.read_text().splitlines(True) if new.exists() else [], fromfile="a/" + relative, tofile="b/" + relative))
    (output / "candidate.patch").write_text(patch)
    patch_hash = store.register_artifact(output / "candidate.patch")
    candidate_id = run_id + "-candidate"
    gap = coverage_gap or "one-candidate held-out validation uses the frozen exploration acceptance path; no unimplemented v0002 predicate or route is fabricated"
    writer = api["TraceWriter"](output / "events.jsonl", run_id=run_id, task_id=operator, session_id=candidate_id, store=store)
    writer.append("candidate_proposed", dict(mode="exploration", hypothesis=proposal["intent"],
        source_parent_hash=sources["baseline"], patch_hash=patch_hash, handler_id=handler_id, handler_version="1.0.0",
        parameters={"mechanism": choice}, expected_effects=[choice["metric"] + " " + choice["expected_direction"]],
        alternatives=["no supported gain", "correctness, resource or case regression"], coverage_gap=gap),
        attempt_id=candidate_id, candidate_id=candidate_id)
    candidate = dict(candidate_id=candidate_id, session_id=candidate_id, source_hashes=sources,
        patch_artifact_hash=patch_hash, handler_id=handler_id, handler_version="1.0.0",
        parameters={"mechanism": choice}, coverage_gap=gap, attempt_evidence_hash=writer.seal_attempt(candidate_id))
    manifest = api["freeze_exploration_manifest"](store, run_id=run_id, task_id=operator, split=split, candidates=[candidate])
    frozen = {"run_id": run_id, "split": split, "candidate": candidate, "frozen_manifest_hash": manifest,
              "proposal_ref": store.register_artifact(workspace / "candidate_plan.json")}
    dump(output / "frozen-candidate.json", frozen)
    return frozen


def capture_mechanism(api, store, database, plan, choice, sources, binaries, prepared, output, commands):
    profiles = {}
    case_id, metric = choice["case_id"], choice["metric"]
    metadata = read(prepared / f"case_{case_id:02d}/metadata.json")
    output_keys = ("output_y", "output_scale") if plan["operator"] == "dynamic_quant" else ("output",)
    for role in ("baseline", "candidate"):
        outputs = {key: str(output / "profile-outputs" / role / (key + ".bin")) for key in output_keys}
        (output / "profile-outputs" / role).mkdir(parents=True)
        config = dict(backend="auto", architecture="Ascend910C", soc="Ascend910_9392", device=0,
            physical_device=plan["physical_device"], chip=0, case_id=case_id, kernel=choice["kernel"], role=role,
            source_dir=str(sources[role]), binary=str(binaries[role]), cwd=str(sources[role]),
            workload=json_contract({key: value for key, value in metadata.items() if key not in output_keys}),
            command=case_command(plan["operator"], binaries[role], metadata, 0, outputs), warmups=10, repeats=5,
            timeout_seconds=min(180, commands.remaining()))
        dump(output / (role + "-profile-config.json"), config)
        with api["timing"].device_lock(plan["physical_device"], min(180, commands.remaining())):
            result = api["profiler"].capture(config, output / (role + "-profile"), database)
        manifest = api["load_capture_manifest"](store, result["manifest_hash"])
        specs = {metric: plan["profile"]["metrics"][metric]}
        profile = api["normalize_profile"](store, result["manifest_hash"], api["expand_specs"](manifest, specs))
        profiles[role] = {"profile": profile, "digest": api["register_json_artifact"](store, profile), "hardware": manifest["hardware_hash"]}
        dump(output / (role + "-normalized-profile.json"), profile)
    if profiles["baseline"]["hardware"] != profiles["candidate"]["hardware"]:
        raise ValueError("independent mechanism captures used different hardware identities")
    return profiles


def finalize(api, store, frozen, operator, run_id, statuses, artifacts, cases, report, output):
    candidate = frozen["candidate"]
    admitted_timing = bool(report and artifacts.get("control_report"))
    projection = report["gate_projection"] if admitted_timing else {"baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": []}
    evidence = dict(candidate_id=candidate["candidate_id"], **statuses, artifacts=artifacts, mechanism_alignment=None, **projection)
    request = dict(schema_version="1.0.0", frozen_manifest_hash=frozen["frozen_manifest_hash"],
                   candidates=[candidate], evidence=[evidence], config={})
    outcome, = api["ExplorationGate"]().evaluate(request, store=store)
    api["verify_exploration"](request, [outcome], store=store)
    outcome_ref = api["register_json_artifact"](store, outcome)
    stages = {}
    for name, status, artifact in (("static_review", statuses["static_review"], "source_review"),
        ("build", statuses["build"], "build_log"), ("correctness", statuses["accuracy"], "accuracy_report"),
        ("runtime", statuses["runtime"], "accuracy_report"),
        ("timing", "passed" if admitted_timing and report["stable"] else ("failed" if report else "not_run"), "measurement_report"),
        ("profile", "passed" if "mechanism_report" in artifacts else
            ("failed" if list(output.glob("*-profile-config.json")) else "not_run"), "mechanism_report")):
        stages[name] = dict(status=status, reason="actual independent controller stages; unavailable evidence is not synthesized",
                            artifact_refs=[artifacts[artifact]] if artifact in artifacts else [])
    trace = api["make_optimization_trace"](dict(run_id=run_id, task_id=operator, session_id=candidate["session_id"],
        attempt_id=candidate["candidate_id"], candidate_id=candidate["candidate_id"], operator=operator, split=frozen.get("split", "validation"),
        source_parent_hash=candidate["source_hashes"]["baseline"]),
        provenance=dict(baseline_source_hash=candidate["source_hashes"]["baseline"], candidate_source_hash=candidate["source_hashes"]["candidate"], patch_hash=candidate["patch_artifact_hash"]),
        intervention=dict(handler=dict(id=candidate["handler_id"], version=candidate["handler_version"], producer_hash=None), parameters=candidate["parameters"]),
        routing=dict(mode="exploration", route=None, coverage_gap=candidate["coverage_gap"]),
        workload=dict(case_ids=list(range(1, 21)), hardware_fingerprint=artifacts.get("hardware_report")),
        validation=dict(**stages, case_count=20, passed_count=sum(case["correct"] is True for case in cases),
                        timing_case_ids=list(range(1, 21)) if report else []),
        result=dict(verdict=outcome["verdict"], speedup=outcome["speedup"], speedup_lcb=outcome["speedup_lcb"],
                    max_regression=report["max_case_regression"] if report and report["max_case_regression"] is not None else None,
                    exploration_outcome_ref=outcome_ref))
    api["validate_optimization_trace"](trace, store)
    dump(output / "trace.json", trace)
    dump(output / "exploration-request.json", request)
    dump(output / "exploration-outcome.json", outcome)
    return outcome


def evaluate(plan_path, baseline_receipt, workspace, destination, run_id, seconds):
    started = time.monotonic()
    deadline = _inherited_deadline(started, seconds)
    from evaluate_skill_release import tree_sha
    from controller_admission import AdmissionRecorder
    plan = read(plan_path)
    operator = plan["operator"]
    api = imports(Path(plan["release"]).resolve())
    source, prepared = validate_plan(plan, api)
    baseline_binary = verify_qualification(plan_path, baseline_receipt, api)
    if api["profiler"].source_inventory(workspace / "baseline") != api["profiler"].source_inventory(source):
        raise ValueError("worker baseline differs from qualified original baseline")
    choice = mechanism_choice(read(workspace / "candidate_plan.json"), plan["profile"])
    output = destination.parent / "host-evidence"
    output.mkdir(parents=True, exist_ok=False)
    commands = Commands(output / "commands", deadline)
    commands.remaining()
    database = output / "evidence.sqlite"
    counts = dict(candidates=1, builds=0, timing_groups=0, profile_groups=0)
    statuses = dict(static_review="passed", build="not_run", accuracy="not_run", runtime="not_run", semantic="not_run", scope="not_run", portability="not_run")
    cases = [dict(case_id=case_id, correct=None, baseline_us=None, candidate_us=None) for case_id in range(1, 21)]
    report, failure, outcome, admission = None, None, None, None
    with api["EpisodeStore"](database) as store:
        frozen = freeze_candidate(api, store, workspace, output, operator, run_id, choice, plan.get("split", "validation"))
        review = dict(status="not_run",
            check="protected oracle, exact complete-operator timer binding, original parent, frozen metric plan",
            sources=frozen["candidate"]["source_hashes"], proposal_ref=frozen["proposal_ref"], task_plan_ref=store.register_artifact(plan_path))
        artifacts = {"baseline_qualification": store.register_artifact(checked(baseline_receipt))}
        phase = "static_review"
        try:
            review.update(status="passed", scope_checks=check_candidate_scope(workspace / "baseline", workspace / "candidate", operator))
            from eval_candidate_evidence import register_candidate_evidence
            artifacts.update(register_candidate_evidence(store, workspace, Path(plan["release"]),
                model=plan.get("model"), baseline_qualification=baseline_receipt))
            phase = "build"
            counts["builds"] = 1
            binary = build(workspace / "candidate", output / "candidate-build", commands, operator)
            statuses["build"] = "passed"
            sources = {role: workspace / role for role in ("baseline", "candidate")}
            binaries = {"baseline": baseline_binary, "candidate": binary}
            admission = AdmissionRecorder(api, store, output, plan, sources, binaries, prepared,
                frozen["candidate"]["source_hashes"], run_id, frozen["candidate"]["candidate_id"], "evaluation",
                profile_kernel=choice["kernel"])
            artifacts["qualification_registration"] = admission.registration_ref
            phase = "accuracy"
            admission.start("correctness")
            rows = correctness(operator, workspace / "candidate", binary, prepared, output / "correctness", commands, api["timing"], plan["physical_device"])
            for case, row in zip(cases, rows, strict=True):
                case["correct"] = row["correct"]
            accuracy = dict(case_ids=list(range(1, 21)), passed_case_ids=[row["case_id"] for row in rows if row["correct"]],
                source_hashes=frozen["candidate"]["source_hashes"], reports_ref=store.register_artifact(output / "correctness/report.json"))
            artifacts["accuracy_report"] = api["register_json_artifact"](store, accuracy)
            admission.complete("correctness", [artifacts["accuracy_report"]], passed=all(row["correct"] for row in rows))
            if not all(row["correct"] for row in rows):
                raise RuntimeError("candidate failed full declared correctness")
            statuses.update(accuracy="passed", semantic="passed", runtime="passed")
            scope = {"passed": True, "policy": "independent frozen-source review with full declared correctness",
                     "source_review_ref": artifacts["source_review"], "route_receipt_ref": artifacts["route_receipt"]}
            statuses.update(scope="passed", portability="passed")
            artifacts["scope_report"] = api["register_json_artifact"](store, dict(
                attestation=scope, hardware_limit="910C/A3 with the unchanged dynamic input contract; no 950 claim",
                accuracy_ref=artifacts["accuracy_report"], baseline_qualification_ref=artifacts["baseline_qualification"]))
            phase = "timing"
            counts["timing_groups"] = 1
            commands.remaining()
            admission.collect("aa_before")
            commands.remaining()
            report = admission.collect("formal")
            for case, measured in zip(cases, report["per_case"], strict=True):
                case.update(baseline_us=measured["baseline_median_ns"] / 1000 if measured["baseline_median_ns"] else None,
                            candidate_us=measured["candidate_median_ns"] / 1000 if measured["candidate_median_ns"] else None)
            if not report["stable"]:
                raise RuntimeError("formal measurement quality failed; no resampling")
            commands.remaining()
            admission.collect("aa_after")
            phase = "profile"
            counts["profile_groups"] = 1
            admission.start("profile")
            profiles = capture_mechanism(api, store, database, plan, choice, sources, binaries, prepared, output, commands)
            metric = choice["metric"]
            mechanism = dict(schema_version="1.0.0", candidate_id=frozen["candidate"]["candidate_id"], hypothesis_basis="heuristic",
                metrics=[dict(name=metric, unit=plan["profile"]["metrics"][metric]["unit"], expected_direction=choice["expected_direction"],
                    baseline=profiles["baseline"]["profile"]["metrics"][metric]["value"], candidate=profiles["candidate"]["profile"]["metrics"][metric]["value"],
                    baseline_profile_hash=profiles["baseline"]["digest"], candidate_profile_hash=profiles["candidate"]["digest"])])
            artifacts["mechanism_report"] = api["register_json_artifact"](store, mechanism)
            artifacts["hardware_report"] = profiles["baseline"]["hardware"]
            admission.complete("profile", [artifacts["mechanism_report"], artifacts["hardware_report"]])
            artifacts.update(admission.finish(mechanism_report_ref=artifacts["mechanism_report"]))
        except Exception as error:
            if admission:
                admission.fail_active(error)
            failure = {"stage": phase, "type": type(error).__name__, "message": str(error)}
            if phase in statuses:
                statuses[phase] = "failed"
            if phase == "static_review":
                review.update(status="failed", reason=failure)
        finally:
            artifacts["static_review_report"] = api["register_json_artifact"](store, review)
            artifacts.setdefault("source_review", artifacts["static_review_report"])
            artifacts["build_log"] = api["register_json_artifact"](store, [
                {"execution": store.register_artifact(checked(pointer)),
                 "stdout": store.register_artifact(checked(read(checked(pointer))["stdout"])),
                 "stderr": store.register_artifact(checked(read(checked(pointer))["stderr"]))}
                for pointer in commands.executions])
            # Keep measured failures/partial samples as actual raw evidence, but
            # expose gate timing arrays only when the frozen collector admits them.
            for name, relative in (("measurement_report", "formal/measurement_report.json"),
                                   ("timing_raw", "formal/raw_measurements.json"), ("timing_config", "formal/config.json")):
                path = output / relative
                if path.is_file():
                    artifacts[name] = store.register_artifact(path)
            if admission and "formal" in admission.collected:
                artifacts["timing_config"] = admission.collected["formal"]["config_ref"]
            if report is None and (output / "formal/measurement_report.json").is_file():
                report = read(output / "formal/measurement_report.json")
            if report:
                for case, measured in zip(cases, report["per_case"], strict=True):
                    for role in ("baseline", "candidate"):
                        value = measured[role + "_median_ns"]
                        case[role + "_us"] = value / 1000 if value else None
            artifacts["evaluation_case_report"] = api["register_json_artifact"](store, cases)
            outcome = finalize(api, store, frozen, operator, run_id, statuses, artifacts, cases, report, output)
    measured = all(case["correct"] is True and all(type(case[field]) in (int, float) and math.isfinite(case[field]) and case[field] > 0
                   for field in ("baseline_us", "candidate_us")) for case in cases)
    receipt = dict(schema_version=1, counts=counts, full_declared_correctness=statuses["accuracy"] == "passed",
        cases=cases, candidate_tree_sha256=tree_sha(workspace / "candidate"), trace=ref(output / "trace.json"), store=ref(database),
        evidence=[ref(output / "exploration-request.json"), ref(output / "exploration-outcome.json"), ref(output / "frozen-candidate.json"),
                  *commands.executions], duration_seconds=time.monotonic() - started, failure=failure, measured_cases_complete=measured,
        formal_outcome=outcome["verdict"])
    dump(destination, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare-task")
    p.add_argument("--preparation", type=Path, required=True)
    p.add_argument("--prepared-inputs", type=Path, required=True)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--profile-plan", type=Path, required=True)
    p.add_argument("--admitted-parameters", type=Path)
    p.add_argument("--repeat", type=int, required=True)
    p.add_argument("--physical-device", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("qualify-baseline")
    q.add_argument("--plan", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("--seconds", type=float, default=3600)
    e = sub.add_parser("evaluate")
    e.add_argument("--plan", type=Path, required=True)
    e.add_argument("--baseline-receipt", type=Path, required=True)
    e.add_argument("--workspace", type=Path, required=True)
    e.add_argument("--result", type=Path, required=True)
    e.add_argument("--run-id", required=True)
    e.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()

    def deadline(_signal, _frame):
        raise TimeoutError("outer controller wall budget expired")

    signal.signal(signal.SIGTERM, deadline)
    if args.command == "prepare-task":
        prepare_task(args.preparation.resolve(), args.prepared_inputs.resolve(), args.release.resolve(), read(args.profile_plan),
                     args.repeat, args.physical_device, args.output.resolve(), read(args.admitted_parameters) if args.admitted_parameters else None)
        return 0
    if args.command == "qualify-baseline":
        result = qualification(args.plan.resolve(), args.output.resolve(), args.seconds)
        return 0 if result["status"] == "passed" else 2
    result = evaluate(args.plan.resolve(), ref(args.baseline_receipt.resolve()), args.workspace.resolve(),
                      args.result.resolve(), args.run_id, args.seconds)
    return 0 if result["measured_cases_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
