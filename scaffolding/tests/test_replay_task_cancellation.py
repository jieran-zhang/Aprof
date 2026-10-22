"""Cancellation history is exact, read-only, and never an admission."""

import json

import pytest

from replay_task_cancellation import bound_ref, replay_task_cancellation, verify_snapshot
from replay_timing_diagnosis import Evidence, digest


def test_bound_ref_uses_exact_two_field_chain_shape(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text("{}")
    assert bound_ref(Evidence(), path) == {"path": str(path), "sha256": digest(path)}


@pytest.mark.parametrize("mutation", ["add", "remove", "change"])
def test_snapshot_rejects_added_removed_or_changed_file(tmp_path, mutation):
    root = tmp_path / "attempt"
    root.mkdir()
    original = root / "raw.txt"
    original.write_bytes(b"original")
    inventory = {"root": str(root), "files": {str(original): {"sha256": digest(original), "bytes": 8}},
                 "file_count": 1, "total_bytes": 8}
    if mutation == "add":
        (root / "extra.txt").write_bytes(b"new")
    elif mutation == "remove":
        original.unlink()
    else:
        original.write_bytes(b"modified")  # Same byte count must still fail the hash check.
    with pytest.raises(ValueError, match="added or removed|changed evidence"):
        verify_snapshot(Evidence(), inventory)


@pytest.mark.parametrize("claim", ["complete", "eligible_for_publication",
                                    "formal_admission_replayed", "actual_timeout"])
def test_cancelled_attempt_cannot_claim_completion_or_admission(tmp_path, claim):
    audit = {"schema_version": 1,
             "purpose": "historical_explicit_cost_projection_cancellation_audit",
             "complete": False, "eligible_for_publication": False,
             "formal_admission_replayed": False, "actual_timeout": False}
    audit[claim] = True
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="cannot confer admission"):
        replay_task_cancellation({"path": str(path), "sha256": digest(path)})
