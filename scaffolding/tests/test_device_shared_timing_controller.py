"""Real CPU subprocesses exercise controller cleanup, never hardware qualification.

The worker below only emits synthetic protocol messages; it does not import ACL,
launch kernels, or produce a performance/measurement admission receipt for release.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.errors import ContractError
from aprof_runtime.store import EpisodeStore

RELEASE = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1"
SCRIPT = RELEASE / "skills/ascendc-aprof-profiling/scripts/device_shared_timing.py"
spec = importlib.util.spec_from_file_location("shared_controller_cpu_fixture", SCRIPT)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)

WORKER = r'''
import json, os, struct, sys, time
from pathlib import Path
directory, behavior = sys.argv[1:]
cycle = int(os.environ['APROF_SHARED_CYCLE'])
mode = os.environ['APROF_SHARED_MODE']
repeat = int(os.environ['APROF_SHARED_REPEAT'])
roles = ['baseline', 'candidate']
affinity = sorted(os.sched_getaffinity(0))
common = dict(schema_version='1.0.0', protocol='shared_buffer_acl_event_v2',
    operator='synthetic_cpu_only', cycle_index=cycle, pid=os.getpid(), device=0,
    context_address='1000', stream_address='2000', warmup=10, repeat=repeat, mode=mode,
    warmup_role_counts={'baseline':20,'candidate':0} if mode=='pilot' else {'baseline':10,'candidate':10},
    prime_repeat=100, execution_mode='direct_enqueue',
    launches_per_operator={r: 1 for r in roles},
    role_symbols={r: r + '_callback' for r in roles},
    buffers=dict(inputs=[dict(name='input', address='10000', bytes=4096)],
                 outputs=[dict(name='output', address='20000', bytes=4096)], workspaces=[]))
def emit(kind, **fields):
    print('APROF_SHARED_TIMING_JSON:' + json.dumps(dict(common, kind=kind, **fields)), flush=True)
start = time.monotonic_ns()
emit('ready', warmup_started_monotonic_ns=start,
     warmup_finished_monotonic_ns=time.monotonic_ns(), cpu_affinity=affinity)
for line in sys.stdin:
    fields = line.split()
    if not fields or fields[0] == 'quit':
        sys.exit(8)  # Controller must complete or terminate this synthetic worker.
    action, index = fields[0], int(fields[1])
    start = time.monotonic_ns()
    if action == 'finish':
        checks = []
        for role in roles:
            begin = time.monotonic_ns()
            Path(directory, role + '.bin').write_text(role)
            checks.append(dict(role=role, implementation=role,
                scope='untimed_callback_verification', started_monotonic_ns=begin,
                finished_monotonic_ns=time.monotonic_ns()))
        emit('complete', command_index=index, untimed_verifications=checks,
             input_bytes_unchanged=True, **({'pilot_samples':3} if mode=='pilot' else {'pairs_per_phase':5}))
        break
    phase = fields[2]
    if action == 'prime':
        order = roles if cycle % 2 == 0 else list(reversed(roles))
        emit('prime', command_index=index, phase=phase,
             started_monotonic_ns=start, finished_monotonic_ns=time.monotonic_ns(),
             prime_order=(['candidate']*4 if behavior=='wrong_order' else ['baseline']*4) if mode=='pilot' else [order[0], order[1], order[1], order[0]])
        continue
    if action == 'sample':
        begin=time.monotonic_ns()
        sample=dict(implementation='baseline', launches_per_operator=1, elapsed_ms=.5,
            elapsed_ns=5000., started_monotonic_ns=begin, finished_monotonic_ns=time.monotonic_ns(),
            cpu_before=affinity[0], cpu_after=affinity[0])
        emit('pilot_sample', command_index=index+(1 if index==1 and behavior=='wrong_index' else 0),
             phase='pilot', sample_index=int(fields[3]), baseline=sample)
        continue
    pair = int(fields[3])
    order = roles if (cycle + pair) % 2 == 0 else list(reversed(roles))
    samples = {}
    for role in order:
        begin = time.monotonic_ns()
        milliseconds = struct.unpack('f', struct.pack('f', .005 * repeat))[0]
        if behavior == 'late_control_failure' and cycle == 5 and phase == 'aa_after' and pair == 4 and role == 'baseline':
            milliseconds *= 2
        samples[role] = dict(implementation=role if phase == 'formal' else 'baseline',
            launches_per_operator=1, elapsed_ms=milliseconds,
            elapsed_ns=milliseconds * 1e6 / repeat, started_monotonic_ns=begin,
            finished_monotonic_ns=time.monotonic_ns(), cpu_before=affinity[0], cpu_after=affinity[0])
    if index == 1 and behavior == 'wrong_index':
        index += 1
    if index == 1 and behavior == 'wrong_order':
        order = list(reversed(order))
    emit('pair', command_index=index, phase=phase, pair_index=pair, order=order,
         started_monotonic_ns=start, finished_monotonic_ns=time.monotonic_ns(), **samples)
'''

VERIFIER = r'''
import json, sys
from pathlib import Path
output, role, behavior, option, result_path = sys.argv[1:]
assert option=='--result'
assert Path(output).read_text() == role
passed = behavior not in ('verifier_exit', 'verifier_false')
result=dict(passed=passed, case_id=1, fixture='synthetic CPU output check')
Path(result_path).write_text(json.dumps(result))
print(json.dumps(result), flush=True)
sys.exit(3 if behavior == 'verifier_exit' else 0)
'''


@pytest.fixture
def controller(tmp_path, monkeypatch):
    # No real device, hardware probe, CANN install, or physical device lock is used.
    monkeypatch.setattr(timing, "device_lock", lambda *_: contextlib.nullcontext())
    for name in ("ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES"):
        monkeypatch.delenv(name, raising=False)
    npu_smi = tmp_path / "fake-npu-smi"
    npu_smi.write_text("synthetic CPU fixture; never executed")
    original_which = timing.shutil.which
    monkeypatch.setattr(timing.shutil, "which", lambda name: str(npu_smi) if name == "npu-smi" else original_which(name))
    monkeypatch.setattr(timing, "capture_process", lambda *args: {
        "argv": args[0], "exit_code": 0, "fixture": "synthetic CPU probe, not hardware evidence"})
    cann = tmp_path / "synthetic-cann"
    info = cann / (timing.platform.machine() + "-linux/ascend_toolkit_install.info")
    info.parent.mkdir(parents=True)
    info.write_text("synthetic install, not a toolchain qualification")
    monkeypatch.setenv("ASCEND_HOME_PATH", str(cann))
    build = tmp_path / "build"
    build.mkdir()
    binary = build / "fake-worker"
    binary.write_text("#!" + sys.executable + "\n" + WORKER)
    binary.chmod(0o755)
    verifier = build / "verify.py"
    verifier.write_text(VERIFIER)
    receipt = build / "build.txt"
    receipt.write_text("No build: synthetic Python worker only")
    prepared = tmp_path / "prepared.bin"
    prepared.write_text("immutable fixture input")
    value = dict(schema_version="1.0.0", operator="synthetic_cpu_only", run_id="cpu-fixture",
        session_id="cpu-fixture", candidate_id="cpu-fixture", device=0, physical_device=0,
        expected_case_ids=[1], roles={r: dict(source_dir=str(build), symbol=r + "_callback",
            launches_per_operator=1) for r in timing.ROLES},
        build=dict(source_dir=str(build), binary=str(binary), receipt_files=[str(receipt)]),
        cases=[dict(case_id=1, workload={"synthetic": True}, prepared_files=[str(prepared)],
            command=[str(binary), "{cycle_dir}", "normal"],
            verify_commands={r: [sys.executable, str(verifier), "{cycle_dir}/" + r + ".bin", r, "normal", "--result", "{cycle_dir}/" + r + "-result.json"] for r in timing.ROLES},
            output_files={r: ["{cycle_dir}/" + r + ".bin"] for r in timing.ROLES})])
    return value


@pytest.mark.parametrize("failure", ["wrong_index", "wrong_order", "verifier_exit", "verifier_false"])
def test_sampling_has_no_disk_writes_and_failure_stops_before_next_cycle(controller, tmp_path, monkeypatch, failure):
    """Exercise the real buffered stdout reader, controller loop, and child cleanup."""
    case = controller["cases"][0]
    if failure.startswith("wrong_"):
        case["command"][-1] = failure
    else:
        case["verify_commands"]["candidate"][-3] = failure
    output = tmp_path / "evidence"
    state = {"sampling": False, "children": [], "commands": 0, "buffered_bytes": 0}
    original_child, original_save, original_command = timing.TimingChild, timing.save, timing.command

    class GuardedLog:
        def __init__(self, log): self.log = log
        def __getattr__(self, key): return getattr(self.log, key)
        def writelines(self, lines):
            assert not state["sampling"], "stdout was flushed while sampling"
            self.log.writelines(lines)

    class ObservedChild(original_child):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.log = GuardedLog(self.log)
            state["children"].append(self)
            state["sampling"] = True
        def close(self, abort=False):
            state["sampling"] = False
            return super().close(abort=abort)

    def checked_save(*args, **kwargs):
        assert not state["sampling"], "raw/config/report was saved while sampling"
        return original_save(*args, **kwargs)

    def checked_command(child, text):
        assert child.path.stat().st_size == 0, "stdout contents landed before sampling ended"
        assert not (output / "raw_measurements.json").exists(), "raw landed before first cycle ended"
        result = original_command(child, text)
        assert child.path.stat().st_size == 0, "stdout reader wrote on the sampling path"
        state["commands"] += 1
        state["buffered_bytes"] = max(state["buffered_bytes"], child.log_bytes)
        return result

    monkeypatch.setattr(timing, "TimingChild", ObservedChild)
    monkeypatch.setattr(timing, "save", checked_save)
    monkeypatch.setattr(timing, "command", checked_command)
    with EpisodeStore(tmp_path / "cpu-only.sqlite") as store:
        register = store.register_artifact
        def checked_register(*args, **kwargs):
            assert not state["sampling"], "CAS disk write occurred while sampling"
            return register(*args, **kwargs)
        monkeypatch.setattr(store, "register_artifact", checked_register)
        with pytest.raises((ValueError, ContractError)):
            timing.collect(controller, output, store)
        raw = json.loads((output / "raw_measurements.json").read_text())
        assert not raw["complete"] and raw["error"]
        assert len(state["children"]) == 1 and raw["sessions"] == []
        assert not (output / "case-01-cycle-1").exists()
        run = json.loads((output / "calibration.json").read_text())["cases"][0]["pilot"]
        log = store.verify_artifact(run["stdout_ref"]).read_text()
        assert state["commands"] >= 1 and state["buffered_bytes"] > 0
        assert timing.PREFIX in log and '"kind": "ready"' in log
        assert run["events"] and run["execution"]["finished_at"] is not None
        if failure.startswith("verifier_"):
            receipt = run["verifications"]["candidate"]
            assert receipt["exit_status"] == (3 if failure == "verifier_exit" else 0)
            assert '"passed": false' in store.verify_artifact(receipt["log_ref"]).read_text()
    for child in state["children"]:
        assert child.process.poll() is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child.process.pid, 0)
    report = json.loads((output / "measurement_report.json").read_text())
    assert not report["stable"] and report["gate_projection"]["baseline_samples_ns"] == []


def test_calibration_freezes_once_before_all_fresh_confirmation_and_reuses_one_oracle(controller, tmp_path):
    output = tmp_path / "success"
    with EpisodeStore(tmp_path / "cpu-only.sqlite") as store:
        report = timing.collect(controller, output, store)
        raw = json.loads((output / "raw_measurements.json").read_text())
        calibration = json.loads((output / "calibration.json").read_text())
        registration = json.loads((output / "registration.json").read_text())
        worker = json.loads(store.verify_artifact(raw["verifier_worker_ref"]).read_text())
        assert report["stable"] and raw["complete"]
        assert len(calibration["cases"]) == 1
        item = calibration["cases"][0]
        assert item["median_ms"] == .5 and item["repeat"] == 10000
        assert registration["repeat_by_case"] == raw["repeat_by_case"] == {"1":10000}
        assert calibration["finished_at"] < registration["created_at"] < raw["started_at"]
        assert "repeat" not in registration
        sessions = [item["pilot"], *raw["sessions"]]
        assert len(sessions) == 7 and len({run["execution"]["pid"] for run in sessions}) == 7
        assert len({run["cycle_dir"] for run in sessions}) == 7
        assert all(run["ready"]["repeat"] == 10000 and run["mode"] == "confirmation" for run in raw["sessions"])
        assert item["pilot"]["ready"]["repeat"] == 100
        assert worker["status"] == "complete" and len(worker["request_refs"]) == 14
        assert {r["verifications"][role]["worker_id"] for r in sessions for role in timing.ROLES} == {worker["worker_id"]}
        assert [r["verifications"][role]["request_index"] for r in sessions for role in timing.ROLES] == list(range(14))
        assert all(r["execution"]["environment"]["APROF_SHARED_REPEAT"] == str(r["ready"]["repeat"]) for r in sessions)


def test_calibration_cap_is_failure_without_clamping_or_confirmation(controller, tmp_path):
    binary = Path(controller["build"]["binary"])
    binary.write_text(binary.read_text().replace("elapsed_ms=.5", "elapsed_ms=.03125").replace("elapsed_ns=5000.", "elapsed_ns=312.5"))
    output = tmp_path / "cap-failure"
    with EpisodeStore(tmp_path / "cpu-only.sqlite") as store:
        with pytest.raises((ValueError, ContractError)):
            timing.collect(controller, output, store)
    raw=json.loads((output/"raw_measurements.json").read_text())
    assert raw["complete"] is False and raw["sessions"] == []
    assert "repeat exceeds 100000 cap" in raw["error"]["message"]
    assert not (output/"registration.json").exists()
    assert not (output/"case-01-cycle-0").exists()


def test_trial_deadline_is_bounded_and_never_restarts_worker(controller, tmp_path):
    with EpisodeStore(tmp_path/"cpu-only.sqlite") as store:
        with pytest.raises(TimeoutError):
            timing.collect(controller, tmp_path/"timeout", store, timeout_seconds=1e-12)
    assert not (tmp_path/"timeout/case-01-cycle-0").exists()


def test_actual_collector_cas_replays_with_only_hardware_probe_mocked(controller, tmp_path, monkeypatch):
    from aprof_runtime import measurement_admission as admission
    build = Path(controller["build"]["source_dir"])
    (build/"device_shared_timing.h").write_bytes((RELEASE/"skills/ascendc-aprof-profiling/assets/device_shared_timing.h").read_bytes())
    monkeypatch.setattr(admission, "_hardware", lambda *_: {"fixture": "CPU-only; not hardware qualification"})
    output = tmp_path / "cas-replay"
    with EpisodeStore(tmp_path/"cpu-only.sqlite") as store:
        timing.collect(controller, output, store)
        artifacts=json.loads((output/"artifacts.json").read_text())
        result=admission.replay_measurement_admission(store, artifacts["measurement_admission"], expected={"operator":"synthetic_cpu_only"})
        assert result["valid"] and result["report"]["stable"]
        assert len(result["gate_projection"]["baseline_samples_ns"]) == 30


def test_last_cycle_control_failure_retains_every_sample_and_all_oracles(controller, tmp_path):
    controller["cases"][0]["command"][-1]="late_control_failure"
    output=tmp_path/"late-failure"
    with EpisodeStore(tmp_path/"cpu-only.sqlite") as store:
        with pytest.raises(ValueError, match="measurement control failed"):
            timing.collect(controller, output, store)
        raw=json.loads((output/"raw_measurements.json").read_text())
        assert raw["complete"] is False and len(raw["sessions"]) == 6
        assert all(len(run["events"]) == 19 and set(run["verifications"]) == {"baseline","candidate"} for run in raw["sessions"])
        assert raw["sessions"][-1]["control_summary"]["aa_after"]["baseline_cv"] > .05
        assert raw["sessions"][-1]["events"][-2]["message"]["baseline"]["elapsed_ms"] == 100.
        worker=json.loads(store.verify_artifact(raw["verifier_worker_ref"]).read_text())
        assert worker["status"] == "aborted" and len(worker["request_refs"]) == 14
        report=json.loads((output/"measurement_report.json").read_text())
        assert not report["stable"] and report["gate_projection"]["baseline_samples_ns"] == []


def test_oracle_start_deadline_preserves_original_error_before_directory_exists(controller, tmp_path, monkeypatch):
    class ExpiredOracle(timing.PersistentOracle):
        def start(self):
            raise TimeoutError("expired before oracle spawn")
    monkeypatch.setattr(timing, "PersistentOracle", ExpiredOracle)
    output = tmp_path/"worker-start-failure"
    with EpisodeStore(tmp_path/"cpu-only.sqlite") as store:
        with pytest.raises(TimeoutError, match="expired before oracle spawn"):
            timing.collect(controller, output, store)
    raw=json.loads((output/"raw_measurements.json").read_text())
    assert raw["error"] == {"type":"TimeoutError","message":"expired before oracle spawn"}
    assert raw["sessions"] == [] and raw["complete"] is False
    assert not (output/"oracle-worker").exists() and not (output/"registration.json").exists()
