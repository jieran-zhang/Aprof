"""Preserve diagnostic graph identity when source evidence is stored as text."""

from pathlib import Path

from . import _diagnosis_v1 as _compiler
from ._diagnosis_v1 import *  # noqa: F403 - preserve the legacy public exports
from .documentation_sources import original_path, source_archives

if not hasattr(_compiler, "_source_compile_region"):
    _compiler._source_compile_region = _compiler.compile_region


def compile_region(root: Path, parent_snapshot: Path) -> dict:
    """Restore verified logical header keys in the frozen source inventory."""
    root = Path(root).resolve()
    artifact = _compiler._source_compile_region(root, parent_snapshot)
    hashes = artifact["source_hashes"]
    try:
        for logical, entry in source_archives(root).items():
            physical = entry["path"]
            if physical not in hashes:
                continue
            original_path(root, logical)
            checksum = hashes.pop(physical)
            if (
                checksum.removeprefix("sha256:") != entry["sha256"]
                or hashes.get(logical, checksum) != checksum
            ):
                raise ValueError(f"source archive identity differs: {logical}")
            hashes[logical] = checksum
    except ValueError as exc:
        raise _compiler.GraphError(str(exc)) from exc
    artifact["source_hashes"] = dict(sorted(hashes.items()))
    return artifact


_compiler.compile_region = compile_region


def __getattr__(name):
    return getattr(_compiler, name)
