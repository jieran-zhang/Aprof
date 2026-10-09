"""Opt-in raw writer publication gates; tiny synthetic files, no actual payloads."""
import contextlib
from pathlib import Path
import pytest
from test_level2_raw_storage_integration import raw,verification,tiny
import level2_storage


def seal_verification(s,monkeypatch):
    monkeypatch.setattr(level2_storage,'exclusive_host',contextlib.nullcontext)
    verification.prepare(s,writers_closed=True)
    return s/'verification/1_normal_A/metadata.json'


def test_cohort_facts_inherits_but_never_enables_lookup_policy(tiny,monkeypatch):
    _,sessions,*_=tiny
    old=verification.facts_for_version;states=[]
    def record(*a,**k):
        states.append(verification.lookup_cache_enabled());return old(*a,**k)
    monkeypatch.setattr(verification,'facts_for_version',record)
    raw.cohort_facts(sessions[0]);assert states and not any(states)
    states.clear()
    with verification.reader_session(cache_verified_bytes=True):
        raw.cohort_facts(sessions[0]);assert states and all(states)
        states.clear()
        with verification.reader_session():
            raw.cohort_facts(sessions[0]);assert states and not any(states)
        assert verification.lookup_cache_enabled()
    assert not verification.lookup_cache_enabled()


def test_prepare_opts_in_only_inside_host_lock_and_exits_before_unlock(tiny,monkeypatch):
    _,sessions,*_,dest=tiny;held=[False];old=raw.write_tar;exits=[]
    @contextlib.contextmanager
    def lock():
        held[0]=True
        try:yield
        finally:
            exits.append(verification.lookup_cache_enabled());held[0]=False
    def write(*a,**k):
        assert held[0] and verification.lookup_cache_enabled()
        return old(*a,**k)
    monkeypatch.setattr(raw,'host_lock',lock);monkeypatch.setattr(raw,'write_tar',write)
    raw.prepare(sessions[0],dest,writers_closed=True)
    assert exits==[False] and not verification.lookup_cache_enabled()


def test_mutated_verification_after_streaming_cannot_publish_seal(tiny,monkeypatch):
    _,sessions,*_,dest=tiny;s=sessions[0];target=seal_verification(s,monkeypatch)
    original=target.read_bytes();write=raw.write_tar
    def corrupt(*a,**k):
        result=write(*a,**k)
        assert verification.lookup_cache_enabled()
        target.write_bytes(original+b' ')
        return result
    monkeypatch.setattr(raw,'write_tar',corrupt)
    with pytest.raises(ValueError):raw.prepare(s,dest,writers_closed=True)
    assert not (dest/'seal.json').exists() and not (dest/'compacted.json').exists()
    assert (s/'raw').is_dir()


def test_mutated_verification_before_unlink_preserves_all_sources(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];target=seal_verification(s,monkeypatch)
    original=target.read_bytes();sync=raw.sync_directory;removed=[]
    def corrupt(p):
        result=sync(p)
        if Path(p)==s:target.write_bytes(original+b' ')
        return result
    monkeypatch.setattr(raw,'sync_directory',corrupt)
    monkeypatch.setattr(raw,'remove_file',lambda *a,**k:removed.append(a))
    with pytest.raises(ValueError):raw.prepare(s,writers_closed=True,retire=True)
    assert not removed and (s/'raw').is_dir()
    assert (s/'raw-archive-storage/seal.json').is_file()
    assert not (s/'raw-archive-storage/compacted.json').exists()


def test_mutated_verification_before_receipt_fails_then_exact_replay_recovers(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];target=seal_verification(s,monkeypatch)
    original=target.read_bytes();remove=raw.remove_directory
    def corrupt(p):
        result=remove(p)
        if Path(p)==s/'raw':target.write_bytes(original+b' ')
        return result
    monkeypatch.setattr(raw,'remove_directory',corrupt)
    with pytest.raises(ValueError):raw.prepare(s,writers_closed=True,retire=True)
    assert not (s/'raw').exists()
    assert (s/'raw-archive-storage/raw.tar').is_file()
    assert not (s/'raw-archive-storage/compacted.json').exists()
    target.write_bytes(original);monkeypatch.setattr(raw,'remove_directory',remove)
    assert raw.prepare(s,writers_closed=True,retire=True)['status']=='complete'


def test_last_cohort_replay_is_flushed_before_any_unlink(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];target=seal_verification(s,monkeypatch)
    original=target.read_bytes();sync=raw.sync_directory;facts=raw.cohort_facts;remove=raw.remove_file
    arm=[False];changed=[False];removed=[]
    def arm_at_durability(path):
        result=sync(path)
        if Path(path)==s:arm[0]=True
        return result
    def change_after_cached_proof(*args,**kwargs):
        result=facts(*args,**kwargs)
        if arm[0] and not changed[0]:
            changed[0]=True;target.write_bytes(original+b' ')
        return result
    def record_remove(*args,**kwargs):
        removed.append(str(args[0]));return remove(*args,**kwargs)
    monkeypatch.setattr(raw,'sync_directory',arm_at_durability)
    monkeypatch.setattr(raw,'cohort_facts',change_after_cached_proof)
    monkeypatch.setattr(raw,'remove_file',record_remove)
    with pytest.raises(ValueError):raw.prepare(s,writers_closed=True,retire=True)
    assert changed[0]
    assert not removed,'last cached proof read was not physically revalidated before unlink'
