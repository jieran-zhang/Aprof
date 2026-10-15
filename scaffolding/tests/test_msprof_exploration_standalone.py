"""All native commands, locks and health queries are replaced with CPU fixtures."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scaffolding/collection/scripts"))
import msprof_exploration_standalone as standalone


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=True))


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    task = tmp_path / "train/tasks/mish"
    baseline = task / "baseline"
    (baseline / "op_host").mkdir(parents=True)
    (baseline / "op_host/mish.asc").write_text("frozen original host")
    verifier = baseline / "scripts/verify_result.py"
    verifier.parent.mkdir(); verifier.write_text("# unchanged original oracle\n")
    binary = tmp_path / "build/standalone"
    binary.parent.mkdir(); binary.write_bytes(b"mock rebuilt binary")
    manifest = tmp_path / "build/build_manifest.json"
    save(manifest, {"operator": "mish", "standalone": standalone.pointer(binary)})
    inputs = tmp_path / "frozen-inputs"
    rows = []
    for case in standalone.ALL_CASES:
        source = inputs / f"case_{case:02d}/input.bin"
        source.parent.mkdir(parents=True); source.write_bytes(b"input" + bytes([case]))
        golden = source.parent / "golden.bin"; golden.write_bytes(b"golden")
        metadata = source.parent / "metadata.json"
        save(metadata, {"numel": case * 10, "dtype": "float32", "input": str(source), "golden": str(golden),
                        "output": str(source.parent / "unused-output.bin"), "legacy_special": float("inf")})
        rows.append({"case_id": case, "metadata": standalone.pointer(metadata), "inputs": {"input": standalone.pointer(source)},
                     "oracle_file": standalone.pointer(golden), "verifier": standalone.pointer(verifier)})
    save(task / "input-bindings.json", {"cases": rows})
    trace = {"active": False, "calls": [], "health": [], "failure": None, "post_health_failure": False, "no_output": False,
             "mutate_verifier": False, "mutate_input": False, "launch_failure": False}
    @contextmanager
    def lock():
        assert not trace["active"]
        trace["active"] = True
        try:
            yield
        finally:
            trace["active"] = False
    def health(path):
        assert trace["active"]
        trace["health"].append(path.name)
        save(path, {"status": "passed", "no_device_processes": True})
        if trace["post_health_failure"] and path.name == "health-after.json":
            raise RuntimeError("post health failed")
    def run(argv, cwd, out, **kwargs):
        assert trace["active"]
        argv = list(map(str, argv))
        trace["calls"].append({"argv": argv, "cwd": str(cwd), "out": out, **kwargs})
        out.mkdir(parents=True, exist_ok=False)
        native = out.name == "native"
        fail = trace["failure"] == ("native" if native else "verify")
        launch_fail = native and trace["launch_failure"]
        record = {"argv": argv, "cwd": str(cwd), "status": "failed" if fail or launch_fail else "passed",
                  "exit_status": None if launch_fail else 1 if fail else 0}
        save(out / "started.json", {"argv": argv})
        (out / "stdout.log").write_text("retained stdout")
        (out / "stderr.log").write_text("retained stderr")
        save(out / "execution.json", record)
        if fail or launch_fail:
            raise RuntimeError("fixture command failure")
        if native:
            if not trace["no_output"]:
                Path(argv[argv.index("--output") + 1]).write_bytes(b"output")
            if trace["mutate_verifier"]:
                verifier.write_text("changed oracle")
        else:
            metadata = json.loads(Path(argv[-1]).read_text())
            assert Path(metadata["output"]).read_bytes() == b"output"
            if trace["mutate_input"]:
                Path(metadata["input"]).write_bytes(b"mutated input")
    monkeypatch.setattr(standalone, "exclusive_host", lock)
    monkeypatch.setattr(standalone, "health", health)
    monkeypatch.setattr(standalone, "run_process", run)
    return task, manifest, inputs, tmp_path / "result", trace


def run(fixture, **kwargs):
    return standalone.correctness(*fixture[:4], **kwargs)


def completion(fixture):
    return json.loads((fixture[3] / "completion.json").read_text())


def test_full_standalone_and_original_oracle_run_once_each_without_touching_inputs(fixture):
    task, manifest, inputs, out, trace = fixture
    before = {str(path): path.read_bytes() for path in inputs.rglob("*") if path.is_file()}
    verifier_before = (task / "baseline/scripts/verify_result.py").read_bytes()
    result = run(fixture)
    assert result["status"] == "passed" and result["passed_count"] == 20
    assert result["native_started"] is True and result["prepared_path_validated_here"] is False
    assert result["performance_evaluated"] is False and result["episode_ref"] is None
    assert len(trace["calls"]) == 40
    assert trace["health"] == ["health-before.json", "health-after.json"]
    assert not trace["active"]
    counts = result["actual_costs"]
    assert counts["native_processes_attempted"] == counts["native_processes_started"] == counts["native_processes_completed"] == 20
    assert counts["verifier_processes_started"] == counts["standalone_complete_calls"] == 20
    binary = json.loads(manifest.read_text())["standalone"]["path"]
    for index, call in enumerate(trace["calls"]):
        if index % 2 == 0:
            assert call["argv"][0] == binary
            assert call["argv"][-2:] == ["--device", "0"]
            assert call["cwd"] == str(task / "baseline")
            assert "extra_env" not in call  # No event timing or profiling mode.
        else:
            assert call["argv"][:3] == [sys.executable, "-B", str(task / "baseline/scripts/verify_result.py")]
    assert before == {str(path): path.read_bytes() for path in inputs.rglob("*") if path.is_file()}
    assert (task / "baseline/scripts/verify_result.py").read_bytes() == verifier_before
    assert json.loads((out / "case_01/verification-metadata.json").read_text())["legacy_special"] == float("inf")
    assert completion(fixture) == result


@pytest.mark.parametrize("failure", ["native", "verify"])
def test_failure_keeps_logs_case_completion_and_costs_without_continuing(fixture, failure):
    fixture[-1]["failure"] = failure
    with pytest.raises(RuntimeError, match="fixture command"):
        run(fixture)
    record = completion(fixture)
    assert record["status"] == "failed" and record["passed_count"] == 0
    assert record["actual_costs"]["native_processes_started"] == 1
    assert record["actual_costs"]["native_processes_completed"] == (failure == "verify")
    assert len(fixture[-1]["calls"]) == (1 if failure == "native" else 2)
    assert (fixture[3] / "case_01/native/stderr.log").read_text() == "retained stderr"
    assert json.loads((fixture[3] / "case_01/correctness.json").read_text())["error"]
    assert not (fixture[3] / "case_02").exists()
    assert fixture[-1]["health"][-1] == "health-after.json"


def test_pre_popen_failure_is_attempted_but_not_started_native(fixture):
    fixture[-1]["launch_failure"] = True
    with pytest.raises(RuntimeError):
        run(fixture)
    record = completion(fixture)
    assert record["native_started"] is False
    assert record["actual_costs"]["native_processes_attempted"] == 1
    assert record["actual_costs"]["native_processes_started"] == 0


@pytest.mark.parametrize("fault", ["binary", "metadata", "input", "verifier", "case_binding", "operator"])
def test_frozen_identity_tampering_never_starts_process(fixture, fault):
    task, manifest, inputs, _, trace = fixture
    if fault == "binary":
        Path(json.loads(manifest.read_text())["standalone"]["path"]).write_bytes(b"changed")
    elif fault in {"metadata", "input"}:
        (inputs / "case_01" / ("metadata.json" if fault == "metadata" else "input.bin")).write_text("changed")
    elif fault == "verifier":
        (task / "baseline/scripts/verify_result.py").write_text("changed")
    elif fault == "case_binding":
        value = json.loads((task / "input-bindings.json").read_text()); value["cases"].pop()
        save(task / "input-bindings.json", value)
    else:
        value = json.loads(manifest.read_text()); value["operator"] = "exp"; save(manifest, value)
    with pytest.raises(ValueError):
        run(fixture)
    assert not trace["calls"]
    assert completion(fixture)["status"] == "failed"


@pytest.mark.parametrize("change", ["mutate_verifier", "mutate_input", "no_output", "post_health_failure"])
def test_during_execution_integrity_and_post_health_failures_preserved(fixture, change):
    fixture[-1][change] = True
    with pytest.raises((RuntimeError, ValueError)):
        run(fixture)
    assert completion(fixture)["status"] == "failed"
    if change == "mutate_verifier":
        assert len(fixture[-1]["calls"]) == 1
    if change == "post_health_failure":
        assert completion(fixture)["passed_count"] == 20
        assert completion(fixture)["health_error"]["message"] == "post health failed"


def test_existing_result_cannot_be_reused_and_subset_cannot_claim_correctness(fixture):
    with pytest.raises(ValueError, match="all twenty"):
        run(fixture, cases=[1, 8, 14, 20])
    assert not fixture[3].exists()
    run(fixture)
    before = {str(path): path.read_bytes() for path in fixture[3].rglob("*") if path.is_file()}
    calls = len(fixture[-1]["calls"])
    with pytest.raises(FileExistsError):
        run(fixture)
    assert len(fixture[-1]["calls"]) == calls
    assert before == {str(path): path.read_bytes() for path in fixture[3].rglob("*") if path.is_file()}


def test_foreign_oracle_rejected_even_with_valid_hash(fixture):
    task = fixture[0]
    foreign = task / "candidate-verifier.py"; foreign.write_text("different oracle")
    value = json.loads((task / "input-bindings.json").read_text())
    value["cases"][0]["verifier"] = standalone.pointer(foreign)
    save(task / "input-bindings.json", value)
    with pytest.raises(ValueError, match="original task baseline verifier"):
        run(fixture)
    assert not fixture[-1]["calls"]


def test_explicit_reuse_calls_real_original_main_twenty_times_with_zero_new_verifier_processes(fixture):
    task, _, _, output, trace = fixture
    verifier = task / "baseline/scripts/verify_result.py"
    source = '''import argparse, json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', required=True)
    args = parser.parse_args()
    metadata = json.loads(Path(args.metadata).read_text())
    assert Path(metadata['output']).read_bytes() == b'output'
    (Path(args.metadata).parent / 'original-main-proof.json').write_text(json.dumps({'main_ran': True}))
    print('original oracle full main passed')

if __name__ == '__main__': main()
'''
    verifier.write_text(source)
    binding = json.loads((task / "input-bindings.json").read_text())
    for row in binding["cases"]:
        row["verifier"] = standalone.pointer(verifier)
    save(task / "input-bindings.json", binding)
    affinity = os.sched_getaffinity(0)
    result = run(fixture, reuse_verifier=True, cpu=str(min(affinity)))
    assert len(trace["calls"]) == 20 and all(call["out"].name == "native" for call in trace["calls"])
    assert result["actual_costs"]["verifier_calls"] == result["actual_costs"]["verifier_call_attempts"] == 20
    assert all(result["actual_costs"][key] == 0 for key in ("verifier_processes_started", "verifier_processes_completed", "verifier_processes_attempted"))
    assert verifier.read_text() == source and os.sched_getaffinity(0) == affinity
    assert len(list(output.glob("case_*/original-main-proof.json"))) == 20
    assert json.loads((output / "request.json").read_text())["oracle_execution_mode"] == "in_process_original_verifier_v1"
    for path in output.glob("case_*/verify.execution.json"):
        row = json.loads(path.read_text())
        assert row["verifier_calls"] == 1 and row["new_process_started"] is False


@pytest.mark.parametrize("operator", __import__("level2_adapters").OPERATORS)
def test_level2_frozen_prepare_recognizes_every_reviewed_host(fixture, operator):
    task, manifest, inputs, output, trace = fixture
    (task / "baseline/op_host/mish.asc").rename(task / "baseline/op_host" / (operator + ".asc"))
    build = json.loads(manifest.read_text()); build["operator"] = operator; save(manifest, build)
    _, actual, _, _, cases, _ = standalone._prepare(task, manifest, inputs, standalone.ALL_CASES)
    assert actual == operator and len(cases) == 20
    assert not trace["calls"] and not output.exists()


def test_level2_maximum_standalone_runs_all_bound_commands_without_legacy_detection(fixture):
    task, manifest, inputs, output, trace = fixture
    (task / "baseline/op_host/mish.asc").rename(task / "baseline/op_host/maximum.asc")
    build = json.loads(manifest.read_text()); build["operator"] = "maximum"; save(manifest, build)
    bindings = json.loads((task / "input-bindings.json").read_text())
    for row in bindings["cases"]:
        path = Path(row["metadata"]["path"]); metadata = json.loads(path.read_text())
        metadata.update(x1=metadata["input"], x2=metadata["golden"], input_shapes=[[3, 1], [1, 4]])
        save(path, metadata); row["metadata"] = standalone.pointer(path)
    save(task / "input-bindings.json", bindings)
    result = run(fixture)
    assert result["status"] == "passed" and result["passed_count"] == 20
    assert all("--x1-shape" in call["argv"] for call in trace["calls"][::2])
    assert result["actual_costs"]["standalone_complete_calls"] == 20
