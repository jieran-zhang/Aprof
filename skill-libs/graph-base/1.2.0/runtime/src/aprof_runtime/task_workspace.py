"""Small owned scratch lifecycle; never remove user sources or final outputs."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import uuid

from .errors import ContractError
from .jsonio import file_hash
from .local_evidence import LocalEvidence
from .task_budget import replay_task_terminal

MARKER = ".aprof-workspace.json"


def _identity(path):
    info = path.stat()
    return [info.st_dev, info.st_ino]


def create_workspace(task_id, *, parent=None, collect=False):
    if not isinstance(task_id, str) or not task_id.strip() or type(collect) is not bool:
        raise ContractError("workspace requires a task id and explicit collection policy")
    from .execution_policy import local_path
    import re
    parent = local_path(parent or "/dev/shm")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id):
        raise ContractError("task id must be a safe path component")
    root = parent / ("aprof-" + task_id)
    root.mkdir(mode=0o700, exist_ok=False)
    (root / "tmp").mkdir()
    (root / "validation-cache").mkdir()
    scratch, final = root / "scratch", root / "final"
    scratch.mkdir(mode=0o700); final.mkdir(mode=0o700)
    marker = {"schema_version": 1, "kind": "task_workspace_v1", "workspace_id": uuid.uuid4().hex,
              "task_id": task_id, "root": str(root), "root_identity": _identity(root),
              "scratch_identity": _identity(scratch), "collection_requested": collect}
    with (root / MARKER).open("x", encoding="utf-8") as stream:
        json.dump(marker, stream, indent=2); stream.write("\n")
    return {**marker, "scratch": str(scratch), "final": str(final)}


def cleanup_workspace(root, *, local_index, terminal_ref, collector_receipt=None):
    """Delete owned scratch only after real exit and, when requested, handoff.

    Receipt replay/archival cost occurs after the task. Rejected cleanup leaves
    all scratch intact. Final deliveries and all paths outside scratch survive.
    """
    root = Path(root).absolute()
    marker_path, scratch = root / MARKER, root / "scratch"
    if root.resolve() != root or root.is_symlink() or marker_path.is_symlink():
        raise ContractError("workspace ownership path changed")
    marker = json.loads(marker_path.read_text())
    cleanup_path = root / "cleanup.json"
    if cleanup_path.exists() or cleanup_path.is_symlink():
        raise ContractError("cleanup record already exists; scratch has not been removed")
    if (marker.get("kind") != "task_workspace_v1" or marker.get("schema_version") != 1
            or marker.get("root") != str(root) or marker.get("root_identity") != _identity(root)
            or type(marker.get("collection_requested")) is not bool
            or not scratch.is_dir() or scratch.is_symlink()
            or marker.get("scratch_identity") != _identity(scratch)):
        raise ContractError("workspace ownership identity changed")
    index = Path(local_index).absolute()
    if index.resolve() != index or not index.is_relative_to(scratch):
        raise ContractError("cleanup index must belong to this task scratch")
    reader = LocalEvidence.from_index(index)
    terminal = reader.read_json_artifact(terminal_ref)
    launch = reader.read_json_artifact(terminal["launch_ref"])
    result = replay_task_terminal(reader, terminal_ref, task_id=marker["task_id"],
                                  budget_ref=launch["budget_ref"])
    handoff = None
    if marker["collection_requested"]:
        if collector_receipt is None:
            raise ContractError("collector handoff must complete before cleanup")
        receipt_path = Path(collector_receipt).resolve(strict=True)
        if receipt_path.is_relative_to(scratch):
            raise ContractError("collector receipt must survive scratch cleanup")
        from .local_archive import verify_archive_receipt
        handoff = verify_archive_receipt(receipt_path, local_index=index,
                                         completion_ref=terminal_ref, task_id=marker["task_id"])
    elif collector_receipt is not None:
        raise ContractError("unexpected collector receipt for a non-archived task")
    summary = {"schema_version": 1, "kind": "task_cleanup_v1", "task_id": marker["task_id"],
        "workspace_id": marker["workspace_id"], "terminal_ref": terminal_ref,
        "local_index_sha256": file_hash(index), "original_status": result["status"],
        "cumulative_execution_seconds": result["cumulative_seconds"],
        "collector_receipt": None if handoff is None else str(receipt_path),
        "removed": str(scratch), "preserved_final": str(root / "final")}
    # CPython's fd-based rmtree does not follow links placed inside scratch.
    if not shutil.rmtree.avoids_symlink_attacks:
        raise ContractError("this Python cannot safely clean task scratch")
    if _identity(scratch) != marker["scratch_identity"]:
        raise ContractError("scratch was replaced during handoff verification")
    # Reserve the output before deleting anything: an occupied record path
    # must not turn a successfully deleted scratch into a reported rejection.
    with cleanup_path.open("x", encoding="utf-8") as stream:
        json.dump({**summary, "cleanup_status": "in_progress"}, stream); stream.flush()
        shutil.rmtree(scratch)
        stream.seek(0); stream.truncate()
        json.dump(summary, stream, indent=2); stream.write("\n")
    return summary
