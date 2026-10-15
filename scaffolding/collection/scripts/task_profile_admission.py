"""Task completion and original PMU execution-window joins; no final gate authority."""
from pathlib import Path

from shared_validation_adapter import selected_runtime
from timing_admission import ReplayCache, ROLES, number, read, require


def _verify_capture_executions(store, manifest, window):
    """Replay ten warmups and five captures against original execution records."""
    require(manifest["policy"]["warmups"] == 10 and manifest["policy"]["repeats"] == 5
            and len(manifest["warmup_runs"]) == 10
            and [row["capture_id"] for row in manifest["captures"]]
            == [f"capture-{index:03d}" for index in range(5)], "profile capture inventory differs")
    clock = window[0]

    def execution(ref):
        nonlocal clock
        record = read(store, ref)
        require(record.get("exit_code") == 0 and not record.get("error")
                and clock <= number(record["started_at"]) <= number(record["ended_at"]) <= window[1],
                "profile execution falls outside its registered stage")
        for key in ("stdout_hash", "stderr_hash"):
            store.verify_artifact(record[key])
        clock = record["ended_at"]
        return record

    for row in manifest["warmup_runs"]:
        record = execution(row["log_hash"])
        require(row["argv"] == record["argv"] and row["exit_code"] == record["exit_code"],
                "profile warmup differs from its original execution")
    for row in manifest["captures"]:
        receipt = read(store, row["log_hash"])
        for key in ("capture", "import"):
            if key == "import" and key not in receipt:
                continue
            embedded = receipt[key]
            record = execution(embedded["log_hash"])
            require({key: value for key, value in embedded.items() if key != "log_hash"} == record,
                    "profile capture differs from its original execution")
            if key == "capture":
                require(row["argv"] == record["argv"] and row["exit_code"] == record["exit_code"],
                        "profile capture command differs")



def verify_task_profile_window(store, mechanism_report_ref, *, window,
                               measurement_admission_ref, expected, profile_configs):
    """Join frozen PMU configs/window to a real current Task completion replay.

    The caller binds window/profile_configs to the frozen outer attempt roster.
    This check does not admit its boundary, total budget, or final process exit.
    """
    selected_runtime()
    from aprof_runtime.measurement_entry import replay_current_measurement_admission
    import shlex

    store = store if isinstance(store, ReplayCache) else ReplayCache(store)
    require(set(expected) == {"operator", "run_id", "session_id", "candidate_id",
                              "source_hashes", "measurement_report_ref"},
            "Task profile requires the complete gate-bound measurement identity")
    require(isinstance(window, list) and len(window) == 2
            and number(window[0]) <= number(window[1]), "profile stage window missing")
    require(set(profile_configs) == set(ROLES), "both frozen role profile configs are required")
    replay = replay_current_measurement_admission(store, measurement_admission_ref, expected=expected)
    completion = read(store, replay["completion_ref"])
    config = read(store, replay["config_ref"])
    registration = read(store, replay["registration_ref"])
    require(number(completion["finished_at"]) <= window[0],
            "profile stage precedes completion of admitted Task measurement")
    build = registration["identity"]["build"]
    mechanism = read(store, mechanism_report_ref)
    manifests = {role: {read(store, metric[role + "_profile_hash"])["capture_manifest_hash"]
                       for metric in mechanism["metrics"]} for role in ROLES}
    require(all(len(references) == 1 for references in manifests.values()),
            "Task profile requires one independent capture manifest per role")
    checked = {}
    for role in ROLES:
        frozen = read(store, profile_configs[role])
        reference = next(iter(manifests[role]))
        manifest = read(store, reference)
        cases = [case for case in config["cases"] if case["case_id"] == frozen["case_id"]]
        require(len(cases) == 1, "profile case was not measured by Task admission")
        case = cases[0]
        require(frozen["role"] == role and frozen["source_dir"] == config["roles"][role]["source_dir"]
                and frozen["binary"] == config["build"]["binary"]
                and frozen["cwd"] == config["build"]["source_dir"]
                and frozen["workload"] == case["workload"]
                and all(str(frozen[key]) == str(config[key]) for key in ("device", "physical_device"))
                and frozen["kernel"] in config["task_profile"]["role_kernel_names"][role][str(frozen["case_id"])],
                "frozen profile config differs from admitted Task role/build/case/kernel")
        command = frozen["command"]
        require(isinstance(command, list) and len(command) == len(case["command"]) + 2
                and command[-2:] == ["--aprof-mechanism-role", role],
                "profile command must select the admitted Task role")
        directory = None
        for actual, template in zip(command[:-2], case["command"]):
            if "{cycle_dir}" in template:
                require(template.count("{cycle_dir}") == 1, "ambiguous Task output-directory template")
                prefix, suffix = template.split("{cycle_dir}")
                require(actual.startswith(prefix) and actual.endswith(suffix),
                        "profile command changed Task output routing")
                current = actual[len(prefix):len(actual) - len(suffix) if suffix else None]
                require(Path(current).is_absolute() and ".." not in Path(current).parts
                        and (directory is None or current == directory),
                        "profile command must use one complete-call output directory")
                directory = current
            else:
                require(actual == template, "profile command changed admitted Task case arguments")
        require(manifest["role"] == role and manifest["case_id"] == frozen["case_id"]
                and manifest["kernel"] == frozen["kernel"]
                and manifest["source_hash"] == replay["source_hashes"][role]
                and manifest["binary_hash"] == build["binary_ref"],
                "profile source/binary/role/case/kernel differs from admitted Task measurement")
        require(read(store, manifest["workload_hash"]) == case["workload"],
                "profile workload differs from admitted Task case")
        hardware = read(store, manifest["hardware_hash"])
        require(hardware.get("host") == replay["hardware"]["host"]
                and isinstance(replay["hardware"].get("cann_home"), str) and replay["hardware"]["cann_home"]
                and hardware.get("cann_home") == replay["hardware"]["cann_home"]
                and all(str(hardware.get(key)) == str(config[key]) for key in ("device", "physical_device")),
                "profile hardware differs from admitted Task registration/config")
        require(all(row["argv"] == frozen["command"] for row in manifest["warmup_runs"]),
                "profile warmup command differs from frozen role config")
        # Same application parsing as profile_evidence.load_capture_manifest.
        for capture in manifest["captures"]:
            argv = capture["argv"]
            if manifest["backend"] == "msprof":
                applications = [arg.split("=", 1)[1] for arg in argv if arg.startswith("--application=")]
                require(len(applications) == 1, "profile capture requires one workload application")
                target = shlex.split(applications[0])
            else:
                require(manifest["backend"] == "npu-compute" and "--" in argv,
                        "profile capture requires an exact supported workload application")
                target = argv[argv.index("--") + 1:]
            require(target == command, "profile capture application differs from admitted Task role/case")
        _verify_capture_executions(store, manifest, window)
        checked[role] = reference
    return {"passed": True, "completion_ref": replay["completion_ref"],
            "proof_ref": replay["receipt_ref"], "config_ref": replay["config_ref"],
            "task_registration_ref": replay["registration_ref"],
            "task_hardware_ref": replay["hardware_ref"], "build": build,
            "source_hashes": replay["source_hashes"], "profile_configs": profile_configs,
            "capture_manifests": checked, "window": window}
