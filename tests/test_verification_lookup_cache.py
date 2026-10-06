"""Small local fixtures only; no real campaign data, hardware, or host lock."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).parents[1]
LIVE=Path(os.environ.get('APROF_TEST_REPO',ROOT))
sys.path[:0]=[str(LIVE/'tests'),str(LIVE/'scripts')]
import test_level2_native_output_storage as fixture_module
spec=importlib.util.spec_from_file_location('lookup_reader_under_test',ROOT/'scripts/level2_verification_storage.py')
store=importlib.util.module_from_spec(spec);spec.loader.exec_module(store)

@pytest.fixture
def sealed(tmp_path,monkeypatch):
    monkeypatch.setattr(fixture_module.dedup,'exclusive_host',contextlib.nullcontext)
    monkeypatch.setattr(fixture_module,'verification',store)
    task,cohort,_,_=fixture_module.fixture(tmp_path)
    session=cohort/'p01'
    originals={p:p.read_bytes() for p in sorted((session/'verification').rglob('*')) if p.is_file()}
    shadow=tmp_path/'shadow'
    store.prepare(session,shadow,writers_closed=True)
    store.prepare(session,writers_closed=True,retire=True)
    return task,session,shadow,originals

def test_all_known_members_and_reader_aliases_skip_hot_filesystem_checks(sealed,monkeypatch):
    _,session,_,originals=sealed;paths=list(originals)
    with store.reader_session(cache_verified_bytes=True):
        assert store.read_bytes(paths[0])==originals[paths[0]]
        assert len(store._LOOKUPS.get()['members'])==len(originals)
        with monkeypatch.context() as m:
            m.setattr(os,'stat',lambda *a,**k:pytest.fail('hot verified byte lookup accessed filesystem'))
            for path,data in originals.items():
                assert store.read_bytes(path)==data and store.is_file(path)
                with store.open_binary(path) as stream:assert stream.read()==data
                assert store.fingerprint(path)=={'sha256':store.digest(data),'size_bytes':len(data)}
                assert store.evidence_binding(path,store.digest(data))['bytes']==data
        with pytest.raises(ValueError,match='hash differs'):store.evidence_binding(paths[0],'sha256:'+'0'*64)
    assert store._LOOKUPS.get() is None and store._CACHE.get() is None

def test_no_cross_context_or_outside_context_positive_cache(sealed,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals))
    for _ in range(2):
        with store.reader_session(cache_verified_bytes=True):
            assert not store._LOOKUPS.get()['members']
            store.read_bytes(path)
    calls=[];old=store.safe
    def safe(*a,**k):calls.append(a[0]);return old(*a,**k)
    monkeypatch.setattr(store,'safe',safe)
    assert store.read_bytes(path)==originals[path] and calls
    assert store._LOOKUPS.get() is None

def test_missing_marker_is_not_cached_and_invalid_new_declaration_rejects(tmp_path):
    path=tmp_path/'run/train/tasks/maximum/stages/aa/cohort/p01/verification/1_normal_A/metadata.json'
    path.parent.mkdir(parents=True);path.write_bytes(b'ordinary')
    with store.reader_session(cache_verified_bytes=True):
        assert store.read_bytes(path)==b'ordinary'
        assert not store._LOOKUPS.get()['members']
        (path.parents[2]/'verification-storage').mkdir()
        with pytest.raises(FileNotFoundError):store.read_bytes(path)

def test_ordinary_legacy_level1_path_falls_back_only_without_declaration(tmp_path):
    path=tmp_path/'run/tasks/exp/stages/search/cohort/p01/verification/1_normal_A/metadata.json'
    path.parent.mkdir(parents=True);path.write_bytes(b'legacy')
    with store.reader_session(cache_verified_bytes=True):
        assert store.read_bytes(path)==b'legacy'
        assert store.is_file(path) and store.fingerprint(path)['sha256']==store.digest(b'legacy')
        assert not store._LOOKUPS.get()['members']
        (path.parents[2]/'verification-storage').mkdir()
        with pytest.raises(ValueError):store.read_bytes(path)

@pytest.mark.parametrize('fault',['unknown_member','dotdot','wrong_result_name'])
def test_cached_roster_does_not_admit_new_or_noncanonical_aliases(sealed,fault):
    _,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        store.read_bytes(path)
        bad=session/'verification/20_normal_A/metadata.json'
        if fault=='dotdot':bad=session/'verification/1_normal_A/../1_normal_A/metadata.json'
        if fault=='wrong_result_name':bad=session/'verification/1_normal_A/precision.json'
        with pytest.raises((ValueError,FileNotFoundError)):store.read_bytes(bad)

@pytest.mark.parametrize('fault',['seal','tar','producer','report','control','loose_member'])
def test_full_exit_revalidation_rejects_mutation_after_hot_hit(sealed,fault):
    _,session,_,originals=sealed;path=next(iter(originals))
    targets={'seal':session/'verification-storage/seal.json','tar':session/'verification-storage/verification.tar',
             'producer':session/'verification-storage/producer.py','report':session.parent/'report.json',
             'control':session/'validation.json','loose_member':path}
    target=targets[fault]
    with pytest.raises((ValueError,KeyError,json.JSONDecodeError)):
        with store.reader_session(cache_verified_bytes=True):
            assert store.read_bytes(path)==originals[path]
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((target.read_bytes() if target.exists() else b'')+b'changed')
            assert store.read_bytes(path)==originals[path]
    assert store._LOOKUPS.get() is None

@pytest.mark.parametrize('ancestor',['verification-storage','session'])
def test_symlink_ancestor_rechecked_at_transaction_boundary(sealed,ancestor):
    _,session,_,originals=sealed;path=next(iter(originals))
    target=session/'verification-storage' if ancestor=='verification-storage' else session
    moved=target.with_name(target.name+'-moved')
    try:
        with pytest.raises(ValueError,match='symlink'):
            with store.reader_session(cache_verified_bytes=True):
                store.read_bytes(path);target.rename(moved);target.symlink_to(moved,target_is_directory=True)
                assert store.read_bytes(path)==originals[path]
    finally:target.unlink();moved.rename(target)

def test_explicit_revalidation_fails_before_publication_and_poison_is_sticky(sealed,tmp_path):
    _,session,_,originals=sealed;path=next(iter(originals));target=session.parent/'report.json';data=target.read_bytes()
    publish=tmp_path/'must-not-publish'
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path);target.write_bytes(b'{}')
            try:
                store.reverify_cached();publish.write_bytes(b'published')
            except (ValueError,KeyError):pass
            target.write_bytes(data)
            with pytest.raises(ValueError,match='already failed'):store.read_bytes(path)
            assert not store._LOOKUPS.get()['members']
    assert not publish.exists()
    with store.reader_session(cache_verified_bytes=True):assert store.read_bytes(path)==originals[path]

def test_successful_explicit_revalidation_clears_lookup_before_reopening(sealed):
    _,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        store.read_bytes(path);assert store._LOOKUPS.get()['members']
        store.reverify_cached();assert not store._LOOKUPS.get()['members']
        assert store.read_bytes(path)==originals[path]

def test_nested_exception_cannot_be_swallowed_into_successful_outer_transaction(sealed):
    _,session,_,originals=sealed;path=next(iter(originals))
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            with pytest.raises(RuntimeError):
                with store.reader_session(cache_verified_bytes=True):raise RuntimeError('reader failed')
            with pytest.raises(ValueError,match='already failed'):store.read_bytes(path)
    assert store._LOOKUPS.get() is None

def test_nested_shadow_destination_is_part_of_positive_identity(sealed):
    _,session,shadow,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        canonical=store.evidence_binding(path)['seal']
        with store.reader_session({session:shadow},cache_verified_bytes=True):
            alternate=store.evidence_binding(path)['seal']
            assert alternate!=canonical
            assert store.read_bytes(path)==originals[path]
            with pytest.raises(ValueError,match='nested'):
                with store.reader_session({session:shadow},cache_verified_bytes=True):pass
        assert store.evidence_binding(path)['seal']==canonical

def test_unrelated_event_append_preserves_bound_prefix(sealed):
    task,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        store.read_bytes(path)
        fixture_module.event(task,'unrelated_later_event',{'scope':'synthetic'})
        store.reverify_cached()
        assert store.read_bytes(path)==originals[path]

def test_nested_archive_failure_at_native_reverify_clears_and_poison_lookup(sealed,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals))
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            with monkeypatch.context() as m:
                m.setattr(store.native_outputs,'reverify_cached',lambda:(_ for _ in ()).throw(ValueError('nested native changed')))
                with pytest.raises(ValueError,match='nested native'):store.reverify_cached()
            assert not store._LOOKUPS.get()['members']

def test_resealed_but_independently_valid_archive_cannot_change_midtransaction(sealed):
    _,session,shadow,originals=sealed;path=next(iter(originals))
    seal=shadow/'seal.json';before=seal.read_bytes()
    with pytest.raises(ValueError,match='seal changed'):
        with store.reader_session({session:shadow},cache_verified_bytes=True):
            store.read_bytes(path)
            # Insignificant seal JSON whitespace still changes its immutable identity.
            seal.write_bytes(before+b' ')
            store.reverify_cached()

def test_default_context_never_creates_positive_lookup_state(sealed,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session():
        assert not store.lookup_cache_enabled() and store._LOOKUPS.get() is None
        store.read_bytes(path)
        calls=[];original=store.safe
        def safe(*a,**k):calls.append(a[0]);return original(*a,**k)
        with monkeypatch.context() as m:
            m.setattr(store,'safe',safe)
            assert store.read_bytes(path)==originals[path] and calls
        assert store._LOOKUPS.get() is None

def test_default_nested_context_actively_suspends_and_revalidates_before_restore(sealed,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        store.read_bytes(path)
        assert store.lookup_cache_enabled() and store._LOOKUPS.get()['members']
        calls=[];original=store.safe
        def safe(*a,**k):calls.append(a[0]);return original(*a,**k)
        with monkeypatch.context() as m:
            m.setattr(store,'safe',safe)
            with store.reader_session():
                assert not store.lookup_cache_enabled()
                assert store.read_bytes(path)==originals[path] and calls
        assert store.lookup_cache_enabled()
        assert not store._LOOKUPS.get()['members']  # full validation ran before resuming opted caller
        store.read_bytes(path)
        assert store._LOOKUPS.get()['members']

def test_default_nested_exception_poison_survives_policy_restore(sealed):
    _,session,_,originals=sealed;path=next(iter(originals))
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            with pytest.raises(RuntimeError):
                with store.reader_session():
                    assert not store.lookup_cache_enabled()
                    raise RuntimeError('legacy writer interrupted')
            assert store.lookup_cache_enabled()
            with pytest.raises(ValueError,match='already failed'):store.read_bytes(path)
    assert not store.lookup_cache_enabled() and store._LOOKUPS.get() is None

def test_read_only_nested_helper_may_explicitly_inherit_policy(sealed):
    _,session,_,originals=sealed;path=next(iter(originals))
    with store.reader_session(cache_verified_bytes=True):
        store.read_bytes(path);state=store._LOOKUPS.get()
        with store.reader_session(cache_verified_bytes=store.lookup_cache_enabled()):
            assert store.lookup_cache_enabled() and store._LOOKUPS.get() is state
        assert store._LOOKUPS.get()['members']

def test_actual_native_writer_default_context_suspends_opted_parent(sealed,tmp_path,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals));seen=[]
    class Observed(Exception):pass
    def audit_read(*args,**kwargs):
        seen.append(store.lookup_cache_enabled())
        assert store._LOOKUPS.get() is not None and not store._LOOKUPS.get()['members']  # validated before writer entry
        assert not store.lookup_cache_enabled()
        calls=[];original=store.safe
        def safe(*a,**k):calls.append(a[0]);return original(*a,**k)
        with monkeypatch.context() as m:
            m.setattr(store,'safe',safe);store.read_bytes(path);assert calls
        raise Observed()
    monkeypatch.setitem(sys.modules,'level2_verification_storage',store)
    monkeypatch.setattr(store.native_outputs,'closed_from_reader',audit_read)
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            with pytest.raises(Observed):
                store.native_outputs.prepare(session.parent,tmp_path/'native-shadow',writers_closed=True)
    assert seen==[False] and not (tmp_path/'native-shadow').exists()

@pytest.mark.parametrize('invalid',[1,'true',None])
def test_cache_policy_requires_actual_boolean(invalid):
    with pytest.raises(ValueError,match='boolean'):
        with store.reader_session(cache_verified_bytes=invalid):pass

def test_actual_dedup_decorator_suspends_opted_parent_before_inventory(sealed,monkeypatch):
    _,session,_,originals=sealed;path=next(iter(originals));seen=[]
    monkeypatch.setitem(sys.modules,'level2_verification_storage',store)
    spec=importlib.util.spec_from_file_location('unchanged_dedup_under_test',LIVE/'scripts/level2_storage.py')
    dedup=importlib.util.module_from_spec(spec);spec.loader.exec_module(dedup)
    monkeypatch.setattr(dedup,'exclusive_host',contextlib.nullcontext)
    class Observed(Exception):pass
    def inventory(*args,**kwargs):
        seen.append(store.lookup_cache_enabled())
        assert not store.lookup_cache_enabled()
        assert store._LOOKUPS.get() is not None and not store._LOOKUPS.get()['members']
        raise Observed()
    monkeypatch.setattr(dedup,'Inventory',inventory)
    with pytest.raises(ValueError,match='already failed'):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            with pytest.raises(Observed):
                dedup.deduplicate(session.parents[5],session.parent,kind='cohort',writers_closed=True,apply=True)
    assert seen==[False]

@pytest.mark.parametrize('fault',['dangling_root','dangling_case','case_symlink','member_symlink','unexpected_case','root_file'])
def test_real_loose_tree_remains_strict_with_virtual_tar_paths(sealed,tmp_path,fault):
    _,session,shadow,originals=sealed;root=session/'verification'
    if fault=='dangling_root':root.symlink_to(tmp_path/'absent',target_is_directory=True)
    elif fault=='root_file':root.write_bytes(b'not a directory')
    else:
        root.mkdir()
        case=root/'1_normal_A'
        if fault=='dangling_case':case.symlink_to(tmp_path/'absent',target_is_directory=True)
        elif fault=='case_symlink':
            target=tmp_path/'case';target.mkdir();case.symlink_to(target,target_is_directory=True)
        elif fault=='unexpected_case':(root/'not_allowed').mkdir()
        else:
            case.mkdir();(case/'metadata.json').symlink_to(tmp_path/'absent')
    with pytest.raises((ValueError,FileNotFoundError)):
        store.verified(session,shadow)

def test_partial_loose_tree_and_exact_remnant_bytes_still_checked(sealed):
    _,session,shadow,originals=sealed;path=next(iter(originals))
    path.parent.mkdir(parents=True);path.write_bytes(originals[path])
    assert store.verified(session,shadow)['payloads'][str(path)]==originals[path]
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='loose verification file differs'):
        store.verified(session,shadow)

def test_virtual_roster_member_cannot_escape_canonical_scope(sealed):
    _,session,shadow,originals=sealed;seal=shadow/'seal.json'
    value=json.loads(seal.read_bytes());value['members'][0]['path']=str(session/'verification/1_normal_A/../1_normal_A/metadata.json')
    seal.write_bytes(store.canonical(value))
    with pytest.raises(ValueError):store.verified(session,shadow)

def test_retired_archive_revalidation_never_physically_walks_each_virtual_member(sealed,monkeypatch):
    _,session,shadow,originals=sealed;calls=[];original=store.location
    def location(path,**kwargs):
        calls.append((str(path),kwargs.get('check_files',True)));return original(path,**kwargs)
    monkeypatch.setattr(store,'location',location)
    value=store.verified(session,shadow)
    for logical in value['payloads']:
        assert (logical,False) in calls
    # process_location retains the physical synthetic path check exactly once.
    assert sum(checked for _,checked in calls)==1

@pytest.mark.parametrize('fault',['loose_member','ancestor_symlink'])
def test_legacy_writer_body_never_receives_stale_inherited_snapshot(sealed,tmp_path,fault):
    _,session,_,originals=sealed;path=next(iter(originals));entered=[]
    with pytest.raises(ValueError):
        with store.reader_session(cache_verified_bytes=True):
            store.read_bytes(path)
            if fault=='loose_member':
                path.parent.mkdir(parents=True);path.write_bytes(b'changed')
            else:
                target=session/'verification';target.symlink_to(tmp_path/'absent',target_is_directory=True)
            with store.reader_session():
                entered.append(True)
    assert entered==[]
