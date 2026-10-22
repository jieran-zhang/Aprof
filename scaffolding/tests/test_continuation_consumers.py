"""CPU-only consumer checks; no native, archives, host locks or live run."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
REPO = Path(os.environ.get('APROF_TEST_REPO', str(ROOT)))
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import pytest
import level2_iteration as iteration
import level2_cohort_continuation as continuation
import msprof_exploration_archive as archive
import msprof_exploration_campaign as campaign
from shared_context_build import source_hash
from test_level2_iteration_boundaries import close_reports_fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return iteration.pointer(path)


def proof(cohort):
    # Explicit fake certificate activates only the mocked continuation branch.
    write(cohort/'continuation-01/qualification.json',{})
    return dict(qualification={'path': str(cohort/'continuation-01/qualification.json'), 'sha256':'sha256:'+'a'*64},
        cohort=str(cohort), protected=[], event_bindings=[],
        directories=[str(cohort / ('p03-continuation-01' if i == 3 else f'p{i:02d}')) for i in range(1,7)],
        failed_directory=str(cohort/'p03'), failed_costs={'native_processes_started':1,'native_processes_completed':0,'role_samples':360},
        interruption_limitations=['Failed process retained; profiler exit unknown.','Interrupted cohort is descriptive only.'])


@pytest.fixture
def report_fixture(tmp_path, monkeypatch):
    task=tmp_path/'run/validation/tasks/dynamic_quant'; child=task/'candidates/dynamic_quant001'
    for directory, data in ((task/'baseline','base'),(child/'op','candidate')):
        (directory/'op_kernel').mkdir(parents=True);(directory/'op_kernel/kernel.asc').write_text(data)
    (task/'baseline-source.tar').write_bytes(b'baseline');(child/'source.tar').write_bytes(b'candidate')
    baseline=iteration.sha(task/'baseline-source.tar')
    item={'candidate_id':'dynamic_quant001','source_hash':iteration.sha(child/'source.tar'),
          'source_parent':{'candidate_id':None,'source_hash':baseline},'probes':[{'case_id':6},{'case_id':16}]}
    cases=[1,8,14,20,6,16]
    hashes={'A':source_hash(task/'baseline'),'B':source_hash(child/'op')}
    build=write(child/'plans/roles.json',{'operator':'dynamic_quant','roles':{k:{'source_sha256':v} for k,v in hashes.items()}})
    frozen={'case_ids':cases,'identity_bindings':{'role_build':build}}
    pref=write(child/'plans/cohort.json',frozen)
    plan={'purpose':'search','case_ids':cases,'comparisons':campaign.comparisons(item,baseline),
          'cohorts':[{'relation':'direct_parent','control_candidate_id':'baseline','plan':pref}]}
    write(child/'stages/search/stage-plan.json',plan)
    cohort=child/'stages/search/direct_parent'
    report={'operator':'dynamic_quant','case_ids':cases,'comparison_kind':'ab','evidence_status':'verified_complete',
        'plan_hash':iteration.digest(frozen),'source_hashes':hashes,'limitations':['Existing A/A limitation.'],
        'suite':{k:{'case_ids':cases} for k in ('normal','swapped')},
        'results':[dict(case_id=c,buffer_config=k,speedup=1.,ci95=[.9,1.1],latency_change=0.,cv_status='limited',
                       calibration_status='applicable',coarse_observed_controls='limited',measurement_quality='complete_with_caution',
                       limitations=[],qualified_performance_eligible=False) for c in cases for k in ('normal','swapped')]}
    write(cohort/'report.json',report);write(cohort/'group-completion.json',{'status':'passed'})
    monkeypatch.setattr(iteration,'verify_source_snapshot',lambda *a:None)
    ledger = close_reports_fixture(task, child, item)
    monkeypatch.setattr(iteration, 'Campaign', lambda _: ledger)
    return task,child,item,baseline,cohort,report


def projected(f):
    task,child,item,baseline,*_=f
    return iteration.comparison_reports(task,child,'dynamic_quant',item,baseline,required=True)


def test_ordinary_feedback_remains_unannotated(report_fixture):
    rows=projected(report_fixture)
    assert len(rows)==1 and 'continuation' not in rows[0]
    assert rows[0]['limitations']==['Existing A/A limitation.']
    assert rows[0]['case_ids']==[1,8,14,20,6,16]


def test_feedback_retains_authenticated_annotation_and_limitations(report_fixture,monkeypatch):
    *_,cohort,report=report_fixture;p=proof(cohort);calls=[]
    def resolve(path,read_bytes=Path.read_bytes,*,require_closed):
        calls.append((path,require_closed));return deepcopy(p)
    monkeypatch.setattr(continuation,'resolve',resolve)
    report['continuation']=continuation.annotation(p);write(cohort/'report.json',report)
    task, child, item, *_ = report_fixture
    ledger = close_reports_fixture(task, child, item)
    monkeypatch.setattr(iteration, 'Campaign', lambda _: ledger)
    row=projected(report_fixture)[0]
    assert row['continuation']==continuation.annotation(p)
    assert row['limitations']==report['limitations']+p['interruption_limitations']
    assert calls==[(cohort,True),(cohort,True)]


@pytest.mark.parametrize('certificate_present',[False,True])
def test_feedback_rejects_missing_or_forged_annotation(report_fixture,monkeypatch,certificate_present):
    *_,cohort,report=report_fixture;p=proof(cohort)
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:p if certificate_present else None)
    if not certificate_present:report['continuation']=continuation.annotation(p)
    write(cohort/'report.json',report)
    with pytest.raises(ValueError,match='annotation differs'):projected(report_fixture)


def test_feedback_rejects_changed_authority_after_projection(report_fixture,monkeypatch):
    *_,cohort,report=report_fixture;p=proof(cohort);count=0
    def resolve(*a,**k):
        nonlocal count
        count+=1;v=deepcopy(p)
        if count>1:v['failed_costs']['role_samples']=0
        return v
    monkeypatch.setattr(continuation,'resolve',resolve)
    report['continuation']=continuation.annotation(p);write(cohort/'report.json',report)
    with pytest.raises(ValueError,match='changed before feedback'):projected(report_fixture)


def collector(run):
    a=archive.Archive.__new__(archive.Archive);a.run=run;a.split='validation';a.root=run/'archive/validation'
    a.fresh=True;a.ledger=SimpleNamespace(config={'tasks':{'dynamic_quant':{'split':'validation'}}},state={'tasks':{'dynamic_quant':{'stages':{}}}})
    a.artifacts={};a.pointer_cache={};a.engineering_bindings={};a.observation_producer_bindings={}
    return a


def test_authenticated_retention_is_not_an_arbitrary_pointer_allowlist(tmp_path,monkeypatch):
    a=collector(tmp_path/'run');p=proof(a.run/'validation/tasks/dynamic_quant/candidates/dynamic_quant001/stages/search/direct_parent')
    forged=deepcopy(p);forged['protected']=[{'path':str(a.run/'validation/ledger/unapproved.json'),'sha256':'sha256:'+'0'*64}]
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:p)
    with pytest.raises(ValueError,match='current resolver'):a._retain_continuation_refs(forged,'dynamic_quant')
    assert not a.artifacts


def test_retention_requires_current_task_scope(tmp_path,monkeypatch):
    a=collector(tmp_path/'run');p=proof(tmp_path/'another_run/validation/tasks/dynamic_quant/cohort')
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:pytest.fail('foreign scope must reject first'))
    with pytest.raises(ValueError,match='outside the current'):a._retain_continuation_refs(p,'dynamic_quant')


def test_retains_both_preservation_archives_and_revokes_token(tmp_path,monkeypatch):
    a=collector(tmp_path/'run');p=proof(a.run/'validation/tasks/dynamic_quant/candidates/dynamic_quant001/stages/search/direct_parent')
    for name in ('failed-raw.tar','failed-native.tar'):
        path=a.run/'storage/maintenance/preservation'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
        p['protected'].append(iteration.pointer(path))
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:deepcopy(p))
    a._retain_continuation_refs(p,'dynamic_quant')
    assert {r['path'] for r in a.artifacts.values()}=={r['path'] for r in p['protected']}
    assert not a._active_ledger_authorities
    with pytest.raises(ValueError,match='active authenticated'):
        a._authenticated_authority_pointer(a.run/'validation/ledger/config.json','dynamic_quant',expected='sha256:'+'0'*64)


@pytest.fixture
def cohort_fixture(tmp_path,monkeypatch):
    a=collector(tmp_path/'run');cohort=a.run/'validation/tasks/dynamic_quant/candidates/dynamic_quant001/stages/search/direct_parent'
    p=proof(cohort);plan={'schedule':[]}
    build=cohort.parent/'roles/build.json';runner=cohort.parent/'runner/build.json'
    write(build,{'roles':{r:{'source_dir':str(cohort.parent/r),'source_sha256':'tree'} for r in 'AB'}});write(runner,{})
    for i,d in enumerate(p['directories']):
        write(Path(d)/'bindings.json',{})
        plan['schedule'].append({'name':f'p{i+1:02d}','request':{'role_build':str(build),'runner_build':str(runner)}})
    write(cohort/'plan.json',plan)
    write(cohort/'group-completion.json',{'status':'passed','completed_sessions':p['directories']})
    saved={**archive.POLICY,'operator':'dynamic_quant','source_hashes':dict.fromkeys('AB','tree'),
           'results':[],'sessions':[{} for _ in range(6)],'continuation':continuation.annotation(p)}
    write(cohort/'report.json',saved)
    retained=[]
    monkeypatch.setattr(a,'_retain_continuation_refs',lambda v,o:retained.append(deepcopy(v)))
    monkeypatch.setattr(a,'audit_paths',lambda *a,**k:None)
    monkeypatch.setattr(a,'bind_closed_observation_producers',lambda *a,**k:None)
    monkeypatch.setattr(a,'document',lambda v:v)
    monkeypatch.setattr(archive,'native_tar_hash',lambda *a:'tree')
    monkeypatch.setattr(archive.analysis,'analyze_task_cohort',lambda *a,**k:deepcopy(saved))
    monkeypatch.setattr(archive.analysis,'compare_saved_report',lambda x,y,**k:None if x==y else pytest.fail('saved report differs'))
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:deepcopy(p))
    return a,cohort,p,saved,retained


def archive_cohort(f):
    a,c,*_=f
    return archive.Archive.cohort.__wrapped__(a,c,'dynamic_quant',c/'base.tar',c/'candidate.tar')


def test_archive_retains_continuation_even_with_current_producers(cohort_fixture):
    a,c,p,saved,retained=cohort_fixture
    result=archive_cohort(cohort_fixture)
    assert retained==[p]
    assert result['summary']['native_process_count']==6
    assert result['summary']['actual_native_processes_including_failed']==7
    assert result['summary']['failed_actual_costs']==p['failed_costs']
    assert result['summary']['continuation']==continuation.annotation(p)


def test_archive_rejects_unapproved_replacement_path(cohort_fixture):
    a,c,p,*_=cohort_fixture
    completion=archive.load(c/'group-completion.json');completion['completed_sessions'][2]=str(c/'p03-other')
    write(c/'group-completion.json',completion)
    with pytest.raises(ValueError,match='authenticated continuation'):archive_cohort(cohort_fixture)


def test_archive_rejects_late_authority_mutation(cohort_fixture,monkeypatch):
    a,c,p,*_=cohort_fixture;count=0
    def resolve(*a,**k):
        nonlocal count
        count+=1;v=deepcopy(p)
        if count>1:v['failed_costs']['role_samples']=0
        return v
    monkeypatch.setattr(continuation,'resolve',resolve)
    with pytest.raises(ValueError,match='changed during archive'):archive_cohort(cohort_fixture)


def test_archive_ordinary_summary_has_no_new_fields(cohort_fixture,monkeypatch):
    a,c,p,saved,_=cohort_fixture
    del saved['continuation'];write(c/'report.json',saved)
    monkeypatch.setattr(continuation,'resolve',lambda *a,**k:None)
    result=archive_cohort(cohort_fixture)
    assert 'continuation' not in result['summary']
    assert 'actual_native_processes_including_failed' not in result['summary']
    assert result['summary']['native_process_count']==6


@pytest.fixture
def certified_closed(tmp_path,monkeypatch):
    # Real Campaign registration/start/qualify/finish and real resolver. Only the
    # fixture's source identity uses tiny bytes; preservation fixture is owned
    # by the resolver tests and will carry its exact reviewed schema.
    import test_continuation_product as fixture
    data=b'tiny source archive identity'
    monkeypatch.setattr(continuation,'SOURCE',continuation.sha(data))
    f=fixture.certified(tmp_path)
    (f['child']/'source.tar').write_bytes(data)
    fixture.close(f)
    return f


def test_real_resolver_archive_retains_exact_ledger_and_prefix_closure(certified_closed):
    f=certified_closed;a=collector(f['run']);p=continuation.resolve(f['cohort'],require_closed=True)
    a._retain_continuation_refs(p,'dynamic_quant')
    indexed={r['path'] for r in a.artifacts.values()}
    assert {r['path'] for r in p['protected']}<=indexed
    for event in p['event_bindings']:
        assert any(r['path']==event['path'] and r.get('selector')=='line:'+str(event['sequence']+1) for r in a.artifacts.values())
    assert not a._active_ledger_authorities
    with pytest.raises(ValueError,match='global ledger'):
        a.pointer(f['run']/'validation/ledger/config.sha256.json','dynamic_quant')


def test_real_resolver_rejects_injected_archive_pointer(certified_closed):
    f=certified_closed;a=collector(f['run']);p=continuation.resolve(f['cohort'],require_closed=True)
    p['protected'].append({'path':str(f['run']/'validation/ledger/arbitrary.json'),'sha256':'sha256:'+'0'*64})
    with pytest.raises(ValueError,match='current resolver'):a._retain_continuation_refs(p,'dynamic_quant')
    assert not a.artifacts


@pytest.mark.parametrize('ledger',[True,False])
def test_real_resolver_event_prefix_changed_after_authentication_rejected(certified_closed,monkeypatch,ledger):
    f=certified_closed;a=collector(f['run']);p=continuation.resolve(f['cohort'],require_closed=True)
    original=continuation.resolve
    binding=next(e for e in p['event_bindings'] if ('ledger' in Path(e['path']).parts)==ledger)
    def changed(*args,**kwargs):
        value=original(*args,**kwargs)
        path=Path(binding['path']);lines=path.read_bytes().splitlines();row=json.loads(lines[binding['sequence']]);row['recorded_at']='after authentication'
        body={k:v for k,v in row.items() if k!='hash'}
        row['hash']=(continuation.digest(body) if ledger else continuation.sha((json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()))
        lines[binding['sequence']]=continuation.canonical(row);path.write_bytes(b'\n'.join(lines)+b'\n')
        return value
    monkeypatch.setattr(continuation,'resolve',changed)
    with pytest.raises(ValueError,match='prefix changed after authentication'):
        a._retain_continuation_refs(p,'dynamic_quant')
    assert not a._active_ledger_authorities


def test_compound_closed_producer_continuation_is_not_flat_pointer(certified_closed,monkeypatch):
    f=certified_closed;a=collector(f['run']);p=continuation.resolve(f['cohort'],require_closed=True)
    origin=f['run']/'producer.py';origin.write_text('current')
    expected='sha256:'+'0'*64
    # Producer lookup only is stubbed; preserve a stable real resolver closure
    # by using a separate synthetic session, not changing authenticated refs.
    synthetic=f['task']/'test-producer-session';write(synthetic/'bindings.json',{str(origin):expected})
    snapshot=f['run']/'bootstrap/source-cas'/'tiny';snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_text('old')
    manifest=f['run']/'bootstrap/proof.json';write(manifest,{})
    import msprof_exploration_provenance as provenance
    monkeypatch.setattr(provenance,'frozen_producer',lambda *a,**k:{'closed_observation':{'cohort_continuation':p},'snapshot':iteration.pointer(snapshot),'frozen_manifest':iteration.pointer(manifest)})
    monkeypatch.setattr(a,'document',lambda v:v)
    a.bind_closed_observation_producers(synthetic,'dynamic_quant')
    assert any(r['path']==str(f['run']/'validation/ledger/config.json') for r in a.artifacts.values())
