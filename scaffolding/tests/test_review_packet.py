"""CPU packet checks; no model calls, token claims, compiler or hardware."""
import hashlib
import json
from pathlib import Path

import pytest

from eval_tool_broker import REVIEW_OBLIGATIONS, inventory
import review_packet as packet


def fixture(tmp_path):
    work = tmp_path / "review"
    files = {"CMakeLists.txt": b"project(exp)\n",
        "op_host/exp.asc": b"// host source\r\nvoid launch() {}\r\n",
        "op_host/aprof_device_timer.h": b"// full timer\nvoid measure() {}\n",
        "op_host/data_utils.h": b"// complete IO\n",
        "op_kernel/exp_kernel.asc": b"// kernel\nvoid exp_kernel() {}\n",
        "op_kernel/exp_tiling.h": b"constexpr int tile = 4096;\n",
        "scripts/verify_result.py": b"assert output == reference\n",
        "scripts/gen_data.py": b"input_values = generate_all_inputs()\n",
        "scripts/cases.py": b"cases = [1, 2]\n",
        "scripts/summarize.py": b"print(results)\n",
        "run.sh": b"#!/bin/sh\n./exp\n"}
    for role in ("baseline", "candidate"):
        for name, data in files.items():
            path = work / role / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if role == "candidate" and name.endswith("exp_tiling.h"):
                data = data.replace(b"4096", b"8192")
            path.write_bytes(data)
    cases = [{"case_id": 1, "dtype": "float32", "shape": [1], "attrs": {"shift": -0.0},
              "special_values": ["NaN", "Infinity"]},
             {"case_id": 2, "dtype": "float32", "shape": [33], "attrs": {"shift": 0.0},
              "special_values": ["NaN", "Infinity"]}]
    values = {"contract.json": {"operator": "exp", "cases": cases, "other": {"keep": "all"}},
              "boundaries.json": {"cases": cases, "frozen": True},
              "checklist.json": {"critical_obligations": {name: "Check " + name for name in REVIEW_OBLIGATIONS},
                                 "decision": "All eight pass; unknown rejects."}}
    for name, value in values.items():
        (work / name).write_text(json.dumps(value, indent=2))
    (work / "diff.txt").write_bytes(b"--- baseline/op_kernel/exp_tiling.h\n+++ candidate/op_kernel/exp_tiling.h\n-4096\n+8192\n")
    return work, inventory(work)


def build(work, expected):
    return packet.build_review_packet(work, expected_inventory=expected)


def test_exact_sources_deduplicated_complete_tables_and_binding(tmp_path):
    work, expected = fixture(tmp_path)
    before = inventory(work)
    result = build(work, expected)
    assert result == build(work, dict(reversed(list(expected.items()))))
    assert inventory(work) == before  # Packing does not write any source or prompt.
    prompt, binding = result["prompt"], result["binding"]
    assert binding["input_inventory"] == expected
    assert binding["packet_sha256"] == "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
    assert binding["packet_bytes"] == len(prompt.encode())
    assert binding["producer_sha256"] == packet._hash(Path(packet.__file__).read_bytes())
    assert binding["packing"]["source_deduplication"] == "exact_bytes"
    assert prompt.startswith(packet.REVIEW_INSTRUCTIONS)
    assert not any("token" in key for key in binding)
    assert set(binding["deferred_sources"]) == {f"{role}/{name}" for role in ("baseline", "candidate")
                                               for name in ("run.sh", "scripts/summarize.py")}
    assert all(reference == expected[name] for name, reference in binding["deferred_sources"].items())
    included = []
    encoded = prompt.encode()
    for block in binding["source_blocks"]:
        data = (work / block["paths"][0]).read_bytes()
        assert encoded.count(data) == 1
        assert block["bytes"] == len(data)
        assert all((work / name).read_bytes() == data and expected[name] == block["sha256"]
                   for name in block["paths"])
        included.extend(block["paths"])
    assert set(included) | set(binding["deferred_sources"]) | set(packet.DOCUMENTS) == set(expected)
    assert len(included) == len(set(included))
    assert (work / "diff.txt").read_bytes() in encoded
    for name in ("contract.json", "boundaries.json", "checklist.json"):
        value = json.loads(prompt.split("\n" + name + " source_sha256=", 1)[1].split("\n")[1])
        if name != "checklist.json":
            table = value["cases"]
            assert "attrs" not in table["defaults"]  # Signed zero is preserved, not coalesced.
            value["cases"] = [{**table["defaults"], **dict(zip(table["columns"], row))}
                              for row in table["rows"]]
        assert packet._json(value) == packet._json(json.loads((work / name).read_text()))


@pytest.mark.parametrize("defect", ["changed_source", "changed_contract", "missing_source", "extra_source",
                                     "missing_document", "symlink", "bad_inventory_hash", "unknown_input"])
def test_frozen_inputs_cannot_change_or_escape(tmp_path, defect):
    work, expected = fixture(tmp_path)
    if defect.startswith("changed"):
        path = work / ("candidate/op_kernel/exp_kernel.asc" if defect == "changed_source" else "contract.json")
        path.write_bytes(path.read_bytes() + b" ")
    elif defect == "missing_source":
        (work / "baseline/op_host/aprof_device_timer.h").unlink()
    elif defect == "extra_source":
        (work / "candidate/op_kernel/extra.h").write_text("extra source")
    elif defect == "missing_document":
        (work / "boundaries.json").unlink()
    elif defect == "symlink":
        (work / "candidate/op_kernel/link.h").symlink_to(work / "baseline/op_kernel/exp_kernel.asc")
    elif defect == "bad_inventory_hash":
        expected["contract.json"] = "not-a-hash"
    else:
        (work / "candidate/results.json").write_text("{}")
        expected = inventory(work)
    with pytest.raises(ValueError):
        build(work, expected)


@pytest.mark.parametrize("name", ["baseline/op_host/aprof_device_timer.h", "candidate/op_kernel/exp_tiling.h",
                                  "baseline/scripts/verify_result.py", "candidate/scripts/gen_data.py"])
def test_required_source_cannot_be_omitted_from_supplied_inventory(tmp_path, name):
    work, _ = fixture(tmp_path)
    (work / name).unlink()
    with pytest.raises(ValueError, match="missing required reviewer source"):
        build(work, inventory(work))


@pytest.mark.parametrize("defect", ["missing_obligation", "duplicate_key", "nonfinite", "heterogeneous_cases"])
def test_lossy_or_incomplete_document_rejected(tmp_path, defect):
    work, _ = fixture(tmp_path)
    if defect == "missing_obligation":
        path = work / "checklist.json"
        value = json.loads(path.read_text()); value["critical_obligations"].pop(REVIEW_OBLIGATIONS[0])
        path.write_text(json.dumps(value))
    elif defect == "duplicate_key":
        (work / "contract.json").write_text('{"operator":"exp","operator":"sigmoid"}')
    elif defect == "nonfinite":
        (work / "boundaries.json").write_text('{"cases":[],"x":NaN}')
    else:
        path = work / "boundaries.json"
        value = json.loads(path.read_text()); value["cases"][0].pop("attrs")
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        build(work, inventory(work))


def test_existing_prompt_is_output_not_input(tmp_path):
    work, expected = fixture(tmp_path)
    result = build(work, expected)
    (work / "prompt.txt").write_text("previous prompt")
    assert build(work, expected) == result
    with pytest.raises(ValueError, match="inventory entry"):
        build(work, inventory(work))


def test_noncanonical_instructions_rejected(tmp_path):
    work, expected = fixture(tmp_path)
    with pytest.raises(ValueError, match="canonical packet instructions"):
        packet.build_review_packet(work, expected_inventory=expected, instructions="Skip the timer obligation")


def test_instructions_preserve_shared_time_limit_and_cost_only_tokens():
    assert "remaining time of the shared\n60-minute task deadline" in packet.REVIEW_INSTRUCTIONS
    assert "Actual token usage is recorded as cost only" in packet.REVIEW_INSTRUCTIONS
    assert "no token-count admission limit" in packet.REVIEW_INSTRUCTIONS
    assert "8000" not in packet.REVIEW_INSTRUCTIONS
    assert all(name in packet.REVIEW_INSTRUCTIONS for name in REVIEW_OBLIGATIONS)
