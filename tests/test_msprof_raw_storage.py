"""CPU-only transport/replay fixtures; no profiler or accelerator is launched."""
from copy import deepcopy
import csv
import difflib
import json
from pathlib import Path
import shutil
import sys
import time

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import msprof_raw_storage as storage
import cannbench_msprof_timing as timing
import msprof_exploration_report as report
from test_msprof_exploration_report import setup_inputs,make_session,put


def request():return {'version':'msprof_kernel_time_study_v2','capture_storage':dict(storage.LOCAL),'capture_storage_producer':{'path':str(Path(storage.__file__).resolve()),'sha256':storage.sha(storage.__file__)}}


def captured(tmp_path):
    directory=tmp_path/'observation';directory.mkdir()
    raw,record=storage.allocate(request(),directory)
    (raw/'PROF_1/device_0/empty').mkdir(parents=True)
    (raw/'PROF_1/device_0/data.bin').write_bytes(bytes(range(256))*10)
    (raw/'PROF_1/host').mkdir();(raw/'PROF_1/host/metadata.json').write_text('{"original_path":"'+str(raw)+'"}')
    execution={'argv':['msprof','--output='+str(raw)],'started_at':time.time(),'ended_at':time.time(),'exit_code':0,'error':None}
    (directory/'native').mkdir();(directory/'native/journal.jsonl').write_text(json.dumps({'type':'session_end','exit_code':0,'context_destroyed':True,'stream_destroyed':True})+'\n')
    put(directory/'msprof.execution.json',execution)
    return directory,raw,record,execution


def test_complete_raw_tree_is_byte_preserved_and_original_argv_stays_real(tmp_path):
    directory,raw,record,execution=captured(tmp_path);before=storage.inventory(raw)
    storage.archive(record,directory)
    assert not raw.exists() and storage.inventory(directory/'raw')==before
    actual,files,identity=storage.verify(request(),directory,execution)
    assert actual==raw and identity['capture_storage']==storage.LOCAL
    assert directory/'raw/PROF_1/device_0/data.bin' in files
    assert (directory/'raw/PROF_1/device_0/empty').is_dir()
    assert str(raw) in (directory/'raw/PROF_1/host/metadata.json').read_text()
    assert execution['argv'][1]=='--output='+str(raw)


@pytest.mark.parametrize('fault',['alter','missing','extra','empty_directory_removed','symlink','manifest','argv','undeclared'])
def test_replay_rejects_incomplete_or_rewritten_closure(tmp_path,fault):
    directory,raw,record,execution=captured(tmp_path);storage.archive(record,directory);req=request()
    target=directory/'raw/PROF_1/device_0/data.bin'
    if fault=='alter':target.write_bytes(b'altered')
    elif fault=='missing':target.unlink()
    elif fault=='extra':(directory/'raw/unrecorded.txt').write_text('extra')
    elif fault=='empty_directory_removed':(directory/'raw/PROF_1/device_0/empty').rmdir()
    elif fault=='symlink':target.unlink();target.symlink_to('/etc/hostname')
    elif fault=='manifest':
        m=json.loads((directory/'raw-storage.json').read_text());m['source_inventory']['files']=[];put(directory/'raw-storage.json',m)
    elif fault=='argv':execution['argv'][1]='--output='+str(directory/'raw')
    else:req.pop('capture_storage')
    with pytest.raises(ValueError):storage.verify(req,directory,execution)


def test_copy_failure_retains_scratch_and_marks_partial_archive(tmp_path,monkeypatch):
    directory,raw,record,execution=captured(tmp_path)
    def fail(*a,**kw):raise OSError('synthetic copy failure')
    monkeypatch.setattr(storage.shutil,'copytree',fail)
    try:
        with pytest.raises(OSError):storage.archive(record,directory)
        assert raw.exists() and not (directory/'raw-storage.json').exists()
        assert json.loads((directory/'raw-storage.failed.json').read_text())['scratch_preserved']
    finally:shutil.rmtree(record['scratch_container'])


def test_v1_unchanged_and_unknown_or_network_scratch_rejected(tmp_path,monkeypatch):
    legacy={'version':'msprof_kernel_time_study_v1'}
    assert storage.allocate(legacy,tmp_path)==(tmp_path/'raw',None)
    assert storage.verify(legacy,tmp_path,{})==(tmp_path/'raw',[],{})
    with pytest.raises(ValueError):storage.policy(dict(legacy,capture_storage=storage.LOCAL))
    with pytest.raises(ValueError):storage.policy(dict(request(),capture_storage=dict(storage.LOCAL,scratch_root='/network')))
    original=Path.read_text
    def mounts(self,*a,**kw):
        return '1 0 0:1 / / rw - fuse.tidalfs none rw\n' if str(self)=='/proc/self/mountinfo' else original(self,*a,**kw)
    monkeypatch.setattr(Path,'read_text',mounts)
    with pytest.raises(ValueError,match='local filesystem'):storage.allocate(request(),tmp_path)


def v2_session(tmp_path):
    req,build=setup_inputs(tmp_path/'setup');req['version']=report.PRODUCER_V2
    for row in req['cases']:row['repeat']=10
    runner=report.load(req['runner_build']);root=Path(req['runner_build']).parent
    original=(root/'original-runner.cpp').read_text();generated=timing.instrument(original,10,per_case=True)
    (root/'runner.cpp').write_text(generated)
    (root/'harness.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),generated.splitlines(True),fromfile='original-runner.cpp',tofile='runner.cpp')))
    runner.update(version=report.PRODUCER_V2,per_case_repeat=True,source_hash=report.sha(root/'runner.cpp'));put(root/'build.json',runner)
    directory=make_session(tmp_path/'measurement',req,build)
    journal=directory/'native/journal.jsonl';records=[json.loads(line) for line in journal.read_text().splitlines()]
    for row in records:
        if row['type']!='session_end':row['timing_protocol']=report.PRODUCER_V2
    journal.write_text(''.join(json.dumps(row)+'\n' for row in records))
    csv_path=next((directory/'raw').rglob('op_summary*.csv'))
    with csv_path.open() as stream:rows=list(csv.DictReader(stream))
    tasks=[{'Device_id':r['Device_id'],'kernel_name':r['Op Name'],'stream_id':r['Stream ID'],'task_id':r['Task ID'],'kernel_type':r['Task Type'],
            'task_time(us)':r['Task Duration(us)'],'task_start(us)':r['Task Start Time(us)'],
            'task_stop(us)':str(__import__('decimal').Decimal(r['Task Start Time(us)'])+__import__('decimal').Decimal(r['Task Duration(us)']))} for r in rows]
    with (csv_path.parent/'task_time.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(tasks[0]));writer.writeheader();writer.writerows(tasks)
    completion=report.load(directory/'completion.json');completion['version']=report.PRODUCER_V2;put(directory/'completion.json',completion)
    put(directory/'samples.json',timing.parse_profile(directory/'raw',journal,build,report.load(directory/'cases.json'),10))
    return directory,req,build


def localize(directory,req):
    req=deepcopy(req);req.update({k:v for k,v in request().items() if k!='version'})
    original=directory/'raw';saved=directory/'raw-direct-fixture';original.rename(saved)
    raw,record=storage.allocate(req,directory)
    shutil.copytree(saved,raw,dirs_exist_ok=True);shutil.rmtree(saved)
    execution=report.load(directory/'msprof.execution.json')
    record['allocated_at']=execution['started_at']-1  # Synthetic capture timestamps are historical.
    put(directory/'raw-storage.request.json',record)
    execution['argv']=[('--output='+str(raw)) if a.startswith('--output=') else a for a in execution['argv']]
    put(directory/'msprof.execution.json',execution);storage.archive(record,directory)
    put(directory/'request.json',req)
    bindings=report.load(directory/'bindings.json')
    for path in list(bindings):
        if Path(path).parent.name=='requests':put(path,req);bindings[path]=report.sha(path)
    bindings[storage.__file__]=report.sha(storage.__file__);put(directory/'bindings.json',bindings)
    return req


def test_full_v2_report_replays_true_scratch_argv_and_closes_all_raw_bytes(tmp_path):
    directory,req,build=v2_session(tmp_path)
    direct=report.verify_observation(directory,req)
    req=localize(directory,req)
    observed=report.verify_observation(directory,req)
    assert observed['cells']==direct['cells'] and observed['source_hashes']==direct['source_hashes']
    assert observed['environment_binding']['capture_storage']==storage.LOCAL
    assert all(str(p) in observed['artifacts'] for p in (directory/'raw').rglob('*') if p.is_file())
    p=next((directory/'raw').rglob('task_time.csv'));p.write_bytes(p.read_bytes()+b'corrupted')
    with pytest.raises(ValueError,match='raw full'):report.verify_observation(directory,req)


def test_capture_storage_is_mandatory_scope_and_invalidates_network_calibration(tmp_path):
    directory,req,build=v2_session(tmp_path);direct=report.verify_observation(directory,req)
    req=localize(directory,req);local=report.verify_observation(directory,req)
    plan={'protocol':report.PROTOCOL_V2,'analysis_version':report.ANALYSIS_V2,'comparison_kind':'ab','case_ids':[1],
          'calibration_scope':{'epoch':'new'},'schedule':[]}
    for i,design in enumerate(report.DESIGN):
        q=dict(req,**dict(zip(['load_order','first_order','buffer_configs'],design)));plan['schedule'].append({'name':'p'+str(i),'request':q})
    with pytest.raises(ValueError,match='capture storage'):report.validate_plan(plan)
    plan['calibration_scope']['capture_storage']=dict(storage.LOCAL)
    plan['calibration_scope']['capture_storage_producer_hash']=request()['capture_storage_producer']['sha256'];report.validate_plan(plan)
    calibration={'protocol':report.PROTOCOL_V2,'analysis_version':report.ANALYSIS_V2,'comparison_kind':'aa','evidence_status':'verified_complete','formal_admission':'not_evaluated',
        'calibration_scope':{'epoch':'new'},'environment_binding':direct['environment_binding'],'operator':direct['operator'],'source_hashes':direct['source_hashes'],
        'calibration_cards':{'1':{'case_binding':direct['case_bindings']['1']}}}
    assert report._calibration_match(calibration,plan,local,'1')[0]=='invalidated'
    calibration['calibration_scope']=deepcopy(plan['calibration_scope'])
    assert report._calibration_match(calibration,plan,local,'1')[0]=='invalidated'  # Claim alone cannot relabel network observations.


def test_local_transport_cannot_change_implementation_after_plan_freeze():
    req=request();req.pop('capture_storage_producer')
    with pytest.raises(ValueError,match='producer'):storage.policy(req)
    req=request();req['capture_storage_producer']['sha256']='sha256:'+'0'*64
    with pytest.raises(ValueError,match='producer'):storage.policy(req)


def test_verified_copyback_is_durable_before_scratch_deletion(tmp_path,monkeypatch):
    directory,raw,record,execution=captured(tmp_path);original=shutil.rmtree
    def blocked(path):
        proof=json.loads((directory/'raw-storage.copyback.json').read_text())
        assert proof['archive_inventory']==storage.inventory(directory/'raw')
        assert proof['durability']['file_count']==2 and (directory/'raw-storage.json').is_file()
        raise PermissionError('synthetic cleanup denial')
    monkeypatch.setattr(storage.shutil,'rmtree',blocked)
    try:
        storage.archive(record,directory)
        manifest=json.loads((directory/'raw-storage.json').read_text())
        assert manifest['scratch_cleanup']['outcome']=='consult_optional_receipt' and raw.exists()
        assert json.loads((directory/'raw-storage.cleanup.json').read_text())['cleanup']['status']=='retained'
        storage.verify(request(),directory,execution)
    finally:original(record['scratch_container'])


@pytest.mark.parametrize('failure',['raw_file','raw_directory','copyback_parent','manifest_parent'])
def test_persistence_failure_always_precedes_cleanup_and_retains_source(tmp_path,monkeypatch,failure):
    directory,raw,record,execution=captured(tmp_path);real_fsync=storage.os.fsync;injected=[];removed=[]
    def fsync(fd):
        path=Path('/proc/self/fd/'+str(fd)).resolve()
        selected=(failure=='raw_file' and path.is_relative_to(directory/'raw') and path.is_file()) or \
                 (failure=='raw_directory' and path==directory/'raw') or \
                 (failure=='copyback_parent' and path==directory and (directory/'raw-storage.copyback.json').exists() and not (directory/'raw-storage.json').exists()) or \
                 (failure=='manifest_parent' and path==directory and (directory/'raw-storage.json').exists())
        if selected and not injected:injected.append(str(path));raise OSError('synthetic persistence failure')
        return real_fsync(fd)
    original=shutil.rmtree
    monkeypatch.setattr(storage.os,'fsync',fsync)
    monkeypatch.setattr(storage.shutil,'rmtree',lambda p:removed.append(str(p)))
    try:
        with pytest.raises(OSError,match='persistence'):storage.archive(record,directory)
        assert injected and raw.exists() and not removed
        assert json.loads((directory/'raw-storage.failed.json').read_text())['scratch_preserved']
    finally:original(record['scratch_container'])


@pytest.mark.parametrize('fault',['argv','container','teardown','unfinished'])
def test_archive_rejects_wrong_destructive_operands_before_any_copy_or_cleanup(tmp_path,fault):
    directory,raw,record,execution=captured(tmp_path)
    victim=Path(__import__('tempfile').mkdtemp(prefix='aprof-msprof-review-victim-',dir='/tmp'))
    (victim/'keep.txt').write_text('unrelated bytes')
    changed=dict(record)
    if fault=='argv':execution['argv'][1]='--output=/tmp/another-profiler/raw';put(directory/'msprof.execution.json',execution)
    elif fault=='container':changed['scratch_container']=str(victim)
    elif fault=='teardown':(directory/'native/journal.jsonl').write_text('')
    else:execution['ended_at']=None;put(directory/'msprof.execution.json',execution)
    try:
        with pytest.raises(ValueError):storage.archive(changed,directory)
        assert raw.exists() and (victim/'keep.txt').read_text()=='unrelated bytes'
        assert not (directory/'raw').exists() and not (directory/'raw-storage.json').exists()
    finally:shutil.rmtree(record['scratch_container']);shutil.rmtree(victim)


def test_optional_cleanup_receipt_failure_does_not_invalidate_durable_transfer(tmp_path,monkeypatch):
    directory,raw,record,execution=captured(tmp_path);real_save=storage.save
    def save(path,value):
        if Path(path).name=='raw-storage.cleanup.json':raise OSError('receipt persistence unavailable')
        return real_save(path,value)
    monkeypatch.setattr(storage,'save',save)
    storage.archive(record,directory)
    assert not raw.exists() and not (directory/'raw-storage.cleanup.json').exists()
    assert json.loads((directory/'raw-storage.json').read_text())['scratch_cleanup']['outcome']=='consult_optional_receipt'
    storage.verify(request(),directory,execution)


def test_failed_native_capture_archives_partial_bytes_but_retains_source(tmp_path):
    directory,raw,record,execution=captured(tmp_path)
    execution['exit_code']=1;put(directory/'msprof.execution.json',execution)
    (directory/'native/journal.jsonl').write_text('')
    try:
        before=storage.inventory(raw);storage.archive(record,directory)
        assert raw.exists() and storage.inventory(directory/'raw')==before
        proof=json.loads((directory/'raw-storage.copyback.json').read_text())
        receipt=json.loads((directory/'raw-storage.cleanup.json').read_text())
        assert proof['native_teardown_complete'] is False
        assert receipt['cleanup']=={'status':'retained','error':None,'reason':'native_teardown_incomplete'}
    finally:shutil.rmtree(record['scratch_container'])
