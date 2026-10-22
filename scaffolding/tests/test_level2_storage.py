"""Storage maintenance cannot infer eligible output files from arbitrary paths."""
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import level2_storage as storage


def save(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(row,sort_keys=True)+'\n');return path


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def ptr(path): return {'path':str(path),'sha256':sha(path)}
def binary(path,data): path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

def exited(path): save(path,dict(exit_code=0,ended_at=123,error=None))


@pytest.fixture(autouse=True)
def local_host_lock(monkeypatch):
    @contextmanager
    def locked(): yield
    monkeypatch.setattr(storage,'exclusive_host',locked)


def pilot(tmp_path,operator='maximum',contents=(b'same output',b'same output')):
    run=tmp_path/'run';task=run/'train/tasks'/operator;scope=task/'preflight/pilot'
    save(task/'manifest.json',dict(version='msprof_task_time_exploration_v2',operator=operator))
    save(scope/'request.json',dict(version='level2_prepared_pilot_v1',case_ids=list(range(1,len(contents)+1))))
    rows=[];outputs=[]
    for i,data in enumerate(contents,1):
        case=scope/f'case_{i:02d}';output=binary(case/'output.bin',data);outputs.append(output)
        native=save(case/'native.json',dict(version='level2_prepared_pilot_native_v1',mode='pilot',exit_code=0,
            warmup_complete_calls=1,profile_complete_calls=1,stream_destroyed=True,context_destroyed=True,finalized=True))
        exited(case/'native.execution.json');exited(case/'verify.execution.json')
        row=dict(case_id=i,correctness=dict(passed=True,output_hash=sha(output)),native=ptr(native))
        save(case/'pilot-case.json',row);rows.append(row)
    save(scope/'pilot.json',dict(version='level2_prepared_pilot_v1',operator=operator,status='passed',error=None,cases=rows))
    return run,task,scope,outputs


def dedup(run,scope,**kw):
    return storage.deduplicate(run,scope,kind=kw.pop('kind','pilot'),writers_closed=True,apply=True,**kw)


def tree(root): return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_verified_dry_run_and_scope_attestation_do_not_mutate_evidence(tmp_path):
    run,_,scope,outputs=pilot(tmp_path)
    before=tree(run)
    with pytest.raises(ValueError,match='affirm'): storage.deduplicate(run,scope,kind='pilot')
    result=storage.deduplicate(run,scope,kind='pilot',writers_closed=True)
    assert result['status']=='verified_dry_run' and result['logical_bytes']==22
    assert [r['path'] for r in result['files']]==list(map(str,outputs)) and tree(run)==before
    assert not (run/'storage').exists()


def test_dedup_preserves_all_paths_bytes_hashes_and_is_idempotent(tmp_path):
    run,task,scope,outputs=pilot(tmp_path)
    original_input=binary(task/'inputs/case_01/input.bin',b'same output')
    source=binary(task/'source/output.bin',b'same output')
    unrelated=binary(scope/'unexpected.bin',b'same output')
    excluded=[p.stat().st_ino for p in (original_input,source,unrelated)]
    before=tree(run)
    result=dedup(run,scope)
    assert result['status']=='passed' and result['reclaimed_bytes']==11 and result['logical_bytes']==22
    assert outputs[0].stat().st_ino==outputs[1].stat().st_ino
    assert all(result['results'][i]['before_hash']==result['results'][i]['after_hash']==sha(p) for i,p in enumerate(outputs))
    assert {p: (run/p).read_bytes() for p in before}==before
    assert [p.stat().st_ino for p in (original_input,source,unrelated)]==excluded
    manifest=json.loads(Path(result['manifest_path']).read_text())
    assert manifest['evidence_bytes_deleted']==0 and manifest['original_records_modified'] is False
    again=dedup(run,scope)
    assert again['reclaimed_bytes']==0 and all(r['status']=='already_linked_or_pool_seed' for r in again['results'])


def test_multiple_existing_links_only_count_reclaimed_last_inode(tmp_path):
    run,_,scope,outputs=pilot(tmp_path,contents=(b'123',b'123',b'123'))
    outputs[2].unlink();storage.os.link(outputs[1],outputs[2])
    result=dedup(run,scope)
    assert [r['reclaimed_bytes'] for r in result['results']]==[0,0,3]
    assert len({p.stat().st_ino for p in outputs})==1


@pytest.mark.parametrize('failure',['pilot_open','native_open','verifier_failed','output_changed','bad_coverage'])
def test_incomplete_or_changed_pilot_refused_before_storage_writes(tmp_path,failure):
    run,_,scope,outputs=pilot(tmp_path)
    if failure=='pilot_open': (scope/'pilot.json').unlink()
    elif failure=='native_open': (scope/'case_01/native.execution.json').unlink()
    elif failure=='verifier_failed': save(scope/'case_01/verify.execution.json',dict(exit_code=1,ended_at=123))
    elif failure=='output_changed': outputs[1].write_bytes(b'changed')
    else:
        row=json.loads((scope/'request.json').read_text());row['case_ids']=[1];save(scope/'request.json',row)
    with pytest.raises((ValueError,FileNotFoundError)): dedup(run,scope)
    assert not (run/'storage').exists()


@pytest.mark.parametrize('where',['output','ancestor','pool'])
def test_symlinks_are_prohibited(tmp_path,where):
    run,_,scope,outputs=pilot(tmp_path)
    if where=='output':
        outputs[1].unlink();outputs[1].symlink_to(outputs[0])
    elif where=='ancestor':
        origin=scope/'case_02';moved=scope/'other';origin.rename(moved);origin.symlink_to(moved,target_is_directory=True)
    else:
        pool=run/'storage/output-cas';pool.mkdir(parents=True)
        (pool/sha(outputs[0]).removeprefix('sha256:')).symlink_to(outputs[0])
    before=outputs[0].read_bytes()
    with pytest.raises(ValueError,match='symlink'):dedup(run,scope)
    assert outputs[0].read_bytes()==before


def test_cannot_select_input_source_boundary_or_unindexed_stage_directory(tmp_path):
    run,task,_,_=pilot(tmp_path)
    for name,kind in [('inputs','pilot'),('source','pilot'),('candidates/a/boundary-validation','cohort'),('stages/unindexed','cohort')]:
        path=task/name;path.mkdir(parents=True)
        with pytest.raises(ValueError): dedup(run,path,kind=kind)


def test_multi_output_bundle_parts_are_validated_and_deduplicated(tmp_path):
    y=b'yyy';scale=b'1234';bundle=struct.pack('<Q',len(y))+y+struct.pack('<Q',len(scale))+scale
    run,_,scope,outputs=pilot(tmp_path,'dynamic_quant',(bundle,bundle))
    parts=[]
    for output in outputs:
        rows=[]
        for name,value in [('output_y',y),('output_scale',scale)]:
            part=binary(output.with_name(output.name+'.'+name),value);parts.append(part)
            rows.append(dict(name=name,path=str(part),bytes=len(value),sha256=sha(part)))
        save(output.with_name(output.name+'.outputs.json'),dict(version='level2_output_bundle_v1',operator='dynamic_quant',outputs=rows))
    result=dedup(run,scope)
    assert len(result['results'])==6 and result['logical_bytes']==2*(len(bundle)+len(y)+len(scale))
    assert parts[0].stat().st_ino==parts[2].stat().st_ino and parts[1].stat().st_ino==parts[3].stat().st_ino
    assert result['reclaimed_bytes']==len(bundle)+len(y)+len(scale)


def test_multi_output_index_cannot_substitute_input_path(tmp_path):
    run,task,scope,outputs=pilot(tmp_path,'dynamic_quant',(b'fake',))
    other=binary(task/'inputs/input.bin',b'fake')
    save(outputs[0].with_name('output.bin.outputs.json'),dict(version='level2_output_bundle_v1',operator='dynamic_quant',outputs=[
        dict(name='output_y',path=str(other),bytes=4,sha256=sha(other)),dict(name='output_scale')]))
    with pytest.raises(ValueError,match='fixed output'):dedup(run,scope)
    assert not (run/'storage').exists()


def test_post_replace_hash_failure_rolls_back_original_inode(tmp_path,monkeypatch):
    run,_,scope,outputs=pilot(tmp_path);original=outputs[1].stat().st_ino
    real_digest=storage.digest;real_replace=storage.os.replace;state={'replaced':False,'failed':False}
    def replace(src,dst):
        real_replace(src,dst)
        if Path(src).suffix=='.tmp':state['replaced']=True
    def digest(path,expected=None):
        if state['replaced'] and not state['failed'] and Path(path)==outputs[1]:
            state['failed']=True;raise ValueError('injected post-replace hash failure')
        return real_digest(path,expected)
    monkeypatch.setattr(storage.os,'replace',replace);monkeypatch.setattr(storage,'digest',digest)
    with pytest.raises(ValueError,match='injected'):dedup(run,scope)
    assert outputs[1].read_bytes()==b'same output' and outputs[1].stat().st_ino==original
    assert not list(scope.rglob('*.bak')) and not list(scope.rglob('*.tmp'))
    report=json.loads(next((run/'storage/dedup').glob('*.json')).read_text())
    assert report['status']=='failed' and report['reclaimed_bytes']==0
    retry=dedup(run,scope)
    assert retry['status']=='passed' and retry['recovery'][0]['status']=='recovered_intact_output'


def test_crash_after_atomic_replace_recovers_only_verified_temporary_links(tmp_path,monkeypatch):
    run,_,scope,outputs=pilot(tmp_path)
    inventory=storage.Inventory(run,scope,'pilot')
    root=run/'storage';transactions=root/'transactions';transaction=transactions/('a'*32)
    transaction.mkdir(parents=True)
    stem='000001';suffix='.aprof-dedup-'+transaction.name+'-'+stem
    backup=outputs[1].with_name(outputs[1].name+suffix+'.bak');temporary=outputs[1].with_name(outputs[1].name+suffix+'.tmp')
    storage.os.link(outputs[1],backup);storage.os.link(outputs[0],temporary);storage.os.replace(temporary,outputs[1])
    save(transaction/(stem+'.intent.json'),dict(version=storage.VERSION,path=str(outputs[1]),sha256=sha(outputs[1]),backup=str(backup),temporary=str(temporary)))
    result=dedup(run,scope)
    assert result['status']=='passed' and len(result['recovery'])==1 and not backup.exists()
    assert result['recovery'][0]['reclaimed_bytes_known'] is False
    assert outputs[1].read_bytes()==b'same output'


def test_wrong_cas_hash_and_permission_mismatch_leave_original_file(tmp_path):
    run,_,scope,outputs=pilot(tmp_path)
    pool=run/'storage/output-cas';pool.mkdir(parents=True)
    bad=binary(pool/sha(outputs[0]).removeprefix('sha256:'),b'wrong')
    inode=outputs[1].stat().st_ino
    with pytest.raises(ValueError,match='hash differs'):dedup(run,scope)
    assert outputs[1].stat().st_ino==inode and outputs[1].read_bytes()==b'same output'
    bad.unlink();outputs[1].chmod(0o600)
    with pytest.raises(ValueError,match='permissions'):dedup(run,scope)
    assert outputs[1].stat().st_ino==inode and outputs[1].stat().st_mode&0o777==0o600


def cohort(tmp_path):
    run=tmp_path/'run';task=run/'train/tasks/maximum';stage=task/'stages/aa-initial';scope=stage/'cohort'
    save(task/'manifest.json',dict(version='msprof_task_time_exploration_v2',operator='maximum'))
    schedule=[];sessions=[];outputs=[]
    for i in range(6):
        directory=scope/f'p{i+1:02d}';request=dict(version='msprof_kernel_time_study_v2',cases=[dict(case_id=1)],buffer_configs='normal,swapped')
        schedule.append(dict(name=directory.name,request=request));save(directory/'request.json',request)
        completed=save(directory/'completion.json',dict(version=request['version'],status='passed',error=None))
        samples=save(directory/'samples.json',{'read_only_fixture':True})
        records=[];validation=[]
        for config in ('normal','swapped'):
            for role in 'AB':
                stem=f'1_{config}_{role}';output=binary(directory/'native'/(stem+'.bin'),b'identical output');outputs.append(output)
                records.append(dict(type='output',case_id='1',buffer_config=config,role=role,path=str(output),validation_scope='final_call_of_final_formal_sample'))
                validation.append(dict(case_id='1',buffer_config=config,role=role,passed=True,output_hash=sha(output)))
                exited(directory/'verification'/stem/'execution.json')
        records.append(dict(type='session_end',exit_code=0,stream_destroyed=True,context_destroyed=True))
        journal=directory/'native/journal.jsonl';journal.write_text(''.join(json.dumps(r)+'\n' for r in records))
        exited(directory/'msprof.execution.json')
        save(directory/'validation.json',dict(scope='final_call_of_final_sample_per_case_config_role',outputs=validation))
        sessions.append(dict(directory=str(directory),completion=ptr(completed),samples=ptr(samples),journal=ptr(journal)))
    plan=dict(schedule=schedule)
    save(scope/'plan.json',plan);save(stage/'stage-plan.json',dict(cohort=plan))
    save(stage/'result.json',dict(status='passed',kind='control',ended_at=321))
    save(scope/'group-completion.json',dict(status='passed',error=None,ended_at=320,completed_sessions=[r['directory'] for r in sessions],sessions=sessions))
    return run,stage,scope,outputs


def test_closed_six_session_cohort_and_whole_stage(tmp_path):
    run,stage,scope,outputs=cohort(tmp_path)
    result=dedup(run,scope,kind='cohort')
    assert len(result['results'])==24 and result['reclaimed_bytes']==23*len(b'identical output')
    assert len({p.stat().st_ino for p in outputs})==1
    again=dedup(run,stage,kind='stage')
    assert again['reclaimed_bytes']==0 and len(again['results'])==24


@pytest.mark.parametrize('failure',['stage_open','group_open','session_hash','index','native_path','verifier_open'])
def test_cohort_requires_closed_bound_indexes(tmp_path,failure):
    run,stage,scope,outputs=cohort(tmp_path)
    if failure=='stage_open': (stage/'result.json').unlink()
    elif failure=='group_open': (scope/'group-completion.json').unlink()
    elif failure=='session_hash':save(scope/'p01/completion.json',{'status':'failed'})
    elif failure=='index':
        path=scope/'p01/validation.json';row=json.loads(path.read_text());row['outputs'].pop();save(path,row)
    elif failure=='verifier_open':(scope/'p01/verification/1_normal_A/execution.json').unlink()
    else:
        journal=scope/'p01/native/journal.jsonl';records=[json.loads(s) for s in journal.read_text().splitlines()]
        records[0]['path']=str(run/'inputs.bin');journal.write_text(''.join(json.dumps(r)+'\n' for r in records))
        p=scope/'group-completion.json';row=json.loads(p.read_text());row['sessions'][0]['journal']=ptr(journal);save(p,row)
    with pytest.raises((ValueError,FileNotFoundError)):dedup(run,scope,kind='cohort')
    assert not (run/'storage').exists()


def test_existing_host_lock_blocks_even_dry_run(tmp_path,monkeypatch):
    run,_,scope,_=pilot(tmp_path)
    @contextmanager
    def occupied():raise RuntimeError('host is not exclusive');yield
    monkeypatch.setattr(storage,'exclusive_host',occupied)
    with pytest.raises(RuntimeError,match='not exclusive'):dedup(run,scope)
    assert not (run/'storage').exists()


def test_cross_filesystem_pool_refused_without_replacing_output(tmp_path,monkeypatch):
    run,_,scope,outputs=pilot(tmp_path)
    pool=run/'storage/output-cas';pool.mkdir(parents=True);transaction=run/'storage/transactions'/('b'*32);transaction.mkdir(parents=True)
    original_stat=Path.stat;inode=outputs[0].stat().st_ino
    def altered_stat(path,*args,**kwargs):
        value=original_stat(path,*args,**kwargs)
        if path==pool:
            fields=list(value);fields[2]+=1;return storage.os.stat_result(fields)
        return value
    monkeypatch.setattr(Path,'stat',altered_stat)
    with pytest.raises(ValueError,match='same filesystem'):
        storage.replace_one(dict(path=str(outputs[0]),sha256=sha(outputs[0])),pool,transaction,0,None)
    assert outputs[0].stat().st_ino==inode and not list(pool.iterdir())


def test_atomic_record_never_overwrites_existing_manifest(tmp_path):
    path=tmp_path/'record.json';storage.write_new(path,{'first':True})
    with pytest.raises(FileExistsError):storage.write_new(path,{'different':True})
    assert json.loads(path.read_text())=={'first':True}
    assert list(tmp_path.iterdir())==[path]


def test_output_hardlinked_to_input_cannot_seed_or_join_cas(tmp_path):
    run,task,scope,outputs=pilot(tmp_path)
    original_input=task/'inputs/input.bin';original_input.parent.mkdir()
    storage.os.link(outputs[0],original_input)
    inodes=[p.stat().st_ino for p in outputs]
    with pytest.raises(ValueError,match='alias outside verified closed outputs'):dedup(run,scope)
    assert [p.stat().st_ino for p in outputs]==inodes
    assert outputs[1].stat().st_ino!=original_input.stat().st_ino
    assert list((run/'storage/output-cas').iterdir())==[]


def test_existing_cas_hardlinked_to_input_refused(tmp_path):
    run,task,scope,outputs=pilot(tmp_path)
    original_input=binary(task/'inputs/input.bin',b'same output')
    pool=run/'storage/output-cas';pool.mkdir(parents=True)
    storage.os.link(original_input,pool/sha(original_input).removeprefix('sha256:'))
    inodes=[p.stat().st_ino for p in outputs]
    with pytest.raises(ValueError,match='CAS has an alias outside'):dedup(run,scope)
    assert [p.stat().st_ino for p in outputs]==inodes


def test_result_write_failure_marks_reclaimed_bytes_as_unknown_lower_bound(tmp_path,monkeypatch):
    run,_,scope,outputs=pilot(tmp_path)
    real_write=storage.write_new
    def fail_result(path,value):
        if path.name.endswith('.result.json'):raise OSError('injected result write failure')
        return real_write(path,value)
    monkeypatch.setattr(storage,'write_new',fail_result)
    with pytest.raises(OSError,match='injected'):dedup(run,scope)
    assert outputs[0].stat().st_ino==outputs[1].stat().st_ino
    value=json.loads(next((run/'storage/dedup').glob('*.json')).read_text())
    assert value['status']=='failed' and value['reclaimed_bytes']==value['reclaimed_bytes_lower_bound']==0
    assert value['reclaimed_bytes_known'] is False and value['accounting_status']=='lower_bound'
    monkeypatch.setattr(storage,'write_new',real_write)
    recovered=dedup(run,scope)
    assert recovered['status']=='passed' and recovered['reclaimed_bytes_known'] is False


def test_same_cas_reuses_previous_verified_scope_aliases(tmp_path):
    run,task,scope,outputs=pilot(tmp_path)
    dedup(run,scope)
    # A second operator has a different closed scope and exact same output bytes.
    other=task.parent/'gcd';other_scope=other/'preflight/pilot'
    import shutil
    shutil.copytree(scope,other_scope)
    save(other/'manifest.json',dict(version='msprof_task_time_exploration_v2',operator='gcd'))
    complete=json.loads((other_scope/'pilot.json').read_text());complete['operator']='gcd'
    for row in complete['cases']:
        case=other_scope/f"case_{row['case_id']:02d}"
        row['native']=ptr(case/'native.json');save(case/'pilot-case.json',row)
    save(other_scope/'pilot.json',complete)
    result=dedup(run,other_scope)
    assert result['reclaimed_bytes']==22 and result['reclaimed_bytes_known'] is True
    assert (other_scope/'case_01/output.bin').stat().st_ino==outputs[0].stat().st_ino
