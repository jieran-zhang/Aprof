"""A closed session may reference an attested old code producer, never mutable data."""
from pathlib import Path
import json
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import msprof_exploration_provenance as provenance
import msprof_exploration_report as report
import msprof_exploration_archive as archive
for module in (provenance,report,archive):
    assert Path(module.__file__).resolve().parent==Path(__file__).resolve().parents[1]/'scripts'
from test_msprof_exploration_provenance import frozen, fresh_producer_fixture
from test_msprof_exploration_report import put


def fixture(frozen,monkeypatch,*,runtime=True):
    value=fresh_producer_fixture(frozen,monkeypatch)
    if runtime:
        origin=value['live'].parent.parent/'src/aprof_runtime/planning.py';origin.parent.mkdir(parents=True)
        value['live'].rename(origin);value['live']=origin
        manifest=provenance.load(value['freeze']);manifest['files'][0]['path']=str(origin);put(value['freeze'],manifest)
    stage=value['task']/'stages/aa';cohort=stage/'cohort';session=cohort/'p01'
    put(session/'completion.json',dict(version=report.PRODUCER_V2,status='passed',error=None,formal_admission='not_evaluated'))
    put(session/'request.json',dict(version=report.PRODUCER_V2))
    put(session/'bindings.json',{str(value['live']):value['expected']})
    put(session/'msprof.execution.json',dict(exit_code=0,error=None,ended_at=3))
    put(stage/'result.json',dict(status='passed',error=None,ended_at=5))
    put(cohort/'group-completion.json',dict(status='passed',error=None,completed_sessions=[str(cohort/f'p{i:02d}') for i in range(1,7)]))
    value['session']=session
    return value


@pytest.mark.parametrize('runtime',[True,False])
def test_old_closed_producer_binding_preserves_original_logical_dictionary(frozen,monkeypatch,runtime):
    value=fixture(frozen,monkeypatch,runtime=runtime)
    original={str(value['live']):value['expected']}
    bindings=report.ObservationBindings(original,value['session']/'completion.json')
    report._bound_file(bindings,value['live'])
    assert dict(bindings)==original and json.dumps(bindings)==json.dumps(original)
    proof=bindings.producer_bindings[0]
    assert proof['origin']=={'path':str(value['live']),'sha256':value['expected']}
    assert set(proof['closed_observation'])=={'completion','bindings','request','execution','stage_result','group_completion'}
    assert provenance.sha(proof['snapshot']['path'])==value['expected']
    report._bound_file(bindings,value['live']);assert len(bindings.producer_bindings)==1


@pytest.mark.parametrize('fault',['open','failed','old_protocol','native_failed','native_open','stage_open','stage_failed','group_failed','wrong_sessions','missing_binding','wrong_binding','task_manifest','snapshot','freeze','unknown_runtime','input_script','symlink','lexical_escape','not_completion'])
def test_no_data_or_incomplete_observation_fallback(frozen,monkeypatch,fault):
    v=fixture(frozen,monkeypatch);session=v['session'];origin=v['live'];evidence=session/'completion.json'
    if fault in ('open','failed','old_protocol'):
        doc=provenance.load(evidence)
        if fault=='old_protocol':doc['version']='msprof_kernel_time_study_v1'
        else:doc['status']='running' if fault=='open' else 'failed'
        put(evidence,doc)
    elif fault in ('native_failed','native_open'):
        doc=provenance.load(session/'msprof.execution.json');doc['exit_code']=1 if fault=='native_failed' else None;put(session/'msprof.execution.json',doc)
    elif fault in ('stage_open','stage_failed'):
        put(session.parent.parent/'result.json',{'status':'running' if fault=='stage_open' else 'failed','ended_at':5})
    elif fault in ('group_failed','wrong_sessions'):
        doc=provenance.load(session.parent/'group-completion.json')
        if fault=='group_failed':doc['status']='failed'
        else:doc['completed_sessions'][0]=str(session.parent/'foreign')
        put(session.parent/'group-completion.json',doc)
    elif fault in ('missing_binding','wrong_binding'):
        put(session/'bindings.json',{} if fault=='missing_binding' else {str(origin):'sha256:'+'0'*64})
    elif fault=='task_manifest':put(v['manifest'],{'modified':True})
    elif fault=='snapshot':
        source=provenance.load(v['freeze'])['files'][0]['snapshot'];Path(source).write_text('corrupt')
    elif fault=='freeze':v['freeze'].unlink()
    elif fault in ('unknown_runtime','input_script'):
        target=origin.with_name('other.py') if fault=='unknown_runtime' else v['task']/'inputs/planning.py'
        target.parent.mkdir(parents=True,exist_ok=True);origin.rename(target);origin=target
        doc=provenance.load(v['freeze']);doc['files'][0]['path']=str(origin);put(v['freeze'],doc)
        put(session/'bindings.json',{str(origin):v['expected']})
    elif fault=='symlink':
        target=origin.with_name('other.py');origin.rename(target);origin.symlink_to(target)
    elif fault=='lexical_escape':origin=origin.parent/'../aprof_runtime/planning.py'
    elif fault=='not_completion':evidence=session/'request.json'
    bindings=report.ObservationBindings({str(origin):v['expected']},evidence)
    with pytest.raises((ValueError,FileNotFoundError)):
        report._bound_file(bindings,origin)


def test_current_producer_hash_remains_exact_without_historical_substitution(frozen,monkeypatch):
    v=fixture(frozen,monkeypatch);actual=report.sha(v['live'])
    bindings=report.ObservationBindings({str(v['live']):actual},v['session']/'completion.json')
    report._bound_file(bindings,v['live'])
    assert not bindings.producer_bindings


def test_regular_pointer_semantics_still_cannot_substitute_runtime_file(frozen,monkeypatch):
    v=fixture(frozen,monkeypatch)
    with pytest.raises(ValueError,match='dependency pointer'):
        provenance.verify_pointer_tree({'producer':{'path':str(v['live']),'sha256':v['expected']}},evidence_path=v['session']/'completion.json')


def test_archive_requires_exact_closed_binding_before_runtime_substitution(frozen,monkeypatch):
    value=fixture(frozen,monkeypatch)
    a=archive.Archive.__new__(archive.Archive)
    a.run=value['task'].parents[2];a.root=a.run/'archive/train'
    a.artifacts={};a.pointer_cache={};a.observation_producer_bindings={}
    a.safe=lambda path,owner=None:Path(path)
    a.frozen_engineering=lambda *args:None
    a.relocated_preparation=lambda *args:None
    with pytest.raises(ValueError,match='hash differs'):
        a.pointer(value['live'],expected=value['expected'])
    a.bind_closed_observation_producers(value['session'],'maximum')
    result=a.pointer(value['live'],expected=value['expected'])
    assert result==a.observation_producer_bindings[(str(value['live']),value['expected'])]['snapshot']
    assert provenance.sha(result['path'])==value['expected']
    saved=list((a.root/'documents').glob('*.json'))
    assert len(saved)==1
    body=provenance.load(saved[0])['closed_observation_producer_binding']
    assert body['origin']=={'path':str(value['live']),'sha256':value['expected']}
    assert body['closed_observation']['bindings']['path']==str(value['session']/'bindings.json')
