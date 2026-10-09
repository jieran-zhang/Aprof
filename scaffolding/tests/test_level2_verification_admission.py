"""Prior-authority admission v2, with genuine frozen v1 compatibility fixtures."""
import importlib.util
import json
from pathlib import Path
import pytest
from test_level2_native_output_storage import fixture,save,blob,native,verification as store,portable,dataset,PROPOSAL,no_hardware
from verification_authority_fixture import packed,sha,legacy_archive

def rewrite_ledger(ledger,rows):
    previous='sha256:'+'0'*64
    for n,row in enumerate(rows):
        row['sequence']=n;row['previous_hash']=previous;row['hash']=sha(packed({k:v for k,v in row.items() if k!='hash'}));previous=row['hash']
    (ledger/'events.jsonl').write_bytes(b''.join(packed(row)+b'\n' for row in rows))

@pytest.mark.parametrize('candidate',[False,True])
def test_new_archive_records_independent_prior_report_authority(tmp_path,candidate):
    task,cohort,dest,_=fixture(tmp_path,candidate=candidate);session=cohort/'p01'
    result=store.prepare(session,dest,writers_closed=True)
    assert result['version']==store.ANCHORED_VERSION
    seal=json.loads((dest/'seal.json').read_text())
    authority=seal['closed_evidence']['report_authority']
    assert authority['kind']==('ledger_closed_feedback_report_v1' if candidate else 'ledger_timing_calibration_v1')
    assert authority['report']==store.raw_ref(cohort/'report.json')
    assert store.verified(session,dest)['seal']==seal

@pytest.mark.parametrize('candidate',[False,True])
@pytest.mark.parametrize('mutations',[('metadata.json','stdout.log'),('metadata.json','stdout.log','execution.json')])
def test_rehashed_report_cannot_replace_previously_anchored_oracle_bytes(tmp_path,candidate,mutations):
    task,cohort,dest,_=fixture(tmp_path,candidate=candidate);session=cohort/'p01'
    report=json.loads((cohort/'report.json').read_text())
    for name in mutations:
        path=session/'verification/1_normal_A'/name;blob(path,b'changed original bytes');report['sessions'][0]['artifacts'][str(path)]=native.digest(path.read_bytes())
    save(cohort/'report.json',report)
    with pytest.raises(ValueError,match='no independent previously recorded'):store.prepare(session,dest,writers_closed=True)
    assert not dest.exists()

@pytest.mark.parametrize('mutation',['no_ledger','no_slot','wrong_workload','wrong_kind','wrong_candidate','wrong_stage','unclosed','wrong_feedback_hash','wrong_relation','wrong_report_path','wrong_report_hash','wrong_own_plan','wrong_finished_result'])
def test_unproven_or_unrelated_ledger_claim_fails_before_publication(tmp_path,mutation):
    task,cohort,dest,_=fixture(tmp_path,candidate=True);session=cohort/'p01';ledger=task.parents[1]/'ledger'
    rows=[json.loads(line) for line in (ledger/'events.jsonl').read_bytes().splitlines()];a=rows[-1]['arguments']
    if mutation=='no_ledger':(ledger/'events.jsonl').unlink()
    else:
        if mutation=='no_slot':a['feedback']['comparisons']=[]
        elif mutation=='wrong_workload':a['workload']='softmax'
        elif mutation=='wrong_kind':rows[2]['arguments']['kind']='build'
        elif mutation=='wrong_candidate':a['candidate_id']='maximum999'
        elif mutation=='wrong_stage':a['stage_ids']=[]
        elif mutation=='unclosed':a['close_feedback']=False
        elif mutation=='wrong_feedback_hash':a['report_ref']='sha256:'+'0'*64
        elif mutation=='wrong_relation':a['feedback']['comparisons'][0]['relation']='original_baseline'
        elif mutation=='wrong_report_path':a['feedback']['comparisons'][0]['report']['path']=str(cohort.parent/'original_baseline/report.json')
        elif mutation=='wrong_report_hash':a['feedback']['comparisons'][0]['report']['sha256']='sha256:'+'0'*64
        elif mutation=='wrong_own_plan':rows[2]['arguments']['plan']={'wrong':True}
        elif mutation=='wrong_finished_result':rows[3]['arguments']['evidence']['result']['sha256']='sha256:'+'0'*64
        if mutation!='wrong_feedback_hash':a['report_ref']=sha((json.dumps(a['feedback'],ensure_ascii=False,sort_keys=True)+'\n').encode())
        rewrite_ledger(ledger,rows)
    with pytest.raises((ValueError,FileNotFoundError)):store.prepare(session,dest,writers_closed=True)
    assert not dest.exists()


def test_ledger_append_after_seal_does_not_change_prior_authority(tmp_path):
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01';store.prepare(session,dest,writers_closed=True)
    ledger=task.parents[1]/'ledger';rows=[json.loads(line) for line in (ledger/'events.jsonl').read_bytes().splitlines()]
    rows.append({**rows[-1],'event_id':'later-unrelated','operation':'observe','arguments':{'workload':'softmax'}});rewrite_ledger(ledger,rows)
    assert store.verified(session,dest)['seal']['version']==store.ANCHORED_VERSION


def test_existing_unanchored_v1_seal_remains_exact_and_truthfully_old(tmp_path):
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01'
    ledger=task.parents[1]/'ledger';(ledger/'events.jsonl').unlink()
    legacy_archive(store,session,session/'verification-storage',retire=True)
    original={p.name:p.read_bytes() for p in (session/'verification-storage').iterdir() if p.is_file()}
    value=store.verified(session);assert value['seal']['version']==store.VERSION
    assert 'report_authority' not in value['seal']['closed_evidence']
    store.prepare(session,writers_closed=True,retire=True)
    assert original=={p.name:p.read_bytes() for p in (session/'verification-storage').iterdir() if p.is_file()}


def test_new_anchored_archive_exports_ledger_and_validates_offline(tmp_path):
    from test_trace_v2_dataset import fixture_data
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01';origin=session/'verification/1_normal_A/metadata.json'
    evidence,body=fixture_data(tmp_path);body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    store.prepare(session,writers_closed=True,retire=True);bundle=tmp_path/'bundle';assert portable.export(root,bundle)['valid']
    closure=json.loads((bundle/'storage-verification/bindings.json').read_text())
    entry=next(iter(closure['archives'].values()));assert str(task.parents[1]/'ledger/events.jsonl') in entry['files']
    task.parents[1].rename(task.parents[1].with_name('original-unavailable'))
    assert portable.verify(bundle)['valid']

@pytest.mark.parametrize('mutation',['arbitrary_slot','wrong_report_hash','wrong_report_path','wrong_kind','wrong_workload','unknown_candidate','source_not_finished'])
def test_calibration_authority_requires_exact_existing_timing_slot(tmp_path,mutation):
    task,cohort,dest,_=fixture(tmp_path);ledger=task.parents[1]/'ledger';rows=[json.loads(v) for v in (ledger/'events.jsonl').read_bytes().splitlines()];a=rows[-1]['arguments']
    if mutation=='arbitrary_slot':a['plan']['random']=a['plan'].pop('calibration_report')
    elif mutation=='wrong_report_hash':a['plan']['calibration_report']['sha256']='sha256:'+'0'*64
    elif mutation=='wrong_report_path':a['plan']['calibration_report']['path']=str(cohort/'other-report.json')
    elif mutation=='wrong_kind':a['kind']='build'
    elif mutation=='wrong_workload':a['workload']='softmax'
    elif mutation=='unknown_candidate':a['candidate_id']='unknown001'
    elif mutation=='source_not_finished':rows[3]['arguments']['outcome']='failure'
    rewrite_ledger(ledger,rows)
    with pytest.raises(ValueError,match='no independent previously recorded'):store.prepare(cohort/'p01',dest,writers_closed=True)
    assert not dest.exists()


def test_self_reported_finalizer_completion_is_not_prior_report_authority(tmp_path):
    task,cohort,dest,_=fixture(tmp_path,candidate=True);ledger=task.parents[1]/'ledger'
    rows=[json.loads(v) for v in (ledger/'events.jsonl').read_bytes().splitlines()][:-1];rewrite_ledger(ledger,rows)
    save(task/'finalization/completion.json',{'version':'level2_final_evaluation_v1','status':'final_evaluations_completed','comparisons':[{'comparisons':[{'report':store.raw_ref(cohort/'report.json')}]}]})
    with pytest.raises(ValueError,match='no independent previously recorded'):store.prepare(cohort/'p01',dest,writers_closed=True)
    assert not dest.exists()


def test_recursive_portable_requires_bound_nested_verification_member(tmp_path):
    from test_trace_v2_dataset import fixture_data
    task,cohort,dest,original=fixture(tmp_path);evidence,body=fixture_data(tmp_path)
    origin=Path(next(iter(original)));body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    for n in range(1,7):store.prepare(cohort/f'p{n:02d}',writers_closed=True,retire=True)
    native.prepare(cohort,writers_closed=True,retire=True)
    bundle=tmp_path/'bundle';assert portable.export(root,bundle)['valid']
    closure=json.loads((bundle/'storage-verification/bindings.json').read_text());assert closure['version']=='level2_storage_portable_v3'
    assert len(closure['archives'])==7 and len(closure['dependencies'])==24
    manifest=json.loads((bundle/'bundle.json').read_text())
    key=next(iter(closure['dependencies']));closure['dependencies'][key]['sha256']='sha256:'+'f'*64
    save(bundle/'storage-verification/bindings.json',closure)
    manifest['files']['storage-verification/bindings.json']=portable.fingerprint(bundle/'storage-verification/bindings.json')
    manifest['storage_closure']['sha256']=manifest['files']['storage-verification/bindings.json']['sha256'];save(bundle/'bundle.json',manifest)
    with pytest.raises(ValueError,match='not pinned by parent proof'):portable.verify(bundle)

@pytest.mark.parametrize('relation',['invented','direct_parent','original_baseline'])
def test_only_known_per_relation_calibration_slots(tmp_path,relation):
    task,cohort,dest,_=fixture(tmp_path);ledger=task.parents[1]/'ledger';rows=[json.loads(v) for v in (ledger/'events.jsonl').read_bytes().splitlines()]
    plan=rows[-1]['arguments']['plan'];plan['cohorts']=[{'relation':relation,'calibration_report':plan.pop('calibration_report')}];rewrite_ledger(ledger,rows)
    if relation=='invented':
        with pytest.raises(ValueError,match='unknown/duplicate calibration relation'):store.prepare(cohort/'p01',dest,writers_closed=True)
        assert not dest.exists()
    else:
        result=store.prepare(cohort/'p01',dest,writers_closed=True);assert result['version']==store.ANCHORED_VERSION


def test_new_retirement_cannot_use_unretired_v1_to_skip_new_admission(tmp_path):
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01'
    legacy_archive(store,session,session/'verification-storage')
    with pytest.raises(ValueError,match='unretired v1 archive'):store.prepare(session,writers_closed=True,retire=True)
    assert (session/'verification').is_dir()

@pytest.mark.parametrize('name',['validation.json','bindings.json','completion.json','msprof.execution.json','native/journal.jsonl'])
def test_session_proof_mutation_rejected_by_original_report_artifact_hash(tmp_path,name):
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01';path=session/name
    if name.endswith('.jsonl'):
        value=[json.loads(v) for v in path.read_bytes().splitlines()];value[0]['extra_unverified']='mutation';blob(path,b''.join(native.canonical(v) for v in value))
    else:
        value=json.loads(path.read_text());value['extra_unverified']='mutation';save(path,value)
    with pytest.raises(ValueError,match='protected session metadata differs'):store.prepare(session,dest,writers_closed=True)
    assert not dest.exists()


def test_validation_row_and_four_loose_files_cannot_disappear_under_original_report(tmp_path):
    task,cohort,dest,_=fixture(tmp_path);session=cohort/'p01';path=session/'validation.json';value=json.loads(path.read_text());row=value['outputs'].pop();save(path,value)
    directory=session/'verification'/f"{row['case_id']}_{row['buffer_config']}_{row['role']}"
    for p in directory.iterdir():p.unlink()
    directory.rmdir()
    with pytest.raises(ValueError,match='protected session metadata differs|roster differs'):store.prepare(session,dest,writers_closed=True)
    assert not dest.exists()
