"""Task-local evidence references; no database, raw-file copy or durable archive."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .errors import StoreError
from .jsonio import canonical_json, file_hash


class LocalEvidence:
    """Keep original files in place and only write small records or mutable log snapshots."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory).absolute()
        if self.directory.resolve() != self.directory:
            raise StoreError("local evidence directory must be canonical")
        self.directory.mkdir(mode=0o700, exist_ok=False)
        self._paths: dict[str, Path] = {}
        self._sequence = 0

    @classmethod
    def from_index(cls, path: str | Path):
        """Open an explicit handoff without copying or trusting the referenced bytes."""
        path = cls._regular(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if (set(value) != {"schema_version", "kind", "directory", "artifacts"}
                or value["schema_version"] != 1 or value["kind"] != "local_evidence_index"
                or not isinstance(value["artifacts"], dict)):
            raise StoreError("invalid local evidence index")
        directory = Path(value["directory"])
        if (not directory.is_absolute() or directory.resolve() != directory
                or not directory.is_dir() or not path.is_relative_to(directory.parent)):
            raise StoreError("local evidence index escaped its task workspace")
        result = object.__new__(cls)
        result.directory = directory
        result._paths = {}
        for digest, source in value["artifacts"].items():
            if (not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                    or not isinstance(source, str) or not Path(source).is_absolute()):
                raise StoreError("invalid local evidence reference")
            result._paths[digest] = Path(source)
        result._sequence = max((int(p.stem.removeprefix("record-"))
            for p in directory.glob("record-*.*")
            if p.stem.removeprefix("record-").isdigit()), default=0)
        return result

    @staticmethod
    def _regular(path: str | Path) -> Path:
        path = Path(path).absolute()
        if path.is_symlink() or not path.is_file():
            raise StoreError(f"local evidence is not a regular file: {path}")
        return path.resolve(strict=True)

    def register_artifact(self, path, *, media_type=None, uri=None) -> str:
        if uri is not None:
            raise StoreError("local evidence does not create archive locations")
        source = self._regular(path)
        digest = file_hash(source)
        self._paths.setdefault(digest, source)
        return digest

    def register_artifacts(self, paths) -> tuple[str, ...]:
        return tuple(self.register_artifact(path) for path in paths)

    def _record(self, data: bytes, suffix: str) -> str:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        # A record must survive an append to the original collection log.
        self._sequence += 1
        path = self.directory / f"record-{self._sequence:06d}{suffix}"
        with path.open("xb") as stream:
            stream.write(data)
        if file_hash(path) != digest:
            raise StoreError("local record changed while it was written")
        self._paths[digest] = path
        return digest

    def register_json(self, value) -> str:
        return self._record(canonical_json(value).encode("utf-8"), ".json")

    def snapshot_file(self, path) -> str:
        """Preserve only the local log prefix that SDK export is about to append to."""
        source = self._regular(path)
        before = file_hash(source)
        digest = self._record(source.read_bytes(), ".log")
        if digest != before or file_hash(source) != before:
            raise StoreError("collection log changed during its local snapshot")
        return digest

    def verify_artifact(self, digest: str) -> Path:
        if digest not in self._paths:
            raise StoreError(f"local evidence is not indexed: {digest}")
        path = self._paths[digest]
        if self._regular(path) != path or file_hash(path) != digest:
            raise StoreError(f"local evidence changed: {digest}")
        return path

    def write_index(self, path) -> Path:
        """Optional task-end handoff; a separate collector owns any later copying."""
        path = Path(path).absolute()
        if path.resolve() != path or not path.is_relative_to(self.directory.parent):
            raise StoreError("local handoff must stay inside the task workspace")
        value = {"schema_version": 1, "kind": "local_evidence_index",
                 "directory": str(self.directory),
                 "artifacts": {digest: str(source) for digest, source in sorted(self._paths.items())}}
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        return path
