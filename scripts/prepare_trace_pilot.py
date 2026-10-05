#!/usr/bin/env python3
"""Prepare a small, reproducible CANNBench AProf trace run.

This script deliberately stops before build, correctness, timing, profiling,
or candidate mutation.  It freezes the run inputs, creates split-isolated
EpisodeStores, snapshots each baseline into the CAS, validates a Context, and
records the conservative expert-prior route that follows from current
evidence.  Existing profiling and runtime tools execute the later stages.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from aprof_runtime import __version__ as RUNTIME_VERSION  # noqa: E402
from aprof_runtime.contracts import Context  # noqa: E402
from aprof_runtime.graph import load_snapshot, route_graph  # noqa: E402
from aprof_runtime.jsonio import content_hash, file_hash, to_primitive  # noqa: E402
from aprof_runtime.store import EpisodeStore  # noqa: E402


SCHEMA_VERSION = "1.0.0"
ALLOWED_SPLITS = {"train", "validation"}
PRODUCER_ROLES = ("model", "prompt", "agent")
DEFAULT_EXCLUDES = (
    ".git",
    ".git/*",
    ".aprof",
    ".aprof/*",
    "build",
    "build/*",
    "build_*",
    "build_*/*",
    "__pycache__",
    "*/__pycache__",
    "*/__pycache__/*",
    "*.pyc",
    "data",
    "data/*",
    "results",
    "results/*",
    "docs/perf",
    "docs/perf/*",
)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{path} must match {SAFE_ID.pattern}")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _repo_path(value: Any, path: str) -> Path:
    text = _string(value, path)
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _repo_relative(path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the AProf checkout: {path}") from exc


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns)


def create_source_snapshot(
    source_root: Path,
    output: Path,
    *,
    root_label: str,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> dict[str, Any]:
    """Create a deterministic, self-describing tar snapshot of a source tree."""

    root = source_root.resolve()
    if not root.is_dir():
        raise ValueError(f"source tree does not exist: {root}")
    if output.exists():
        raise ValueError(f"refusing to overwrite source snapshot: {output}")

    files: list[tuple[str, Path, int, int, str]] = []
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = candidate.relative_to(root).as_posix()
        if _excluded(relative, excludes):
            continue
        if candidate.is_symlink():
            raise ValueError(f"source snapshot rejects symlinks: {candidate}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"source snapshot requires regular files: {candidate}")
        stat = candidate.stat()
        files.append(
            (
                relative,
                candidate,
                stat.st_mode & 0o777,
                stat.st_size,
                file_hash(candidate),
            )
        )
    if not files:
        raise ValueError(f"source snapshot contains no files: {root}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "aprof_source_snapshot_v1",
        "root_label": root_label,
        "excludes": list(excludes),
        "files": [
            {"path": relative, "mode": mode, "size_bytes": size, "sha256": digest}
            for relative, _, mode, size, digest in files
        ],
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        manifest_info = tarfile.TarInfo("APROF_SOURCE_SNAPSHOT.json")
        manifest_info.size = len(manifest_bytes)
        _normalize_tar_info(manifest_info, 0o644)
        archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for relative, candidate, mode, size, _ in files:
            info = tarfile.TarInfo(f"source/{relative}")
            info.size = size
            _normalize_tar_info(info, mode)
            with candidate.open("rb") as stream:
                archive.addfile(info, stream)
    return {
        "path": str(output),
        "sha256": file_hash(output),
        "file_count": len(files),
        "manifest_sha256": _sha256_bytes(manifest_bytes),
    }


def _normalize_tar_info(info: tarfile.TarInfo, mode: int) -> None:
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = mode
    info.pax_headers = {}


def _pending_names(manifest: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in manifest.get("pending_operators", []):
        name = item.get("name") if isinstance(item, dict) else item
        values.append(_string(name, "pending operator"))
    return values


def _split_state(expected_version: str) -> tuple[dict[str, dict[str, Any]], str]:
    root = REPO_ROOT / "benchmarks" / "cannbench"
    manifests = {
        name: _load_json(root / name / "manifest.json")
        for name in ("train", "validation", "test")
    }
    for name, manifest in manifests.items():
        if manifest.get("split_version") != expected_version:
            raise ValueError(
                f"{name} split version {manifest.get('split_version')!r} "
                f"does not match requested {expected_version!r}"
            )
    membership = {
        name: {
            "active_operators": manifest["active_operators"],
            "pending_operators": _pending_names(manifest),
        }
        for name, manifest in manifests.items()
    }
    digest = hashlib.sha256(
        json.dumps(membership, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    index = _load_json(root / "split_index.json")
    if digest != index.get("membership_sha256"):
        raise ValueError(
            "frozen CANNBench membership digest mismatch: "
            f"expected {index.get('membership_sha256')}, got {digest}"
        )
    return manifests, digest


def _selection(value: Any, path: str) -> tuple[str, int | None]:
    if value is None:
        return "argmax", None
    if not isinstance(value, dict) or set(value) != {"mode", "seed"}:
        raise ValueError(f"{path} must contain exactly mode and seed")
    mode, seed = value["mode"], value["seed"]
    if mode == "argmax" and seed is None:
        return mode, None
    if mode == "sample" and isinstance(seed, int) and not isinstance(seed, bool):
        return mode, seed
    raise ValueError(f"{path} requires argmax/null or sample/integer")


def _budget(value: Any, path: str) -> dict[str, int]:
    fields = {"candidate_limit", "build_limit", "timing_limit", "full_profile_limit"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{path} must contain exactly {sorted(fields)}")
    result: dict[str, int] = {}
    for name in sorted(fields):
        item = value[name]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ValueError(f"{path}.{name} must be a non-negative integer")
        result[name] = item
    return result


def _case_ids(value: Any, path: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a non-empty array")
    if any(isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 20 for item in value):
        raise ValueError(f"{path} values must be integers from 1 through 20")
    if len(set(value)) != len(value):
        raise ValueError(f"{path} values must be unique")
    return value


def _producer_paths(config: dict[str, Any]) -> dict[str, Path]:
    raw = config.get("producer_artifacts", {})
    if not isinstance(raw, dict) or set(raw) - set(PRODUCER_ROLES):
        raise ValueError(f"producer_artifacts may contain only {PRODUCER_ROLES}")
    result: dict[str, Path] = {}
    for role, value in raw.items():
        path = _repo_path(value, f"producer_artifacts.{role}")
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"producer_artifacts.{role} is not a regular file: {path}")
        result[role] = path
    return result


def _git_state() -> dict[str, Any]:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    return {"commit": commit, "dirty": dirty}


def _validate_config(config: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "run_id", "split_version", "graph", "tasks"}
    optional = {"producer_artifacts", "notes"}
    missing, unknown = required - set(config), set(config) - required - optional
    if missing or unknown:
        raise ValueError(f"config fields invalid: missing={sorted(missing)}, unknown={sorted(unknown)}")
    if config["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    _safe_id(config["run_id"], "run_id")
    _safe_id(config["split_version"], "split_version")
    _producer_paths(config)
    tasks = config["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty array")
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        path = f"tasks[{index}]"
        required_task = {
            "task_id", "split", "operator", "op_dir", "hardware_fingerprint",
            "origin", "lineage_id", "sentinel_case_ids", "budget",
        }
        optional_task = {"selection", "evidence", "device", "build_jobs"}
        if not isinstance(task, dict):
            raise ValueError(f"{path} must be an object")
        missing = required_task - set(task)
        unknown = set(task) - required_task - optional_task
        if missing or unknown:
            raise ValueError(f"{path} fields invalid: missing={sorted(missing)}, unknown={sorted(unknown)}")
        task_id = _safe_id(task["task_id"], f"{path}.task_id")
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        if task["split"] not in ALLOWED_SPLITS:
            raise ValueError(f"{path}.split must be train or validation; sealed test is forbidden")
        _safe_id(task["operator"], f"{path}.operator")
        _string(task["hardware_fingerprint"], f"{path}.hardware_fingerprint")
        if task["origin"] not in {"natural", "single_fault_injection", "rewind", "no_harm"}:
            raise ValueError(f"{path}.origin is not supported")
        _safe_id(task["lineage_id"], f"{path}.lineage_id")
        _case_ids(task["sentinel_case_ids"], f"{path}.sentinel_case_ids")
        _budget(task["budget"], f"{path}.budget")
        _selection(task.get("selection"), f"{path}.selection")
        evidence = task.get("evidence", {"predicate_states": {}})
        if not isinstance(evidence, dict) or not isinstance(evidence.get("predicate_states", {}), dict):
            raise ValueError(f"{path}.evidence.predicate_states must be an object")
        for field, default in (("device", 0), ("build_jobs", 4)):
            item = task.get(field, default)
            minimum = 0 if field == "device" else 1
            if isinstance(item, bool) or not isinstance(item, int) or item < minimum:
                raise ValueError(f"{path}.{field} must be an integer >= {minimum}")
    return config


def prepare(config: dict[str, Any], output_root: Path) -> dict[str, Any]:
    config = _validate_config(config)
    run_id = config["run_id"]
    split_version = config["split_version"]
    graph_path = _repo_path(config["graph"], "graph")
    graph, graph_manifest = load_snapshot(graph_path)
    if graph_manifest is None:
        raise ValueError("graph must be an immutable snapshot directory with a validated manifest")
    manifests, membership_digest = _split_state(split_version)
    producer_paths = _producer_paths(config)

    validated_tasks: list[tuple[dict[str, Any], Path]] = []
    canonical_operator_root = (REPO_ROOT / "benchmarks" / "cannbench" / "operators").resolve()
    for index, task in enumerate(config["tasks"]):
        split = task["split"]
        operator = task["operator"]
        if operator not in manifests[split]["active_operators"]:
            raise ValueError(f"tasks[{index}]: {operator!r} is not active in split {split!r}")
        op_dir = _repo_path(task["op_dir"], f"tasks[{index}].op_dir")
        expected = canonical_operator_root / operator
        if op_dir != expected or not op_dir.is_dir():
            raise ValueError(
                f"tasks[{index}].op_dir must be the canonical project {expected}"
            )
        validated_tasks.append((task, op_dir))

    root = output_root.resolve()
    run_dir = root / run_id
    if run_dir.exists():
        raise ValueError(f"refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir()
    input_config_path = run_dir / "input-config.json"
    _write_json(input_config_path, config)

    stores: dict[str, Path] = {}
    producer_hashes: dict[str, str] = {role: "unknown" for role in PRODUCER_ROLES}
    for split in sorted({task["split"] for task, _ in validated_tasks}):
        store_path = run_dir / split / "episodes.sqlite"
        with EpisodeStore(store_path):
            pass
        stores[split] = store_path

    # Producer artifacts are required in every split-local CAS that may later
    # contain episodes; hashes remain identical because registration is content-addressed.
    for split, store_path in stores.items():
        with EpisodeStore(store_path) as store:
            for role, path in producer_paths.items():
                digest = store.register_artifact(path, media_type="application/octet-stream")
                if producer_hashes[role] == "unknown":
                    producer_hashes[role] = digest
                elif digest != producer_hashes[role]:
                    raise ValueError(f"producer artifact hash changed while preparing role {role}")

    empty_patch = artifacts_dir / "empty.patch"
    empty_patch.write_bytes(b"")
    empty_patch_hashes: dict[str, str] = {}
    for split, store_path in stores.items():
        with EpisodeStore(store_path) as store:
            empty_patch_hashes[split] = store.register_artifact(
                empty_patch, media_type="text/x-diff"
            )

    prepared_tasks: list[dict[str, Any]] = []
    created_at = _utc_now()
    for task, op_dir in validated_tasks:
        task_id, split, operator = task["task_id"], task["split"], task["operator"]
        task_dir = run_dir / "tasks" / task_id
        task_dir.mkdir(parents=True)
        snapshot_path = task_dir / "artifacts" / "baseline-source.tar"
        snapshot = create_source_snapshot(
            op_dir, snapshot_path, root_label=f"cannbench/{operator}"
        )
        with EpisodeStore(stores[split]) as store:
            baseline_hash = store.register_artifact(
                snapshot_path, media_type="application/x-tar"
            )
        if baseline_hash != snapshot["sha256"]:
            raise ValueError("baseline snapshot hash changed during CAS registration")

        budget = _budget(task["budget"], f"task.{task_id}.budget")
        evidence = task.get("evidence", {"predicate_states": {}})
        context_value = {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "operator": operator,
            "hardware_fingerprint": task["hardware_fingerprint"],
            "workload": {
                "origin": task["origin"],
                "lineage_id": task["lineage_id"],
                "split": split,
                "split_version": split_version,
                "sentinel_case_ids": task["sentinel_case_ids"],
                "acceptance_case_ids": list(range(1, 21)),
                "baseline_source_artifact_hash": baseline_hash,
                "project_path": _repo_relative(op_dir, "op_dir"),
            },
            "budget": budget,
            "evidence": evidence,
        }
        context = Context.from_dict(context_value)
        selection_mode, selection_seed = _selection(task.get("selection"), f"task.{task_id}.selection")
        route = route_graph(
            graph,
            context,
            selection_mode=selection_mode,
            selection_seed=selection_seed,
        )
        context_path, route_path = task_dir / "context.json", task_dir / "route.json"
        _write_json(context_path, to_primitive(context))
        _write_json(route_path, to_primitive(route))

        device, jobs = task.get("device", 0), task.get("build_jobs", 4)
        stages = {
            "schema_version": SCHEMA_VERSION,
            "op_dir": str(op_dir),
            "output_dir": str(task_dir / "executions" / "baseline"),
            "stages": [
                {
                    "name": "build",
                    "commands": [
                        ["cmake", "-S", ".", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"],
                        ["cmake", "--build", "build", f"-j{jobs}"],
                    ],
                    "timeout_seconds": 1200,
                    "required": True,
                },
                {
                    "name": "correctness",
                    "commands": [
                        ["bash", "run.sh", "--all", "--skip-build", "--device", str(device)]
                    ],
                    "timeout_seconds": 3600,
                    "required": True,
                },
            ],
        }
        stages_path = task_dir / "profile-stages.baseline.json"
        _write_json(stages_path, stages)

        python = sys.executable
        commands = {
            "validate_context": [
                python, "-m", "aprof_runtime", "contract", "validate",
                "--kind", "context", "--input", str(context_path),
            ],
            "route_current_context": [
                python, "-m", "aprof_runtime", "graph", "route",
                "--graph", str(graph_path), "--context", str(context_path),
                "--selection-mode", selection_mode,
            ] + (["--selection-seed", str(selection_seed)] if selection_seed is not None else []),
            "dry_run_baseline_stages": [
                python,
                str(REPO_ROOT / "skills/aprof/profiling/scripts/run_profile_stages.py"),
                "--config", str(stages_path),
                "--report", str(task_dir / "profile-stages.baseline.dry-run.json"),
                "--dry-run",
            ],
            "execute_baseline_stages": [
                python,
                str(REPO_ROOT / "skills/aprof/profiling/scripts/run_profile_stages.py"),
                "--config", str(stages_path),
                "--report", str(task_dir / "profile-stages.baseline.json"),
            ],
            "verify_episode_store": [
                python, "-m", "aprof_runtime", "episode", "verify",
                "--store", str(stores[split]),
            ],
        }
        commands_path = task_dir / "next-commands.json"
        _write_json(commands_path, {
            "environment": {"PYTHONPATH": str(REPO_ROOT / "src")},
            "commands": commands,
        })

        prepared_tasks.append({
            "task_id": task_id,
            "operator": operator,
            "split": split,
            "origin": task["origin"],
            "lineage_id": task["lineage_id"],
            "state_directory": str(task_dir),
            "episode_store": str(stores[split]),
            "baseline_snapshot": snapshot,
            "context": {"path": str(context_path), "sha256": file_hash(context_path)},
            "route": {
                "path": str(route_path),
                "sha256": file_hash(route_path),
                "selected_edge_id": route.selected_edge_id,
                "selected_mechanism_id": route.selected_mechanism_id,
                "behavior_probability": route.behavior_probability,
                "selection_mode": route.selection_mode,
                "selection_seed": route.selection_seed,
            },
            "baseline_stage_config": {
                "path": str(stages_path), "sha256": file_hash(stages_path)
            },
            "next_commands": str(commands_path),
            "status": "prepared_no_execution",
        })

    warnings: list[str] = []
    missing_producers = [role for role, digest in producer_hashes.items() if digest == "unknown"]
    if missing_producers:
        warnings.append(
            "producer artifacts are missing for " + ", ".join(missing_producers)
            + "; resulting episodes are exploratory and default policy training will skip them"
        )
    placeholder_fingerprints = [
        task["task_id"] for task, _ in validated_tasks
        if task["hardware_fingerprint"].upper().startswith(("REPLACE", "UNKNOWN"))
    ]
    if placeholder_fingerprints:
        warnings.append(
            "exact hardware fingerprints are still required for tasks: "
            + ", ".join(placeholder_fingerprints)
        )
    repository_state = _git_state()
    if repository_state["dirty"]:
        warnings.append("the checkout is dirty; commit or record the intended diff before executing traces")

    run_manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "aprof_trace_pilot_run_v1",
        "run_id": run_id,
        "created_at": created_at,
        "config_sha256": content_hash(config),
        "input_config": {
            "path": str(input_config_path),
            "file_sha256": file_hash(input_config_path),
        },
        "repository": repository_state,
        "runtime_build": f"aprof-runtime/{RUNTIME_VERSION}",
        "graph": {
            "path": _repo_relative(graph_path, "graph"),
            "version": graph["graph_version"],
            "canonical_hash": content_hash(graph),
            "graph_file_hash": (
                "sha256:" + graph_manifest["graph_sha256"]
            ),
        },
        "dataset": {
            "name": "cannbench",
            "split_version": split_version,
            "membership_sha256": membership_digest,
            "sealed_test_allowed": False,
        },
        "producer_hashes": producer_hashes,
        "empty_patch_hashes": empty_patch_hashes,
        "stores": {name: str(path) for name, path in sorted(stores.items())},
        "tasks": prepared_tasks,
        "notes": config.get("notes", ""),
        "warnings": warnings,
        "status": "prepared_no_execution",
    }
    manifest_path = run_dir / "run-manifest.json"
    _write_json(manifest_path, run_manifest)
    return {"run_directory": str(run_dir), "manifest": str(manifest_path), "value": run_manifest}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".aprof" / "runs",
        help="parent directory for the immutable run directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare(_load_json(args.config), args.output_root)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "run_directory": result["run_directory"],
                "manifest": result["manifest"],
                "warnings": result["value"]["warnings"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
