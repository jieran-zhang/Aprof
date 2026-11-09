"""Resolve byte-exact evidence behind reading views and archived source text."""

import hashlib
import json
from pathlib import Path
import re


def checked_path(root, name):
    root = Path(root).resolve()
    relative = Path(name)
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe document path: {name}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"document path escapes package: {name}")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"document path is a symlink: {name}")
        if part == root:
            break
    return path


def adaptations(root):
    path = checked_path(root, "tools/documentation-adaptations.json")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "aprof.documentation-adaptations/v1":
        raise ValueError("unsupported documentation adaptation manifest")
    return data["files"]


def source_archives(root):
    """Restrict header aliases to read-only third-party source snapshots."""
    manifest = checked_path(root, "tools/source-archives.json")
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != "aprof.source-archives/v1":
        raise ValueError("unsupported source archive manifest")
    rows = data.get("files")
    if not isinstance(rows, dict):
        raise ValueError("invalid source archive entries")
    for name, row in rows.items():
        relative = Path(name)
        if (
            name != relative.as_posix()
            or ".." in relative.parts
            or not re.fullmatch(
                r"skills/[^/]+/(?:sources/|knowledge/sources/).+\.(?:h|hpp|hh|hxx)",
                name,
            )
        ):
            raise ValueError(f"source archive is outside snapshot scope: {name}")
        if not isinstance(row, dict) or row.get("path") != name + ".txt":
            raise ValueError(f"unexpected source archive path: {name}")
        if not isinstance(row.get("sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", row["sha256"]
        ):
            raise ValueError(f"invalid source archive checksum: {name}")
    return rows


def original_path(root, name, *, entries=None, archives=None):
    """Validate both identities; only evidence readers receive the original."""
    path = checked_path(root, name)
    aliases = source_archives(root) if archives is None else archives
    archived = aliases.get(Path(name).as_posix())
    if archived is not None:
        if path.exists():
            raise ValueError(f"archived source has a shadow file: {name}")
        source = checked_path(root, archived["path"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != archived["sha256"]:
            raise ValueError(f"archived source bytes changed: {name}")
        return source
    rows = adaptations(root) if entries is None else entries
    entry = rows.get(Path(name).as_posix())
    if entry is None:
        return path
    if path.suffix != ".md":
        raise ValueError(f"adapted document must be Markdown: {name}")
    original = f"sources/document-originals/{entry['source_sha256']}.txt"
    if entry["original"] != original:
        raise ValueError(f"unexpected original document path: {name}")
    source = checked_path(root, original)
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["view_sha256"]:
        raise ValueError(f"adapted document bytes changed: {name}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != entry["source_sha256"]:
        raise ValueError(f"original document bytes changed: {name}")
    return source
