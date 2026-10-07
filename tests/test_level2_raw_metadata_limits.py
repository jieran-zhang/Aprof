"""Metadata I/O only: no raw collector, archive retirement, or hardware."""
from pathlib import Path
import hashlib,json,sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_raw_archive_storage as raw


def test_full20_sized_seal_metadata_can_publish_and_reload(tmp_path):
    # Reproduce the class of real 20.7 MB full20 seal that failed at 16 MiB.
    data=json.dumps({'closed_evidence':{'retained':'x'*(20*1024*1024)}}).encode()
    path=tmp_path/'seal.json'
    raw.publish_bytes(path,data)
    ref={'path':str(path),'sha256':'sha256:'+hashlib.sha256(data).hexdigest()}
    assert len(raw.load_ref(ref)['closed_evidence']['retained'])==20*1024*1024
    raw.publish_bytes(path,data)  # Existing immutable identical record is reusable.
    bad=dict(ref,sha256='sha256:'+'0'*64)
    with pytest.raises(ValueError,match='reference hash differs'):raw.load_ref(bad)


def test_oversized_metadata_rejected_before_publication(tmp_path,monkeypatch):
    monkeypatch.setattr(raw,'MAX_METADATA',128)
    path=tmp_path/'seal.json'
    with pytest.raises(ValueError,match='before publication'):raw.publish_bytes(path,b'x'*129)
    assert list(tmp_path.iterdir())==[]
    raw.publish_bytes(path,b'x'*128)
    assert raw.small_read(path)==b'x'*128
    with pytest.raises(ValueError,match='before publication'):raw.publish_bytes(path,b'y'*129)
    assert path.read_bytes()==b'x'*128


def test_reader_still_rejects_evidence_larger_than_configured_bound(tmp_path,monkeypatch):
    monkeypatch.setattr(raw,'MAX_METADATA',128)
    path=tmp_path/'oversize.json';path.write_bytes(b'x'*129)
    with pytest.raises(ValueError,match='metadata limit exceeded'):raw.small_read(path)
