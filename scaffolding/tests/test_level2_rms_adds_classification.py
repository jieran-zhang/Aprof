"""Frozen original-source / generated-role RMS Adds proof. No compiler or device."""
import copy, hashlib, json, tarfile
from pathlib import Path
import pytest
import shared_context_build
from level2_failure_classification import classify_failure, reviewed_role_makefile
from test_level2_failure_classification import execution, ref, save, write

FIXTURE = Path(__file__).parent/'fixtures/rms_adds_semantic_failure_v6.json'

def rms_compiler(tmp_path):
    witness=json.loads(FIXTURE.read_text())
    task=tmp_path/'run/train/tasks/rms_norm';parent=task/'candidates/rms_norm001';build=parent/'build'
    stage={'candidate_id':parent.name,'stage_id':parent.name+'-build','kind':'build','status':'failed',
           'native_started':False,'error':{'type':'RuntimeError','message':'process failed (2): cmake'}}
    save(parent/'stages/build/result.json',stage)
    source=parent/'op'
    for name,data in witness['native'].items():write(source/name,data)
    write(source/'CMakeLists.txt',witness['cmake'])
    with tarfile.open(parent/'source.tar','w') as archive:archive.add(source,arcname='source')
    save(parent/'stages/build/stage-plan.json',{'source_hash':ref(parent/'source.tar')['sha256']})
    digest=hashlib.sha256()
    for name,data in sorted(witness['native'].items()):digest.update(name.encode()+b'\0'+data.encode()+b'\0')
    digest=digest.hexdigest();sdk='/opt/Ascend/cann-9.0.0';compiler=sdk+'/bin/bisheng'
    for kind,args,code,error in [('configure',['cmake','-S',build,'-B',build/'build'],0,None),
        ('build',['cmake','--build',build/'build','-j2'],2,stage['error']['message'])]:
        row=execution(args,code,error);row.update(environment_overrides={},cwd=str(shared_context_build.HARNESS.parents[3]))
        setup=f'source {sdk}/set_env.sh || exit $?; export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${{LD_LIBRARY_PATH:-}}; exec "$@"'
        row['shell_argv']=['taskset','-c','40-43','bash','-c',setup,'feedback-hardware',*row['argv']]
        save(build/(kind+'-execution/execution.json'),row)
    write(build/'configure-execution/stdout.log',f'-- CMAKE_ASC_COMPILER: {compiler}\n-- CMAKE_ASC_LLD_LINKER: {sdk}/aarch64-linux/ccec_compiler/bin/ld.lld\n')
    write(build/'configure-execution/stderr.log','')
    write(build/'build/CMakeFiles/3.22.1/CMakeASCCompiler.cmake',f'set(CMAKE_ASC_COMPILER "{compiler}")\nset(CMAKE_ASC_COMPILER_LOADED 1)\n')
    manifest={'version':'shared_context_build_v1','operator':'rms_norm','roles':{},
        'harness':{p.name:ref(p)['sha256'][7:] for p in shared_context_build.HARNESS.iterdir() if p.is_file()}}
    for role in ('A','B'):
        generated,identity,_=shared_context_build.generate_adapter(source,'rms_norm',role,digest)
        for name,data in witness['native'].items():write(build/role/name,generated if name=='op_host/rms_norm.asc' else data)
        manifest['roles'][role]={**identity,'npu_arch':'dav-2201','source_dir':str(parent/'op'),'adapter_sha256':hashlib.sha256(generated.encode()).hexdigest()}
        d=build/'build/CMakeFiles'/f'role_{role}.dir'
        write(d/'flags.make',f'# compile ASC with {compiler}\nASC_DEFINES = -Drole_{role}_EXPORTS\nASC_INCLUDES = -I{build/role/"op_host"} -I{build/role/"op_kernel"} -I{shared_context_build.HARNESS}\nASC_FLAGS = --npu-arch=dav-2201\n')
        write(d/'build.make',reviewed_role_makefile(build,role,'rms_norm',compiler)+'\n')
        for name in ('depend.make','compiler_depend.make','compiler_depend.ts'):write(d/name,'# Empty CMake dependency file\n')
        write(d/'progress.make',f'CMAKE_PROGRESS_1 = {1 if role=="A" else 3}\nCMAKE_PROGRESS_2 = {2 if role=="A" else 4}\n')
    save(build/'build_manifest.json',manifest)
    write(build/'build-execution/stdout.log',''.join(f'[ 25%] Building ASC object CMakeFiles/role_{role}.dir/{role}/op_host/rms_norm.asc.o\n' for role in ('B','A')))
    write(build/'build-execution/stderr.log',witness['stderr'].replace('$BUILD',str(build)).replace('$SDK',sdk))
    return task,parent,stage

def test_original_rms_adds_conflict_has_complete_readonly_closure(tmp_path):
    task,parent,stage=rms_compiler(tmp_path)
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    out=classify_failure(task,parent,stage)
    assert out['status']=='source_attempt_failed',out
    assert out['rule']=='original_source_rms_adds_gm_scalar_conflict'
    assert 'inherited Make environment and pre-execution recipe hashes were not recorded' in out['reason']
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert out==classify_failure(task,parent,stage)
    assert all(ref(Path(r['path']))==r for r in out['evidence'])
    names={r['path'] for r in out['evidence']}
    for name in ['source.tar','stages/build/stage-plan.json','op/op_kernel/rms_norm_kernel.asc',
        'build/build_manifest.json','build/A/op_kernel/rms_norm_kernel.asc','build/B/op_kernel/rms_norm_kernel.asc',
        'build/build/CMakeFiles/role_A.dir/build.make','build/build/CMakeFiles/role_B.dir/flags.make']:
        assert str(parent/name) in names
    for name in ('shared_context_build.py','level2_adapters.py'):assert any(p.endswith('/'+name) for p in names)

@pytest.mark.parametrize('fault',[
    'extra_error','sdk_internal_error','sdk_note_changed','missing_complete_B','foreign_path','wrong_column',
    'source_line_changed','source_archive_changed','source_symlink','role_kernel_changed','adapter_disabled_include',
    'recipe_extra_command','recipe_override','flags_extra','dependencies_nonempty','harness_hash_changed',
    'manifest_source_hash_changed','manifest_other_operator','stderr_unknown','stdout_unknown',
    'configure_failed','configure_stderr','wrong_shell','make_override','native_started','source_stage_hash_changed'])
def test_rms_positive_diagnostic_does_not_override_unproven_context(tmp_path,fault):
    task,parent,stage=rms_compiler(tmp_path);build=parent/'build';err=build/'build-execution/stderr.log'
    def edit(path,fn):path.write_text(fn(path.read_text()))
    if fault=='extra_error':edit(err,lambda s:s+"\n/tmp/other.asc:1:1: error: unknown thing\n")
    elif fault=='sdk_internal_error':edit(err,lambda s:s+'internal compiler error\n')
    elif fault=='sdk_note_changed':edit(err,lambda s:s.replace("'float' vs. '__gm__ float'","'float' vs. 'double'"))
    elif fault=='missing_complete_B':edit(err,lambda s:s.replace(str(build/'B')+"/op_host/../op_kernel/rms_norm_kernel.asc:180:45: error: no matching function for call to 'Adds'",''))
    elif fault=='foreign_path':edit(err,lambda s:s.replace('/op_host/../op_kernel/','/op_host/../../outside/'))
    elif fault=='wrong_column':edit(err,lambda s:s.replace(':180:45:',':180:46:'))
    elif fault=='source_line_changed':edit(parent/'op/op_kernel/rms_norm_kernel.asc',lambda s:s.replace('t_->epsilon, paddedRows','epsilon, paddedRows'))
    elif fault=='source_archive_changed':
        with (parent/'source.tar').open('ab') as f:f.write(b'changed')
    elif fault=='source_symlink':
        p=parent/'op/op_kernel/rms_norm_kernel.asc';raw=p.read_bytes();p.unlink();outside=tmp_path/'outside.asc';outside.write_bytes(raw);p.symlink_to(outside)
    elif fault=='role_kernel_changed':edit(build/'B/op_kernel/rms_norm_kernel.asc',lambda s:s+'\n// drift\n')
    elif fault=='adapter_disabled_include':edit(build/'A/op_host/rms_norm.asc',lambda s:s.replace('#include "../op_kernel/rms_norm_kernel.asc"','#if 0\n#include "../op_kernel/rms_norm_kernel.asc"\n#endif'))
    elif fault=='recipe_extra_command':edit(build/'build/CMakeFiles/role_A.dir/build.make',lambda s:s.replace('\t'+str('/opt/Ascend/cann-9.0.0/bin/bisheng'),'\tfalse\n\t/opt/Ascend/cann-9.0.0/bin/bisheng',1))
    elif fault=='recipe_override':edit(build/'build/CMakeFiles/role_B.dir/build.make',lambda s:s+'override SHELL = /bin/evil\n')
    elif fault=='flags_extra':edit(build/'build/CMakeFiles/role_A.dir/flags.make',lambda s:s+'export OTHER=1\n')
    elif fault=='dependencies_nonempty':write(build/'build/CMakeFiles/role_B.dir/compiler_depend.make','all: injected\n')
    elif fault in ('harness_hash_changed','manifest_source_hash_changed','manifest_other_operator'):
        p=build/'build_manifest.json';v=json.loads(p.read_text())
        if fault=='harness_hash_changed':v['harness'][next(iter(v['harness']))]='wrong'
        elif fault=='manifest_source_hash_changed':v['roles']['A']['source_sha256']='wrong'
        else:v['operator']='maximum'
        save(p,v)
    elif fault=='stderr_unknown':edit(err,lambda s:s+'unsupported warning\n')
    elif fault=='stdout_unknown':edit(build/'build-execution/stdout.log',lambda s:s+'unreviewed output\n')
    elif fault=='configure_stderr':write(build/'configure-execution/stderr.log','warning: new SDK\n')
    elif fault in ('configure_failed','wrong_shell','make_override'):
        p=build/('configure-execution/execution.json' if fault=='configure_failed' else 'build-execution/execution.json');v=json.loads(p.read_text())
        if fault=='configure_failed':v['exit_status']=1
        elif fault=='wrong_shell':v['shell_argv'][5]+='; extra command'
        else:v['environment_overrides']['MAKEFLAGS']='--eval=anything'
        save(p,v)
    elif fault=='native_started':stage['native_started']=True;save(parent/'stages/build/result.json',stage)
    elif fault=='source_stage_hash_changed':save(parent/'stages/build/stage-plan.json',{'source_hash':'wrong'})
    out=classify_failure(task,parent,stage);assert out['status']=='infrastructure_blocked',out


def test_new_original_source_is_not_blessed_by_same_diagnostic(tmp_path):
    task,parent,stage=rms_compiler(tmp_path)
    # Even internally consistent new source/manifest/recipes is outside this rule.
    original=parent/'op/op_kernel/rms_norm_kernel.asc';original.write_text(original.read_text()+'\n// another source\n')
    with tarfile.open(parent/'source.tar','w') as archive:archive.add(parent/'op',arcname='source')
    save(parent/'stages/build/stage-plan.json',{'source_hash':ref(parent/'source.tar')['sha256']})
    native={str(p.relative_to(parent/'op')):p.read_bytes() for name in ('op_host','op_kernel') for p in (parent/'op'/name).rglob('*') if p.is_file()}
    digest=hashlib.sha256()
    for name,data in sorted(native.items()):digest.update(name.encode()+b'\0'+data+b'\0')
    manifest=json.loads((parent/'build/build_manifest.json').read_text())
    for role in ('A','B'):
        generated,identity,_=shared_context_build.generate_adapter(parent/'op','rms_norm',role,digest.hexdigest())
        manifest['roles'][role]={**identity,'npu_arch':'dav-2201','source_dir':str(parent/'op'),'adapter_sha256':hashlib.sha256(generated.encode()).hexdigest()}
        for name,data in native.items():write(parent/'build'/role/name,generated if name=='op_host/rms_norm.asc' else data.decode())
    save(parent/'build/build_manifest.json',manifest)
    out=classify_failure(task,parent,stage)
    assert out['status']=='infrastructure_blocked' and 'finite witness' in out['reason'],out
