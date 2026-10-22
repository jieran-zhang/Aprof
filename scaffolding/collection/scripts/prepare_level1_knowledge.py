#!/usr/bin/env python3
"""Freeze task-local knowledge and attest actual reads for isolated Level1 agents.

Preparation is read-only for canonical operators/skills/graph. A manifest is a
catalog, not a claim that an agent read its contents: only the ``read`` command
returns bytes and appends to knowledge_reads.jsonl. No hardware commands run.
"""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
import ast
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
OPERATORS = {
    "foreach_norm": "train", "exp": "train", "masked_scale": "train",
    "foreach_addcdiv_scalar": "train", "mish": "train", "sigmoid": "train",
    "gelu": "validation",
}
PINNED_CANNBENCH = "ae5610d57f39b829714191e56bdf863fad708586"
DEFAULT_BUDGET = {"candidate_limit": 6, "build_limit": 6, "timing_limit": 6, "full_profile_limit": 3}
DEFAULT_SKILLS = ("ascendc-aprof-workflow", "npu-arch", "ascendc-aprof-parallel-planning", "ascendc-aprof-diagnosis", "ascendc-aprof-profiling", "ascendc-aprof-optimization")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def artifact(path: Path, root: Path | None = None) -> dict[str, Any]:
    return {"path": str(path.relative_to(root) if root else path.resolve()), "sha256": digest(path.read_bytes()), "size_bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE).strip()


def dependency_state(repo_root: Path) -> dict[str, Any]:
    result = {}
    for name in ("cann-bench",):
        path = repo_root / "scaffolding/third_party" / name
        if not (path / ".git").exists():
            raise ValueError(f"dependency is not initialized: {path}")
        commit = git(path, "rev-parse", "HEAD")
        if name == "cann-bench" and commit != PINNED_CANNBENCH:
            raise ValueError(f"cann-bench must remain pinned to {PINNED_CANNBENCH}, found {commit}")
        status = git(path, "status", "--porcelain")
        if status:
            raise ValueError(f"dependency has uncommitted changes: {name}")
        result[name] = {"commit": commit, "url": git(path, "remote", "get-url", "origin"), "path": str(path.resolve())}
    inventory = []
    for entry in registry_entries(repo_root):
        source = skill_lib() / entry["source"]
        if not (source / "SKILL.md").is_file() or not entry["source"].startswith("skills/"):
            raise ValueError(f"local knowledge source is unavailable: {entry['source']}")
        inventory.extend(artifact(path, skill_lib()) for path in sorted(source.rglob("*"))
                         if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    result["aprof-knowledge"] = {"inventory_sha256": digest(canonical(inventory)), "files": inventory}
    return result


def registry_entries(repo_root: Path) -> list[dict[str, Any]]:
    registry = json.loads((skill_lib() / "skillgraph/registry.json").read_text())
    return registry["capabilities"]["core"] + registry["support_skills"]


def resolve_reference(repo_root: Path, reference: str) -> Path:
    """Resolve only registry-owned knowledge in the selected release."""
    root = skill_lib()
    entries = registry_entries(root)
    for entry in entries:
        if reference in (entry["name"], *entry.get("legacy_names", [])):
            reference = entry["source"] + "/SKILL.md"
            break
    relative = Path(reference)
    if ".." in relative.parts:
        raise ValueError("knowledge reference escapes release")
    candidate = (relative if relative.is_absolute() else root / relative).resolve()
    allowed = [root / entry["source"] for entry in entries]
    if not any(candidate.is_relative_to(path) for path in allowed):
        raise ValueError("knowledge reference is not a registry-owned skill")
    if not candidate.is_file():
        raise ValueError(f"knowledge reference cannot be resolved: {reference}")
    return candidate


def json_safe(value: Any) -> Any:
    """Represent special workload values explicitly without non-JSON numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"value": None, "reason": "workload_special_value", "special": "nan" if math.isnan(value) else ("+inf" if value > 0 else "-inf")}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def literal(node: ast.AST) -> Any:
    """Read trusted case constants without importing their Python module."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [literal(v) for v in node.elts]
    if isinstance(node, ast.Dict):
        return {literal(k): literal(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return (-1 if isinstance(node.op, ast.USub) else 1) * literal(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return literal(node.left) * literal(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        return literal(node.left) ** literal(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float" and len(node.args) == 1 and not node.keywords:
        arg = literal(node.args[0])
        if arg in ("inf", "-inf", "nan"):
            return float(arg)
    raise ValueError(f"unsupported case literal: {ast.dump(node)}")


def local_cases(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text())
    rows = keys = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets):
                rows = literal(node.value)
            if any(isinstance(target, ast.Name) and target.id == "keys" for target in node.targets):
                keys = literal(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "zip" and isinstance(node.args[0], (ast.Tuple, ast.List)):
            keys = literal(node.args[0])
    if rows is None or keys is None:
        raise ValueError(f"cannot extract CASES/get_case keys: {path}")
    result = [dict(zip(keys, row)) for row in rows]
    if [row["case_id"] for row in result] != list(range(1, 21)):
        raise ValueError("Level1 case IDs must be exactly 1..20")
    return result


def decode_special(value: Any) -> Any:
    if isinstance(value, str) and value in ("inf", "-inf", "nan"):
        return float(value)
    if isinstance(value, list):
        return [decode_special(v) for v in value]
    if isinstance(value, dict):
        return {k: decode_special(v) for k, v in value.items()}
    return value


def normalized_local_case(operator: str, row: dict[str, Any]) -> dict[str, Any]:
    attrs = {key: row[key] for key in ("base", "scale", "shift", "scalar", "approximate") if key in row}
    if operator == "masked_scale":
        shapes, dtypes, ranges = [row["shape"], row["shape"]], [row["x_dtype"], row["mask_dtype"]], [row["x_range"], row["mask_range"]]
    elif operator == "foreach_addcdiv_scalar":
        shapes, dtypes, ranges = [row["shapes"]] * 3, [row["dtype"]], row["value_ranges"]
    else:
        shapes, dtypes, ranges = [row.get("shapes", row.get("shape"))], [row["dtype"]], row["value_range"]
    return json_safe({"case_id": row["case_id"], "input_shape": shapes, "dtype": dtypes, "attrs": attrs, "value_range": ranges})


def verify_task_parity(repo_root: Path, operator: str) -> dict[str, Any]:
    """Verify the exact case matrix and freeze the explicitly local oracle.

    Case/tolerance equivalence is machine checked. Oracle and checker behavior
    are preserved as distinct contracts; no algebraic similarity is mislabeled
    as proof of equivalence with the full official evaluator.
    """
    if operator not in OPERATORS:
        raise ValueError("task outside the authorized seven-task campaign")
    root = repo_root.resolve()
    local = root / "scaffolding/benchmarks/cannbench/operators" / operator
    upstream = root / "scaffolding/third_party/cann-bench/tasks/level1" / operator
    local_matrix = [normalized_local_case(operator, row) for row in local_cases(local / "scripts/cases.py")]
    with (upstream / "cases.csv").open(newline="", encoding="utf-8-sig") as stream:
        upstream_matrix = [json_safe({"case_id": int(row["case_id"]), **{key: decode_special(json.loads(row[key])) for key in ("input_shape", "dtype", "attrs", "value_range")}}) for row in csv.DictReader(stream)]
    mismatches = [{"case_id": a["case_id"], "local": a, "upstream": b} for a, b in zip(local_matrix, upstream_matrix) if a != b]
    if len(upstream_matrix) != 20:
        mismatches.append({"reason": "upstream_case_count", "count": len(upstream_matrix)})
    import yaml
    proto = yaml.safe_load((upstream / "proto.yaml").read_text())["operator"]
    expected_thresholds = proto.get("precision_thresholds", {"float16": 2**-10, "bfloat16": 2**-7, "float32": 2**-13})
    local_thresholds = None
    for node in ast.walk(ast.parse((local / "scripts/verify_result.py").read_text())):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "threshold" for target in node.targets):
            if isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Dict):
                local_thresholds = literal(node.value.value)
    if local_thresholds != expected_thresholds:
        mismatches.append({"reason": "threshold_mismatch", "local": local_thresholds, "upstream": expected_thresholds})
    oracle_notes = {
        "foreach_norm": "Local torch.norm promotes FP16/BF16 to FP32 and casts back, as the task golden does; the full upstream evaluator additionally controls FP64/native-reference execution.",
        "foreach_addcdiv_scalar": "Local NumPy FP32 x1+(x2/x3)*scalar and output cast follow task formula; task-specific relaxed thresholds match proto.yaml.",
        "exp": "Local NumPy FP32 affine/log/exp and output cast follow task formula; transcendental implementation differs from upstream torch.",
        "masked_scale": "Local PyTorch x*mask*scale and output cast follow the upstream task formula and mixed input dtypes.",
        "mish": "Local oracle uses stable NumPy softplus (max(x,0)+log1p(exp(-abs(x)))) times tanh; upstream task calls torch.nn.functional.mish. Algebraic equivalence does not establish numerical equivalence.",
        "sigmoid": "Local oracle calls torch.sigmoid in input dtype, matching the task function; official evaluator precision promotion remains a separate contract.",
        "gelu": "Local oracle calls torch.nn.functional.gelu on float32 decoded input with the exact approximate attribute, then casts output; upstream task function runs on its evaluator-selected dtype.",
    }
    comparison_root = root / "scaffolding/third_party/cann-bench/src/kernel_eval"
    return {
        "schema_version": "1.0.0", "operator": operator, "split": OPERATORS[operator],
        "upstream_commit": git(root / "scaffolding/third_party/cann-bench", "rev-parse", "HEAD"),
        "case_count": len(local_matrix), "case_matrix_equal": not any("case_id" in item or item.get("reason") == "upstream_case_count" for item in mismatches),
        "thresholds_equal": local_thresholds == expected_thresholds, "mismatches": mismatches,
        "local_case_matrix_sha256": digest(canonical(local_matrix)), "upstream_case_matrix_sha256": digest(canonical(upstream_matrix)),
        "specification": {"schema": proto["schema"], "formula": proto["formula"], "layout": "contiguous ND", "cases": local_matrix},
        "precision_contract": {"active": "local_baseline_verifier_v1", "thresholds": local_thresholds, "epsilon": 1e-7, "mere_comparator": "<", "mare_multiplier": 10, "special_values": "matching NaN/+Inf/-Inf positions", "upstream_checker_equivalent": False,
            "oracle_note": oracle_notes[operator], "checker_note": "Local checker is plain finite-value MERE/MARE plus special-value masks; upstream also handles small-value and cancellation regions using native/FP64 references. Use the user-selected local baseline contract unchanged and do not claim official evaluator equivalence."},
        "evidence": {"local": [artifact(local / "scripts" / name) for name in ("cases.py", "gen_data.py", "verify_result.py")], "upstream": [artifact(upstream / name) for name in ("cases.csv", "cases.yaml", "proto.yaml", "golden.py")], "upstream_checker": artifact(comparison_root / "checkers/relative_error_checker.py"), "upstream_compare": artifact(comparison_root / "utils/compare.py")},
    }


def verify_split(repo_root: Path, operator: str, split: str) -> dict[str, Any]:
    if split not in ("train", "validation") or OPERATORS.get(operator) != split:
        raise ValueError("operator/split is outside the authorized seven-task campaign; sealed test is refused")
    path = repo_root / "scaffolding/benchmarks/cannbench" / split / "manifest.json"
    manifest = json.loads(path.read_text())
    if manifest.get("sealed") or operator not in manifest["active_operators"]:
        raise ValueError("operator not in requested unsealed split")
    return artifact(path)


def source_inventory(root: Path) -> list[dict[str, Any]]:
    excluded = {".git", ".aprof", "__pycache__", "data", "results", "perf"}
    files = []
    for path in sorted(root.rglob("*")):
        parts = path.relative_to(root).parts
        if any(part in excluded or part.startswith("build") for part in parts) or path.suffix in (".pyc", ".pyo"):
            continue
        if path.is_symlink():
            raise ValueError(f"baseline source must not contain symlinks: {path}")
        if path.is_file():
            files.append(artifact(path, root))
    return files


def prepare_manifest(repo_root: Path, operator: str, split: str, *, run_id: str, session_id: str,
                     output_dir: Path, commands: dict | None = None, budget: dict | None = None) -> dict[str, Any]:
    root = repo_root.resolve()
    split_ref = verify_split(root, operator, split)
    dependencies = dependency_state(root)
    parity = verify_task_parity(root, operator)
    if parity["mismatches"]:
        raise ValueError(f"upstream case/threshold parity failed: {parity['mismatches']}")
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"refusing to overwrite knowledge directory: {output_dir}")
    op_dir = root / "scaffolding/benchmarks/cannbench/operators" / operator
    source = source_inventory(op_dir)
    references = list(DEFAULT_SKILLS) + [
        "skills/ascendc-aprof-diagnosis/references/source-hypothesis-routing.md",
        "skills/ascendc-aprof-diagnosis/references/workload-aware-diagnosis.md",
        "skills/ascendc-aprof-profiling/references/metric-bundles.md",
        "skills/ascendc-aprof-optimization/references/optimization-candidate-design.md",
        "skills/ascendc-aprof-optimization/references/optimization-strategy-routing.md",
        "skills/ascendc-aprof-optimization/references/" + ("reduction-sort-optimization-playbook.md" if operator == "foreach_norm" else "vector-scalar-pipeline-playbook.md"),
    ]
    read_catalog = [{"requested_reference": ref, **artifact(resolve_reference(root, ref)), "purpose": "required workflow" if ref in DEFAULT_SKILLS else "initial targeted reference"} for ref in references]
    optional = []
    local_optional = []
    for directory in ("diagnosis", "optimization", "profiling"):
        for path in sorted((skill_lib() / "skills" / ("ascendc-aprof-" + directory) / "references").glob("*.md")):
            local_optional.append({"requested_reference": str(path.relative_to(skill_lib())), **artifact(path), "purpose": "on-demand local branch; do not load all by default"})
    for entry in registry_entries(root):
        for path in sorted((skill_lib() / entry["source"] / "references").rglob("*.md")):
            reference = str(path.relative_to(skill_lib()))
            optional.append({"requested_reference": reference, **artifact(path), "purpose": "precise local lookup; read only when relevant"})
    manifest = {
        "schema_version": "1.0.0", "kind": "aprof_level1_knowledge_manifest", "created_at": utc_now(),
        "run_id": run_id, "session_id": session_id, "operator": operator, "split": split,
        "repo_root": str(root), "op_dir": str(op_dir), "split_manifest": split_ref,
        "dependencies": dependencies, "producer": artifact(Path(__file__).resolve()),
        "graph": artifact(skill_lib() / "skillgraph/versions/v0001/graph.json"),
        "runtime_contracts": [artifact(path) for path in sorted((skill_lib() / "schemas").glob("*.json"))],
        "source": {"files": source, "inventory_sha256": digest(canonical(source))},
        "workload": {"cases": json_safe(local_cases(op_dir / "scripts/cases.py")), "layout": "contiguous", "sentinel_cases": [1, 8, 14, 20], "correctness_cases": list(range(1, 21))},
        "task_parity": parity,
        "required_reads": read_catalog, "optional_precise_reads": optional, "optional_local_reads": local_optional,
        "actual_reads_path": str(output_dir / "knowledge_reads.jsonl"),
        "commands": commands or {}, "remaining_budget": budget or dict(DEFAULT_BUDGET),
        "boundary": {"graph_policy_eligible": split == "train", "sealed_test_read_allowed": False, "historical_outcomes_read_allowed": False, "default_external_skill_entry_read_allowed": False},
        "instructions": "Read required skills through this helper; load local mechanism references and at most one operator playbook. Architecture and parallel planning precede workload-dispatched execution tuning. Read only catalogued AProf references; source URLs are provenance, not external skill dependencies. Each candidate has one atomic intent. Baseline remains read-only; all outcomes are recorded. Only machine gates determine verdicts."
    }
    manifest["manifest_sha256"] = digest(canonical(manifest))
    write_json(output_dir / "manifest.json", manifest)
    (output_dir / "knowledge_reads.jsonl").touch(exist_ok=False)
    return manifest


def read_reference(manifest_path: Path, reference: str, used_for: str, *, role: str | None = None) -> str:
    if not used_for.strip():
        raise ValueError("an actual knowledge read requires a purpose")
    manifest = json.loads(manifest_path.read_text())
    expected_hash = manifest.pop("manifest_sha256")
    if digest(canonical(manifest)) != expected_hash:
        raise ValueError("knowledge manifest hash mismatch")
    root = Path(manifest["repo_root"])
    verify_split(root, manifest["operator"], manifest["split"])
    path = resolve_reference(root, reference)
    allowed = manifest["required_reads"] + manifest["optional_precise_reads"] + manifest["optional_local_reads"]
    entry = next((item for item in allowed if item["path"] == str(path)), None)
    if entry is None:
        raise ValueError("reference is outside authorized knowledge catalog")
    content = path.read_bytes()
    sha256 = digest(content)
    if entry and sha256 != entry["sha256"]:
        raise ValueError("knowledge reference changed after manifest freeze")
    record = {"schema_version": "1.0.0", "manifest_sha256": expected_hash, "run_id": manifest["run_id"], "session_id": manifest["session_id"], "operator": manifest["operator"], "split": manifest["split"], "timestamp": utc_now(), "requested_reference": reference, "path": str(path), "sha256": sha256, "used_for": used_for, "role": role}
    log_path = Path(manifest["actual_reads_path"])
    with log_path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        lines = stream.readlines()
        if lines and not lines[-1].endswith("\n"):
            raise ValueError("incomplete knowledge read log; preserve it and recover explicitly")
        verify_read_records(lines, expected_hash)
        previous = json.loads(lines[-1]) if lines else None
        record["sequence"] = len(lines) + 1
        record["previous_read_hash"] = previous["read_hash"] if previous else None
        record["read_hash"] = digest(canonical(record))
        stream.write(canonical(record).decode() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return content.decode("utf-8")


def verify_read_records(lines: list[str], manifest_sha256: str) -> None:
    previous = None
    for sequence, line in enumerate(lines, 1):
        if not line.endswith("\n"):
            raise ValueError("incomplete knowledge read record")
        record = json.loads(line)
        read_hash = record.pop("read_hash")
        if record["manifest_sha256"] != manifest_sha256 or record["sequence"] != sequence or record["previous_read_hash"] != previous or digest(canonical(record)) != read_hash:
            raise ValueError("knowledge read hash chain mismatch")
        previous = read_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--operator", required=True, choices=OPERATORS)
    prepare.add_argument("--split", required=True, choices=("train", "validation"))
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--session-id", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--commands", type=Path)
    read = sub.add_parser("read")
    read.add_argument("--manifest", type=Path, required=True)
    read.add_argument("--reference", required=True)
    read.add_argument("--used-for", required=True)
    read.add_argument("--role")
    audit = sub.add_parser("audit")
    audit.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        manifest = prepare_manifest(REPO_ROOT, args.operator, args.split, run_id=args.run_id, session_id=args.session_id, output_dir=args.output, commands=json.loads(args.commands.read_text()) if args.commands else None)
        print(json.dumps({"manifest": str(args.output.resolve() / "manifest.json"), "sha256": manifest["manifest_sha256"]}))
    elif args.command == "read":
        print(read_reference(args.manifest, args.reference, args.used_for, role=args.role), end="")
    else:
        reports = [verify_task_parity(REPO_ROOT, operator) for operator in OPERATORS]
        write_json(args.output, {"schema_version": "1.0.0", "reports": reports})
        print(json.dumps({"path": str(args.output), "operators": len(reports), "matched": sum(not report["mismatches"] for report in reports)}))
        return int(any(report["mismatches"] for report in reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
