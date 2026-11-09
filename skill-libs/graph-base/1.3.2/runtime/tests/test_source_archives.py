
import hashlib
import json
from pathlib import Path

import pytest

from aprof_runtime import diagnosis, _diagnosis_v1
from aprof_runtime.errors import GraphError
from aprof_runtime.documentation_sources import original_path, source_archives
from aprof_runtime.knowledge import local, read_record

ROOT = Path(__file__).resolve().parents[2]
NAME = "skills/example/sources/upstream/revision/kernel.h"


@pytest.fixture
def archived(tmp_path):
    payload = b"// Upstream copyright\r\n#pragma once\r\n"
    checksum = hashlib.sha256(payload).hexdigest()
    physical = tmp_path / (NAME + ".txt")
    physical.parent.mkdir(parents=True)
    physical.write_bytes(payload)
    tools = tmp_path / "tools"
    tools.mkdir()
    manifest = {
        "schema_version": "aprof.source-archives/v1",
        "files": {NAME: {"path": NAME + ".txt", "sha256": checksum}},
    }
    (tools / "source-archives.json").write_text(json.dumps(manifest))
    (tools / "frozen-files.json").write_text(json.dumps({"files": {NAME: checksum}}))
    (tmp_path / "skills/example/SKILL.md").write_text("---\nname: example\n---\n")
    (tmp_path / "skills/registry.json").write_text(
        json.dumps(
            {
                "capabilities": {
                    "core": [{"name": "example", "source": "skills/example"}]
                },
                "support_skills": [],
                "workflow_plugin": {"agents": []},
            }
        )
    )
    return tmp_path, physical, payload


def test_logical_header_resolves_to_byte_exact_archive(archived):
    root, physical, payload = archived
    assert not (root / NAME).exists()
    assert original_path(root, NAME) == physical
    assert local(root, NAME).read_bytes() == payload


def test_archive_tampering_is_rejected_by_reader(archived):
    root, physical, _ = archived
    physical.write_bytes(b"replaced source")
    with pytest.raises(ValueError, match="archived source bytes changed"):
        original_path(root, NAME)


def test_shadow_header_is_rejected(archived):
    root, _, payload = archived
    (root / NAME).write_bytes(payload)
    with pytest.raises(ValueError, match="shadow file"):
        original_path(root, NAME)


def test_diagnosis_inventory_keeps_logical_source_identity(archived, monkeypatch):
    root, _, payload = archived
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    artifact = {"source_hashes": {NAME: checksum, NAME + ".txt": checksum}}
    monkeypatch.setattr(_diagnosis_v1, "_source_compile_region", lambda *_: artifact)
    actual = diagnosis.compile_region(root, Path("parent"))
    assert actual["source_hashes"] == {NAME: checksum}


def test_diagnosis_inventory_rejects_conflicting_identity(archived, monkeypatch):
    root, _, payload = archived
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    artifact = {"source_hashes": {NAME: "sha256:" + "0" * 64, NAME + ".txt": checksum}}
    monkeypatch.setattr(_diagnosis_v1, "_source_compile_region", lambda *_: artifact)
    with pytest.raises(GraphError, match="source archive identity differs"):
        diagnosis.compile_region(root, Path("parent"))


@pytest.mark.parametrize("destination", ["../../outside.txt", "sources/other.txt"])
def test_archive_redirect_is_rejected(archived, destination):
    root, _, _ = archived
    path = root / "tools/source-archives.json"
    manifest = json.loads(path.read_text())
    manifest["files"][NAME]["path"] = destination
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unexpected source archive path"):
        source_archives(root)


@pytest.mark.parametrize(
    "logical", ["runtime/source.h", "../outside.h", "skills/example/source.cpp"]
)
def test_archive_scope_is_restricted_to_snapshot_headers(archived, logical):
    root, _, _ = archived
    path = root / "tools/source-archives.json"
    manifest = json.loads(path.read_text())
    manifest["files"][logical] = manifest["files"].pop(NAME)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        source_archives(root)


@pytest.mark.parametrize(
    "relative",
    [
        "branches/fusion-composition/recipes/cv-multistage-handoff.md",
        "branches/pipeline-sync/recipes/slots.md",
    ],
)
def test_archived_headers_keep_compiled_record_identity(relative):
    region = ROOT / "skills/ascendc-aprof-optimization/knowledge"
    name = (region / relative).relative_to(ROOT).as_posix()
    index = json.loads((region / "index.json").read_text())
    expected = next(row for row in index["records"] if row["source_path"] == name)
    actual = read_record(ROOT / name, ROOT)
    for field in ("source_path", "source_hash", "body", "sources"):
        assert actual[field] == expected[field]
