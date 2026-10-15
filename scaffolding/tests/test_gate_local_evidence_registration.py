"""Regression for registering a new gate request through retained local evidence."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))


def test_gate_request_survives_local_registration(tmp_path, monkeypatch):
    monkeypatch.setenv('APROF_SKILL_LIB', str(REPO / 'skill-libs/graph-base/1.0.0'))
    from task_rule_gate_completion import GateEvidence
    from aprof_runtime.jsonio import content_hash
    from aprof_runtime.local_evidence import LocalEvidence
    from aprof_runtime.traces import register_json_artifact

    local = LocalEvidence(tmp_path / 'records')
    store = GateEvidence(local, [])
    request = {'schema_version': '1.0.0', 'purpose': 'new local gate request'}
    reference = register_json_artifact(store, request)
    assert reference == content_hash(request)
    assert store.verify_artifact(reference).is_relative_to(local.directory)
    assert register_json_artifact(store, request) == reference
    index = local.write_index(tmp_path / 'local-index.json')
    assert LocalEvidence.from_index(index).verify_artifact(reference).read_bytes() == store.verify_artifact(reference).read_bytes()
