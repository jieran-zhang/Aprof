"""Resolve byte-exact evidence originals behind adapted Markdown reading views."""

import hashlib
import json
from pathlib import Path


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


def original_path(root, name, *, entries=None):
    """Validate both identities; only evidence readers receive the original."""
    path = checked_path(root, name)
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
