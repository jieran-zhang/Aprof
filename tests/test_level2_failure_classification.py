"""Positive failure attribution from real producer-shaped records; no devices."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from level2_failure_classification import classify_failure


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')
    return path


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def ref(path):
    return {'path': str(path), 'sha256': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()}


def execution(argv, code=0, error=None):
    return {'argv': list(map(str, argv)), 'started_at': 1, 'ended_at': 2,
            'exit_status': code, 'status': 'passed' if code == 0 else 'failed', 'error': error}


def fixtures(tmp_path, kind='build', error=None):
    task = tmp_path / 'run/train/tasks/maximum'
    parent = task / 'candidates/maximum001'
    directory = parent / 'stages' / kind
    stage = {'candidate_id': parent.name, 'stage_id': parent.name+'-'+kind, 'kind': kind,
             'status': 'failed', 'native_started': kind == 'correctness',
             'error': error or {'type': 'RuntimeError', 'message': 'process failed (2): cmake'}}
    save(directory / 'result.json', stage)
    return task, parent, directory, stage


def compiler(tmp_path):
    task, parent, directory, stage = fixtures(tmp_path)
    build = parent / 'build'
    save(build / 'configure-execution/execution.json', execution(['cmake', '-S', build, '-B', build/'build']))
    save(build / 'build-execution/execution.json', execution(['cmake','--build',build/'build','-j2'],2,stage['error']['message']))
    source = write(parent/'op/op_kernel/maximum.h', 'void wrong() { missing_api(); }\n')
    write(build/'build-execution/stdout.log','')
    write(build/'build-execution/stderr.log',f"{source}:1:16: error: use of undeclared identifier 'missing_api'\n")
    return task, parent, stage


def health(root):
    for name in ('health-before.json','health-after.json'):
        save(root/name, {'status':'passed','error':None,'exit_code':0})


def oracle(tmp_path, prepared=False, adam=False):
    error = {'type':'RuntimeError','message':'command exited 1' if prepared else 'original oracle main exited 1'}
    task, parent, directory, stage = fixtures(tmp_path, 'correctness', error)
    root = directory / ('evidence' if prepared else 'standalone')
    verifier = write(task/'baseline/scripts/verify_result.py', 'unchanged original verifier\n')
    binary = write(parent/'build/build/standalone', 'binary\n')
    build = {'standalone':ref(binary),'roles':{'B':{'source_sha256':'source_hash','kernel_symbols':['maximum_kernel']}}}
    build_path = save(parent/'build/build_manifest.json',build)
    save(root/'completion.json',{'status':'failed','error':error,'health_error':None})
    health(root)
    if prepared:
        request = {'role':'B','verifier_hash':ref(verifier)['sha256'],'role_build_hash':ref(build_path)['sha256']}
    else:
        request = {'verifier':ref(verifier),'standalone':ref(binary)}
    save(root/'request.json',request)
    case = root/'case_01'
    output = write(case/'output.bin','numeric output bytes')
    metadata = {'case_id':1,'output':str(output)}
    metadata_path = save(case/'verification-metadata.json',metadata)
    verify = execution([sys.executable,verifier,'--metadata',metadata_path],1,error)
    verify.update(verifier=ref(verifier),metadata=ref(metadata_path),oracle_dependencies=[ref(verifier)])
    save(case/'verify.execution.json',verify)
    native = execution([binary,'--case','1'])
    save(case/('native.execution.json' if prepared else 'native/execution.json'),native)
    if prepared:
        save(case/'native.json',{'source_sha256':'source_hash','kernel_symbols':['maximum_kernel'],
            'mode':'correctness','exit_code':0,'stream_destroyed':True,'context_destroyed':True,'finalized':True})
    result = {'case_id':1,'precision_pass' if adam else 'passed':False, 'mere':0.1,'threshold':0.001}
    save(case/('precision.json' if adam else 'result.json'), result)
    write(case/'verify.stdout.log',json.dumps(result)+'\n')
    return task, parent, stage, root, case


def dispatch(tmp_path):
    task = tmp_path/'run/train/tasks/maximum'
    parent = task/'candidates/maximum001'
    root = parent/'boundary-validation'
    script = write(task/'agent/boundary_guard.py','guard source\n')
    binary = write(parent/'build/build/standalone','binary bytes\n')
    save(parent/'build/build_manifest.json',{'standalone':ref(binary)})
    plan = save(parent/'dispatch_plan.json',{'entries':[{'tiling_key':1,'kernel_entry':'expected'}],
        'fallback':{'tiling_key':0,'kernel_entry':'generic'}})
    request = save(root/'request.json',{'candidate':parent.name,'dispatch_logs_required':True,
        'script':ref(script),'binary':ref(binary),'dispatch_plan':ref(plan)})
    health(root)
    for name in ('prepare','verify'):
        save(root/name/'execution.json',execution([sys.executable,script]))
    command = {'name':'aligned','argv':['--shape','32'],'expected_key':1,'expected_entry':'expected'}
    save(root/'inputs/coordinator_commands.json',[command])
    native = save(root/'executions/aligned/execution.json',execution([binary,*command['argv']]))
    logs = [{'tiling_key':0,'kernel_entry':'generic'}]
    write(root/'executions/aligned/stdout.log','APROF_DISPATCH_JSON:'+json.dumps(logs[0])+'\n')
    guard = {'status':'failed','request':ref(request),'error':None,'verification_error':None,
        'cases':[{'name':'aligned','execution':ref(native),'error':None,'expected_process_passed':True,
                  'dispatch_log_passed':False,'dispatch_logs':logs}]}
    save(root/'completion.json',guard)
    return task,parent,root,guard


def test_semantic_compiler_proof_is_replayable_and_read_only(tmp_path):
    task,parent,stage = compiler(tmp_path)
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    value=classify_failure(task,parent,stage)
    assert value['status']=='source_attempt_failed' and value['rule']=='original_source_compiler_diagnostic'
    assert value==classify_failure(task,parent,stage)
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert value['evidence'] and all(ref(Path(r['path']))==r for r in value['evidence'])


@pytest.mark.parametrize('error_type',['TimeoutExpired','TimeoutError','KeyboardInterrupt','OSError',
    'FileNotFoundError','PermissionError','ConnectionError','FileExistsError','RuntimeError','ValueError'])
def test_unknown_or_infrastructure_error_never_counts_by_class_alone(tmp_path,error_type):
    task,parent,directory,stage=fixtures(tmp_path,error={'type':error_type,'message':'unclassified actual failure'})
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


@pytest.mark.parametrize('fault',['missing_sdk','missing_header','disk_full','configure_failed','tool_signal',
    'adapter_diagnostic','unknown_diagnostic','stale_stage','missing_log','wrong_argv','symlink'])
def test_build_positive_witness_does_not_override_infrastructure(tmp_path,fault):
    task,parent,stage=compiler(tmp_path);build=parent/'build';stderr=build/'build-execution/stderr.log'
    if fault=='missing_sdk':stderr.write_text(stderr.read_text()+'cannot execute asc: No such file or directory\n')
    elif fault=='missing_header':stderr.write_text(stderr.read_text()+"fatal error: 'kernel_operator.h' file not found\n")
    elif fault=='disk_full':stderr.write_text(stderr.read_text()+'No space left on device\n')
    elif fault=='configure_failed':save(build/'configure-execution/execution.json',execution(['cmake'],1,'missing ASC package'))
    elif fault=='tool_signal':save(build/'build-execution/execution.json',execution(['cmake'], -9,'killed'))
    elif fault=='adapter_diagnostic':stderr.write_text(stderr.read_text().replace(str(parent/'op'),str(build/'B')))
    elif fault=='unknown_diagnostic':stderr.write_text(stderr.read_text().replace('use of undeclared identifier','unexpected error'))
    elif fault=='stale_stage':stage['error']['message']='other error'
    elif fault=='missing_log':stderr.unlink()
    elif fault=='wrong_argv':save(build/'build-execution/execution.json',execution(['other'],2,stage['error']['message']))
    elif fault=='symlink':other=write(tmp_path/'other','logs');stderr.unlink();stderr.symlink_to(other)
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


@pytest.mark.parametrize('prepared,adam',[(False,False),(True,False),(False,True)])
def test_original_oracle_numeric_failure_needs_complete_real_witness(tmp_path,prepared,adam):
    task,parent,stage,root,case=oracle(tmp_path,prepared,adam)
    value=classify_failure(task,parent,stage)
    assert value['status']=='source_attempt_failed',value
    assert value['rule']=='original_oracle_numeric_mismatch'


@pytest.mark.parametrize('fault',['host_adapter_prestart','native_failed','health_failed','oracle_import',
    'oracle_timeout','oracle_io','unbound_verifier','changed_verifier','missing_result','passed_result',
    'missing_output','stdout_missing','wrong_case','metadata_relocated','native_not_finalized'])
def test_correctness_non_numeric_failure_remains_unfinished(tmp_path,fault):
    task,parent,stage,root,case=oracle(tmp_path,prepared=fault=='native_not_finalized')
    if fault=='host_adapter_prestart':
        stage.update(native_started=False,error={'type':'ValueError','message':'expected exactly one supported host; found []'})
        save(parent/'stages/correctness/result.json',stage)
    elif fault=='native_failed':save(case/'native/execution.json',execution(['native'],-11,'signal'))
    elif fault=='health_failed':save(root/'health-after.json',{'status':'failed','exit_code':1,'error':'device unhealthy'})
    elif fault in ('oracle_import','oracle_timeout','oracle_io'):
        error={'type':{'oracle_import':'ImportError','oracle_timeout':'TimeoutExpired','oracle_io':'RuntimeError'}[fault],
               'message':{'oracle_import':'torch not found','oracle_timeout':'expired','oracle_io':'unclassified callback failure'}[fault]}
        value=json.loads((case/'verify.execution.json').read_text());value['error']=error;save(case/'verify.execution.json',value)
    elif fault=='unbound_verifier':value=json.loads((root/'request.json').read_text());value['verifier']['sha256']='sha256:'+'0'*64;save(root/'request.json',value)
    elif fault=='changed_verifier':write(task/'baseline/scripts/verify_result.py','changed\n')
    elif fault=='missing_result':(case/'result.json').unlink()
    elif fault=='passed_result':save(case/'result.json',{'case_id':1,'passed':True})
    elif fault=='missing_output':(case/'output.bin').unlink()
    elif fault=='stdout_missing':write(case/'verify.stdout.log','')
    elif fault=='wrong_case':save(case/'result.json',{'case_id':2,'passed':False})
    elif fault=='metadata_relocated':value=json.loads((case/'verify.execution.json').read_text());value['argv'][-1]='/tmp/othermetadata.json';save(case/'verify.execution.json',value)
    elif fault=='native_not_finalized':value=json.loads((case/'native.json').read_text());value['finalized']=False;save(case/'native.json',value)
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


def test_bound_actual_dispatch_mismatch_counts_as_source_failure(tmp_path):
    task,parent,root,guard=dispatch(tmp_path)
    value=classify_failure(task,parent,guard=guard)
    assert value['status']=='source_attempt_failed',value
    assert value['rule']=='actual_dispatch_mismatch'


@pytest.mark.parametrize('fault',['verification_timeout','verification_oserror','verification_generic_error',
    'prepare_failed','native_failed','health_failed','plan_changed','stdout_changed','claimed_failure','missing_case'])
def test_guard_arbitrary_exception_or_claim_is_not_source_failure(tmp_path,fault):
    task,parent,root,guard=dispatch(tmp_path)
    if fault.startswith('verification_'):
        guard['verification_error']={'type':{'verification_timeout':'TimeoutExpired','verification_oserror':'OSError',
            'verification_generic_error':'RuntimeError'}[fault],'message':'failure'}
        save(root/'completion.json',guard)
    elif fault=='prepare_failed':save(root/'prepare/execution.json',execution(['prepare'],1,'failed'))
    elif fault=='native_failed':save(root/'executions/aligned/execution.json',execution(['native'],1,'failed'))
    elif fault=='health_failed':save(root/'health-after.json',{'status':'failed','error':'device','exit_code':1})
    elif fault=='plan_changed':save(parent/'dispatch_plan.json',{})
    elif fault=='stdout_changed':write(root/'executions/aligned/stdout.log','APROF_DISPATCH_JSON:{"tiling_key":1,"kernel_entry":"expected"}\n')
    elif fault=='claimed_failure':
        logs=[{'tiling_key':1,'kernel_entry':'expected'}];guard['cases'][0]['dispatch_logs']=logs
        write(root/'executions/aligned/stdout.log','APROF_DISPATCH_JSON:'+json.dumps(logs[0])+'\n');save(root/'completion.json',guard)
    elif fault=='missing_case':guard['cases']=[];save(root/'completion.json',guard)
    assert classify_failure(task,parent,guard=guard)['status']=='infrastructure_blocked'


@pytest.mark.parametrize('kind',['timing','runtime','profile'])
def test_measurement_and_runtime_failures_never_finish_source_round(tmp_path,kind):
    task,parent,directory,stage=fixtures(tmp_path,kind)
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


@pytest.mark.parametrize('bad_error',[None,[],{'message':'unknown'},'non-structured error'])
def test_malformed_error_is_blocked_not_a_classifier_exception(tmp_path,bad_error):
    task,parent,directory,stage=fixtures(tmp_path)
    stage['error']=bad_error;save(directory/'result.json',stage)
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


def test_actual_maximum_pre_native_adapter_failure_is_conservatively_unfinished(tmp_path):
    # Exact kind/message shape of the retained initial formal-run failure; source
    # invocation never occurred and no performance values are needed for this test.
    error={'type':'ValueError','message':'expected exactly one supported host in baseline, found []'}
    task,parent,directory,stage=fixtures(tmp_path,'correctness',error)
    stage['native_started']=False;save(directory/'result.json',stage)
    completion={'status':'failed','native_started':False,'error':error,'health_error':None,
                'actual_costs':{'native_processes_started':0,'standalone_complete_calls':0}}
    save(directory/'standalone/completion.json',completion)
    result=classify_failure(task,parent,stage)
    assert result['status']=='infrastructure_blocked' and 'before any confirmed native' in result['reason']


def test_multi_output_numeric_failure_binds_every_named_output(tmp_path):
    task,parent,stage,root,case=oracle(tmp_path)
    metadata_path=case/'verification-metadata.json'
    metadata={'case_id':1,'output_y':str(case/'output.bin'),
              'output_scale':str(write(case/'output_scale.bin','scale bytes'))}
    save(metadata_path,metadata)
    verify_path=case/'verify.execution.json';verify=json.loads(verify_path.read_text())
    verify['metadata']=ref(metadata_path);save(verify_path,verify)
    value=classify_failure(task,parent,stage)
    assert value['status']=='source_attempt_failed',value
    assert {str(case/'output.bin'),str(case/'output_scale.bin')} <= {r['path'] for r in value['evidence']}
    (case/'output_scale.bin').unlink()
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


def test_compiler_dotdot_escape_to_generated_adapter_never_counts_as_source(tmp_path):
    task,parent,stage=compiler(tmp_path)
    write(parent/'build/generated-adapter.cpp','void generated() { missing_api(); }\n')
    diagnostic=parent/'op/../build/generated-adapter.cpp'
    write(parent/'build/build-execution/stderr.log',
          f"{diagnostic}:1:16: error: use of undeclared identifier 'missing_api'\n")
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value
    assert 'noncanonical' in value['reason']
    assert str(diagnostic) not in {r['path'] for r in value['evidence']}


def test_oracle_dotdot_output_escape_does_not_prove_private_native_output(tmp_path):
    task,parent,stage,root,case=oracle(tmp_path)
    write(root/'other-output.bin','outside private case')
    metadata_path=case/'verification-metadata.json'
    save(metadata_path,{'case_id':1,'output':str(case/'../other-output.bin')})
    verify_path=case/'verify.execution.json';verify=json.loads(verify_path.read_text())
    verify['metadata']=ref(metadata_path);save(verify_path,verify)
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value
    assert 'noncanonical' in value['reason']


@pytest.mark.parametrize('field',['task','parent'])
def test_classifier_entry_requires_canonical_task_and_candidate(tmp_path,field):
    task,parent,stage=compiler(tmp_path)
    if field=='task':task=task/'../maximum'
    else:parent=parent/'../maximum001'
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked' and 'noncanonical' in value['reason']
    assert not value['evidence']
