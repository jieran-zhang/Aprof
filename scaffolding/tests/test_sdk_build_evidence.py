import json
from pathlib import Path
import shutil
import sys

import pytest

import sdk_build_evidence as sdk
from aprof_runtime.local_evidence import LocalEvidence


@pytest.fixture
def case(tmp_path, monkeypatch):
    vendor = tmp_path/'sdk'; assembly = tmp_path/'assembly'; local = LocalEvidence(tmp_path/'records')
    tools = {name: str(vendor/'bin'/name) for name in sdk.TOOLS}
    monkeypatch.setattr(sdk, 'SDK', vendor); monkeypatch.setattr(sdk, 'TOOLS', tools)
    def put(path, data='fixture'):
        path=Path(path); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(data); return path
    for path in [*tools.values(), *(vendor/n for n in sdk.MODULES), vendor/'include/kernel.h']:
        put(path)
    header=vendor/'include/kernel.h'; source=put(assembly/'source/op_host/exp.asc')
    contract = {'sdk_resource_evidence': {'sdk_source_excerpts': {'header': {
        'source_path':str(header),'source_sha256':sdk.digest(header.read_bytes())}},
        'sdk_facility_observations': {'selected_sdk_headers': [], 'compiler': {
            'path':tools['compiler'],'sha256':sdk.digest(Path(tools['compiler']).read_bytes())}}}}
    contract_path=put(tmp_path/'contract.json',json.dumps(contract))
    contract_ref=sdk.pointer(contract_path,local); binding=sdk.freeze(local,contract_ref)
    refs=sdk.metadata_paths(assembly,'exp'); obj='CMakeFiles/exp.dir/op_host/exp.asc.o'
    cache={'CMAKE_ASC_COMPILER':tools['compiler'],'CMAKE_CXX_COMPILER':tools['cxx'],
        'CMAKE_MAKE_PROGRAM':tools['make'],'CMAKE_COMMAND':tools['cmake'],'CMAKE_ASC_LLD_LINKER':tools['linker'],
        'ASC_DIR':str(vendor/'lib64/cmake'),'CMAKE_BUILD_TYPE':'Release','CMAKE_GENERATOR':'Unix Makefiles',
        'CMAKE_HOME_DIRECTORY':str(assembly/'source')}
    texts={'cache':'\n'.join(k+':STRING='+v for k,v in cache.items()),
        'flags':f'ASC_DEFINES = \nASC_INCLUDES = -I{assembly}/source/op_host -I{assembly}/source/op_kernel\nASC_FLAGS = --npu-arch=dav-2201\n',
        'rules':f'\t{tools["compiler"]} $(ASC_DEFINES) $(ASC_INCLUDES) -fPIC $(ASC_FLAGS) -MD -MT {obj} -MF {obj}.d -o {obj} -c --asc-aicore-lang {source}\n',
        'link':f'{tools["compiler"]} {obj} -o exp -lascendcl',
        'modules':'\n'.join('"'+str(vendor/n)+'"' for n in sdk.MODULES),
        'dependencies':obj+': \\\n '+str(source)+' '+str(header)+'\n'}
    for k,path in refs.items():put(path,texts[k])
    evidence=sdk.finish(local,binding,assembly,'exp')
    review=put(tmp_path/'review.json',json.dumps({'contract_ref':contract_ref}))
    attempt=put(assembly/'build-attempt.json',json.dumps({'independent_review':sdk.pointer(review,local)}))
    build={'attempt_ref':sdk.pointer(attempt,local),'binary':{'path':str(assembly/'build/exp')},
           'sdk_build_ref':evidence,'commands':[{'environment':sdk.environment()} for _ in range(2)]}
    return local,build,{'operator':'exp'},texts,assembly,binding,header,put


def test_new_contract_full_credential_and_original_environment(case):
    local,build,proof,*_=case
    sdk.verify(build,proof,reader=local)
    assert not {'ASCFLAGS','CC','CXX','CPATH','LD_PRELOAD','CMAKE_TOOLCHAIN_FILE'} & sdk.environment().keys()


@pytest.mark.parametrize('field,bad',[
 ('flags','ASC_DEFINES = -D__MSTX_DFX_REPORT__=1\n'),
 ('flags','ASC_DEFINES = -DASCENDC_DEBUG=1\n'),
 ('flags','ASC_FLAGS = --npu-arch=dav-2201 --run-mode=cpu\n'),
 ('flags','ASC_FLAGS = --npu-arch=dav-3510\n'),
 ('flags','ASC_FLAGS = --npu-arch=dav-2201 @inject.rsp\n'),
 ('cache','CMAKE_ASC_COMPILER:FILEPATH=/tmp/other-bisheng\n'),
 ('cache','CMAKE_TOOLCHAIN_FILE:FILEPATH=/tmp/injected.cmake\n')])
def test_effective_flags_and_compiler_rejected(case,field,bad):
    _,_,_,texts,assembly,*_=case
    texts[field]+='\n'+bad
    with pytest.raises(ValueError):sdk.parse_effective(texts,assembly,'exp',{})


def test_actual_environment_changed(case):
    local,build,proof,*_=case
    build['commands'][0]['environment']['ASCFLAGS']='-DASCENDC_TIME_STAMP_ON'
    with pytest.raises(ValueError,match='environment'):sdk.verify(build,proof,reader=local)


def test_missing_credential_new_contract_rejected(case):
    local,build,proof,*_=case
    del build['sdk_build_ref']
    with pytest.raises(ValueError,match='requires actual build credential'):sdk.verify(build,proof,reader=local)


def test_reviewed_header_mutation_rejected_before_build(case):
    local,_,_,_,_,binding,header,_=case
    header.write_text('changed')
    with pytest.raises(ValueError,match='changed'):
        sdk.verify_binding(sdk.value(binding),live=True)


def test_legacy_no_sdk_contract_keeps_original_branch(case):
    local,build,proof,_,assembly,_,_,put=case
    old=put(assembly/'old-contract.json','{}');review=put(assembly/'old-review.json',json.dumps({'contract_ref':sdk.pointer(old,local)}))
    attempt=put(assembly/'old-attempt.json',json.dumps({'independent_review':sdk.pointer(review,local)}))
    build['attempt_ref']=sdk.pointer(attempt,local);del build['sdk_build_ref']
    sdk.verify(build,proof,reader=local)


def test_archived_bytes_replay_without_original_sdk_or_assembly(case,tmp_path):
    local,build,proof,_,assembly,_,header,_=case
    archived=tmp_path/'archive';archived.mkdir()
    copies={}
    for ref,path in local._paths.items():
        dest=archived/ref[7:];shutil.copyfile(path,dest);copies[ref]=dest
    shutil.rmtree(assembly);shutil.rmtree(header.parent.parent)
    class Reader:
        def verify_artifact(self,ref):return copies[ref]
    sdk.verify(build,proof,reader=Reader())


def test_real_short_command_does_not_inherit_build_injection(tmp_path,monkeypatch):
    import time
    from validation_host_evaluator import Commands
    monkeypatch.setenv('ASCFLAGS','-DASCENDC_DEBUG=1')
    monkeypatch.setenv('LD_PRELOAD','/definitely/not/a/library.so')
    commands=Commands(tmp_path/'commands',time.monotonic()+20)
    commands.directory.mkdir()
    env=sdk.environment()
    record=commands.run('environment',[sys.executable,'-c','import json,os; print(json.dumps(dict(os.environ)))'],tmp_path,environment=env)
    actual=json.loads(Path(record['stdout']['path']).read_text())
    assert record['exit_status']==0 and record['environment']==env
    assert 'ASCFLAGS' not in actual and 'LD_PRELOAD' not in actual
    assert actual['ASCEND_HOME_PATH']==str(sdk.SDK)
