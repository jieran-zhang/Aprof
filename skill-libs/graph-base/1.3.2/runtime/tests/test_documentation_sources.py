"""Adapted reading views must never replace or weaken evidence identities."""

import hashlib
import json

import pytest

from aprof_runtime.documentation_sources import original_path
from aprof_runtime.knowledge import local


@pytest.fixture
def document(tmp_path):
    original = b"# Original\r\n[missing](old.md)\r\n"
    view = b"# Original\nmissing\n"
    checksum = hashlib.sha256(original).hexdigest()
    archive = tmp_path / f"sources/document-originals/{checksum}.txt"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(original)
    page = tmp_path / "sources/page.md"
    page.write_bytes(view)
    manifest = tmp_path / "tools/documentation-adaptations.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "aprof.documentation-adaptations/v1",
                "files": {
                    "sources/page.md": {
                        "original": archive.relative_to(tmp_path).as_posix(),
                        "source_sha256": checksum,
                        "view_sha256": hashlib.sha256(view).hexdigest(),
                    }
                },
            }
        )
    )
    return tmp_path, page, archive


def test_evidence_reader_keeps_exact_original_bytes(document):
    root, page, archive = document
    assert local(root, "sources/page.md") == archive
    assert local(root, "sources/page.md").read_bytes() == archive.read_bytes()
    assert page.read_bytes() != archive.read_bytes()


def test_modified_reading_view_is_rejected(document):
    root, page, _ = document
    page.write_bytes(b"unexpected edited view")
    with pytest.raises(ValueError, match="adapted document bytes changed"):
        original_path(root, "sources/page.md")


def test_modified_original_is_rejected(document):
    root, _, archive = document
    archive.write_bytes(b"replacement evidence")
    with pytest.raises(ValueError, match="original document bytes changed"):
        original_path(root, "sources/page.md")


def test_manifest_cannot_redirect_evidence_outside_package(document):
    root, _, _ = document
    manifest = root / "tools/documentation-adaptations.json"
    data = json.loads(manifest.read_text())
    data["files"]["sources/page.md"]["original"] = "../../other.txt"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unexpected original document path"):
        original_path(root, "sources/page.md")


def test_unadapted_documents_keep_normal_paths(tmp_path):
    path = tmp_path / "normal.md"
    path.write_text("# Normal\n")
    assert local(tmp_path, "normal.md") == path
