"""Offline mechanical-adaptation checks. These never qualify real hardware."""
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "collection/scripts/qualify_shared_timing_v051.py"
SPEC = importlib.util.spec_from_file_location("qualify_shared_timing_v051_test", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def original_host(operator):
    return f'''#include "aprof_device_timer.h"
unchanged_before();
        aprof::Run(stream, device, "{operator}", 1, [&]() {{
        {operator}_kernel<<<tiling.blockNum, nullptr, stream>>>(
            static_cast<uint8_t *>(devIn), static_cast<uint8_t *>(devOut), static_cast<uint8_t *>(devTiling));
        }});
unchanged_after();
'''


def original_oracle(operator):
    if operator == "exp":
        return '''p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args()
with open(m['input'],'rb') as fi, open(m['output'],'rb') as fo:
    expected=quantize(np.exp(temp).astype(np.float32),dt)
    passed=special_ok and mere<threshold and rel_max<10*threshold
(mp.parent/'result.json').write_text(json.dumps(result))
'''
    return '''    parser.add_argument("--metadata", required=True)
with open(metadata["input"], "rb") as input_file, open(metadata["output"], "rb") as output_file:
    expected = torch_golden(values, dtype)
    passed = special_ok and mere < threshold and rel_max < 10 * threshold
(metadata_path.parent / "result.json").write_text(json.dumps(result))
'''


@pytest.mark.parametrize("operator", module.OPERATORS)
def test_host_two_named_callbacks_share_original_kernel_and_buffers(operator):
    adapted = module.adapt_host(original_host(operator), operator)
    assert adapted.count(operator + "_kernel<<<") == 2
    assert '"input", devIn, bytes' in adapted
    assert '"tiling", devTiling, sizeof(tiling)' in adapted
    assert '"output", devOut, bytes' in adapted
    assert '"launch_baseline", "launch_candidate"' in adapted
    assert 'std::string(role) == "baseline" ? baseline_output : candidate_output' in adapted
    assert "unchanged_before();" in adapted and adapted.endswith("unchanged_after();\n")
    with pytest.raises(ValueError, match="exactly once"):
        module.adapt_host(adapted, operator)


@pytest.mark.parametrize("operator", module.OPERATORS)
def test_oracle_only_redirects_io_and_requires_both_new_paths(operator):
    original = original_oracle(operator)
    adapted = module.adapt_oracle(original, operator)
    for line in original.splitlines():
        if "expected" in line or "passed" in line:
            assert line in adapted
    assert "required=True" in adapted
    assert "--output" in adapted and "--result" in adapted
    assert "open(m['input'],'rb')" in adapted or 'open(metadata["input"], "rb")' in adapted
    assert "parent/'result.json'" not in adapted and 'parent / "result.json"' not in adapted
    with pytest.raises(ValueError, match="exactly once"):
        module.adapt_oracle(adapted, operator)


@pytest.fixture
def prepared(tmp_path):
    round2 = tmp_path / "round2"
    for operator in module.OPERATORS:
        source = round2 / operator / "baseline"
        for name in ("op_host", "op_kernel", "scripts"):
            (source / name).mkdir(parents=True)
        (source / "CMakeLists.txt").write_text("# fixture, never compiled\n")
        (source / "op_host" / (operator + ".asc")).write_text(original_host(operator))
        (source / "op_host/aprof_device_timer.h").write_text("// original timer\n")
        (source / "op_kernel" / (operator + "_kernel.asc")).write_text("// unchanged original arithmetic\n")
        (source / "op_kernel" / (operator + "_tiling.h")).write_text("// unchanged original tiling\n")
        (source / "scripts/verify_result.py").write_text(original_oracle(operator))
        for case_id in range(1, 21):
            folder = round2 / operator / "prepared" / f"case_{case_id:02d}"
            folder.mkdir(parents=True)
            (folder / "input.bin").write_bytes(b"\0\0")
            metadata = dict(case_id=case_id, shape=[1], numel=1, dtype="float16", input=str(folder / "input.bin"),
                            output=str(folder / "original-output.bin"))
            if operator == "exp":
                metadata.update(base=-1.0, scale=1.0, shift=0.0)
            if case_id == 12:
                metadata["value_range"] = [-math.inf, math.inf]
            if case_id == 13:
                metadata["value_range"] = [math.nan, math.nan]
            (folder / "metadata.json").write_text(json.dumps(metadata))
    anchor = tmp_path / "diagnostic-anchor.json"
    anchor.write_text("{}")
    output = tmp_path / "qualification"
    plan = module.prepare(round2, output, anchor)
    return output, plan


def test_prepare_preserves_sources_metadata_inputs_and_fixed_roster(prepared):
    output, plan = prepared
    module.load_plan(output)
    module.strict_runtime_roundtrip(output / "plan.json")
    for operator in module.OPERATORS:
        item = plan["operators"][operator]
        proof = module.read(item["source_review"])
        assert len(item["cases"]) == 20
        assert item["max_attempts"] == 1
        assert item["timeline"]["case_ids"] == [1, module.LARGE_CASE[operator]]
        assert set(proof["patches"]) == {f"op_host/{operator}.asc", "scripts/verify_result.py"}
        for path in proof["unchanged_files"]:
            assert proof["original_files"][path] == proof["adapted_files"][path]
        config = module.make_config(plan, output, operator, 0, 0)
        assert config["roles"]["baseline"]["source_dir"] == item["original_source"]
        assert config["roles"]["candidate"]["source_dir"] == item["original_source"]
        assert config["build"]["source_dir"] == item["source"]
        for case in config["cases"]:
            for role, command in case["verify_commands"].items():
                assert command[command.index("--metadata") + 1] == case["prepared_files"][0]
                assert command[command.index("--output") + 1] == "{cycle_dir}/" + role + ".bin"
                assert command[command.index("--result") + 1] == "{cycle_dir}/" + role + "-result.json"
        assert item["cases"][11]["workload"]["value_range"] == [
            {"__aprof_nonfinite_float__": "-Infinity"}, {"__aprof_nonfinite_float__": "Infinity"}]
        assert item["cases"][12]["workload"]["value_range"] == [{"__aprof_nonfinite_float__": "NaN"}] * 2


def test_prepared_input_tampering_blocks_build(prepared):
    output, plan = prepared
    Path(plan["operators"]["exp"]["cases"][0]["input"]).write_bytes(b"\1\1")
    with pytest.raises(ValueError, match="frozen file changed"):
        module.load_plan(output)


def test_build_failure_is_terminal_without_retry(prepared, monkeypatch):
    output, _ = prepared
    monkeypatch.setattr(module, "diagnostic_admission", lambda plan: {"test_only": True})
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2))
    with pytest.raises(RuntimeError, match="build command failed"):
        module.build(output, "exp")
    receipt = module.read(output / "exp/build-receipt.json")
    assert receipt["status"] == "failed" and receipt["commands"][0]["exit_status"] == 2
    with pytest.raises(FileExistsError):
        module.build(output, "exp")


def test_missing_diagnostic_never_compiles(prepared, monkeypatch):
    output, _ = prepared
    def rejected(_):
        raise ValueError("diagnostic rejected")
    def unexpected(*args, **kwargs):
        pytest.fail("no compiler command may start before diagnostic replay")
    monkeypatch.setattr(module, "diagnostic_admission", rejected)
    monkeypatch.setattr(module.subprocess, "run", unexpected)
    with pytest.raises(ValueError, match="diagnostic rejected"):
        module.build(output, "sigmoid")
    assert module.read(output / "sigmoid/build-receipt.json")["commands"] == []


def test_timeline_uses_full_production_protocol():
    commands = module.protocol_commands()
    assert len(commands) == 19 and commands[-1] == "finish 18"
    assert sum(c.startswith("pair") for c in commands) == 15
    assert [c for c in commands if c.startswith("prime")] == ["prime 0 aa_before", "prime 6 formal", "prime 12 aa_after"]
    assert 2 * 10 + 3 * 4 * 100 + 3 * 5 * 2 * 100 + 2 == 4222


def test_freeze_registers_direct_native_timeline_and_command_files(prepared, monkeypatch):
    output, _ = prepared
    monkeypatch.setattr(module, "diagnostic_admission", lambda plan: {"test_only": True})
    def fake_build(command, **_):
        if command[1] == "--build":
            directory = Path(command[2])
            directory.mkdir()
            (directory / directory.parent.parent.name).write_bytes(b"unit-test-only-not-a-real-executable")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, "run", fake_build)
    for operator in module.OPERATORS:
        module.build(output, operator)
    frozen = module.freeze(output)
    assert frozen["accepted"] is False
    timeline = module.read(output / "timeline-plan.json")
    assert [(r["operator"], r["case_id"]) for r in timeline["runs"]] == [("exp", 1), ("exp", 9), ("sigmoid", 1), ("sigmoid", 4)]
    for run in timeline["runs"]:
        assert Path(run["application"][0]).name == run["operator"]
        assert "timeline-driver" not in run["application"]
        command_file = Path(run["command_file"]["path"])
        assert command_file.read_text() == "\n".join(module.protocol_commands()) + "\n"
        assert frozen["frozen_files"][str(command_file)] == run["command_file"]["sha256"]
        assert run["environment"] == {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": "0", "APROF_SHARED_COMMANDS": str(command_file),
            "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "{confirmation_repeat}"}
        assert run["expected_kernel_tasks_formula"] == "1222+30*R"
        assert run["repeat_source"] == "completed_confirmation_registration"
        config = module.read(frozen["configs"][run["operator"]])
        for command in config["cases"][0]["verify_commands"].values():
            assert command[0] == str(Path(command[0]).resolve())


@pytest.mark.parametrize("operator", module.OPERATORS)
@pytest.mark.parametrize("case_id", [12, 13])
def test_actual_special_value_metadata_strict_runtime_roundtrip(tmp_path, operator, case_id):
    path = module.ROOT.parent / "validation-graph-base-1.0.0-round2-20261014" / operator / "prepared" / f"case_{case_id:02d}" / "metadata.json"
    if not path.is_file():
        pytest.skip("original prepared corpus is not installed")
    before = path.read_bytes()
    metadata = json.loads(before)
    bad = tmp_path / "old-invalid-workload.json"
    bad.write_text(json.dumps({k: v for k, v in metadata.items() if k not in {"input", "output"}}))
    with pytest.raises(ValueError, match="strict runtime JSON roundtrip failed"):
        module.strict_runtime_roundtrip(bad)
    encoded = module.workload_json({k: v for k, v in metadata.items() if k not in {"input", "output"}})
    corrected = tmp_path / "workload.json"
    module.save_new(corrected, encoded)
    module.strict_runtime_roundtrip(corrected)
    for key in ("shape", "dtype", "numel", "case_id"):
        assert encoded[key] == metadata[key]
    for key in ("base", "scale", "shift"):
        if key in metadata:
            assert encoded[key] == metadata[key]
    assert path.read_bytes() == before


def test_save_new_does_not_write_nonfinite_json(tmp_path):
    with pytest.raises(ValueError, match="Out of range float values"):
        module.save_new(tmp_path / "rejected.json", {"value": math.nan})
