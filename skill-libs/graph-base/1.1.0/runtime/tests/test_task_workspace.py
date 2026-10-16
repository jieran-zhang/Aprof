import json
from pathlib import Path
import sys

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_budget import prepare_budget_plan, run_task
from aprof_runtime.task_workspace import create_workspace, cleanup_workspace


def completed_task(tmp_path, *, collect=False):
    from aprof_runtime.local_archive import freeze_package_identity
    workspace = create_workspace("cpu-cleanup-task", parent=tmp_path, collect=collect)
    scratch = Path(workspace["scratch"])
    local = LocalEvidence(scratch / "records")
    scope = local.register_json({"purpose": "real CPU failure retained in cleanup"})
    budget = local.register_json(prepare_budget_plan(task_id=workspace["task_id"], scope_ref=scope, budget_seconds=20))
    destination = scratch / "segment-1"
    job = local.register_json({"argv": [sys.executable, "-I", "-c", "raise SystemExit(7)"],
        "cwd": str(scratch), "output_dir": str(destination), "environment": {}, "timeout_seconds": 20,
        "package_identity_ref": freeze_package_identity(local)})
    result = run_task(local, budget_ref=budget, job_ref=job, destination=destination)
    assert result["status"] == "failed"
    return workspace, result


def test_cleanup_preserves_user_source_final_and_actual_failed_cost(tmp_path):
    workspace, result = completed_task(tmp_path)
    source = tmp_path / "user.cpp"
    source.write_text("user source")
    final = Path(workspace["final"]) / "kernel.cpp"
    final.write_text("delivered code")
    (Path(workspace["scratch"]) / "source-link").symlink_to(source)
    outcome = cleanup_workspace(workspace["root"], local_index=result["local_index"],
                                terminal_ref=result["terminal_ref"])
    assert outcome["original_status"] == "failed"
    assert outcome["cumulative_execution_seconds"] > 0
    assert source.read_text() == "user source" and final.read_text() == "delivered code"
    assert not Path(workspace["scratch"]).exists()
    assert json.loads((Path(workspace["root"]) / "cleanup.json").read_text()) == outcome


def test_collector_required_cleanup_rejects_missing_handoff(tmp_path):
    workspace, result = completed_task(tmp_path, collect=True)
    with pytest.raises(ContractError, match="handoff"):
        cleanup_workspace(workspace["root"], local_index=result["local_index"], terminal_ref=result["terminal_ref"])
    assert Path(result["local_index"]).exists()


def test_replaced_scratch_does_not_authorize_user_directory_deletion(tmp_path):
    workspace, result = completed_task(tmp_path)
    scratch = Path(workspace["scratch"])
    kept = scratch.with_name("kept")
    scratch.rename(kept)
    scratch.symlink_to(kept, target_is_directory=True)
    with pytest.raises(ContractError, match="ownership"):
        cleanup_workspace(workspace["root"], local_index=result["local_index"], terminal_ref=result["terminal_ref"])
    assert kept.is_dir()


def test_other_task_index_cannot_authorize_cleanup(tmp_path):
    workspace, result = completed_task(tmp_path)
    another = create_workspace("other-task", parent=tmp_path)
    with pytest.raises(ContractError, match="this task"):
        cleanup_workspace(another["root"], local_index=result["local_index"], terminal_ref=result["terminal_ref"])
    assert Path(another["scratch"]).exists()


def test_occupied_cleanup_record_preserves_all_scratch(tmp_path):
    workspace, result = completed_task(tmp_path)
    (Path(workspace["root"]) / "cleanup.json").write_text("prior record")
    with pytest.raises(ContractError, match="already exists"):
        cleanup_workspace(workspace["root"], local_index=result["local_index"], terminal_ref=result["terminal_ref"])
    assert Path(result["local_index"]).exists()


def test_collector_handoff_then_cleanup_preserves_independent_archive(tmp_path):
    from aprof_runtime.local_archive import archive, verify_archive_receipt
    workspace, result = completed_task(tmp_path, collect=True)
    local = LocalEvidence.from_index(result["local_index"])
    receipt = tmp_path / "archive-receipt.json"
    archived = archive(result["local_index"], local.verify_artifact(result["terminal_ref"]),
        tmp_path / "trace.sqlite", receipt, task_id=workspace["task_id"])
    assert archived["terminal_status"] == "failed" and archived["cost_scope"] == "post_task_archive"
    outcome = cleanup_workspace(workspace["root"], local_index=result["local_index"],
                                terminal_ref=result["terminal_ref"], collector_receipt=receipt)
    assert outcome["original_status"] == "failed"
    verified = verify_archive_receipt(receipt, local_index=None,
        completion_ref=result["terminal_ref"], task_id=workspace["task_id"])
    assert verified["task_cost_seconds"] == outcome["cumulative_execution_seconds"]


def test_collector_handoff_cannot_cover_later_index_changes(tmp_path):
    from aprof_runtime.local_archive import archive
    workspace, result = completed_task(tmp_path, collect=True)
    local = LocalEvidence.from_index(result["local_index"])
    receipt = tmp_path / "archive-receipt.json"
    archive(result["local_index"], local.verify_artifact(result["terminal_ref"]),
            tmp_path / "trace.sqlite", receipt, task_id=workspace["task_id"])
    local.register_json({"uncollected": True})
    changed = local.write_index(Path(workspace["scratch"]) / "later-index.json")
    with pytest.raises(ContractError, match="index binding"):
        cleanup_workspace(workspace["root"], local_index=changed,
                          terminal_ref=result["terminal_ref"], collector_receipt=receipt)
    assert Path(workspace["scratch"]).exists()
