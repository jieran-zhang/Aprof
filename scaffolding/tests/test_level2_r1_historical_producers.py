"""Versioned historical roster replay; no native process or live campaign writes."""
from pathlib import Path
import copy
import pytest
import level2_r1_queue as q
from test_level2_r1_queue import queued
CURRENT=set(q.FRESH_PRODUCERS)


def request(version=q.VERSION):
    queue_hash=next(h for h,v in q.LEGACY_QUEUE_ROSTERS.items() if v==version)
    refs=[{'path':str(q.ROOT/'scaffolding/collection/scripts'/n),'sha256':'sha256:'+'1'*64} for n in sorted(q.LEGACY_PRODUCER_NAMES)]
    for r in refs:
        if Path(r['path']).name=='level2_r1_queue.py':r['sha256']=queue_hash
        if Path(r['path']).name=='msprof_exploration_provenance.py':r['sha256']=q.LEGACY_PROVENANCE_HASH
    return {'version':version,'producers':refs}


@pytest.mark.parametrize('version',[q.VERSION,q.CONTINUATION_VERSION])
def test_reviewed_exact_historical_roster_only_replays(version):
    r=request(version)
    assert q.producer_names(r,live_producers=False)==q.LEGACY_PRODUCER_NAMES
    with pytest.raises(ValueError,match='closure differs'):q.producer_names(r,live_producers=True)


@pytest.mark.parametrize('mutation',['missing_old','one_new','unknown_extra','duplicate','unknown_queue','unknown_provenance','wrong_version','handoff_downgrade'])
def test_self_declared_legacy_subsets_or_new_queue_downgrade_rejected(mutation):
    r=request()
    if mutation=='missing_old':r['producers'].pop(0)
    elif mutation in ['one_new','unknown_extra']:r['producers'].append({'path':str(q.ROOT/'scaffolding/collection/scripts'/('level2_guard_contract.py' if mutation=='one_new' else 'arbitrary.py')),'sha256':'sha256:'+'2'*64})
    elif mutation=='duplicate':r['producers'].append(copy.deepcopy(r['producers'][0]))
    elif mutation in ['unknown_queue','unknown_provenance']:
        target='level2_r1_queue.py' if mutation=='unknown_queue' else 'msprof_exploration_provenance.py'
        next(x for x in r['producers'] if Path(x['path']).name==target)['sha256']='sha256:'+'2'*64
    elif mutation=='wrong_version':r['version']=q.CONTINUATION_VERSION
    elif mutation=='handoff_downgrade':r['version']=q.HANDOFF_VERSION
    with pytest.raises(ValueError):q.producer_names(r,live_producers=False)


@pytest.fixture
def historical(queued,monkeypatch):
    queue,calls,_,_,_=queued;old=q.load(queue/'request.json')
    monkeypatch.setattr(q,'FRESH_PRODUCERS',CURRENT)
    scripts=q.ROOT/'scaffolding/collection/scripts'
    for n in q.LEGACY_PRODUCER_NAMES:
        if not (scripts/n).exists():(scripts/n).write_text('# historical synthetic CPU fixture '+n+'\n')
    refs=[q.pointer(scripts/n) for n in sorted(q.LEGACY_PRODUCER_NAMES)]
    monkeypatch.setattr(q,'LEGACY_QUEUE_ROSTERS',{q.sha(scripts/'level2_r1_queue.py'):q.VERSION})
    monkeypatch.setattr(q,'LEGACY_PROVENANCE_HASH',q.sha(scripts/'msprof_exploration_provenance.py'))
    snapshot=queue.parents[1]/'bootstrap/historical-cas';snapshot.mkdir()
    files=[]
    for ref in refs:
        p=Path(ref['path']);dst=snapshot/p.name;dst.write_bytes(p.read_bytes());files.append({**ref,'snapshot':str(dst)})
    eng=queue.parents[1]/'bootstrap/historical.json';q.atomic(eng,{'version':'level2_frozen_engineering_v1','files':files})
    old['engineering']=q.pointer(eng);old['producers']=refs;q.atomic(queue/'request.json',old)
    state=q.load(queue/'state.json');state['request']=q.pointer(queue/'request.json');q.atomic(queue/'state.json',state)
    return queue,old,state,eng,calls


def test_complete_legacy_engineering_binding_passes_without_child(historical):
    queue,r,state,_,calls=historical
    q.request_identity(queue,state,r,live_producers=False)
    assert not calls.exists()
    with pytest.raises(ValueError,match='closure differs'):q.request_identity(queue,state,r)
    assert not calls.exists()


@pytest.mark.parametrize('mutation',['cas_bytes','engineering_sha','snapshot_missing','origin_alias','origin_elsewhere','new_names_without_snapshots'])
def test_historical_every_producer_still_binds_frozen_engineering(historical,mutation):
    queue,r,state,eng,calls=historical;v=q.load(eng)
    if mutation=='cas_bytes':Path(v['files'][0]['snapshot']).write_text('tampered')
    elif mutation=='engineering_sha':v['files'][0]['sha256']='sha256:'+'f'*64
    elif mutation=='snapshot_missing':Path(v['files'][0]['snapshot']).unlink()
    elif mutation in ['origin_alias','origin_elsewhere']:
        name=Path(r['producers'][0]['path']).name
        r['producers'][0]['path']=str(q.ROOT/'scaffolding/collection/scripts'/'..'/'scripts'/name) if mutation=='origin_alias' else str(q.ROOT/'elsewhere'/name)
    elif mutation=='new_names_without_snapshots':
        for n in sorted(CURRENT-set(q.LEGACY_PRODUCER_NAMES)):
            r['producers'].append({'path':str(q.ROOT/'scaffolding/collection/scripts'/n),'sha256':'sha256:'+'f'*64})
    q.atomic(eng,v);r['engineering']=q.pointer(eng)
    with pytest.raises((ValueError,OSError)):q.request_identity(queue,state,r,live_producers=False)
    assert not calls.exists()


def test_full_current_roster_is_unchanged_and_never_needs_legacy_rule():
    r={'version':q.HANDOFF_VERSION,'producers':[{'path':str(q.ROOT/'scaffolding/collection/scripts'/n),'sha256':'sha256:'+'3'*64} for n in sorted(CURRENT|{'level2_r1_queue.py','run_msprof_exploration_stage.py','prepare_trace_pilot.py'})]}
    assert q.producer_names(r,live_producers=True)==set(Path(x['path']).name for x in r['producers'])
