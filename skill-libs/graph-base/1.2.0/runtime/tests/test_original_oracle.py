from copy import deepcopy
import json
from pathlib import Path
import shutil
import struct
import sys
import time

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.original_oracle import MODE, config_contract, contract, execute, OracleFailure
from aprof_runtime.unified_timing import file_hash, replay_capture, replay_oracle
from test_unified_capture import capture_config, FakeRunner
from single_role_task import collect, preflight


ORACLE = """import json
from pathlib import Path
actual = Path('out.bin').read_bytes()
expected = Path('golden.bin').read_bytes()
passed = actual == expected
Path('result.json').write_text(json.dumps({'passed': passed}))
raise SystemExit(0 if passed else 1)
"""


def ref(root, path):
    return {"path": str(path.relative_to(root)), "sha256": file_hash(path)}


def original_config(root, *, program=ORACLE):
    config = capture_config(root)
    case = config["cases"][0]
    Path(case["oracle_source"]).write_text(program)
    spec = {"mode": MODE, "entrypoint": "oracle.py", "argv": [],
            "files": {"oracle.py": case["oracle_source"], "golden.bin": case["checks"][0]["expected"]},
            "outputs": {"out.bin": {"actual": "outputs/output.bin", "dtype": "bfloat16"}},
            "result": {"path": "result.json", "passed_field": "passed"},
            "environment": {"python": str(Path(sys.executable).resolve()),
                            "sha256": file_hash(sys.executable), "packages": {}}, "timeout_seconds": 10}
    case["oracle_replay"] = spec
    case["workload"]["oracle_limits"] = {"mode": MODE, "contract_sha256": config_contract(spec)}
    del case["checks"], case["oracle_command"]
    return config


def retained(tmp_path, *, program=ORACLE):
    config = original_config(tmp_path / "input", program=program)
    root = tmp_path / "correctness"
    collect(config, root, correctness_only=True, runner=FakeRunner(config))
    case = root / "case_1"
    receipt = json.loads((case / "oracle_receipt.json").read_text())
    limits = config["cases"][0]["workload"]["oracle_limits"]
    return config, case, receipt, limits


def test_original_program_live_correctness_timing_and_portable_replay(tmp_path):
    config, root, receipt, limits = retained(tmp_path)
    correct = root.parent / "correctness.json"
    config["correctness"] = {"path": str(correct), "sha256": file_hash(correct)}
    collect(config, tmp_path / "timing", runner=FakeRunner(config))
    assert replay_capture(tmp_path / "timing/case_1/capture.json")["median_us"] == 80
    moved = tmp_path / "moved"
    shutil.copytree(root, moved)
    shutil.rmtree(tmp_path / "input")
    replay_oracle(moved, receipt, ref(moved, moved / "output.json"), limits)


def test_passed_receipt_does_not_override_original_failure(tmp_path):
    _, root, receipt, limits = retained(tmp_path)
    output = root / "outputs/output.bin"
    output.write_bytes(struct.pack("<ff", 9.0, 2.0))
    receipt["checks"][0]["actual"] = ref(root, output)
    (root / "output.json").write_text(json.dumps({"files": [ref(root, output)]}))
    receipt["output_sha256"] = file_hash(root / "output.json")
    with pytest.raises(OracleFailure, match="numerical_mismatch"):
        replay_oracle(root, receipt, ref(root, root / "output.json"), limits)


@pytest.mark.parametrize("mutation", ["dependency", "threshold", "output_dtype", "missing_output", "extra_output", "entrypoint"])
def test_contract_and_output_bindings(tmp_path, mutation):
    _, root, receipt, limits = retained(tmp_path)
    if mutation == "dependency":
        (root / receipt["replay"]["files"]["golden.bin"]["path"]).write_bytes(b"changed")
    elif mutation == "threshold":
        receipt["replay"]["argv"] = ["--relaxed"]
    elif mutation == "output_dtype":
        receipt["checks"][0]["dtype"] = "float32"
    elif mutation == "missing_output":
        receipt["checks"] = []
    elif mutation == "extra_output":
        receipt["checks"].append(deepcopy(receipt["checks"][0]))
    else:
        receipt["oracle_source"] = receipt["replay"]["files"]["golden.bin"]
    with pytest.raises(ContractError):
        replay_oracle(root, receipt, ref(root, root / "output.json"), limits)


def test_oracle_cannot_modify_output(tmp_path):
    program = ORACLE.replace("actual =", "Path('out.bin').write_bytes(b'changed')\nactual =")
    config = original_config(tmp_path / "input", program=program)
    with pytest.raises(ContractError, match="改写"):
        collect(config, tmp_path / "correctness", correctness_only=True, runner=FakeRunner(config))


def test_all_case_preflight_stops_before_first_native(tmp_path):
    config = capture_config(tmp_path / "input")
    unsupported = deepcopy(config["cases"][0])
    unsupported["case_id"] = 2
    unsupported["checks"][0]["dtype"] = "bfloat16"
    config["cases"].append(unsupported)
    runner = FakeRunner(config)
    with pytest.raises(OracleFailure, match="oracle_adapter_unsupported"):
        collect(config, tmp_path / "correctness", correctness_only=True, runner=runner)
    assert runner.calls == []


def test_missing_environment_is_not_numerical_failure(tmp_path):
    config = original_config(tmp_path / "input")
    case = config["cases"][0]
    case["oracle_replay"]["environment"]["packages"] = {"aprof-does-not-exist": "1"}
    case["workload"]["oracle_limits"]["contract_sha256"] = config_contract(case["oracle_replay"])
    with pytest.raises(OracleFailure, match="oracle_environment_unavailable"):
        preflight(config)


def test_original_oracle_continues_after_soft_target(tmp_path):
    _, root, receipt, limits = retained(tmp_path)
    result = execute(root, receipt, limits, deadline=time.monotonic() - 1)
    assert result["returncode"] == 0


def test_same_invocation_reuses_execution_but_rechecks_bytes(tmp_path, monkeypatch):
    _, root, receipt, limits = retained(tmp_path)
    verified = set()
    execute(root, receipt, limits, verified=verified)
    import aprof_runtime.original_oracle as module
    def unexpected(*args, **kwargs):
        raise AssertionError("unchanged evidence should reuse this invocation's actual execution")
    monkeypatch.setattr(module.subprocess, "Popen", unexpected)
    replay_oracle(root, receipt, ref(root, root / "output.json"), limits, verified=verified)
    (root / "outputs/output.bin").write_bytes(b"tampered")
    with pytest.raises(ContractError, match="SHA256"):
        replay_oracle(root, receipt, ref(root, root / "output.json"), limits, verified=verified)


def test_error_without_result_is_not_precision_failure(tmp_path):
    config = original_config(tmp_path / "input", program="raise RuntimeError('broken oracle')")
    with pytest.raises(OracleFailure, match="oracle_execution_failed"):
        collect(config, tmp_path / "correctness", correctness_only=True, runner=FakeRunner(config))


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", "out.bin/child", "result.json"])
def test_bundle_path_escape_and_collisions(tmp_path, path):
    config = original_config(tmp_path / "input")
    case = config["cases"][0]
    spec = case["oracle_replay"]
    spec["files"][path] = spec["files"]["golden.bin"]
    case["workload"]["oracle_limits"]["contract_sha256"] = config_contract(spec)
    with pytest.raises(ContractError):
        preflight(config)
