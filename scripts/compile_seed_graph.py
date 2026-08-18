#!/usr/bin/env python3
"""Compile the expert-authored JSON sources into an immutable SkillGraph snapshot.

The compiler deliberately uses only the Python standard library.  Source JSON is
human-reviewed; generated files are canonical JSON and therefore byte-for-byte
reproducible.  An existing snapshot may only be reconstructed identically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0.0"
GRAPH_VERSION = "v0001"
SOURCE_FILES = (
    ("anchors.json", "anchors"),
    ("predicates.json", "predicates"),
    ("mechanisms.json", "mechanisms"),
    ("transformations.json", "transformations"),
    ("edges.json", "edges"),
)
EDGE_TYPES = {"facet_of", "supports", "refutes", "problem_to_skill_prior"}
EVALUATION_MODES = {"feature_rule", "source_match", "derived"}
IMPLEMENTATION_STATES = {"implemented", "unimplemented"}
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
LINE_RANGE_RE = re.compile(r"^([1-9][0-9]*)-([1-9][0-9]*)$")


class GraphCompileError(ValueError):
    """The source graph is invalid or would mutate an immutable snapshot."""


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GraphCompileError(f"missing source file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GraphCompileError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphCompileError(f"source root must be an object: {path}")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise GraphCompileError(f"unsupported schema_version in {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GraphCompileError(message)


def _repo_source_path(repo_root: Path, relative: str, item_id: str) -> Path:
    """Resolve provenance without permitting absolute paths or repository escape."""
    path = Path(relative)
    _require(
        bool(relative)
        and not path.is_absolute()
        and "\\" not in relative
        and all(part not in {"", ".", ".."} for part in path.parts),
        f"{item_id}: provenance path must be normalized and repository-relative",
    )
    root = repo_root.resolve()
    try:
        resolved = (root / path).resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise GraphCompileError(
            f"{item_id}: provenance source resolves outside repository root: {relative}"
        ) from exc
    return resolved


def _validate_provenance(
    item_id: str, provenance: Any, repo_root: Path
) -> None:
    _require(
        isinstance(provenance, list) and provenance,
        f"{item_id}: provenance must be a non-empty list",
    )
    for record in provenance:
        _require(isinstance(record, dict), f"{item_id}: invalid provenance record")
        relative = record.get("path")
        line_range = record.get("lines")
        _require(isinstance(relative, str), f"{item_id}: provenance path is required")
        lowered = relative.lower()
        _require(
            "fast_gelu" not in lowered and "inject" not in lowered,
            f"{item_id}: benchmark injections and FastGELU history are not seed priors",
        )
        match = LINE_RANGE_RE.fullmatch(str(line_range))
        _require(match is not None, f"{item_id}: lines must be an inclusive N-M range")
        start, end = (int(part) for part in match.groups())
        _require(start <= end, f"{item_id}: reversed provenance line range")
        source_path = _repo_source_path(repo_root, relative, item_id)
        _require(source_path.is_file(), f"{item_id}: missing provenance source {relative}")
        line_count = len(source_path.read_text(encoding="utf-8").splitlines())
        _require(end <= line_count, f"{item_id}: provenance line {end} exceeds {relative}")


def _validate_items(
    collection: str, items: Any, prefix: str, repo_root: Path
) -> set[str]:
    _require(isinstance(items, list), f"{collection} must be a list")
    ids: set[str] = set()
    for item in items:
        _require(isinstance(item, dict), f"{collection} entries must be objects")
        item_id = item.get("id")
        _require(
            isinstance(item_id, str) and item_id.startswith(prefix),
            f"invalid {collection} id: {item_id!r}",
        )
        _require(item_id not in ids, f"duplicate id: {item_id}")
        _require(
            isinstance(item.get("version"), str)
            and VERSION_RE.fullmatch(item["version"]) is not None,
            f"{item_id}: version must be semantic X.Y.Z",
        )
        _validate_provenance(item_id, item.get("provenance"), repo_root)
        ids.add(item_id)
    return ids


def _validate_graph(graph: dict[str, Any], repo_root: Path) -> None:
    prior_semantics = graph.get("prior_semantics")
    _require(isinstance(prior_semantics, dict), "prior_semantics is required")
    _require(
        prior_semantics.get("score_type") == "uncalibrated_expert_score",
        "prior scores must be labeled uncalibrated_expert_score",
    )
    _require(
        prior_semantics.get("interpretation") == "ordinal_initial_ranking_only",
        "prior scores may only claim ordinal initial ranking",
    )
    _require(
        prior_semantics.get("calibrated_probability") is False,
        "expert seed scores are not calibrated probabilities",
    )
    _require(
        prior_semantics.get("scale_id") == "expert_seed_scale_v1",
        "v0001 requires the fixed expert seed score scale",
    )
    _require(
        prior_semantics.get("temperature") == 1.0
        and prior_semantics.get("temperature_status") == "fixed_untrained",
        "v0001 requires fixed untrained temperature 1.0",
    )
    anchor_ids = _validate_items("anchors", graph["anchors"], "anchor.", repo_root)
    predicate_ids = _validate_items(
        "predicates", graph["predicates"], "predicate.", repo_root
    )
    mechanism_ids = _validate_items(
        "mechanisms", graph["mechanisms"], "mechanism.", repo_root
    )
    transformation_ids = _validate_items(
        "transformations", graph["transformations"], "transformation.", repo_root
    )
    edge_ids = _validate_items("edges", graph["edges"], "edge.", repo_root)

    expected_anchors = {
        "anchor.ai_core_utilization",
        "anchor.api_algorithm",
        "anchor.data_movement",
        "anchor.onchip_memory",
        "anchor.pipeline_parallel",
        "anchor.tiling",
    }
    _require(anchor_ids == expected_anchors, "v0001 must contain exactly six expert facets")
    for anchor in graph["anchors"]:
        _require(anchor.get("kind") == "facet", f"{anchor['id']}: anchor must be facet")
        _require(anchor.get("selectable") is False, f"{anchor['id']}: facet is not selectable")
        _require(anchor.get("trainable") is False, f"{anchor['id']}: facet is not trainable")

    _require(
        "mechanism.unknown_unresolved" in mechanism_ids,
        "first-class unknown mechanism is required",
    )
    _require("transformation.noop" in transformation_ids, "NOOP action is required")

    for predicate in graph["predicates"]:
        evaluation = predicate.get("evaluation")
        _require(isinstance(evaluation, dict), f"{predicate['id']}: evaluation is required")
        _require(
            evaluation.get("mode") in EVALUATION_MODES,
            f"{predicate['id']}: invalid evaluation mode",
        )
        _require(
            evaluation.get("implementation_status") in IMPLEMENTATION_STATES,
            f"{predicate['id']}: implementation status must be explicit",
        )
        _require(
            isinstance(evaluation.get("extractor_id"), str),
            f"{predicate['id']}: extractor_id is required",
        )
        _require(
            predicate.get("returns") == "true_false_unknown",
            f"{predicate['id']}: predicates must preserve unknown",
        )

    required_contract_fields = {
        "applicability",
        "required_evidence",
        "parameter_schema",
        "capacity_constraints",
        "semantic_invariants",
        "expected_profile_delta",
        "contraindications",
        "gate_spec",
        "rollback_spec",
    }
    for transformation in graph["transformations"]:
        missing = required_contract_fields - transformation.keys()
        _require(not missing, f"{transformation['id']}: missing contract fields {sorted(missing)}")
        evidence = transformation["required_evidence"]
        _require(
            isinstance(evidence, dict)
            and isinstance(evidence.get("all"), list)
            and isinstance(evidence.get("any"), list),
            f"{transformation['id']}: required_evidence needs all/any arrays",
        )
        referenced = set(evidence["all"] + evidence["any"])
        _require(
            referenced <= predicate_ids,
            f"{transformation['id']}: unknown evidence predicates {sorted(referenced - predicate_ids)}",
        )

    all_node_ids = anchor_ids | predicate_ids | mechanism_ids | transformation_ids
    incoming_prior_targets: set[str] = set()
    outgoing_prior_sources: set[str] = set()
    for edge in graph["edges"]:
        edge_type = edge.get("edge_type")
        source = edge.get("source")
        target = edge.get("target")
        _require(edge_type in EDGE_TYPES, f"{edge['id']}: invalid edge_type")
        _require(source in all_node_ids, f"{edge['id']}: missing source node {source}")
        _require(target in all_node_ids, f"{edge['id']}: missing target node {target}")
        _require(isinstance(edge.get("hard_preconditions"), list), f"{edge['id']}: hard_preconditions must be a list")
        for condition in edge["hard_preconditions"]:
            _require(isinstance(condition, dict), f"{edge['id']}: invalid hard precondition")
            _require(condition.get("predicate") in predicate_ids, f"{edge['id']}: unknown precondition predicate")
            _require(condition.get("state") in (True, False, "unknown"), f"{edge['id']}: invalid precondition state")

        if edge_type == "problem_to_skill_prior":
            _require(source in mechanism_ids, f"{edge['id']}: prior source must be a mechanism")
            _require(target in transformation_ids, f"{edge['id']}: prior target must be a transformation")
            _require(edge.get("trainable") is True, f"{edge['id']}: priors must be trainable")
            _require(
                isinstance(edge.get("prior_logit"), (int, float))
                and not isinstance(edge.get("prior_logit"), bool),
                f"{edge['id']}: numeric prior_logit is required",
            )
            _require(
                edge.get("prior_status") == "expert_seed_unverified",
                f"{edge['id']}: expert seed prior must remain explicitly unverified",
            )
            incoming_prior_targets.add(target)
            outgoing_prior_sources.add(source)
        else:
            _require(edge.get("trainable") is False, f"{edge['id']}: evidence/facet edges are fixed")
            _require(edge.get("prior_logit") is None, f"{edge['id']}: fixed edges cannot have logits")
            _require("prior_status" not in edge, f"{edge['id']}: fixed edges cannot claim prior status")
            if edge_type == "facet_of":
                _require(source in mechanism_ids and target in anchor_ids, f"{edge['id']}: invalid facet edge")
            else:
                _require(source in predicate_ids and target in mechanism_ids, f"{edge['id']}: invalid evidence edge")

    _require(len(edge_ids) == len(graph["edges"]), "edge ids are not unique")
    _require(
        mechanism_ids <= outgoing_prior_sources,
        f"mechanisms without an action: {sorted(mechanism_ids - outgoing_prior_sources)}",
    )
    _require(
        transformation_ids <= incoming_prior_targets,
        f"transformations unreachable from priors: {sorted(transformation_ids - incoming_prior_targets)}",
    )


def _source_digest(source_bytes: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(source_bytes):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_bytes[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _provenance_inputs(
    collections: dict[str, list[dict[str, Any]]], repo_root: Path
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    """Bind both complete provenance files and cited slices into the seed hash."""
    material: dict[str, bytes] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for collection in sorted(collections):
        for item in collections[collection]:
            item_id = str(item["id"])
            for record in item["provenance"]:
                relative = str(record["path"])
                line_range = str(record["lines"])
                source_path = _repo_source_path(repo_root, relative, item_id)
                raw = source_path.read_bytes()
                try:
                    lines = raw.decode("utf-8").splitlines(keepends=True)
                except UnicodeDecodeError as exc:
                    raise GraphCompileError(
                        f"{item_id}: provenance source is not UTF-8: {relative}"
                    ) from exc
                match = LINE_RANGE_RE.fullmatch(line_range)
                _require(match is not None, f"{item_id}: invalid provenance line range")
                start, end = (int(part) for part in match.groups())
                _require(end <= len(lines), f"{item_id}: provenance line {end} exceeds {relative}")
                slice_bytes = "".join(lines[start - 1 : end]).encode("utf-8")

                material[f"provenance:file:{relative}"] = raw
                material[f"provenance:slice:{relative}:{line_range}"] = slice_bytes
                file_entry = metadata.setdefault(
                    relative,
                    {"file_sha256": _sha256(raw), "slices": {}},
                )
                _require(
                    file_entry["file_sha256"] == _sha256(raw),
                    f"{item_id}: provenance path changed while compiling: {relative}",
                )
                file_entry["slices"][line_range] = _sha256(slice_bytes)
    return material, metadata


def build_snapshot(source_dir: Path, repo_root: Path) -> dict[str, bytes]:
    source_bytes: dict[str, bytes] = {}
    collections: dict[str, list[dict[str, Any]]] = {}
    prior_semantics: dict[str, Any] | None = None
    for filename, collection in SOURCE_FILES:
        path = source_dir / filename
        raw = path.read_bytes() if path.is_file() else b""
        source_bytes[filename] = raw
        document = _load_json(path)
        values = document.get(collection)
        _require(isinstance(values, list), f"{path}: missing {collection} list")
        collections[collection] = sorted(values, key=lambda item: item["id"])
        if collection == "edges":
            metadata = document.get("prior_semantics")
            _require(isinstance(metadata, dict), f"{path}: prior_semantics is required")
            prior_semantics = metadata

    graph: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "graph_version": GRAPH_VERSION,
        "created_from": {"kind": "expert_seed", "source_sha256": "pending"},
        "prior_semantics": prior_semantics,
        **collections,
    }
    _validate_graph(graph, repo_root)
    provenance_bytes, provenance_digests = _provenance_inputs(collections, repo_root)
    source_sha = _source_digest({**source_bytes, **provenance_bytes})
    graph["created_from"]["source_sha256"] = source_sha
    graph_bytes = _canonical_bytes(graph)

    lineage = {
        "schema_version": SCHEMA_VERSION,
        "graph_version": GRAPH_VERSION,
        "parent_graph_versions": [],
        "origin": "expert_seed",
        "source_sha256": source_sha,
        "source_files": [filename for filename, _ in SOURCE_FILES],
        "excluded_seed_sources": ["injection recipes", "FastGELU optimization history"],
    }
    lineage_bytes = _canonical_bytes(lineage)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "graph_version": GRAPH_VERSION,
        "immutable": True,
        "graph_sha256": _sha256(graph_bytes),
        "source_sha256": source_sha,
        "counts": {name: len(values) for name, values in collections.items()},
        "files": {
            "graph": "graph.json",
            "lineage": "lineage.json",
            "checksums": "checksums.json",
        },
    }
    manifest_bytes = _canonical_bytes(manifest)
    checksums = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": "sha256",
        "files": {
            "graph.json": _sha256(graph_bytes),
            "lineage.json": _sha256(lineage_bytes),
            "manifest.json": _sha256(manifest_bytes),
        },
        "source_files": {
            name: _sha256(source_bytes[name]) for name in sorted(source_bytes)
        },
        "provenance_sources": provenance_digests,
    }
    return {
        "graph.json": graph_bytes,
        "lineage.json": lineage_bytes,
        "manifest.json": manifest_bytes,
        "checksums.json": _canonical_bytes(checksums),
    }


def materialize_snapshot(
    source_dir: Path, output_dir: Path, repo_root: Path, *, check: bool = False
) -> dict[str, bytes]:
    artifacts = build_snapshot(source_dir.resolve(), repo_root.resolve())
    mismatches: list[str] = []
    for filename, expected in artifacts.items():
        path = output_dir / filename
        if not path.is_file() or path.read_bytes() != expected:
            mismatches.append(filename)
    if check:
        if mismatches:
            raise GraphCompileError(f"snapshot check failed: {', '.join(sorted(mismatches))}")
        return artifacts

    changed_existing = [name for name in mismatches if (output_dir / name).exists()]
    if changed_existing:
        raise GraphCompileError(
            "immutable snapshot differs; publish a new graph version instead: "
            + ", ".join(sorted(changed_existing))
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in artifacts.items():
        path = output_dir / filename
        if not path.exists():
            path.write_bytes(content)
    return artifacts


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=repo_root / "skillgraph/source")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "skillgraph/versions/v0001")
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--check", action="store_true", help="verify snapshot bytes without writing")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        artifacts = materialize_snapshot(
            args.source_dir, args.output_dir, args.repo_root, check=args.check
        )
    except GraphCompileError as exc:
        raise SystemExit(f"error: {exc}") from exc
    action = "verified" if args.check else "compiled"
    print(f"{action} {GRAPH_VERSION}: {len(artifacts)} deterministic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
