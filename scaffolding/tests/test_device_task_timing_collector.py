"""Synthetic CPU collection exercises Task CAS/oracle/replay, never hardware admission."""

import json
import os
import shutil
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.store import EpisodeStore
from aprof_runtime.task_measurement_admission import replay_task_measurement_admission
from aprof_runtime.task_timing import protocol_commands
from test_shared_measurement_admission import wire
from test_task_timing import table, task_rows

SCRIPTS = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
import device_task_timing as task_collector
from device_task_timing import collect


def executable(path, body):
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)
    return str(path)


@pytest.mark.parametrize("needs_export,cross_cycle_shift,tamper_csv", [
    (False, False, False), (True, False, False), (False, True, False), (False, False, True)])
def test_six_cycle_task_collector_and_raw_cas_replay(tmp_path, monkeypatch, needs_export, cross_cycle_shift, tamper_csv):
    bin_dir, build_dir, base_dir, cand_dir = (tmp_path / name for name in
                                             ("bin", "build-source", "baseline-source", "candidate-source"))
    for directory in (bin_dir, build_dir, base_dir, cand_dir):
        directory.mkdir()
    (base_dir / "kernel.cpp").write_text("baseline")
    (cand_dir / "kernel.cpp").write_text("candidate")
    release = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1"
    header = release / "skills/ascendc-aprof-profiling/assets/device_shared_timing.h"
    (build_dir / "device_shared_timing.h").write_bytes(header.read_bytes())
    (build_dir / "build.json").write_text("{}")
    prepared = tmp_path / "prepared.bin"
    prepared.write_bytes(b"input")
    templates = tmp_path / "templates"
    templates.mkdir()
    commands = tmp_path / "expected-commands.txt"
    commands.write_text("\n".join(protocol_commands()) + "\n")
    native = executable(build_dir / "fake-native", """
import json, os, pathlib, sys
directory = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])
cycle = int(os.environ['APROF_SHARED_CYCLE'])
assert os.environ['APROF_SHARED_MODE'] == 'confirmation'
assert os.environ['APROF_SHARED_REPEAT'] == '100'
assert pathlib.Path(os.environ['APROF_SHARED_COMMANDS']).read_text() == pathlib.Path(%r).read_text()
messages = json.loads(pathlib.Path(%r, f'messages-{cycle}.json').read_text())
affinity = sorted(os.sched_getaffinity(0))
for message in messages:
    message['pid'] = os.getpid()
    if message['kind'] == 'ready': message['cpu_affinity'] = affinity
    if message['kind'] == 'pair':
        for role in ('baseline', 'candidate'):
            message[role]['cpu_before'] = message[role]['cpu_after'] = affinity[0]
for role in ('baseline', 'candidate'):
    (directory / (role + '.bin')).write_bytes(b'correct')
for message in messages:
    print('APROF_SHARED_TIMING_JSON:' + json.dumps(message, sort_keys=True), flush=True)
""" % (str(commands), str(templates)))
    profiler = executable(bin_dir / "msprof", """
import os, pathlib, shlex, shutil, subprocess, sys
args = sys.argv[1:]
if '--export=on' in args:
    folder = pathlib.Path(next(a.split('=',1)[1] for a in args if a.startswith('--output='))) / 'mindstudio_profiler_output'
else:
    output = pathlib.Path(next(a.split('=',1)[1] for a in args if a.startswith('--output=')))
    application = shlex.split(next(a.split('=',1)[1] for a in args if a.startswith('--application=')))
    result = subprocess.run(application, env=os.environ, capture_output=True, text=True)
    print(result.stdout, end='')
    if result.returncode: raise SystemExit(result.returncode)
    folder = output / 'PROF_000001' / 'mindstudio_profiler_output'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'raw.prof').write_bytes(b'raw-profile')
if '--export=on' in args or not %r:
    shutil.copyfile(pathlib.Path(%r, 'tasks-' + os.environ['APROF_SHARED_CYCLE'] + '.csv'),
                    folder / 'op_summary.csv')
""" % (needs_export, str(templates)))
    executable(bin_dir / "npu-smi", "print('synthetic board probe')\n")
    verifier = tmp_path / "verify.py"
    verifier.write_text("""
import json, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
result = pathlib.Path(sys.argv[sys.argv.index('--result') + 1])
value = {'case_id': int(sys.argv[sys.argv.index('--case-id') + 1]),
         'passed': output.read_bytes() == b'correct'}
result.write_text(json.dumps(value))
print(json.dumps(value))
""")
    cann = tmp_path / "cann"
    info = cann / (os.uname().machine + "-linux") / "ascend_toolkit_install.info"
    info.parent.mkdir(parents=True)
    info.write_text("synthetic CANN install receipt")
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("ASCEND_HOME_PATH", str(cann))
    python = str(Path(sys.executable).resolve())
    config = {"schema_version": "1.0.0", "operator": "synthetic_exp", "run_id": "cpu-run",
        "session_id": "cpu-session", "candidate_id": "candidate", "device": 0, "physical_device": 0,
        "expected_case_ids": [1], "roles": {
            "baseline": {"source_dir": str(base_dir), "symbol": "baseline_callback", "launches_per_operator": 1},
            "candidate": {"source_dir": str(cand_dir), "symbol": "candidate_callback", "launches_per_operator": 1}},
        "build": {"source_dir": str(build_dir), "binary": native,
                  "receipt_files": [str(build_dir / "build.json")]},
        "cases": [{"case_id": 1, "workload": {"shape": [1024], "dtype": "float32"},
                   "prepared_files": [str(prepared)],
                   "command": [native, "--output-dir", "{cycle_dir}"],
                   "verify_commands": {role: [python, str(verifier), "--case-id", "1", "--output", "{cycle_dir}/" + role + ".bin",
                       "--result", "{cycle_dir}/" + role + "-result.json"]
                       for role in ("baseline", "candidate")},
                   "output_files": {role: ["{cycle_dir}/" + role + ".bin"]
                                    for role in ("baseline", "candidate")}}],
        "task_profile": {"profiler": profiler, "scratch_root": str(tmp_path / "local-scratch"),
                         "role_kernel_names": {"baseline": ["exp_kernel"],
                                               "candidate": ["exp_kernel"]}}}
    if cross_cycle_shift:
        second = deepcopy(config["cases"][0])
        second["case_id"] = 2
        for role in ("baseline", "candidate"):
            second["verify_commands"][role][3] = "2"
        config["cases"].append(second)
        config["expected_case_ids"].append(2)
    for cycle in range(6):
        ready, events = wire(config, cycle, repeat=100)
        messages = [ready, *(event["message"] for event in events)]
        (templates / f"messages-{cycle}.json").write_text(json.dumps(messages))
        rows = task_rows(messages, config["task_profile"]["role_kernel_names"])
        if cross_cycle_shift and cycle >= 3:
            for row in rows:
                row["Task Duration(us)"] = str(float(row["Task Duration(us)"]) * 1.25)
        (templates / f"tasks-{cycle}.csv").write_text(table(rows))
    original_profile_ref = task_collector._profile_ref
    profile_calls = []

    def counted_profile_ref(*args):
        profile_calls.append(1)
        return original_profile_ref(*args)

    monkeypatch.setattr(task_collector, "_profile_ref", counted_profile_ref)
    if tamper_csv:
        original_partition = task_collector.partition_task_samples

        def tampered_partition(table_path, *args, **kwargs):
            result = original_partition(table_path, *args, **kwargs)
            Path(table_path).write_text(Path(table_path).read_text() + "\n")
            return result

        monkeypatch.setattr(task_collector, "partition_task_samples", tampered_partition)
    with EpisodeStore(tmp_path / "store.db") as store:
        if tamper_csv:
            with pytest.raises(ValueError, match="Task table changed during parsing"):
                collect(config, tmp_path / "collection", store, timeout_seconds=120)
            raw = json.loads((tmp_path / "collection/raw_measurements.json").read_text())
            assert len(raw["sessions"]) == 1 and profile_calls == [1]
            return
        if cross_cycle_shift:
            with pytest.raises(ValueError, match="case 1: Task measurement controls failed"):
                collect(config, tmp_path / "collection", store, timeout_seconds=120)
            raw = json.loads((tmp_path / "collection/raw_measurements.json").read_text())
            assert raw["complete"] is False and len(raw["sessions"]) == 6
            assert "overall formal: CV exceeds 5%" in raw["error"]["message"]
            assert not (tmp_path / "collection/case-02-cycle-0").exists()
            assert all(session["control_summary"]["formal"]["baseline_cv"] == 0
                       for session in raw["sessions"])
            assert len(profile_calls) == 6
            return
        report = collect(config, tmp_path / "collection", store, timeout_seconds=120)
        assert report["stable"] is True
        receipt = json.loads((tmp_path / "collection/measurement_admission.json").read_text())
        raw = json.loads((tmp_path / "collection/raw_measurements.json").read_text())
        scratch = tmp_path / "local-scratch"
        assert scratch.stat().st_mode & 0o777 == 0o700
        registration = json.loads((tmp_path / "collection/registration.json").read_text())
        storage = json.loads(store.verify_artifact(registration["profile_storage_ref"]).read_text())
        assert storage["scratch_root"] == str(scratch)
        assert storage["mode"] == "local_profile_then_copy"
        for row in raw["sessions"]:
            local_profile = scratch / f"case-01-cycle-{row['cycle']}" / "profile"
            persistent_profile = tmp_path / "collection" / f"case-01-cycle-{row['cycle']}" / "profile"
            assert "--output=" + str(local_profile) in row["capture"]["argv"]
            assert persistent_profile.is_dir()
            transfer = json.loads(store.verify_artifact(row["profile_transfer_ref"]).read_text())
            assert transfer["source_dir"] == str(local_profile)
            assert transfer["destination_dir"] == str(persistent_profile)
            for key in ("source_inventory_ref", "persisted_inventory_ref", "source_after_inventory_ref"):
                assert json.loads(store.verify_artifact(transfer[key]).read_text())
            if needs_export:
                assert "--output=" + str(local_profile / "PROF_000001") in row["export"]["argv"]
        shutil.rmtree(scratch)
        assert not scratch.exists()
        result = replay_task_measurement_admission(store, store.register_artifact(
            tmp_path / "collection/measurement_admission.json"), expected={"operator": "synthetic_exp"})
        assert result["valid"] is True and result["metric"] == "msprof.op_summary.Task_Duration"
        assert len(raw["sessions"]) == 6
        assert all((row["export"] is not None) == needs_export for row in raw["sessions"])
        assert all((row["capture_files_ref"] != row["profile_files_ref"]) == needs_export
                   for row in raw["sessions"])
        assert len(profile_calls) == (12 if needs_export else 6)
        assert receipt["protocol"] == "shared_buffer_msprof_task_v2"


def test_profile_snapshot_rejects_nested_symlink_before_any_index(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "first.csv").write_text("task")
    (profile / "linked.csv").symlink_to(profile / "first.csv")
    with EpisodeStore(tmp_path / "store.db") as store:
        with pytest.raises(ValueError, match="symlink result refused"):
            task_collector.profile_files(profile, store)
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0
