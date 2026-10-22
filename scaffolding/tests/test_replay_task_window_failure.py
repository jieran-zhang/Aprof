"""The retained failed window attempt cannot become admission evidence."""

import json

import pytest

from replay_task_window_failure import SLOTS, STATUSES, _exact_attempt_statuses, bound, replay_task_window_failure
from replay_timing_diagnosis import Evidence, digest


@pytest.mark.parametrize("change", [
    {"exp-confirmation": "passed"},
    {"sigmoid-confirmation": "not_run"},
    {"exp-observation-01": "passed"},
])
def test_exact_failed_roster_rejects_relabeling(change):
    statuses = dict(zip(SLOTS, STATUSES, strict=True))
    _exact_attempt_statuses(statuses)
    with pytest.raises(ValueError, match="different slot roster or status"):
        _exact_attempt_statuses(statuses | change)


def test_exact_failed_roster_rejects_added_slot():
    with pytest.raises(ValueError, match="different slot roster or status"):
        _exact_attempt_statuses(dict(zip(SLOTS, STATUSES, strict=True)) | {"extra": "not_run"})
    with pytest.raises(ValueError, match="different slot roster or status"):
        _exact_attempt_statuses(dict(zip(SLOTS[:-1], STATUSES[:-1], strict=True)))


def test_original_raw_reference_cannot_be_replaced_by_same_length(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_bytes(b"old")
    reference = {"path": str(raw), "sha256": digest(raw)}
    raw.write_bytes(b"new")
    with pytest.raises(ValueError, match="changed evidence"):
        bound(Evidence(), reference, raw)


@pytest.mark.parametrize("claim", ["accepted", "eligible_for_publication", "complete_method_qualification"])
def test_failure_manifest_cannot_claim_acceptance(tmp_path, claim):
    manifest = {"schema_version": 1, "purpose": "historical_failed_task_window_v1",
                "accepted": False, "eligible_for_publication": False,
                "complete_method_qualification": False}
    manifest[claim] = True
    path = tmp_path / "leaf.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="cannot grant acceptance"):
        replay_task_window_failure({"path": str(path), "sha256": digest(path)})
