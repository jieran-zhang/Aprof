"""Real tiny CPU process exits and independent immutable archive handoffs."""
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

import pytest

from aprof_runtime import local_archive as archive
from aprof_runtime import __version__
from aprof_runtime import task_budget
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.store import default_object_directory


def finished(tmp_path, code=2):
    scratch = tmp_path/'scratch'; scratch.mkdir()
    local = LocalEvidence(scratch/'records')
    scope_ref = local.register_json({'scope':'tiny CPU process only'})
    budget_ref = local.register_json(task_budget.prepare_budget_plan(task_id='tiny-task',scope_ref=scope_ref,budget_seconds=20))
    package_ref = archive.freeze_package_identity(local)
    job_ref = local.register_json(dict(package_identity_ref=package_ref, argv=[sys.executable,'-B','-c',f'print("cpu"); raise SystemExit({code})'],
        cwd=str(scratch), output_dir=str(scratch/'child'), environment={'PYTHONDONTWRITEBYTECODE':'1'}, timeout_seconds=20))
    result = task_budget.run_task(local,budget_ref=budget_ref,job_ref=job_ref,destination=scratch/'child')
    return local, result, local.verify_artifact(result['terminal_ref'])


def collect(tmp_path, local, result, completion):
    receipt = tmp_path/'archive'/'receipt.json'
    value = archive.archive(result['local_index'],completion,tmp_path/'archive'/'trace.sqlite',receipt,
        expected_release_version='1.3.2',expected_runtime_version=__version__)
    return receipt, value


def verify(receipt, result):
    return archive.verify_archive_receipt(receipt,local_index=result['local_index'],
        completion_ref=result['terminal_ref'],task_id='tiny-task')


@pytest.mark.parametrize('code,status', [(0,'passed'),(2,'failed')])
def test_real_process_terminal_and_complete_archive(tmp_path,code,status):
    local, result, completion = finished(tmp_path,code)
    before = file_hash(completion)
    receipt, value = collect(tmp_path,local,result,completion)
    checked = verify(receipt,result)
    assert checked == value
    assert value['terminal_status'] == result['status'] == status
    assert value['completion_ref'] == before == file_hash(completion)
    assert value['archive_complete'] is True and value['admission_authority'] is False
    assert value['task_cost_seconds'] > 0 and value['elapsed_seconds'] > 0
    assert value['package_identity']['release_version'] == '1.3.2'
    assert value['package_identity']['runtime_version'] == __version__
    index = json.loads(Path(result['local_index']).read_text())
    assert value['artifact_refs'] == sorted(index['artifacts'])
    # Delete only this fixture's scratch; package producers are indexed in place.
    shutil.rmtree(local.directory.parent)
    assert archive.verify_archive_receipt(receipt,local_index=None,
        completion_ref=result['terminal_ref'],task_id='tiny-task')['terminal_status'] == status


@pytest.mark.parametrize('mutation', ['complete','task','handler','index','status','cost','refs','bytes','db'])
def test_cleanup_rejects_invalid_handoff(tmp_path,mutation):
    local,result,completion = finished(tmp_path)
    receipt,value = collect(tmp_path,local,result,completion)
    if mutation == 'complete': value['archive_complete'] = False
    if mutation == 'task': value['task_id'] = 'another-task'
    if mutation == 'handler': value['package_identity']['runtime_version'] = '0.2.3'
    if mutation == 'index': value['local_index_sha256'] = 'sha256:'+'0'*64
    if mutation == 'status': value['terminal_status'] = 'passed'
    if mutation == 'cost': value['elapsed_seconds'] = -1
    if mutation == 'refs': value['artifact_refs'] = value['artifact_refs'][:-1]
    if mutation == 'bytes': value['artifact_bytes'] += 1
    if mutation == 'db': value['store_sha256'] = 'sha256:'+'0'*64
    receipt.write_text(json.dumps(value))
    with pytest.raises((ContractError,StoreError)): verify(receipt,result)


def test_missing_cas_object_blocks_cleanup(tmp_path):
    local,result,completion = finished(tmp_path)
    receipt,value = collect(tmp_path,local,result,completion)
    with archive.archive_reader(value['store']) as reader:
        reader.verify_artifact(result['execution_ref']).unlink()
    with pytest.raises(StoreError,match='missing|unreadable'): verify(receipt,result)


@pytest.mark.parametrize('mutation', ['pretend_pass','future','missing_execution'])
def test_terminal_requires_real_exit_and_complete_index(tmp_path,mutation):
    local,result,completion = finished(tmp_path)
    terminal = json.loads(completion.read_text())
    if mutation == 'pretend_pass': terminal['status'] = 'passed'
    if mutation == 'future': terminal['finished_at'] = time.time()+100
    if mutation == 'missing_execution': terminal['execution_ref'] = 'sha256:'+'0'*64
    reference = local.register_json(terminal)
    result['local_index'] = str(local.write_index(local.directory.parent/'mutated-index.json'))
    with pytest.raises((ContractError,StoreError)):
        archive.archive(result['local_index'],local.verify_artifact(reference),tmp_path/'archive.sqlite',tmp_path/'receipt.json')
    assert not (tmp_path/'archive.sqlite').exists()


def test_explicit_version_mismatch_and_scratch_destination_rejected(tmp_path):
    local,result,completion = finished(tmp_path)
    with pytest.raises(ContractError,match='version differs'):
        archive.archive(result['local_index'],completion,tmp_path/'store.sqlite',tmp_path/'receipt.json',expected_release_version='0.5.1')
    with pytest.raises(ContractError,match='outside task scratch'):
        archive.archive(result['local_index'],completion,local.directory.parent/'store.sqlite',tmp_path/'receipt.json')
    assert not (tmp_path/'store.sqlite').exists()


def test_package_entry_is_bound_to_its_version(tmp_path):
    local,result,completion = finished(tmp_path)
    command = [sys.executable,'-B',str(archive.PACKAGE/'tools/archive_local_evidence.py'),
        '--index',result['local_index'],'--completion',str(completion),'--store',str(tmp_path/'store.sqlite'),
        '--receipt',str(tmp_path/'receipt.json'),'--release-version','0.5.1','--runtime-version','0.2.2']
    executed = subprocess.run(command,cwd=tmp_path,capture_output=True,text=True)
    assert executed.returncode != 0 and 'version differs' in executed.stderr
    assert not (tmp_path/'store.sqlite').exists()


def test_legacy_completion_requires_its_historical_handler(tmp_path):
    scratch = tmp_path/'scratch';scratch.mkdir();local=LocalEvidence(scratch/'records')
    ref=local.register_json(dict(schema_version='1.0.0',kind='local_measurement_completion',run_id='legacy',
        protocol='shared_buffer_msprof_task_window_v5',status='failed',started_at=time.time()-2,
        finished_at=time.time()-1,elapsed_seconds=1))
    index=local.write_index(scratch/'index.json');receipt=tmp_path/'receipt.json'
    with pytest.raises(ContractError,match='historical archive handler'):
        archive.archive(index,local.verify_artifact(ref),tmp_path/'store.sqlite',receipt,task_id='legacy')
    assert not receipt.exists()


def test_unbound_or_changed_task_package_cannot_be_relabelled(tmp_path):
    local,result,completion = finished(tmp_path)
    terminal=json.loads(completion.read_text())
    launch=json.loads(local.verify_artifact(terminal['launch_ref']).read_text())
    job=json.loads(local.verify_artifact(launch['job_ref']).read_text())
    identity=json.loads(local.verify_artifact(job['package_identity_ref']).read_text())
    identity['runtime_version']='0.2.3'
    changed=local.register_json(identity)
    with pytest.raises(ContractError,match='metadata differs'):
        archive.verify_package_identity(local,changed)
    assert archive.verify_package_identity(local,job['package_identity_ref'])['release_version']=='1.3.2'
    assert 'runtime/src/aprof_runtime/gates.py' in identity['files']
    assert 'runtime/src/aprof_runtime/task_budget.py' in identity['files']
    assert 'runtime/src/aprof_runtime/stage_recovery.py' in identity['files']
    assert not any('/tests/' in name or '.runtime-env' in name for name in identity['files'])


def test_installed_runtime_finds_package_and_rejects_different_source(tmp_path):
    import os
    package = tmp_path/'installed-package'
    for name in archive.identity_files():
        target=package/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(archive.PACKAGE/name,target)
    installed=package/'.runtime-env/lib/python3.11/site-packages'
    shutil.copytree(package/'runtime/src/aprof_runtime',installed/'aprof_runtime')
    environment=dict(os.environ,PYTHONPATH=str(installed),PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-B','-c',
        'from aprof_runtime import local_archive as a; print(a.PACKAGE); print(a.package_identity()["runtime_version"])']
    result=subprocess.run(command,cwd=tmp_path,env=environment,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.splitlines()==[str(package),__version__]
    source=package/'runtime/src/aprof_runtime/local_archive.py'
    source.write_text(source.read_text()+'\n# source drift\n')
    rejected=subprocess.run(command,cwd=tmp_path,env=environment,capture_output=True,text=True)
    assert rejected.returncode!=0 and 'installed archive runtime differs' in rejected.stderr


def test_scaffolding_dispatch_requires_explicit_package_and_keeps_legacy_bytes(tmp_path):
    repository=archive.PACKAGE.parents[2]
    dispatcher=repository/'scaffolding/collection/scripts/archive_local_evidence.py'
    if not dispatcher.is_file():
        pytest.skip('开发仓库 scaffolding 兼容专项；独立技能包不携带该入口')
    result=subprocess.run([sys.executable,'-B',str(dispatcher)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode!=0 and '--skill-lib' in result.stderr and '--legacy-v051' in result.stderr
    old=dispatcher.with_name('archive_local_evidence_v051.py')
    assert 'skill-libs/graph-base/0.5.1' in old.read_text()
    assert 'task_terminal_v1' not in old.read_text()
    unsupported=tmp_path/'unsupported-package'
    unsupported.mkdir()
    missing=subprocess.run([sys.executable,'-B',str(dispatcher),'--skill-lib',str(unsupported)],
        cwd=tmp_path,capture_output=True,text=True)
    assert missing.returncode!=0 and 'no fallback' in missing.stderr


def test_archive_rejects_parent_index_omitting_merged_child_raw(tmp_path):
    from aprof_runtime.store import EpisodeStore
    scratch=tmp_path/'scratch';scratch.mkdir();local=LocalEvidence(scratch/'records')
    scope=local.register_json({'scope':'tiny failed child with complete handoff'})
    budget=local.register_json(task_budget.prepare_budget_plan(task_id='tiny-task',scope_ref=scope,budget_seconds=20))
    child_index=scratch/'child'/'evidence'/'index.json'
    code="""import hashlib,json,pathlib
p=pathlib.Path(%r);p.parent.mkdir();(p.parent/'records').mkdir()
raw=p.parent/'raw.bin';raw.write_bytes(b'00')
ref='sha256:'+hashlib.sha256(raw.read_bytes()).hexdigest()
p.write_text(json.dumps(dict(schema_version=1,kind='local_evidence_index',directory=str(p.parent/'records'),artifacts={ref:str(raw)})))
raise SystemExit(2)
""" % str(child_index)
    job=local.register_json(dict(package_identity_ref=archive.freeze_package_identity(local),
        argv=[sys.executable,'-B','-c',code],cwd=str(scratch),output_dir=str(scratch/'child'),
        environment={'PYTHONDONTWRITEBYTECODE':'1'},timeout_seconds=20,evidence_indices=[str(child_index)]))
    result=task_budget.run_task(local,budget_ref=budget,job_ref=job,destination=scratch/'child')
    assert result['status']=='failed'
    completion=local.verify_artifact(result['terminal_ref'])
    receipt,value=collect(tmp_path,local,result,completion)
    assert verify(receipt,result)['terminal_status']=='failed'
    raw_ref=next(iter(json.loads(child_index.read_text())['artifacts']))
    parent=json.loads(Path(result['local_index']).read_text());parent['artifacts'].pop(raw_ref)
    incomplete=scratch/'incomplete-index.json';incomplete.write_text(json.dumps(parent))
    with pytest.raises(ContractError,match='omitted merged child evidence'):
        archive.archive(incomplete,completion,tmp_path/'incomplete.sqlite',tmp_path/'incomplete-receipt.json')
    assert not (tmp_path/'incomplete.sqlite').exists()
    # Even a consistent forged receipt/DB-index pair must retain the child's whole roster.
    with EpisodeStore(value['store']) as store: ref=store.register_artifact(incomplete)
    value.update(local_index=str(incomplete),local_index_sha256=ref,store_sha256=file_hash(value['store']),
                 artifact_refs=sorted(parent['artifacts']),artifact_bytes=value['artifact_bytes']-2)
    forged=tmp_path/'forged-receipt.json';forged.write_text(json.dumps(value))
    with pytest.raises(ContractError,match='omitted merged child evidence'):
        archive.verify_archive_receipt(forged,local_index=None,completion_ref=result['terminal_ref'],task_id='tiny-task')
