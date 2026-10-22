from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
from single_role_task import PROTOCOL, collect, sha256
from fast_task_screen import compare
from aprof_runtime.unified_timing import replay_capture


def capture_config(root):
    root.mkdir()
    files = {}
    for name in ("kernel.cpp", "adapter.cpp", "binary", "compiler", "probe.py", "oracle.py", "msprof.py"):
        path = root / name
        path.write_text(name)
        files[name] = str(path)
    for name in ("input.bin", "expected.bin"):
        path = root / name
        path.write_bytes(struct.pack("<ff", 1.0, 2.0))
        files[name] = str(path)
    declaration = root / "declaration.json"
    declaration.write_text(json.dumps({"schema_version": 1, "operator": "test",
        "created_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "case_ids": [1], "correctness_case_ids": [1],
        "reuse_policy": {"max_age_seconds": 3600, "max_ab_gap_seconds": 3600}}))
    python = str(Path(sys.executable).resolve())
    return {"schema_version": 1, "protocol": PROTOCOL, "operator": "test", "implementation": "complete_test",
        "source_files": [files["kernel.cpp"]], "binary": files["binary"], "adapter_files": [files["adapter.cpp"]],
        "toolchain_files": [files["compiler"]], "device": 0,
        "hardware_probe_command": [python, files["probe.py"]], "export_python": python, "export_script": files["msprof.py"],
        "declaration": {"path": str(declaration), "sha256": sha256(declaration)},
        "cache_policy": {"eviction_kernel": "CannBenchCacheClean", "eviction_bytes": 512,
                         "l2_bytes": 256, "address_policy": "reuse-one-allocation"},
        "cases": [{"case_id": 1, "workload": {"shape": [2], "oracle_limits": {"atol": 0, "rtol": 0, "equal_nan": False}},
                   "input_files": [files["input.bin"]], "kernel_names": ["first", "second"],
                   "command": [files["binary"], "profile"], "correctness_command": [files["binary"], "correctness"],
                   "oracle_command": [python, files["oracle.py"]], "oracle_source": files["oracle.py"],
                   "checks": [{"actual": "outputs/output.bin", "expected": files["expected.bin"],
                               "dtype": "float32", "atol": 0, "rtol": 0, "equal_nan": False}]}]}


class FakeRunner:
    def __init__(self, config, *, duration=80, fail=None, bad_count=False, extra_prof=False, wrong_output=False):
        self.config, self.duration, self.fail = config, duration, fail
        self.bad_count, self.extra_prof, self.wrong_output = bad_count, extra_prof, wrong_output
        self.calls = []

    def __call__(self, argv, *, cwd, env, timeout_seconds):
        root = Path(cwd)
        pid = 100 + len(self.calls)
        self.calls.append(list(argv))
        stdout = ""
        name = Path(argv[1]).name
        if name == "probe.py":
            stage = "hardware"
            stdout = json.dumps({"device": 0, "physical_device": "machine/npu0", "soc_version": "910C"})
        elif name in ("profile", "correctness"):
            stage = name
            output = root / "outputs/output.bin"
            output.write_bytes(struct.pack("<ff", 9.0 if self.wrong_output else 1.0, 2.0))
            if name == "profile":
                profile = Path(env["APROF_TASK_PROFILE_DIR"]) / "PROF_test"
                profile.mkdir()
                (profile / "raw.bin").write_bytes(b"raw task trace")
                if self.extra_prof:
                    (profile.parent / "PROF_extra").mkdir()
                native = {"protocol": PROTOCOL, "operator": "test", "implementation": "complete_test",
                    "case_id": int(env["APROF_TASK_CASE_ID"]), "capture_id": env["APROF_TASK_CAPTURE_ID"],
                    "pid": pid, "device": 0, "warmup_calls": 5, "formal_calls": 19 if self.bad_count else 20,
                    "l2_bytes": 256, "eviction_bytes": 512, "input_bytes_unchanged": True}
                stdout = "APROF_SINGLE_ROLE_TASK_JSON:" + json.dumps(native) + "\n"
            else:
                assert "APROF_TASK_PROFILE_DIR" not in env
        elif name == "msprof.py":
            stage = "export"
            profile = Path(argv[argv.index("-dir") + 1])
            rows = ["Op Name,OP Type,Task Duration(us),Stream ID"]
            for _ in range(20):
                rows.extend(["CannBenchCacheClean,CannBenchCacheClean,12,7",
                             f"first,Target,{self.duration / 2},7", f"second,Target,{self.duration / 2},7"])
            (profile / "kernel_details.csv").write_text("\n".join(rows) + "\n")
        elif name == "oracle.py":
            stage = "oracle"
            stdout = "original oracle passed\n"
        else:
            raise AssertionError(argv)
        return {"pid": pid, "stdout": stdout, "stderr": "", "returncode": 1 if self.fail == stage else 0}


def prepare_correctness(config, root):
    runner = FakeRunner(config)
    collect(config, root, runner=runner, correctness_only=True)
    path = root / "correctness.json"
    config["correctness"] = {"path": str(path), "sha256": sha256(path)}
    assert [Path(argv[1]).name for argv in runner.calls] == ["correctness", "oracle.py"]
    return path


def test_collect_replay_and_reuse_candidate_as_parent(tmp_path):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    collect(config, tmp_path / "a", runner=FakeRunner(config, duration=100))
    collect(config, tmp_path / "b", runner=FakeRunner(config, duration=80))
    collect(config, tmp_path / "c", runner=FakeRunner(config, duration=60))
    a, b, c = [tmp_path / name / "case_1/capture.json" for name in ("a", "b", "c")]
    result = replay_capture(b)
    assert result["values_us"] == [80] * 20
    assert "role" not in result["capture"]
    assert compare(a, b)["apparent_speedup"] == 1.25
    assert compare(b, c)["apparent_speedup"] == pytest.approx(4 / 3)


@pytest.mark.parametrize("option,message", [("bad_count", "native 采集"), ("extra_prof", "PROF 目录"),
                                           ("wrong_output", "oracle 原始输出")])
def test_capture_rejects_invalid_native_or_output(tmp_path, option, message):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    with pytest.raises(ValueError, match=message):
        collect(config, tmp_path / "bad", runner=FakeRunner(config, **{option: True}))
    assert (tmp_path / "bad/failure.json").is_file()


def test_native_failure_stops_before_export(tmp_path):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    runner = FakeRunner(config, fail="profile")
    with pytest.raises(ValueError, match="退出码非零"):
        collect(config, tmp_path / "bad", runner=runner)
    assert [Path(argv[1]).name for argv in runner.calls] == ["probe.py", "profile"]
    assert (tmp_path / "bad/case_1/logs/native.stdout").is_file()


def test_full_correctness_must_precede_any_timing(tmp_path):
    config = capture_config(tmp_path / "inputs")
    runner = FakeRunner(config)
    with pytest.raises(KeyError, match="correctness"):
        collect(config, tmp_path / "bad", runner=runner)
    assert not runner.calls
    with pytest.raises(ValueError, match="oracle 原始输出"):
        collect(config, tmp_path / "wrong", runner=FakeRunner(config, wrong_output=True), correctness_only=True)


def test_changed_binary_invalidates_prior_correctness(tmp_path):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    Path(config["binary"]).write_text("changed binary")
    runner = FakeRunner(config)
    with pytest.raises(ValueError, match="binary 与完整正确性"):
        collect(config, tmp_path / "bad", runner=runner)
    assert not runner.calls


def test_changed_golden_invalidates_prior_correctness(tmp_path):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    Path(config["cases"][0]["checks"][0]["expected"]).write_bytes(struct.pack("<ff", 3.0, 2.0))
    runner = FakeRunner(config)
    with pytest.raises(ValueError, match="golden 与完整正确性"):
        collect(config, tmp_path / "bad", runner=runner)
    assert not runner.calls


def test_raw_profile_and_output_tampering_fail_replay(tmp_path):
    config = capture_config(tmp_path / "inputs")
    prepare_correctness(config, tmp_path / "correctness")
    collect(config, tmp_path / "a", runner=FakeRunner(config))
    capture = tmp_path / "a/case_1/capture.json"
    raw = capture.parent / "profile/PROF_test/raw.bin"
    raw.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA256"):
        replay_capture(capture)


def test_oracle_cannot_rewrite_actual_output(tmp_path):
    config = capture_config(tmp_path / "inputs")

    class MutatingOracle(FakeRunner):
        def __call__(self, argv, **kwargs):
            result = super().__call__(argv, **kwargs)
            if Path(argv[1]).name == "oracle.py":
                (Path(kwargs["cwd"]) / "outputs/output.bin").write_bytes(struct.pack("<ff", 5.0, 2.0))
            return result

    with pytest.raises(ValueError, match="oracle 改写"):
        collect(config, tmp_path / "bad", runner=MutatingOracle(config), correctness_only=True)
    assert (tmp_path / "bad/case_1/logs/oracle.stdout").is_file()


def test_cases_share_private_snapshots_without_linking_user_sources(tmp_path):
    config = capture_config(tmp_path / "inputs")
    second = deepcopy(config["cases"][0])
    second["case_id"] = 2
    config["cases"].append(second)
    declaration = Path(config["declaration"]["path"])
    value = json.loads(declaration.read_text())
    value.update(case_ids=[1, 2], correctness_case_ids=[1, 2])
    declaration.write_text(json.dumps(value))
    config["declaration"]["sha256"] = sha256(declaration)
    collect(config, tmp_path / "correctness", runner=FakeRunner(config), correctness_only=True)
    first = tmp_path / "correctness/case_1/evidence/source/0000-kernel.cpp"
    second = tmp_path / "correctness/case_2/evidence/source/0000-kernel.cpp"
    assert first.stat().st_ino == second.stat().st_ino
    assert first.stat().st_ino != Path(config["source_files"][0]).stat().st_ino
    costs = json.loads((tmp_path / "correctness/collection_costs.json").read_text())
    assert costs["snapshot_copied_bytes"] < costs["snapshot_linked_bytes"]
    assert costs["elapsed_seconds"] >= costs["snapshot_seconds"] >= 0
