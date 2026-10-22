"""Positive failure attribution from real producer-shaped records; no devices."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
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


def kernel_type_compiler(tmp_path, definition=None):
    """Producer-shaped frozen source/role/CMake proof; never invoke a compiler."""
    import tarfile
    import shared_context_build
    task,parent,directory,stage=fixtures(tmp_path)
    build=parent/'build';sdk='/opt/Ascend/cann-9.0.0';compiler=sdk+'/bin/bisheng'
    source=parent/'op'
    write(source/'op_host/maximum.asc', '#include "../op_kernel/maximum_kernel.asc"\nint main(int argc, char **argv) { maximum_same_int64<<<1,nullptr,stream>>>(p); aclrtMemcpy(host, 8, p, 8, ACL_MEMCPY_DEVICE_TO_HOST); WriteFile("output",host,8); return 0; }\n')
    write(source/'op_kernel/maximum_kernel.asc', definition if definition is not None else
          'extern "C" __global__ __aicore__ void maximum_same_int64(void *p) { scalar_compare(p); }\n')
    with tarfile.open(parent/'source.tar','w') as archive:
        archive.add(source,arcname='source')
    save(directory/'stage-plan.json',{'source_hash':ref(parent/'source.tar')['sha256']})
    h=hashlib.sha256()
    for path in sorted(p for p in source.rglob('*') if p.is_file()):
        h.update(str(path.relative_to(source)).encode()+b'\0'+path.read_bytes()+b'\0')
    digest=h.hexdigest()
    for kind,argv,code,error in [('configure',['cmake','-S',build,'-B',build/'build'],0,None),
             ('build',['cmake','--build',build/'build','-j2'],2,stage['error']['message'])]:
        row=execution(argv,code,error);row['environment_overrides']={};row['cwd']=str(shared_context_build.HARNESS.parents[3])
        row['shell_argv']=['taskset','-c','40-43','bash','-c',
            f'source {sdk}/set_env.sh || exit $?; export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${{LD_LIBRARY_PATH:-}}; exec "$@"','feedback-hardware',*row['argv']]
        save(build/(kind+'-execution/execution.json'),row)
    write(build/'configure-execution/stdout.log',f'-- CMAKE_ASC_COMPILER: {compiler}\n'
          f'-- CMAKE_ASC_LLD_LINKER: {sdk}/aarch64-linux/ccec_compiler/bin/ld.lld\n')
    write(build/'configure-execution/stderr.log','')
    write(build/'build/CMakeFiles/3.22.1/CMakeASCCompiler.cmake',
          f'set(CMAKE_ASC_COMPILER "{compiler}")\nset(CMAKE_ASC_COMPILER_LOADED 1)\n')
    manifest={'version':'shared_context_build_v1','operator':'maximum','roles':{},'harness':{p.name:ref(p)['sha256'][7:] for p in shared_context_build.HARNESS.iterdir() if p.is_file()}}
    diagnostics=[];warnings=[]
    for role in ('A','B'):
        symbol=f'sc_{role}_{digest[:12]}_maximum_same_int64'
        generated,identity,_=shared_context_build.generate_adapter(source,'maximum',role,digest)
        host=write(build/role/'op_host/maximum.asc',generated)
        write(build/role/'op_kernel/maximum_kernel.asc',(source/'op_kernel/maximum_kernel.asc').read_text())
        manifest['roles'][role]={**identity,'role':role,'source_dir':str(source),'source_sha256':digest,
            'kernel_symbols':symbol,'adapter_sha256':ref(host)['sha256'][7:],'npu_arch':'dav-2201'}
        write(build/'build/CMakeFiles'/f'role_{role}.dir/flags.make',
              f'# compile ASC with {compiler}\nASC_DEFINES = -Drole_{role}_EXPORTS\nASC_INCLUDES = -I{build/role/"op_host"} -I{build/role/"op_kernel"} -I{shared_context_build.HARNESS}\nASC_FLAGS = --npu-arch=dav-2201\n')
        obj=f'CMakeFiles/role_{role}.dir/{role}/op_host/maximum.asc.o'
        for dependency in ('depend.make','compiler_depend.make','compiler_depend.ts'):
            write(build/'build/CMakeFiles'/f'role_{role}.dir'/dependency,'# Empty CMake dependency file\n')
        write(build/'build/CMakeFiles'/f'role_{role}.dir/progress.make',f'CMAKE_PROGRESS_1 = {1 if role == "A" else 3}\nCMAKE_PROGRESS_2 = {2 if role == "A" else 4}\n')
        includes=''.join(f'include CMakeFiles/role_{role}.dir/{name}\n' for name in ('depend.make','compiler_depend.make','progress.make','flags.make'))
        from level2_failure_classification import reviewed_role_makefile
        write(build/'build/CMakeFiles'/f'role_{role}.dir/build.make',
              reviewed_role_makefile(build,role,'maximum',compiler)+'\n')
        diagnostics.append(f'ld.lld: error: Error: the type of kernel function {symbol} auto derivate failed, please manually add the function type attribute')
        warnings.append(f'WARNING: kernel type of __global__ func: {symbol} is not marked. auto type derivate may be failed.')
    save(build/'build_manifest.json',manifest)
    write(build/'build-execution/stdout.log','\n'.join(warnings)+'\n')
    write(build/'build-execution/stderr.log','\n'.join(diagnostics+[
        'bishengbisheng: : error: error: ld.lld command failed with exit code 1 (use -v to see invocation)',
        'ld.lld command failed with exit code 1 (use -v to see invocation)',
        'gmake[1]: *** Waiting for unfinished jobs....',
        'gmake: *** [Makefile:91: all] Error 2'])+'\n')
    return task,parent,stage


def test_kernel_type_inference_requires_two_original_source_roles(tmp_path):
    task,parent,stage=kernel_type_compiler(tmp_path)
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    value=classify_failure(task,parent,stage)
    assert value['status']=='source_attempt_failed',value
    assert value['rule']=='original_source_kernel_type_inference'
    assert value==classify_failure(task,parent,stage)
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    paths={r['path'] for r in value['evidence']}
    assert all(ref(Path(r['path']))==r for r in value['evidence'])
    required=['source.tar','stages/build/stage-plan.json','op/op_kernel/maximum_kernel.asc',
        'build/build_manifest.json','build/configure-execution/stdout.log',
        'build/build/CMakeFiles/3.22.1/CMakeASCCompiler.cmake',
        *[f'build/{role}/op_host/maximum.asc' for role in ('A','B')],
        *[f'build/{role}/op_kernel/maximum_kernel.asc' for role in ('A','B')],
        *[f'build/build/CMakeFiles/role_{role}.dir/build.make' for role in ('A','B')]]
    assert {str(parent/p) for p in required} <= paths


@pytest.mark.parametrize('definition',[
    '// extern "C" __global__ __aicore__ void maximum_same_int64(void *p) {}\n',
    '/* extern "C" __global__ __aicore__ void maximum_same_int64(void *p) {} */\n',
    'const char *text="__global__ __aicore__ void maximum_same_int64(void *p) {}";\n',
    'extern "C" __global__ __aicore__ void generated_only(void *p) {}\n',
    'extern "C" __global__ __aicore__ void maximum_same_int64(void *p);\n',
    '#if 0\nextern "C" __global__ __aicore__ void maximum_same_int64(void *p) {}\n#endif\n',
    'extern "C" __global__ __aicore__ void maximum_same_int64(void *p) {}\n' * 2,
])
def test_kernel_type_generated_comment_string_conditional_or_ambiguous_definition_is_blocked(tmp_path,definition):
    task,parent,stage=kernel_type_compiler(tmp_path,definition)
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


@pytest.mark.parametrize('fault',[
    'sdk_missing','tool_crash','environment_error','unresolved_linker','unknown_linker',
    'extra_stdout_error','configure_failed','build_signal','single_role','role_mismatch',
    'wrong_prefix','changed_source','changed_archive','corrupt_archive','unsafe_archive',
    'generated_changed_kernel','generated_wrong_rename','generated_hash','generated_definition','generated_include','wrong_manifest_source',
    'wrong_manifest_hash','wrong_manifest_symbol','missing_compiler','wrong_compiler_record',
    'wrong_compiler_recipe','wrong_compiler_flags','wrong_linker_sdk','configure_stderr',
    'environment_override','sdk_shell_mismatch','shell_extra_export','missing_recipe','recipe_symlink',
])
def test_kernel_type_positive_witness_never_overrides_unknown_or_infrastructure_failure(tmp_path,fault):
    import tarfile
    task,parent,stage=kernel_type_compiler(tmp_path);build=parent/'build'
    stderr=build/'build-execution/stderr.log';manifest_path=build/'build_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if fault in ('sdk_missing','tool_crash','environment_error','unresolved_linker','unknown_linker'):
        extra={'sdk_missing':'cannot execute bisheng: No such file or directory',
            'tool_crash':'bisheng: internal compiler error: crash',
            'environment_error':'ld.lld: error: failed to load environment',
            'unresolved_linker':'ld.lld: error: undefined symbol: aclrtCreateStream',
            'unknown_linker':'ld.lld: error: unexpected unsupported link failure'}[fault]
        stderr.write_text(stderr.read_text()+extra+'\n')
    elif fault=='extra_stdout_error':write(build/'build-execution/stdout.log','error: unrecognized option\n')
    elif fault=='configure_failed':
        p=build/'configure-execution/execution.json';v=json.loads(p.read_text());v['exit_status']=1;save(p,v)
    elif fault=='build_signal':
        p=build/'build-execution/execution.json';v=json.loads(p.read_text());v['exit_status']=-9;save(p,v)
    elif fault=='single_role':stderr.write_text('\n'.join(x for x in stderr.read_text().splitlines() if 'sc_B_' not in x)+'\n')
    elif fault=='role_mismatch':stderr.write_text(stderr.read_text().replace('sc_B_','sc_A_'))
    elif fault=='wrong_prefix':stderr.write_text(stderr.read_text().replace(manifest['roles']['A']['source_sha256'][:12],'a'*12))
    elif fault=='changed_source':write(parent/'op/op_kernel/maximum_kernel.asc','changed source\n')
    elif fault=='changed_archive':write(parent/'source.tar','changed archive\n')
    elif fault=='corrupt_archive':
        write(parent/'source.tar','invalid tar bytes');save(parent/'stages/build/stage-plan.json',{'source_hash':ref(parent/'source.tar')['sha256']})
    elif fault=='unsafe_archive':
        with tarfile.open(parent/'source.tar','a') as archive:
            member=tarfile.TarInfo('../outside');member.type=tarfile.SYMTYPE;member.linkname='/tmp/outside';archive.addfile(member)
        save(parent/'stages/build/stage-plan.json',{'source_hash':ref(parent/'source.tar')['sha256']})
    elif fault=='generated_changed_kernel':write(build/'A/op_kernel/maximum_kernel.asc','generated different kernel\n')
    elif fault=='generated_wrong_rename':
        p=build/'A/op_host/maximum.asc';p.write_text(p.read_text().replace('#define maximum_same_int64','#define generated_entry'))
        manifest['roles']['A']['adapter_sha256']=ref(p)['sha256'][7:];save(manifest_path,manifest)
    elif fault in ('generated_definition','generated_include'):
        p=build/'A/op_host/maximum.asc'
        if fault=='generated_definition':p.write_text(p.read_text()+'__global__ __aicore__ void maximum_same_int64(void *p) {}\n')
        else:p.write_text(p.read_text().replace('../op_kernel/maximum_kernel.asc','generated_kernel.asc'))
        manifest['roles']['A']['adapter_sha256']=ref(p)['sha256'][7:];save(manifest_path,manifest)
    elif fault=='generated_hash':manifest['roles']['A']['adapter_sha256']='0'*64;save(manifest_path,manifest)
    elif fault=='wrong_manifest_source':manifest['roles']['A']['source_dir']=str(build/'A');save(manifest_path,manifest)
    elif fault=='wrong_manifest_hash':manifest['roles']['A']['source_sha256']='0'*64;save(manifest_path,manifest)
    elif fault=='wrong_manifest_symbol':manifest['roles']['A']['kernel_symbols']='generated_only';save(manifest_path,manifest)
    elif fault=='missing_compiler':write(build/'configure-execution/stdout.log','-- Compiler identity unavailable\n')
    elif fault=='wrong_compiler_record':write(build/'build/CMakeFiles/3.22.1/CMakeASCCompiler.cmake','set(CMAKE_ASC_COMPILER "/other/bisheng")\nset(CMAKE_ASC_COMPILER_LOADED 1)\n')
    elif fault=='wrong_compiler_recipe':write(build/'build/CMakeFiles/role_A.dir/build.make','\t/other/bisheng -c --asc-aicore-lang other.asc\n')
    elif fault=='wrong_compiler_flags':write(build/'build/CMakeFiles/role_A.dir/flags.make','# compile ASC with /opt/Ascend/cann-9.0.0/bin/bisheng\nASC_FLAGS = --npu-arch=unsupported\n')
    elif fault=='wrong_linker_sdk':
        p=build/'configure-execution/stdout.log';p.write_text(p.read_text().replace('/opt/Ascend/cann-9.0.0/aarch64-linux','/other/sdk/aarch64-linux'))
    elif fault=='configure_stderr':write(build/'configure-execution/stderr.log','warning: unknown compiler environment\n')
    elif fault in ('environment_override','sdk_shell_mismatch','shell_extra_export'):
        p=build/'build-execution/execution.json';v=json.loads(p.read_text())
        if fault=='environment_override':v['environment_overrides']={'ASC':'/wrong/compiler'}
        elif fault=='shell_extra_export':v['shell_argv'][5]=v['shell_argv'][5].replace('exec', 'export ASC=/other/bisheng; exec')
        else:v['shell_argv'][5]='source /other/sdk/set_env.sh || exit $?; exec "$@"'
        save(p,v)
    elif fault=='missing_recipe':(build/'build/CMakeFiles/role_A.dir/build.make').unlink()
    elif fault=='recipe_symlink':
        p=build/'build/CMakeFiles/role_A.dir/build.make';other=write(tmp_path/'recipe',p.read_text());p.unlink();p.symlink_to(other)
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


@pytest.mark.parametrize('mutation',[
    'disabled_original_replaced_by_generated_include','unreviewed_forced_include_recipe',
    'unreviewed_forced_include_only','overridden_defines','unreviewed_include_search',
    'recipe_redefines_flags','extra_role_header','changed_harness_identity',
])
def test_generated_compile_authority_cannot_be_misattributed_to_original(tmp_path,mutation):
    task,parent,stage=kernel_type_compiler(tmp_path);build=parent/'build'
    manifest_path=build/'build_manifest.json';manifest=json.loads(manifest_path.read_text())
    for role in ('A','B'):
        host=build/role/'op_host/maximum.asc';symbol=manifest['roles'][role]['kernel_symbols']
        generated=build/role/'op_kernel/generated_kernel.asc'
        if mutation in ('disabled_original_replaced_by_generated_include','unreviewed_forced_include_recipe'):
            generated.write_text(f'extern "C" __global__ __aicore__ void {symbol}(void *p) {{ generated_scalar_failure(p); }}\n')
        if mutation=='disabled_original_replaced_by_generated_include':
            host.write_text(host.read_text().replace('#include "../op_kernel/maximum_kernel.asc"',
                '#if 0\n#include "../op_kernel/maximum_kernel.asc"\n#endif\n#include "../op_kernel/generated_kernel.asc"'))
            manifest['roles'][role]['adapter_sha256']=ref(host)['sha256'][7:]
        elif mutation in ('unreviewed_forced_include_recipe','unreviewed_forced_include_only'):
            recipe=build/'build/CMakeFiles'/f'role_{role}.dir/build.make'
            recipe.write_text(recipe.read_text().replace(' $(ASC_DEFINES)',f' -include {generated} $(ASC_DEFINES)'))
        elif mutation in ('overridden_defines','unreviewed_include_search'):
            flags=build/'build/CMakeFiles'/f'role_{role}.dir/flags.make'
            if mutation=='overridden_defines':flags.write_text(flags.read_text().replace('ASC_DEFINES = ','ASC_DEFINES = -Dmaximum_same_int64=generated '))
            else:flags.write_text(flags.read_text().replace('ASC_INCLUDES = ','ASC_INCLUDES = -I/unknown/include '))
        elif mutation=='recipe_redefines_flags':
            recipe=build/'build/CMakeFiles'/f'role_{role}.dir/build.make'
            recipe.write_text('ASC_DEFINES := -include generated.asc\n'+recipe.read_text())
        elif mutation=='extra_role_header':write(build/role/'op_host/kernel_operator.h','generated override\n')
        elif mutation=='changed_harness_identity':manifest['harness']['level2_adapter_common.h']='0'*64
    save(manifest_path,manifest)
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


@pytest.mark.parametrize('mutation',['extra_shell_before','extra_linker_after','extra_dependency',
                                    'inline_shell','duplicate_target_recipe','make_shell_expansion'])
def test_complete_object_target_cannot_hide_an_additional_failure_producer(tmp_path,mutation):
    task,parent,stage=kernel_type_compiler(tmp_path);build=parent/'build'
    for role in ('A','B'):
        recipe=build/'build/CMakeFiles'/f'role_{role}.dir/build.make';text=recipe.read_text()
        obj=f'CMakeFiles/role_{role}.dir/{role}/op_host/maximum.asc.o'
        if mutation=='extra_shell_before':text=text.replace('\t@$(CMAKE_COMMAND)', '\tsh -c "generate_failure"\n\t@$(CMAKE_COMMAND)')
        elif mutation=='extra_linker_after':text+='\t/opt/Ascend/cann-9.0.0/bin/ld.lld generated.o\n'
        elif mutation=='extra_dependency':text=obj+': generated_failure\n'+text
        elif mutation=='inline_shell':text=text.replace(obj+': ../',obj+': ; sh -c generate_failure\n'+obj+': ../')
        elif mutation=='duplicate_target_recipe':text+=obj+': other\n\tsh -c generate_failure\n'
        else:text='EXTRA = $(shell generate_failure)\n'+text
        recipe.write_text(text)
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


@pytest.mark.parametrize('operator',['../generated','exp','rms_norm','maximum/extra'])
def test_kernel_type_operator_must_match_reviewed_level2_task(tmp_path,operator):
    task,parent,stage=kernel_type_compiler(tmp_path)
    path=parent/'build/build_manifest.json';value=json.loads(path.read_text());value['operator']=operator;save(path,value)
    result=classify_failure(task,parent,stage)
    assert result['status']=='infrastructure_blocked' and 'reviewed Level2 task' in result['reason'],result


@pytest.mark.parametrize('name',['depend.make','compiler_depend.make','compiler_depend.ts','progress.make'])
def test_make_dependency_cannot_supply_hidden_commands(tmp_path,name):
    task,parent,stage=kernel_type_compiler(tmp_path)
    path=parent/'build/build/CMakeFiles/role_A.dir'/name
    path.write_text(path.read_text()+'EXTRA := $(shell generate_failure)\n')
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'


@pytest.mark.parametrize('statement',[
    'override CMAKE_COMMAND = /tmp/generated-linker-wrapper',
    'override SHELL = /tmp/generated-shell-wrapper',
    'export CMAKE_COMMAND = /tmp/generated-wrapper',
    'private SHELL = /tmp/generated-wrapper',
    'COLOR = true; /tmp/generated-wrapper',
    'define CMAKE_COMMAND\n/tmp/generated-wrapper\nendef',
    '$(eval SHELL := /tmp/generated-wrapper)',
    '.ONESHELL:',
    '.SHELLFLAGS = -c /tmp/generated-wrapper',
    'include /tmp/generated-makefile',
    'role_A: SHELL = /tmp/generated-wrapper',
    'MAKEFLAGS = --eval=generated',
    'export MAKEFILES := /tmp/generated-makefile',
    'undefine CMAKE_COMMAND',
])
def test_complete_make_authority_rejects_all_unreviewed_effective_statements(tmp_path,statement):
    task,parent,stage=kernel_type_compiler(tmp_path)
    for role in ('A','B'):
        p=parent/'build/build/CMakeFiles'/f'role_{role}.dir/build.make'
        p.write_text(p.read_text()+statement+'\n')
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


def test_make_continued_comment_cannot_hide_reviewed_shell_assignment(tmp_path):
    task,parent,stage=kernel_type_compiler(tmp_path)
    p=parent/'build/build/CMakeFiles/role_A.dir/build.make'
    p.write_text(p.read_text().replace('SHELL = /bin/sh','# swallowed next line \\\nSHELL = /bin/sh'))
    value=classify_failure(task,parent,stage)
    assert value['status']=='infrastructure_blocked',value


@pytest.mark.parametrize('name',['MAKEFLAGS','MFLAGS','MAKEFILES','GNUMAKEFLAGS'])
def test_recorded_make_environment_override_is_never_admitted(tmp_path,name):
    task,parent,stage=kernel_type_compiler(tmp_path)
    p=parent/'build/build-execution/execution.json';value=json.loads(p.read_text())
    value['environment_overrides']={name:'injected'};save(p,value)
    assert classify_failure(task,parent,stage)['status']=='infrastructure_blocked'
