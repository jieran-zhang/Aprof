"""Task-local v4 collection with real CPU children, strict parsing and gate replay."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import types

import pytest

REPO = Path(__file__).resolve().parents[2]
RELEASE = REPO / "skill-libs/graph-base/0.5.1"
sys.path.insert(0, str(RELEASE / "skills/ascendc-aprof-profiling/scripts"))
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import ContractError, StoreError
import aprof_runtime.store as store_module
import aprof_runtime.task_window_measurement_admission as admission
import aprof_runtime.measurement_entry as entry
import device_task_window_timing as collector
from test_shared_measurement_admission import pilot_wire, wire
from test_task_window_timing import rows_for, table


def executable(path, body):
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)
    return str(path)


@pytest.mark.parametrize("mode", ("success", "early_csv", "changed_raw", "replay_timeout", "handoff_timeout"))
def test_local_native_oracle_complete_gate_and_failure(tmp_path, monkeypatch, mode):
    scenario = mode
    mutation = scenario if scenario in {"early_csv", "changed_raw"} else "none"
    release = RELEASE
    build = tmp_path / "build"
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    templates = tmp_path / "templates"
    for directory in (build, baseline, candidate, templates):
        directory.mkdir()
    (baseline / "kernel.cpp").write_text("baseline")
    (candidate / "kernel.cpp").write_text("candidate")
    (build / "op_host").mkdir()
    (build / "op_host/device_task_profile.h").write_bytes(collector.HEADER_ASSET.read_bytes())
    (build / "op_host/device_shared_timing.h").write_bytes(
        (release / "skills/ascendc-aprof-profiling/assets/device_shared_timing.h").read_bytes())
    (build / "build.json").write_text("{}")
    prepared = tmp_path / "input.bin"
    prepared.write_bytes(b"input")
    verifier = tmp_path / "verify.py"
    verifier.write_text("""
import json, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
result = pathlib.Path(sys.argv[sys.argv.index('--result') + 1])
answer = {'case_id': 1, 'passed': output.read_bytes() == b'correct'}
result.write_text(json.dumps(answer))
print(json.dumps(answer))
""")
    native = executable(build / "native", """
import json, os, pathlib, sys
directory = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])
profile = pathlib.Path(os.environ['APROF_TASK_PROFILE_DIR'])
assert profile.is_dir() and not list(profile.iterdir())
mode = os.environ['APROF_SHARED_MODE']
cycle = int(os.environ['APROF_SHARED_CYCLE'])
name = 'pilot' if mode == 'pilot' else 'cycle-' + str(cycle)
messages = json.loads((pathlib.Path(%r) / (name + '.json')).read_text())
assert int(os.environ['APROF_SHARED_REPEAT']) == (100 if mode == 'pilot' else 200)
assert pathlib.Path(os.environ['APROF_SHARED_COMMANDS']).read_text() == (
    'prime 0 pilot\\nsample 1 pilot 0\\nsample 2 pilot 1\\nsample 3 pilot 2\\nfinish 4\\n'
    if mode == 'pilot' else pathlib.Path(%r).read_text())
raw = profile / 'PROF_SYNTH/device_0/data/raw'
raw.parent.mkdir(parents=True)
raw.write_bytes(b'raw bytes')
log = profile / 'PROF_SYNTH/mindstudio_profiler_log/collection_host.log'
log.parent.mkdir(parents=True)
log.write_bytes(b'collection\\n')
if %r == 'early_csv':
    table = profile / 'PROF_SYNTH/mindstudio_profiler_output/op_summary.csv'
    table.parent.mkdir(parents=True)
    table.write_bytes(b'premature table')
for role in ('baseline', 'candidate'):
    (directory / (role + '.bin')).write_bytes(b'correct')
pathlib.Path(sys.argv[sys.argv.index('--output') + 1]).write_bytes(b'correct')
affinity = sorted(os.sched_getaffinity(0))
for message in messages:
    message['pid'] = os.getpid()
    if message['kind'] == 'ready': message['cpu_affinity'] = affinity
    if message['kind'] in ('pilot_sample', 'pair'):
        for sample in (message['baseline'], message.get('candidate')) if message['kind'] == 'pair' else (message['baseline'],):
            if sample is not None: sample['cpu_before'] = sample['cpu_after'] = affinity[0]
    print('APROF_SHARED_TIMING_JSON:' + json.dumps(message, sort_keys=True), flush=True)
""" % (str(templates), str(templates / "commands.txt"), mutation))
    cann = tmp_path / "cann"
    profiler_path = cann / "tools/profiler/bin/msprof"
    profiler_path.parent.mkdir(parents=True)
    profiler = executable(profiler_path, "print('unused native profiler entry')\n")
    summary_entry = cann / "tools/profiler/profiler_tool/analysis/msprof/msprof.py"
    summary_entry.parent.mkdir(parents=True)
    summary_entry.write_text("""
import os, pathlib, shutil, sys
assert not any(name.startswith('APROF_') for name in os.environ)
args = sys.argv[1:]
assert args[:2] == ['export', 'summary']
assert args[2] == '-dir' and args[4:] == ['--format', 'csv']
prof = pathlib.Path(args[3])
name = prof.parent.parent.name
table = prof / 'mindstudio_profiler_output/op_summary.csv'
table.parent.mkdir(parents=True)
shutil.copyfile(pathlib.Path(%r) / (name.replace('case-01-', '') + '.csv'), table)
(prof / 'mindstudio_profiler_log/collection_host.log').open('ab').write(b'export\\n')
if %r == 'changed_raw': (prof / 'device_0/data/raw').write_bytes(b'changed')
""" % (str(templates), mutation))
    (templates / "commands.txt").write_text("\n".join(collector.protocol_commands()) + "\n")
    smi = executable(tmp_path / "npu-smi", "print('synthetic board probe')\n")
    install = cann / (os.uname().machine + "-linux/ascend_toolkit_install.info")
    install.parent.mkdir(parents=True)
    install.write_text("synthetic CANN")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("ASCEND_HOME_PATH", str(cann))
    dependency = tmp_path / "dependency"
    dependency.write_text("fixed compiler")
    monkeypatch.setattr(admission, "_CANN", str(cann))
    monkeypatch.setattr(admission, "PROFILE_DEPENDENCY_PATHS",
                        (profiler, str(dependency), str(collector.SUMMARY_PYTHON), str(summary_entry)))
    monkeypatch.setattr(admission, "SUMMARY_ENTRY", str(summary_entry))
    monkeypatch.setattr(collector, "SUMMARY_ENTRY", summary_entry)
    python = str(Path(sys.executable).resolve())
    config = {"schema_version": "1.0.0", "operator": "exp", "run_id": "cpu-run",
        "session_id": "cpu-session", "candidate_id": "candidate", "device": 0, "physical_device": 0,
        "expected_case_ids": [1], "roles": {
            "baseline": {"source_dir": str(baseline), "symbol": "baseline_callback", "launches_per_operator": 1},
            "candidate": {"source_dir": str(candidate), "symbol": "candidate_callback", "launches_per_operator": 1}},
        "build": {"source_dir": str(build), "binary": native, "receipt_files": [str(build / "build.json")]},
        "cases": [{"case_id": 1, "workload": {"shape": [1024], "dtype": "float32"},
            "prepared_files": [str(prepared)], "command": [native, "--output-dir", "{cycle_dir}",
                                                        "--output", "{cycle_dir}/final.bin"],
            "verify_commands": {role: [python, str(verifier), "--case-id", "1",
                "--output", "{cycle_dir}/" + role + ".bin",
                "--result", "{cycle_dir}/" + role + "-result.json"] for role in ("baseline", "candidate")},
            "output_files": {role: ["{cycle_dir}/" + role + ".bin"] for role in ("baseline", "candidate")}}],
        "task_profile": {"profiler": profiler, "scratch_root": str(tmp_path / "scratch"),
            "role_kernel_names": {"baseline": ["exp_kernel"], "candidate": ["exp_kernel"]}}}
    for name, mode, cycle in [("pilot", "pilot", 0),
                              *((f"cycle-{index}", "confirmation", index) for index in range(6))]:
        repeat = 100 if mode == "pilot" else 200
        ready, events = pilot_wire(config) if mode == "pilot" else wire(config, cycle, repeat=repeat)
        messages = [ready, *(item["message"] for item in events)]
        (templates / (name + ".json")).write_text(json.dumps(messages))
        (templates / (name + ".csv")).write_text(table(rows_for(
            messages, config["task_profile"]["role_kernel_names"], mode, cycle, repeat,
            pilot_durations=("50",) * 3)))
    readers = []
    def local_reader(directory):
        reader = LocalEvidence(directory)
        readers.append(reader)
        return reader
    monkeypatch.setattr(collector, "LocalEvidence", local_reader)
    def forbidden_archive(*args, **kwargs):
        pytest.fail("online local measurement reached database, CAS, or profile copy")
    monkeypatch.setattr(sqlite3, "connect", forbidden_archive)
    monkeypatch.setattr(store_module.EpisodeStore, "__init__", forbidden_archive)
    monkeypatch.setattr(store_module, "_object_path", forbidden_archive)
    monkeypatch.setattr(collector, "copy_profile_tree", forbidden_archive)
    snapshots = []
    snapshot_file = LocalEvidence.snapshot_file
    def observe_log_snapshot(self, path):
        snapshots.append(str(path))
        assert collector.COLLECTION_LOG.fullmatch(Path(path).relative_to(Path(path).parents[2]).as_posix())
        return snapshot_file(self, path)
    monkeypatch.setattr(LocalEvidence, "snapshot_file", observe_log_snapshot)
    replayed = []
    replay = admission.replay_task_window_measurement_admission
    real_time = time
    offset = [0.0]
    clock = types.SimpleNamespace(time=real_time.time, monotonic_ns=real_time.monotonic_ns,
                                  monotonic=lambda: real_time.monotonic() + offset[0])
    monkeypatch.setattr(collector, "time", clock)
    def replay_then_exhaust(*args, **kwargs):
        value = replay(*args, **kwargs)
        replayed.append(value["valid"])
        if scenario == "replay_timeout": offset[0] = 121.0
        return value
    monkeypatch.setattr(admission, "replay_task_window_measurement_admission", replay_then_exhaust)
    output = tmp_path / "collection"
    if scenario == "handoff_timeout":
        monkeypatch.setattr(collector.old, "time", clock)
        write_index = LocalEvidence.write_index
        def finish_after_budget(reader, path):
            result = write_index(reader, path)
            offset[0] = 121.0
            return result
        monkeypatch.setattr(LocalEvidence, "write_index", finish_after_budget)
        with pytest.raises(TimeoutError):
            collector.collect_local(config, output, timeout_seconds=120)
        completion = json.loads((output / "local-result.json").read_text())
        assert completion["status"] == "failed" and "handoff" in completion["error"]["message"]
        refs = json.loads((output / "artifacts.json").read_text())
        reopened = LocalEvidence.from_index(output / "local-evidence-index.json")
        with pytest.raises(StoreError, match="changed"):
            reopened.verify_artifact(refs["measurement_admission"])
        assert json.loads((output / "measurement_report.json").read_text())["stable"] is True
        return
    result = collector.collect_local(config, output, timeout_seconds=120)
    completion = json.loads((output / "local-result.json").read_text())
    proof = json.loads((output / "measurement-proof.json").read_text())
    raw = json.loads((output / "raw_measurements.json").read_text())
    artifacts = json.loads((output / "artifacts.json").read_text())
    assert artifacts["measurement_admission"] == result["measurement_admission_ref"]
    assert readers[0].verify_artifact(result["measurement_admission_ref"]) == output / "local-result.json"
    assert completion["kind"] == "local_measurement_completion"
    assert completion["proof_ref"] == readers[0].register_artifact(output / "measurement-proof.json")
    assert (output / "local-evidence-index.json").is_file()
    assert not list(tmp_path.rglob("*.db")) and not list(tmp_path.rglob("*.objects"))
    assert not list(tmp_path.rglob("profile-persistence.json"))
    assert not list(tmp_path.rglob("scratch-reclamation.json"))
    assert snapshots
    if scenario in {"early_csv", "changed_raw"}:
        assert completion["status"] == result["status"] == "failed"
        assert ("unexpectedly contains" if scenario == "early_csv" else "modified a captured non-log profile file") in completion["error"]["message"]
        assert not raw["complete"] and not replayed
        assert (tmp_path / "scratch/case-01-pilot/profile").is_dir()
    else:
        assert replayed == [True]
        assert raw["complete"] is True and len(raw["sessions"]) == 6
        calibration = json.loads((output / "calibration.json").read_text())
        assert raw["repeat_by_case"] == {"1": 200}
        for session in [calibration["cases"][0]["pilot"], *raw["sessions"]]:
            directory = Path(session["cycle_dir"])
            assert (tmp_path / "scratch" / directory.name / "profile/PROF_SYNTH/device_0/data/raw").read_bytes() == b"raw bytes"
            assert not (directory / "profile").exists()
            assert "profile_persistence_ref" not in session
            assert not (directory / "final.bin").exists()
            assert (directory / "baseline.bin").read_bytes() == (directory / "candidate.bin").read_bytes() == b"correct"
        if scenario == "success":
            assert completion["status"] == result["status"] == "passed"
            assert result["report"]["stable"] is True and completion["error"] is None
            reopened = LocalEvidence.from_index(result["local_index"])
            checked = entry.replay_current_measurement_admission(reopened, result["measurement_admission_ref"], expected={"operator": "exp"})
            assert checked["valid"] and len(checked["gate_projection"]["baseline_samples_ns"]) == 30
            # Reopening the handoff preserves original paths; only mutable log prefixes are copied.
            for source in (prepared, Path(native), baseline / "kernel.cpp", candidate / "kernel.cpp"):
                digest = collector.file_hash(source)
                assert reopened.verify_artifact(digest) == source
            session = raw["sessions"][0]
            captured = json.loads(reopened.verify_artifact(session["capture_files_ref"]).read_text())
            final = json.loads(reopened.verify_artifact(session["profile_files_ref"]).read_text())
            log = "PROF_SYNTH/mindstudio_profiler_log/collection_host.log"
            assert reopened.verify_artifact(captured[log]).read_bytes() == b"collection\n"
            assert reopened.verify_artifact(final[log]).read_bytes() == b"collection\nexport\n"
            original = reopened.verify_artifact(final["PROF_SYNTH/device_0/data/raw"])
            original.write_bytes(b"mutated after handoff")
            with pytest.raises(StoreError, match="local evidence changed"):
                reopened.verify_artifact(final["PROF_SYNTH/device_0/data/raw"])
        else:
            assert completion["status"] == result["status"] == "failed"
            assert completion["elapsed_seconds"] > completion["timeout_seconds"]
            assert completion["error"]["type"] == "TimeoutError"
            assert json.loads(readers[0].verify_artifact(proof["measurement_report_ref"]).read_text())["stable"] is True
    if scenario != "success":
        assert not result["report"]["stable"]
        assert all(not values for values in result["report"]["gate_projection"].values())
        with pytest.raises(ContractError, match="completed passing local job"):
            entry.replay_current_measurement_admission(readers[0], result["measurement_admission_ref"], expected={"operator": "exp"})


@pytest.mark.parametrize("explicit", (False, True))
def test_cli_local_output_and_no_store_argument(tmp_path, monkeypatch, capsys, explicit):
    config = tmp_path / "config.json"; config.write_text('{"sentinel": true}')
    requested = tmp_path / "explicit-work"
    argv = ["collector", "--config", str(config)]
    if explicit: argv += ["--output", str(requested)]
    monkeypatch.setattr(sys, "argv", argv)
    created = []
    mkdtemp = collector.tempfile.mkdtemp
    def local_temporary(*, prefix):
        assert not explicit
        value = mkdtemp(prefix=prefix, dir=tmp_path)
        created.append(Path(value))
        return value
    monkeypatch.setattr(collector.tempfile, "mkdtemp", local_temporary)
    def capture_local(value, output, *, timeout_seconds):
        assert value == {"sentinel": True} and timeout_seconds == 3600
        assert not output.exists()
        if explicit: assert output == requested
        else:
            assert output == created[0] / "work"
            assert output.parent.stat().st_mode & 0o777 == 0o700
        return {"status": "passed"}
    monkeypatch.setattr(collector, "collect_local", capture_local)
    assert collector.main() == 0
    response = json.loads(capsys.readouterr().out)
    assert response["authority"] == "local_online_measurement"
    assert Path(response["result"]).name == "local-result.json"
    assert explicit or created[0].is_dir()


def test_cli_records_initialization_failure_without_admission(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.json"; config.write_text('{}')
    output = tmp_path / "work"
    monkeypatch.setattr(sys, "argv", ["collector", "--config", str(config), "--output", str(output)])
    def fail(*args, **kwargs):
        output.mkdir()
        raise ValueError("source identity failed")
    monkeypatch.setattr(collector, "collect_local", fail)
    assert collector.main() == 2
    failure = json.loads((output / "local-failure.json").read_text())
    assert failure["kind"] == "local_measurement_failure" and failure["status"] == "failed"
    assert not (output / "local-result.json").exists()


@pytest.mark.parametrize("mutation", ("source_changed", "fsync_failure"))
def test_parallel_copy_failure_keeps_partial_and_does_not_publish(tmp_path, monkeypatch, mutation):
    source = tmp_path / "source"
    (source / "raw/nested").mkdir(parents=True)
    (source / "empty_directory").mkdir()
    for index in range(12):
        (source / "raw/nested" / str(index)).write_bytes(bytes([index]) * (index + 1))
    (source / "empty_file").write_bytes(b"")
    deadline = time.monotonic() + 30
    inventory = collector.old.profile_inventory(source, deadline=deadline)
    destination = tmp_path / "destination"
    if mutation == "source_changed":
        original = collector.profile_inventory
        calls = 0
        def inventory_with_mutation(path, *, deadline):
            nonlocal calls
            calls += 1
            if calls == 3:
                (source / "raw/nested/0").write_bytes(b"changed")
            return original(path, deadline=deadline)
        monkeypatch.setattr(collector, "profile_inventory", inventory_with_mutation)
    else:
        def refuse_fsync(descriptor):
            raise OSError("synthetic fsync failure")
        monkeypatch.setattr(collector.os, "fsync", refuse_fsync)
    with pytest.raises((ValueError, OSError), match="inventory changed|fsync failure"):
        collector.copy_profile_tree(source, destination, inventory, deadline=deadline)
    assert not destination.exists()
    assert destination.with_name("destination.partial").is_dir()
    assert source.is_dir()
