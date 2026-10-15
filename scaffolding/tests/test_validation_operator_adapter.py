from pathlib import Path
import shutil
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "collection/scripts"
sys.path.insert(0, str(SCRIPTS))
import validation_operator_adapter as adapter


@pytest.mark.parametrize("operator", adapter.SUPPORTED_OPERATORS)
def test_complete_operator_wrapper_covers_every_pristine_launch(tmp_path, operator):
    canonical = adapter.ROOT / "scaffolding/benchmarks/cannbench/operators" / operator
    original = (canonical / "op_host" / f"{operator}.asc").read_text()
    host = tmp_path / "op_host"
    host.mkdir()
    instrumented = adapter.instrument_text(original, operator)
    path = host / f"{operator}.asc"
    path.write_text(instrumented)
    shutil.copy2(adapter.HEADER, host / "aprof_device_timer.h")
    result = adapter.check_instrumentation(tmp_path, operator)
    assert result["host_launch_sites"] == original.count("<<<")
    # The wrapped compute body is preserved byte-for-byte, including the
    # required GQA/WQ stage synchronizations and tiling transfers.
    begin, end, *_ = adapter.WRAPPERS[operator]
    body = original[original.index(begin):original.index(end) + len(end)]
    assert body in instrumented
    path.write_text(instrumented + "\nescaped<<<1, nullptr, stream>>>();\n")
    with pytest.raises(ValueError, match="escaped"):
        adapter.check_instrumentation(tmp_path, operator)


def test_case_dispatch_and_dynamic_multikernel_counts():
    metadata = {"shape": [2, 8, 16], "dtype": "float16", "num_groups": 4, "epsilon": 1e-5,
                "x": "/x", "gamma": "/gamma", "beta": "/beta"}
    argv = adapter.case_command("group_norm", Path("/binary"), metadata, 0, {"output": "/output"})
    assert argv[argv.index("--groups") + 1] == "4"
    assert adapter.launches_per_call("gqa", {"query_shape": [3, 16, 8, 64], "key_shape": [3, 32, 2, 64]}) == 15
    assert adapter.launches_per_call("weight_quant_batch_matmul", {}) == 3
    assert adapter.json_contract({"epsilon": float("nan")}) == {"epsilon": "NaN"}
    exp = {"numel": 65, "dtype": "float32", "input": "/x", "base": 2.0, "scale": 0.5, "shift": -1.0}
    argv = adapter.case_command("exp", Path("/binary"), exp, 0, {"output": "/output"})
    for name in ("base", "scale", "shift"):
        assert argv[argv.index("--" + name) + 1] == str(exp[name])


def test_scope_rejects_work_moved_into_untimed_helper(tmp_path):
    prepared = tmp_path / "prepared"
    adapter.prepare("gelu", prepared, tmp_path / "unused-upstream")
    baseline = prepared / "baseline"
    candidate = tmp_path / "candidate"
    shutil.copytree(baseline, candidate)
    assert adapter.check_candidate_scope(baseline, candidate, "gelu")["outside_host_identical"]
    path = candidate / "op_host/gelu.asc"
    original = path.read_text()
    path.write_text(original.replace(adapter.BEGIN, "untimed_helper();\n" + adapter.BEGIN))
    with pytest.raises(ValueError, match="outside"):
        adapter.check_candidate_scope(baseline, candidate, "gelu")
    path.write_text(original)
    helper = candidate / "op_kernel/new_helper.h"
    helper.write_text("void helper() { hidden<<<1, nullptr, stream>>>(); }\n")
    with pytest.raises(ValueError, match="helper"):
        adapter.check_candidate_scope(baseline, candidate, "gelu")


@pytest.mark.parametrize("operator", adapter.EXTERNAL_CASES)
def test_external_oracle_relocation_changes_only_lookup_path(tmp_path, operator):
    canonical = adapter.ROOT / "scaffolding/benchmarks/cannbench/operators" / operator
    tree = tmp_path / "source"
    shutil.copytree(canonical / "scripts", tree / "scripts")
    original = (tree / "scripts/cases.py").read_text()
    original_generator = (tree / "scripts/gen_data.py").read_bytes()
    original_verifier = (tree / "scripts/verify_result.py").read_bytes()
    tasks = tmp_path / "tasks"
    upstream = tasks / adapter.EXTERNAL_CASES[operator]
    upstream.parent.mkdir(parents=True)
    upstream.write_text("cases: []\n")
    result = adapter.relocate_cases(tree, operator, tasks)
    assert (tree / "scripts/cases.yaml").read_bytes() == upstream.read_bytes()
    assert result["case_spec"]["sha256"] == adapter.sha(upstream)
    assert (tree / "scripts/gen_data.py").read_bytes() == original_generator
    assert (tree / "scripts/verify_result.py").read_bytes() == original_verifier
    changed = (tree / "scripts/cases.py").read_text()
    assert len(original.splitlines()) == len(changed.splitlines())
    assert sum(old != new for old, new in zip(original.splitlines(), changed.splitlines())) == 1
    assert 'Path(__file__).with_name("cases.yaml")' in changed
