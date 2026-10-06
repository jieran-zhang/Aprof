"""Real reviewed raw reader against tiny synthetic six-session authority proof.

This checks the attestor evidence interface, not a full real final replay.
"""
import importlib.util
from pathlib import Path
import sys
import pytest
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'scripts'),str(P/'src')]
import level2_raw_archive_storage as raw
import level2_evidence_storage as facade
from test_level2_raw_archive_storage import tiny
spec=importlib.util.spec_from_file_location('attestor_real_raw_unit',P/'scripts/level2_final_report_attestation.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def test_actual_retired_raw_logical_identity_enters_attestor_binding(tiny,monkeypatch):
    task,sessions,*_=tiny;session=sessions[0]
    logical=session/'raw/unused/extra.bin';before=logical.read_bytes()
    raw.prepare(session,writers_closed=True,retire=True)
    assert not logical.exists()
    runtime=a.Runtime.__new__(a.Runtime);runtime.storage=facade
    openings=[];original=raw.RawArchive.__init__
    def count(self,*args,**kwargs):
        openings.append(1);original(self,*args,**kwargs)
    monkeypatch.setattr(raw.RawArchive,'__init__',count)
    with runtime.reader_session():
        evidence=a.Evidence(runtime)
        pointer=evidence.pointer(logical)
        assert pointer=={'path':str(logical),'sha256':a.digest(before)}
        assert runtime.read(logical)==before
        binding=evidence.storage_bindings[str(logical)]
        assert binding['version']==raw.VERSION
        assert len(binding['closed_evidence']['sessions'])==6
        assert binding['closed_evidence']['report_authority']['kind']=='ledger_timing_calibration_v1'
        assert binding['closed_evidence']['protected'] and binding['closed_evidence']['event_bindings']
        compact=a.compact_storage_bindings(evidence.storage_bindings.values())
        assert compact['origins'][str(logical)]['sha256']==pointer['sha256']
        assert next(iter(compact['closed_evidence'].values()))==binding['closed_evidence']
        evidence.recheck()
    assert len(openings)==1


def test_tampered_tar_prevents_attestor_recheck(tiny):
    task,sessions,*_=tiny;session=sessions[0]
    raw.prepare(session,writers_closed=True,retire=True)
    runtime=a.Runtime.__new__(a.Runtime);runtime.storage=facade
    with pytest.raises(ValueError):
        with runtime.reader_session():
            evidence=a.Evidence(runtime);evidence.pointer(session/'raw/unused/extra.bin')
            archive=session/'raw-archive-storage/raw.tar'
            data=bytearray(archive.read_bytes());data[1536]^=1;archive.write_bytes(data)
            evidence.recheck()
