#!/usr/bin/env python3
"""Archive a failed Cummin A/A control's verified native outputs.

This is a narrow reader for partial control evidence. It preserves original
logical paths and SHA-256 identities but does not qualify the failed control.
The prior dedup manifest binds every byte to the passed per-session validations.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import uuid

from level2_storage import digest, exclusive_host, safe, sync_directory, write_new

VERSION = "level2_partial_native_archive_v1"
CHUNK = 8 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(safe(path).read_bytes())


def pointer(path):
    return {"path": str(path), "sha256": digest(path)[0]}


def authority(stage):
    stage = Path(stage)
    require(stage.is_absolute() and ".." not in stage.parts and stage == stage.resolve()
            and stage.parent.name == "stages" and stage.parent.parent.name == "cummin"
            and stage.name.startswith("aa-"), "only canonical Cummin A/A stage is supported")
    result_path = stage / "result.json"
    result = read(result_path)
    require(result.get("kind") == "control" and result.get("status") == "failed"
            and result.get("ended_at") is not None, "partial control must be terminal failed")
    maintenance = stage / "partial-output-dedup"
    completed = sorted(maintenance.glob("*/completion.json"))
    require(len(completed) == 1, "one prior complete partial output dedup receipt required")
    receipt_path = completed[0]
    receipt = read(receipt_path)
    manifest_ref = receipt.get("manifest")
    require(receipt.get("version") == "level2_partial_control_output_dedup_v1"
            and receipt.get("status") == "complete" and receipt.get("source_bytes_preserved") is True
            and receipt.get("logical_paths_preserved") is True
            and isinstance(manifest_ref, dict) and set(manifest_ref) == {"path", "sha256"},
            "prior dedup receipt differs")
    manifest_path = Path(manifest_ref["path"])
    require(manifest_path == receipt_path.parent / "manifest.json"
            and pointer(manifest_path) == manifest_ref, "dedup manifest binding differs")
    manifest = read(manifest_path)
    require(manifest.get("stage") == str(stage) and manifest.get("version") == receipt["version"]
            and manifest.get("authority", {}).get("stage_result") == pointer(result_path)
            and len(manifest.get("outputs", [])) == receipt.get("logical_files")
            and manifest.get("selected_sessions") == [r["name"] for r in manifest.get("sessions", [])],
            "prior dedup closure differs")
    for session in manifest["sessions"]:
        for name in ("completion", "validation"):
            ref = session[name]
            require(pointer(ref["path"]) == ref, "session proof changed")
    for bundle in manifest["bundles"]:
        require(pointer(bundle["path"]) == bundle, "output bundle changed")
    rows = manifest["outputs"]
    require(len(rows) == len({r["path"] for r in rows}) and all(
        isinstance(r.get("sha256"), str) and r["sha256"].startswith("sha256:")
        and isinstance(r.get("size_bytes"), int) and r["size_bytes"] >= 0
        and Path(r["path"]).is_relative_to(stage / "cohort") for r in rows),
        "logical output roster differs")
    groups = {}
    for row in rows:
        groups.setdefault((row["sha256"], row["size_bytes"]), []).append(Path(row["path"]))
    require(len(groups) == receipt.get("unique_payloads"), "dedup payload count differs")
    return {"stage": stage, "result": pointer(result_path), "dedup_manifest": manifest_ref,
            "dedup_receipt": pointer(receipt_path), "rows": rows, "groups": groups}


def object_name(sha):
    require(len(sha) == 71 and sha.startswith("sha256:")
            and all(c in "0123456789abcdef" for c in sha[7:]), "invalid object digest")
    return "objects/" + sha[7:]


def preflight(data):
    """Only one distinct inode and one content hash per deduped payload."""
    stage = data["stage"]
    for (sha, size), paths in data["groups"].items():
        first = safe(paths[0], stage)
        info = first.stat()
        require(info.st_size == size and digest(first, sha)[0] == sha, "canonical bytes changed")
        require(all(safe(path, stage).stat().st_ino == info.st_ino for path in paths),
                "prior dedup hardlinks changed")


def create_archive(path, groups):
    require(not path.exists() and not path.is_symlink(), "archive already exists")
    temporary = path.with_name(".partial-archive-" + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as output:
            with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for (sha, size), paths in sorted(groups.items()):
                    info = tarfile.TarInfo(object_name(sha))
                    info.size, info.mode, info.mtime, info.uid, info.gid = size, 0o444, 0, 0, 0
                    info.uname = info.gname = ""
                    with safe(paths[0]).open("rb") as source:
                        archive.addfile(info, source)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class PartialArchive:
    def __init__(self, stage, destination):
        self.data = authority(stage)
        self.destination = Path(destination)
        self.seal_path = safe(self.destination / "seal.json")
        self.seal = read(self.seal_path)
        expected = self.data
        require(self.seal.get("version") == VERSION and self.seal.get("stage") == str(stage)
                and self.seal.get("result") == expected["result"]
                and self.seal.get("dedup_manifest") == expected["dedup_manifest"]
                and self.seal.get("dedup_receipt") == expected["dedup_receipt"],
                "partial archive authority differs")
        self.tar_path = safe(self.destination / "native.tar")
        require(self.seal.get("archive") == pointer(self.tar_path), "archive bytes changed")
        expected_objects = {object_name(sha): (sha, size) for sha, size in expected["groups"]}
        require(self.seal.get("objects") == [{"name": name, "sha256": sha, "size_bytes": size}
                for name, (sha, size) in sorted(expected_objects.items())], "sealed object roster differs")
        with tarfile.open(self.tar_path, "r:") as archive:
            members = archive.getmembers()
            require(len(members) == len(expected_objects)
                    and {m.name for m in members} == set(expected_objects)
                    and all(m.isfile() and m.size == expected_objects[m.name][1] for m in members),
                    "tar member roster differs")
            for member in members:
                stream = archive.extractfile(member)
                require(stream is not None, "missing tar stream")
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(CHUNK), b""):
                    h.update(block)
                require("sha256:" + h.hexdigest() == expected_objects[member.name][0],
                        "tar member hash differs")
        self.rows = {row["path"]: row for row in expected["rows"]}
        self.loose_inodes = {}
        for key, paths in expected["groups"].items():
            surviving = [path for path in paths if path.exists()]
            if not surviving:
                continue
            first = safe(surviving[0], expected["stage"])
            info = first.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_size == key[1]
                    and digest(first, key[0])[0] == key[0], "surviving canonical bytes changed")
            require(all(safe(path, expected["stage"]).stat().st_ino == info.st_ino
                        for path in surviving), "surviving hardlink aliases differ")
            self.loose_inodes[key] = info.st_ino
        receipt = self.destination / "compacted.json"
        if receipt.exists():
            value = read(receipt)
            require(value.get("version") == VERSION and value.get("status") == "complete"
                    and value.get("seal") == pointer(self.seal_path)
                    and value.get("logical_files_retired") == len(self.rows)
                    and all(not Path(name).exists() for name in self.rows),
                    "retirement receipt or loose remainder differs")

    def fingerprint(self, logical):
        path = Path(logical)
        require(str(path) in self.rows, "unknown logical output")
        row = self.rows[str(path)]
        return {"sha256": row["sha256"], "size_bytes": row["size_bytes"]}

    @contextmanager
    def open_binary(self, logical):
        """Stream the original logical payload without extracting it to disk."""
        row = self.rows.get(str(logical))
        require(row is not None, "unknown logical output")
        with tarfile.open(self.tar_path, "r:") as archive:
            stream = archive.extractfile(object_name(row["sha256"]))
            require(stream is not None, "missing logical payload")
            with stream:
                yield stream


@contextmanager
def reader_session(stage, destination):
    """Reverify the full archive and authority at both transaction boundaries."""
    archive = PartialArchive(stage, destination)
    try:
        yield archive
    finally:
        PartialArchive(stage, destination)


def prepare(stage, destination=None, *, writers_closed=False, retire=False):
    require(writers_closed is True, "all control writers must have exited")
    stage = Path(stage)
    canonical = stage / "partial-native-output-storage"
    destination = canonical if destination is None else Path(destination)
    require((retire and destination == canonical) or
            (not retire and destination.is_absolute() and destination.is_relative_to(Path("/tmp"))
             and destination != Path("/tmp")), "retirement requires canonical destination; shadow requires /tmp")
    with exclusive_host():
        data = authority(stage)
        if not (destination / "seal.json").exists():
            preflight(data)
            require(not destination.exists(), "unsealed destination already exists")
            destination.mkdir(parents=True)
            sync_directory(destination.parent)
            tar_path = destination / "native.tar"
            create_archive(tar_path, data["groups"])
            objects = [{"name": object_name(sha), "sha256": sha, "size_bytes": size}
                       for sha, size in sorted(data["groups"])]
            seal = {"version": VERSION, "stage": str(stage), "result": data["result"],
                    "dedup_manifest": data["dedup_manifest"], "dedup_receipt": data["dedup_receipt"],
                    "archive": pointer(tar_path), "objects": objects}
            write_new(destination / "seal.json", seal)
            sync_directory(destination)
        archive = PartialArchive(stage, destination)
        if not retire:
            return {"status": "sealed_shadow", "seal": pointer(destination / "seal.json"),
                    "logical_files": len(archive.rows), "objects": len(data["groups"])}
        for name, row in archive.rows.items():
            path = Path(name)
            if path.exists():
                info = safe(path, stage).stat()
                require(info.st_ino == archive.loose_inodes[(row["sha256"], row["size_bytes"])]
                        and info.st_size == row["size_bytes"],
                        "logical hardlink changed before retirement")
                path.unlink()
                sync_directory(path.parent)
        receipt_path = destination / "compacted.json"
        receipt = {"version": VERSION, "status": "complete", "seal": pointer(destination / "seal.json"),
                   "logical_files_retired": len(archive.rows), "source_bytes_preserved": True}
        if receipt_path.exists():
            require(read(receipt_path) == receipt, "prior immutable receipt differs")
        else:
            write_new(receipt_path, receipt)
        PartialArchive(stage, destination)
        return {"status": "complete", "receipt": pointer(receipt_path),
                "logical_files": len(archive.rows), "objects": len(data["groups"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--shadow-destination", type=Path)
    parser.add_argument("--writers-closed", action="store_true")
    parser.add_argument("--retire", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.stage, args.shadow_destination,
                             writers_closed=args.writers_closed, retire=args.retire)))


if __name__ == "__main__":
    main()
