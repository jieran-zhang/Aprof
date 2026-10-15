import json
from pathlib import Path

import pytest

from level2_partial_control_output_dedup import deduplicate
from level2_partial_native_archive import PartialArchive, prepare, reader_session
from test_level2_partial_control_output_dedup import fixture


def test_partial_archive_retains_logical_hashes_after_retirement(tmp_path):
    stage, names = fixture(tmp_path)
    deduplicate(stage, names[1], writers_closed=True, apply=True)
    logical = stage / "cohort" / names[1] / "native/5_swapped_B.bin.indices"
    original = logical.read_bytes()
    shadow = tmp_path / "shadow"
    assert prepare(stage, shadow, writers_closed=True)["status"] == "sealed_shadow"
    with reader_session(stage, shadow) as preview:
        assert preview.fingerprint(logical)["size_bytes"] == len(original)
        with preview.open_binary(logical) as stream:
            assert stream.read() == original
    assert prepare(stage, writers_closed=True, retire=True)["status"] == "complete"
    assert not logical.exists()
    with reader_session(stage, stage / "partial-native-output-storage") as restored:
        with restored.open_binary(logical) as stream:
            assert stream.read() == original
    assert (stage / "cohort" / names[1] / "validation.json").is_file()


def test_tampered_source_or_seal_blocks_retirement(tmp_path):
    stage, names = fixture(tmp_path)
    deduplicate(stage, names[1], writers_closed=True, apply=True)
    source = stage / "cohort" / names[0] / "native/1_normal_A.bin"
    source.write_bytes(b"X" * source.stat().st_size)
    with pytest.raises(ValueError):
        prepare(stage, writers_closed=True, retire=True)
    assert source.exists()
    assert not (stage / "partial-native-output-storage").exists()
    source.write_bytes(b"case-1-packed")
    shadow = tmp_path / "shadow"
    prepare(stage, shadow, writers_closed=True)
    seal = shadow / "seal.json"
    value = json.loads(seal.read_text());value["version"] = "forged";seal.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        PartialArchive(stage, shadow)
    assert source.exists()
