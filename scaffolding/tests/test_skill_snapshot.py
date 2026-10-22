"""快照复用包校验，不修改源包或覆盖已有归档。"""
import pytest

from snapshot_skill_lib import snapshot
from validate_learning_records import Validator, file_hash


def package(root, *, corrupt=False):
    root.mkdir()
    (root / "README.md").write_text("合成包，无硬件运行\n")
    (root / "tools").mkdir()
    (root / "tools/release.py").write_text('''
from pathlib import Path
import hashlib
def verify_unsealed(root):
    files = {p.relative_to(root).as_posix(): 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    CORRUPTION
    return {'files':files, 'release_id':'synthetic/1.1.0', 'runtime_version':'0.0.0', 'status':'unsealed'}
'''.replace("CORRUPTION", "files['README.md'] = 'sha256:' + '0' * 64" if corrupt else "pass"))
    (root / "tools/launcher").write_text("#!/bin/sh\nexit 0\n")
    (root / "tools/launcher").chmod(0o755)


def test_copy_and_manifest_preserve_payload_and_executable(tmp_path):
    source, dest = tmp_path / "source", tmp_path / "archive"
    package(source)
    result = snapshot(source, dest)
    manifest = Validator(dest).read(result["skill_lib_ref"])
    assert manifest["schema_version"] == "aprof.skill-lib-snapshot/v1"
    assert manifest["publication_performed"] is False
    assert manifest["files"]
    for path, sha in manifest["files"].items():
        assert file_hash(dest / path) == sha
    assert (dest / "skill-lib/tools/launcher").stat().st_mode & 0o111
    before = (dest / "skill-lib.snapshot.json").read_bytes()
    with pytest.raises(ValueError, match="新目录"):
        snapshot(source, dest)
    assert (dest / "skill-lib.snapshot.json").read_bytes() == before


def test_cannot_copy_inside_source(tmp_path):
    source = tmp_path / "source"
    package(source)
    with pytest.raises(ValueError, match="包外"):
        snapshot(source, source / "nested")
    assert not (source / "nested").exists()


def test_copy_hash_failure_does_not_create_completed_manifest(tmp_path):
    source, dest = tmp_path / "source", tmp_path / "archive"
    package(source, corrupt=True)
    with pytest.raises(ValueError, match="复制期间"):
        snapshot(source, dest)
    assert not (dest / "skill-lib.snapshot.json").exists()
    assert (source / "README.md").read_text() == "合成包，无硬件运行\n"
