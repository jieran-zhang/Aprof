#!/usr/bin/env python3
"""CPU-only, branch-independent trace snapshots with no experiment execution.

Published v2 records retain their original bytes and identities. An unfinished
campaign is an event/feedback snapshot, never an invented optimization_memory.
Large existing payloads can be hard linked; this retains data after an original
directory is removed, but is deliberately not described as an independent backup.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import uuid

VERSION = "unified_optimization_trace_collection_v1"
CHUNK = 1024 * 1024
TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".log", ".txt", ".md",
                 ".py", ".asc", ".cpp", ".h", ".hpp", ".patch", ".yaml", ".sh"}


def progress(message):
    print(message, file=sys.stderr, flush=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    with path.open("xb") as out:
        out.write(encoded)
        out.flush()
        os.fsync(out.fileno())
    return {"path": str(path), "sha256": digest(encoded)}


def safe_path(root, relative):
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe collection path")
    target = root / relative
    for part in [target, *target.parents]:
        require(not part.is_symlink(), "symlink is not a snapshot")
        if part == root:
            break
    return target


def walk_files(root):
    """One stat per directory entry, without traversing symbolic links."""
    with os.scandir(root) as entries:
        for entry in sorted(entries, key=lambda item: item.name):
            require(not entry.is_symlink(), f"symlink source: {entry.path}")
            if entry.is_dir(follow_symlinks=False):
                yield from walk_files(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path), entry.stat(follow_symlinks=False)
            else:
                raise ValueError(f"unsupported source: {entry.path}")


def prefetched_files(items):
    """Bound small-file I/O to 16 readers and at most 32 × 8 MiB in flight."""
    def read(item):
        path, info = item
        info = info if info is not None else path.stat(follow_symlinks=False)
        require(stat.S_ISREG(info.st_mode) and not path.is_symlink(), "nonregular evidence")
        data = None
        if info.st_size <= 8 * CHUNK:
            data = path.read_bytes()
            after = path.stat(follow_symlinks=False)
            require((info.st_ino, info.st_size, info.st_mtime_ns) ==
                    (after.st_ino, after.st_size, after.st_mtime_ns), "source changed during prefetch")
            require(len(data) == info.st_size, "short source read")
        return path, info, data
    iterator = iter(items)
    with ThreadPoolExecutor(max_workers=16) as workers:
        pending = deque()
        for _ in range(32):
            item = next(iterator, None)
            if item is None:
                break
            pending.append(workers.submit(read, item))
        while pending:
            yield pending.popleft().result()
            item = next(iterator, None)
            if item is not None:
                pending.append(workers.submit(read, item))


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.hash.update(data)
        return data


class PackedFiles:
    """Dense regular TAR members avoid spending one filesystem entry per CAS blob."""
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.path = root / name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("xb")
        self.archive = tarfile.open(fileobj=self.stream, mode="w", format=tarfile.USTAR_FORMAT)
        self.entries = {}

    def add(self, source, key, expected=None, prepared=None):
        if key in self.entries:
            entry = self.entries[key]
            require(expected is None or entry["sha256"] == expected, "conflicting packed identity")
            return entry
        source = Path(source)
        before = prepared[0] if prepared is not None else source.stat(follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and not source.is_symlink(), "nonregular evidence")
        name = hashlib.sha256(key.encode()).hexdigest()
        member = tarfile.TarInfo(name)
        member.size = before.st_size
        member.mode = stat.S_IMODE(before.st_mode)
        offset = self.stream.tell() + 512
        buffered = prepared[1] if prepared is not None else None
        with (io.BytesIO(buffered) if buffered is not None else source.open("rb")) as original:
            hashed = HashReader(original)
            self.archive.addfile(member, hashed)
            actual = "sha256:" + hashed.hash.hexdigest()
        if buffered is None:
            after = source.stat(follow_symlinks=False)
            require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                    (after.st_ino, after.st_size, after.st_mtime_ns), "source changed while snapshotting")
        require(expected is None or actual == expected, f"signed evidence changed: {source}")
        entry = {"container": self.name, "member": name, "offset": offset,
                 "size_bytes": before.st_size, "sha256": actual,
                 "mode": stat.S_IMODE(before.st_mode)}
        self.entries[key] = entry
        return entry

    def close(self):
        self.archive.close()
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


def published_pointers(checkouts):
    found = {}
    for checkout in checkouts:
        runs = Path(checkout) / ".aprof/runs"
        for pattern in ("*/dataset/v2/current.json", "*/archive/*/v2/current.json"):
            for pointer in sorted(runs.glob(pattern)):
                value = read_json(pointer)
                revision = pointer.parent / "revisions" / value["revision"]
                manifest = revision / "manifest.json"
                require(digest(manifest.read_bytes()) == value["manifest_hash"], "published pointer mismatch")
                campaign = pointer.relative_to(runs).parts[0]
                dataset = str(pointer.parent.relative_to(runs / campaign))
                key = f"{campaign}/{dataset}"
                previous = found.get(key)
                require(previous is None or previous["revision"] == value["revision"],
                        f"conflicting published revisions across checkouts: {key}")
                found[key] = dict(campaign=campaign, dataset=dataset,
                                  pointer=pointer, directory=pointer.parent,
                                  revision=value["revision"], manifest=read_json(manifest))
    return list(found.values())


def snapshot_level1(root, checkouts):
    pointers = published_pointers(checkouts)
    require(pointers, "no published Level1 dataset found")
    evidence_pack = PackedFiles(root, "level1/evidence.tar")
    evidence, datasets, record_catalog, lesson_catalog = {}, [], [], []
    try:
        for item in pointers:
            progress(f"Level1: {item['campaign']} {item['dataset']}")
            source = item["directory"]
            rev = source / "revisions" / item["revision"]
            base = Path("level1") / item["campaign"] / item["dataset"]
            dst = root / base
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["pointer"], dst / "current.json")
            # All revision metadata and record/context CAS retain revision history.
            metadata_pack = PackedFiles(root, str(base / "revision-history.tar"))
            metadata = {}
            for subdir in ("revisions", "cas"):
                folder = source / subdir
                if folder.is_dir():
                    for path, info, data in prefetched_files(walk_files(folder)):
                        name = str(path.relative_to(source))
                        metadata[name] = metadata_pack.add(path, name, prepared=(info, data))
            metadata_pack.close()
            write_json(dst / "revision-history-index.json", metadata)
            for name, expected in item["manifest"]["files"].items():
                path = rev / name
                require(digest(path.read_bytes()) == expected, f"changed revision file: {path}")
                target = dst / "current" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            shutil.copy2(rev / "manifest.json", dst / "current/manifest.json")
            ix = read_json(rev / "evidence_index.json")
            mapping = {}
            unique = {ref["sha256"]: ref for ref in ix.values() if ref["sha256"] not in evidence}
            by_path = {ref["path"]: key for key, ref in unique.items()}
            for path, info, data in prefetched_files((Path(path), None) for path in by_path):
                key = by_path[str(path)]
                ref = unique[key]
                packed = evidence_pack.add(path, key, expected=key, prepared=(info, data))
                require(packed["size_bytes"] == ref["size_bytes"], "signed evidence size mismatch")
                evidence[key] = packed
                if len(evidence) % 10000 == 0:
                    progress(f"Level1: {len(evidence)} signed evidence objects packed")
            for evidence_id, ref in ix.items():
                key = ref["sha256"]
                require(key in evidence, "evidence prefetch lost an identity")
                mapping[evidence_id] = key
            write_json(dst / "evidence-map.json", mapping)
            counts = Counter()
            for split in ("train", "validation"):
                for filename, catalog in (("optimization_traces.jsonl", record_catalog),
                                          ("lessons.jsonl", lesson_catalog)):
                    path = dst / "current" / split / filename
                    if not path.exists():
                        continue
                    for line_number, line in enumerate(path.read_bytes().splitlines(), 1):
                        value = json.loads(line)
                        catalog.append({"dataset": str(base), "split": split,
                                        "path": str(path.relative_to(root)), "line": line_number,
                                        "id": value["id"], "record_hash": value["record_hash"],
                                        "record_kind": value["record_kind"]})
                        counts[filename] += 1
            datasets.append(dict(campaign=item["campaign"], dataset=item["dataset"],
                                 revision=item["revision"], source=str(source),
                                 local_path=str(base), counts=dict(counts),
                                 current_indexed_evidence_objects=len(mapping),
                                 current_indexed_evidence_complete=True,
                                 history_external_evidence_complete=False))
    finally:
        evidence_pack.close()
    write_json(root / "level1/evidence-index.json", evidence)
    # No last-writer-wins merge: the same stable ID may have distinct revisions.
    def catalog(rows, name):
        groups = {}
        for row in rows:
            groups.setdefault((row["record_kind"], row["id"], row["record_hash"]), []).append(row)
        unique = [dict(record_kind=k[0], id=k[1], record_hash=k[2], occurrences=v)
                  for k, v in sorted(groups.items())]
        write_json(root / f"level1/{name}-catalog.json", unique)
        return len(unique)
    return dict(datasets=datasets, memory_rows=len(record_catalog), lesson_rows=len(lesson_catalog),
                unique_memory_revisions=catalog(record_catalog, "memory"),
                unique_lesson_revisions=catalog(lesson_catalog, "lesson"),
                latest_campaign=max((d["campaign"] for d in datasets if "msprof-feedback" in d["campaign"]), default=None),
                current_evidence_objects=len(evidence),
                current_evidence_bytes=sum(e["size_bytes"] for e in evidence.values()),
                raw_profiler_scope="Published current evidence-index closure only; unrelated original run files are not included.")


def known_payload_hashes(files):
    """Reuse recorded identities; never pretend that reuse is a fresh hash check."""
    hashes = {}
    available = {str(p) for p, _ in files}
    ambiguous = set()
    def add(path, value):
        if isinstance(path, str) and path in available and path not in ambiguous and isinstance(value, str) and \
                re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            if path in hashes and hashes[path] != value:
                # Historical in-place build repairs can have different recorded
                # bytes at one name. Such names must not be content-deduplicated.
                ambiguous.add(path)
                del hashes[path]
            else:
                hashes[path] = value
    def visit(node):
        if isinstance(node, dict):
            add(node.get("path"), node.get("sha256"))
            for key, value in node.items():
                add(key, value)
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    chosen = [(p, s) for p, s in files if p.name in
              ("bindings.json", "input-bindings.json", "retention.json", "seal.json")]
    for path, _, data in prefetched_files(chosen):
        visit(json.loads(data if data is not None else path.read_bytes()))
    journals = [(p, s) for p, s in files if p.name == "journal.jsonl" and p.parent.name == "native"]
    for path, _, data in prefetched_files(journals):
        validation = path.parent.parent / "validation.json"
        if not validation.is_file():
            continue
        values = read_json(validation)
        outputs = {(str(v["case_id"]), v["buffer_config"], v["role"]): v["output_hash"]
                   for v in values.get("outputs", []) if "output_hash" in v}
        for line in (data if data is not None else path.read_bytes()).splitlines():
            if b'"output"' not in line:
                continue
            row = json.loads(line)
            if row.get("type") == "output":
                key = (str(row["case_id"]), row["buffer_config"], row["role"])
                if key in outputs:
                    add(row["path"], outputs[key])
    return hashes


def snapshot_level2(root, run, threshold, raw_budget=64 * 1024**3, packed_budget=64 * 1024**3):
    run = Path(run).resolve()
    base = Path("level2") / run.name
    target = root / base
    target.mkdir(parents=True, exist_ok=True)
    inventory = list(walk_files(run))
    packed_bytes = sum(s.st_size for p, s in inventory
                       if not (s.st_size > threshold and p.suffix.lower() not in TEXT_SUFFIXES))
    require(packed_bytes <= packed_budget, "Level2 packed-byte budget exceeded before copying")
    space = os.statvfs(root)
    require(packed_bytes + raw_budget + len(inventory) * 1024 < space.f_bavail * space.f_frsize,
            "insufficient available logical space for the declared snapshot budgets")
    hashes = known_payload_hashes(inventory)
    progress(f"Level2: packed bytes {packed_bytes}; raw budget {raw_budget}; {len(hashes)} recorded path hashes")
    # Retain existing storage containers before spending the raw budget on loose outputs.
    inventory.sort(key=lambda item: (0 if item[0].suffix == ".tar" else 1, str(item[0])))
    pack = PackedFiles(root, str(base / "snapshot.tar"))
    files, readable, raw_count, raw_bytes, omitted = {}, [], 0, 0, []
    payloads = {}
    try:
        for path, info, data in prefetched_files(inventory):
            relative = str(path.relative_to(run))
            if info.st_size > threshold and path.suffix.lower() not in TEXT_SUFFIXES:
                expected = hashes.get(str(path))
                key = expected[7:] if expected else hashlib.sha256(relative.encode()).hexdigest()
                if key in payloads:
                    require(payloads[key]["size_bytes"] == info.st_size, "same recorded hash has differing sizes")
                    files[relative] = dict(payloads[key], deduplicated_by="recorded_sha256_not_rehashed")
                    continue
                if raw_bytes + info.st_size > raw_budget:
                    files[relative] = dict(external_source_path=str(path), size_bytes=info.st_size,
                        mode=stat.S_IMODE(info.st_mode), sha256=expected,
                        integrity="external_raw_not_centralized", reason="unique_raw_byte_budget")
                    omitted.append(relative)
                    continue
                local = base / "payloads" / key[:2] / key
                destination = root / local
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.link(path, destination, follow_symlinks=False)
                actual = destination.stat()
                require((actual.st_ino, actual.st_dev, actual.st_size) ==
                        (info.st_ino, info.st_dev, info.st_size), "hardlink snapshot mismatch")
                files[relative] = dict(path=str(local), size_bytes=info.st_size,
                                       mode=stat.S_IMODE(info.st_mode), sha256=expected,
                                       integrity="physical_hardlink_size_snapshot", mtime_ns=info.st_mtime_ns)
                payloads[key] = files[relative]
                raw_count += 1
                raw_bytes += info.st_size
            else:
                files[relative] = pack.add(path, relative, prepared=(info, data))
            if len(files) % 10000 == 0:
                progress(f"Level2: {len(files)} files retained, {raw_count} large payload hardlinks")
            # Common entry points stay browsable without extracting an archive.
            parts = Path(relative).parts
            if (len(parts) == 1 and path.suffix in (".json", ".md")) or \
                    ("feedback" in parts and path.suffix == ".json") or \
                    (path.name == "events.jsonl") or \
                    (parts[0] in ("reports",) and path.suffix in (".json", ".md", ".txt")) or \
                    ("pause-" in relative and path.suffix in (".json", ".txt", ".md")):
                out = target / "readable" / relative
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, out)
                readable.append(str(out.relative_to(root)))
    finally:
        pack.close()
    write_json(target / "file-index.json", files)
    write_json(target / "external-raw-inventory.json", {name: files[name] for name in omitted})
    attempts, operators = [], []
    for split in ("train", "validation"):
        for task in sorted((run / split / "tasks").iterdir()):
            if not task.is_dir():
                continue
            events = [json.loads(line) for line in (task / "events.jsonl").read_bytes().splitlines()]
            registrations = [e for e in events if e["kind"] == "source_attempt_registered"]
            closed = [e for e in events if e["kind"] in
                      ("candidate_feedback_closed", "candidate_feedback_reclassified")]
            candidate_feedback = {}
            for event in closed:
                ref = event["value"]["feedback"]
                feedback = read_json(ref["path"])
                require(digest(Path(ref["path"]).read_bytes()) == ref["sha256"], "closed feedback changed")
                if event["kind"] == "candidate_feedback_reclassified":
                    require(feedback["status"] == "source_attempt_failed"
                            and feedback["reclassification"]["source_attempt_added"] is False
                            and feedback["reclassification"]["native_reexecuted"] is False,
                            "reclassification is not a closed historical source failure")
                candidate_feedback[feedback["candidate_id"]] = (feedback, event)
            for event in registrations:
                candidate = event["value"]["candidate_id"]
                feedback, closure = candidate_feedback.get(candidate, (None, None))
                attempts.append(dict(schema_version="partial_source_attempt_index_v1", operator=task.name,
                    original_split=split, candidate_id=candidate, registered_event=event,
                    closed_event=closure, feedback=feedback, published_optimization_memory=False,
                    graph_policy_eligible=False, episode_ref=None))
            operators.append(dict(operator=task.name, original_split=split,
                source_attempts=len(registrations), closed_feedback=len(candidate_feedback),
                finalization_report_present=(task / "finalization/report.json").exists()))
    with (target / "source_attempts.jsonl").open("xb") as out:
        for attempt in attempts:
            out.write((json.dumps(attempt, sort_keys=True) + "\n").encode())
    manifest = read_json(run / "campaign-manifest.json")
    summary = dict(source=str(run), local_path=str(base), status="paused_partial_snapshot",
        source_attempts_planned=manifest["source_attempts_planned"], registered_attempts=len(attempts),
        closed_attempts=sum(a["closed_event"] is not None for a in attempts), operators=operators,
        published_optimization_memories=0, published_lessons=0, all_attempts_complete=False,
        full_final_acceptance_complete=False, graph_policy_eligible=False, episode_ref=None,
        snapshot_files=len(files), snapshot_logical_bytes=sum(f["size_bytes"] for f in files.values()),
        hardlinked_payload_files=raw_count, hardlinked_payload_bytes=raw_bytes,
        all_run_regular_files_indexed=True, all_run_regular_files_included=not omitted,
        external_raw_files=len(omitted), external_raw_bytes=sum(files[name]["size_bytes"] for name in omitted),
        unique_raw_byte_budget=raw_budget, packed_byte_budget=packed_budget,
        metadata_and_small_evidence_hashed=True,
        full_payload_content_hash_verification=False, semantic_archive_closure_verified=False,
        raw_payload_warning="Large payloads are physical hardlinks, not symlinks or an independent backup; do not modify either name in place.",
        readable_files=readable)
    write_json(target / "status.json", summary)
    return summary


def resumed_level1(root, checkouts):
    """Reuse an interrupted organizer's fully written Level1 pack, without rereading payloads."""
    datasets = []
    for item in published_pointers(checkouts):
        base = Path("level1") / item["campaign"] / item["dataset"]
        current = root / base / "current"
        require(digest((current / "manifest.json").read_bytes()) ==
                read_json(item["pointer"])["manifest_hash"], "resume published manifest mismatch")
        for name, expected in item["manifest"]["files"].items():
            require(digest((current / name).read_bytes()) == expected, "resume published bytes changed")
        mapping = read_json(root / base / "evidence-map.json")
        counts = {name: sum(len((current / split / name).read_bytes().splitlines()) for split in ("train", "validation"))
                  for name in ("optimization_traces.jsonl", "lessons.jsonl")}
        datasets.append(dict(campaign=item["campaign"], dataset=item["dataset"], revision=item["revision"],
            source=str(item["directory"]), local_path=str(base), counts=counts,
            current_indexed_evidence_objects=len(mapping), current_indexed_evidence_complete=True,
            history_external_evidence_complete=False))
    evidence = read_json(root / "level1/evidence-index.json")
    return dict(datasets=datasets,
        memory_rows=sum(d["counts"]["optimization_traces.jsonl"] for d in datasets),
        lesson_rows=sum(d["counts"]["lessons.jsonl"] for d in datasets),
        unique_memory_revisions=len(read_json(root / "level1/memory-catalog.json")),
        unique_lesson_revisions=len(read_json(root / "level1/lesson-catalog.json")),
        latest_campaign=max(d["campaign"] for d in datasets if "msprof-feedback" in d["campaign"]),
        current_evidence_objects=len(evidence), current_evidence_bytes=sum(e["size_bytes"] for e in evidence.values()),
        raw_profiler_scope="Published current evidence-index closure only; unrelated original run files are not included.")


def snapshot_method_validation(root, source):
    source = Path(source).absolute()
    require((source / "method-validation-summary.json").is_file(), "method validation is not closed")
    inventory = list(walk_files(source))
    require(sum(s.st_size for _, s in inventory) <= 16 * 1024**3, "method snapshot exceeds 16 GiB budget")
    base = Path("method-validation") / source.name
    pack = PackedFiles(root, str(base / "evidence.tar"))
    files = {}
    try:
        for path, info, data in prefetched_files(inventory):
            relative = str(path.relative_to(source))
            files[relative] = pack.add(path, relative, prepared=(info, data))
            if path.suffix in (".json", ".md", ".txt") and len(Path(relative).parts) <= 2:
                dst = root / base / "readable" / relative
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dst)
    finally:
        pack.close()
    write_json(root / base / "file-index.json", files)
    return dict(source=str(source), local_path=str(base), files=len(files),
                logical_bytes=sum(e["size_bytes"] for e in files.values()),
                new_source_attempts=0, scope="Method validation evidence, including retained failed observations; not optimizer rounds.")


def organize(output, checkouts, level2, threshold, *, resume_staging=None,
             raw_budget=64 * 1024**3, packed_budget=64 * 1024**3, method_validation=None):
    output = Path(output).absolute()
    require(not output.exists(), "destination exists; publish a new snapshot instead of replacing evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    if resume_staging is None:
        staging = output.with_name(output.name + ".staging-" + uuid.uuid4().hex[:12])
        staging.mkdir()
        one = snapshot_level1(staging, checkouts)
    else:
        staging = Path(resume_staging).absolute()
        require(staging.parent == output.parent and staging.name.startswith(output.name + ".staging-")
                and not staging.is_symlink(), "unsafe resume staging")
        one = resumed_level1(staging, checkouts)
        # Only the explicitly selected unpublished partial copy is replaced.
        if (staging / "level2").exists():
            shutil.rmtree(staging / "level2")
    two = snapshot_level2(staging, level2, threshold, raw_budget, packed_budget)
    index = dict(version=VERSION, created_at=datetime.now(timezone.utc).isoformat(),
                 level1=one, level2=two,
                 record_deduplication="Exact (record_kind, stable id, record_hash); retain every different revision and dataset occurrence.",
                 original_paths="Provenance only. Local indices resolve copied bytes without consulting the old checkout.")
    if method_validation is not None:
        index["method_validation"] = snapshot_method_validation(staging, method_validation)
    write_json(staging / "index.json", index)
    text = f"""# Optimization traces\n\nThis directory is independent of a Git branch. Original experiments were not changed.\n\n- Level1: {one['memory_rows']} published memory rows, {one['lesson_rows']} published lesson rows across {len(one['datasets'])} datasets. See `level1/memory-catalog.json` and `level1/lesson-catalog.json`; original JSONL files are under each dataset's `current/`. Latest series: `{one['latest_campaign']}`.\n- Level2: {two['closed_attempts']}/{two['source_attempts_planned']} source attempts have closed feedback; `level2/{Path(level2).name}/source_attempts.jsonl` is a partial attempt index, **not** published v2 memories. All 16 operator event streams, feedback, source snapshots, reports and the pause checkpoint are retained. No successful missing attempts, lessons, or training episodes were synthesized.\n\nPublished Level1 current evidence is fully packed and SHA-256 checked against its signed indices ({one['current_evidence_objects']} distinct objects). Revision-history metadata is retained, but evidence belonging only to superseded revisions is not claimed complete. This does not include unrelated raw files outside the published evidence closure.\n\nLevel2 includes every regular file present in the paused run. Metadata and small files are hashed in `snapshot.tar`; large binary/TAR payloads are physical hardlinks under `payloads/`. Removing the original path does not remove these files. Hardlinks share bytes with the original and are **not an independent backup**: never modify either name in place. Large payload hashes and final semantic archive closure have not been reverified; file presence is not a completed experiment or a portable v2 validation claim.\n\nUse `python tools/organize_optimization_traces.py verify --output .` for structural verification, add `--deep` to hash packed bytes. `read --level level2 --source-relative train/tasks/gather/feedback/gather002.json --output .` reads by local index only. Level1 evidence can be read with `read --level level1 --sha256 sha256:... --output .`.\n\nThe collection is data, excluded from the skill-library Git repository. `index.json` is the authoritative entry point.\n"""
    text = text.replace("Level2 includes every regular file present in the paused run.",
        "Level2 indexes every regular file present in the paused run. "
        f"{two['external_raw_files']} large raw files remain explicitly external because of the raw-byte budget; "
        "see external-raw-inventory.json. Metadata, sources, patches, events, feedback and reports are retained centrally.")
    text = text.replace("large binary/TAR payloads are physical hardlinks", "retained large binary/TAR payloads are physical hardlinks")
    (staging / "README.md").write_text(text)
    (staging / "tools").mkdir()
    shutil.copy2(__file__, staging / "tools/organize_optimization_traces.py")
    # Seals protect metadata and every index; payload integrity has its own scope.
    seal = {}
    for path, _ in walk_files(staging):
        relative = str(path.relative_to(staging))
        if path.suffix in (".json", ".jsonl", ".py", ".md"):
            seal[relative] = digest(path.read_bytes())
    write_json(staging / "metadata-seal.json", seal)
    verify(staging, deep=False)
    os.rename(staging, output)
    return index


def entries(root):
    yield from read_json(root / "level1/evidence-index.json").values()
    for path in (root / "level1").rglob("revision-history-index.json"):
        yield from read_json(path).values()
    index = read_json(root / "index.json")
    yield from read_json(root / index["level2"]["local_path"] / "file-index.json").values()
    if "method_validation" in index:
        yield from read_json(root / index["method_validation"]["local_path"] / "file-index.json").values()


def entry_bytes(root, entry):
    require("external_source_path" not in entry, "raw payload is explicitly external; no original-path fallback")
    if "container" in entry:
        with safe_path(root, entry["container"]).open("rb") as stream:
            stream.seek(entry["offset"])
            remaining = entry["size_bytes"]
            while remaining:
                block = stream.read(min(CHUNK, remaining))
                require(block, "truncated evidence container")
                remaining -= len(block)
                yield block
    else:
        with safe_path(root, entry["path"]).open("rb") as stream:
            yield from iter(lambda: stream.read(CHUNK), b"")


def verify(output, deep=False):
    root = Path(output).absolute()
    index = read_json(root / "index.json")
    require(index["version"] == VERSION, "unsupported collection version")
    for name, expected in read_json(root / "metadata-seal.json").items():
        require(digest(safe_path(root, name).read_bytes()) == expected, f"metadata changed: {name}")
    containers, packed, linked, external, checked_payloads = {}, 0, 0, 0, set()
    for entry in entries(root):
        if "external_source_path" in entry:
            external += 1
            continue
        if "container" in entry:
            name = entry["container"]
            if name not in containers:
                containers[name] = safe_path(root, name).stat().st_size
            require(entry["offset"] >= 512 and entry["offset"] + entry["size_bytes"] <= containers[name],
                    "invalid TAR member bounds")
            if deep:
                h = hashlib.sha256()
                for block in entry_bytes(root, entry):
                    h.update(block)
                require("sha256:" + h.hexdigest() == entry["sha256"], "packed evidence changed")
            packed += 1
        else:
            if entry["path"] not in checked_payloads:
                path = safe_path(root, entry["path"])
                require(path.is_file() and path.stat().st_size == entry["size_bytes"], "missing/changed linked payload")
                checked_payloads.add(entry["path"])
            linked += 1
    return dict(version=VERSION, status="passed", packed_entries=packed, linked_payloads=linked,
                external_raw_entries=external, all_raw_payloads_local=not external,
                unique_linked_payload_files=len(checked_payloads),
                packed_content_hashes_checked=deep, linked_payload_hashes_checked=False,
                semantic_archive_closure_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("organize")
    create.add_argument("--output", required=True)
    create.add_argument("--level1-checkout", action="append", required=True)
    create.add_argument("--level2-run", required=True)
    create.add_argument("--hardlink-threshold-mib", type=int, default=8)
    create.add_argument("--raw-budget-gib", type=int, default=64)
    create.add_argument("--packed-budget-gib", type=int, default=64)
    create.add_argument("--resume-staging")
    create.add_argument("--method-validation")
    check = sub.add_parser("verify")
    check.add_argument("--output", required=True)
    check.add_argument("--deep", action="store_true")
    read = sub.add_parser("read")
    read.add_argument("--output", required=True)
    read.add_argument("--level", choices=("level1", "level2"), required=True)
    read.add_argument("--sha256")
    read.add_argument("--source-relative")
    args = parser.parse_args()
    if args.action == "organize":
        result = organize(args.output, args.level1_checkout, args.level2_run,
                          args.hardlink_threshold_mib * CHUNK, resume_staging=args.resume_staging,
                          raw_budget=args.raw_budget_gib * 1024**3,
                          packed_budget=args.packed_budget_gib * 1024**3,
                          method_validation=args.method_validation)
    elif args.action == "verify":
        result = verify(args.output, args.deep)
    else:
        root = Path(args.output).absolute()
        if args.level == "level1":
            entry = read_json(root / "level1/evidence-index.json")[args.sha256]
        else:
            index = read_json(root / "index.json")
            entry = read_json(root / index["level2"]["local_path"] / "file-index.json")[args.source_relative]
        import sys
        for block in entry_bytes(root, entry):
            sys.stdout.buffer.write(block)
        return
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
