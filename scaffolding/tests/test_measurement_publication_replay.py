"""Focused offline publication guards; synthetic controls are never acceptance evidence."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sqlite3
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("measurement_publication_test", ROOT / "scaffolding/tools/verify_measurement_publication.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def controls():
    return {"case_ids": list(range(1, 21)), "controls": [
        {"case_id": case, "overall": {"formal": {"role_bias": 0.0}},
         "cycles": [{"cycle": cycle, "formal": {"role_bias": 0.0}} for cycle in range(6)]}
        for case in range(1, 21)]}


def test_formal_aa_requires_full_scope_and_every_cycle():
    report = controls()
    module.formal_aa_controls(report)
    for location in (report["controls"][0]["overall"], report["controls"][18]["cycles"][5]):
        location["formal"]["role_bias"] = 0.020001
        with pytest.raises(ValueError, match="formal A/A role bias"):
            module.formal_aa_controls(report)
        location["formal"]["role_bias"] = 0.0
    report["controls"][0]["cycles"].pop()
    with pytest.raises(ValueError, match="six fresh cycles"):
        module.formal_aa_controls(report)


@pytest.mark.parametrize("value", [True, -0.1, float("nan"), float("inf")])
def test_formal_aa_rejects_invalid_statistics(value):
    report = controls()
    report["controls"][0]["overall"]["formal"]["role_bias"] = value
    with pytest.raises(ValueError, match="formal A/A role bias"):
        module.formal_aa_controls(report)


def test_duplicate_or_missing_case_cannot_replace_complete_confirmation():
    report = controls()
    report["controls"][19] = deepcopy(report["controls"][0])
    with pytest.raises(ValueError, match="missing confirmation controls"):
        module.formal_aa_controls(report)


def test_file_pointer_rejects_tampering_and_symlinks(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("{}")
    pointer = module.bound(target)
    assert module.reference(pointer) == target
    target.write_text('{"accepted":true}')
    with pytest.raises(ValueError, match="changed"):
        module.reference(pointer)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        module.reference(dict(path=str(link), sha256=module.digest(target)))


def test_readonly_cas_requires_indexed_unchanged_content(tmp_path):
    path = tmp_path / "evidence.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE artifacts(content_hash TEXT)")
    connection.commit()
    source = tmp_path / "raw.json"
    source.write_text("{}")
    hexadecimal = module.digest(source)
    ref = "sha256:" + hexadecimal
    destination = tmp_path / "evidence.sqlite.objects/sha256" / hexadecimal[:2] / hexadecimal[2:]
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    reader = module.ReadonlyCAS(path)
    with pytest.raises(ValueError, match="not indexed"):
        reader.verify_artifact(ref)
    # A publication reader owns a fixed read-only snapshot. End it before
    # completing an independently written store, then open a fresh replay.
    reader.close()
    connection.execute("INSERT INTO artifacts VALUES(?)", (ref,))
    connection.commit()
    reader = module.ReadonlyCAS(path)
    assert reader.load(ref) == {}
    destination.write_text("tampered")
    with pytest.raises(ValueError, match="content changed"):
        reader.verify_artifact(ref)
    reader.close()
    connection.close()


def test_method_validator_rejects_summary_before_any_runtime_import(tmp_path):
    report = tmp_path / "report.json"
    report.write_text('{"accepted": true, "stable": true}')
    with pytest.raises(ValueError, match="invalid publication report schema"):
        module.verify_in_process(ROOT / "skill-libs/graph-base/0.5.1", report)


@pytest.mark.parametrize('protocol', ['shared_buffer_acl_event_v2', 'shared_buffer_msprof_task_v1'])
def test_old_history_cannot_enter_task_publication_even_with_complete_envelope(tmp_path, protocol):
    import json
    report = tmp_path / "old-event-report.json"
    value = {key: {} for key in ('history_ref', 'confirmations', 'observation_refs',
             'attempt_roster_ref', 'install_receipt_ref', 'candidate_inventory_ref', 'old_release_baseline_ref')}
    value.update(schema_version=1, protocol=protocol, qualification_dir=str(tmp_path))
    report.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='only the Task Duration'):
        module.verify_in_process(ROOT / 'skill-libs/graph-base/0.5.1', report)


@pytest.mark.parametrize("tamper", ["schema", "contracts", "arithmetic"])
def test_new_admission_cannot_change_frozen_machine_rules(tmp_path, tamper):
    baseline = ROOT / "skill-libs/graph-base/0.5.0"
    candidate = tmp_path / "candidate"
    for relative in ("schemas", "skillgraph/versions"):
        shutil.copytree(baseline / relative, candidate / relative)
    runtime = candidate / "runtime/src/aprof_runtime"
    runtime.mkdir(parents=True)
    for name in ("contracts.py", "gates.py"):
        shutil.copyfile(baseline / "runtime/src/aprof_runtime" / name, runtime / name)
    module.protected_rules(candidate, baseline)
    if tamper == "schema":
        (candidate / "schemas/extra.schema.json").write_text("{}")
    elif tamper == "contracts":
        (runtime / "contracts.py").write_text((runtime / "contracts.py").read_text() + "\n# changed contract\n")
    else:
        with (runtime / "gates.py").open("a") as file:
            file.write("\ndef _median(samples):\n    return 1.0\n")
    with pytest.raises(ValueError, match="frozen"):
        module.protected_rules(candidate, baseline)
