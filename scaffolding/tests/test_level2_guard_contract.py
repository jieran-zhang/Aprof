from pathlib import Path
import copy,json,hashlib,sys
from types import SimpleNamespace
import pytest
import numpy as np
import torch
import level2_guard_contract as gc
import level2_candidate_guard as runner
import level2_failure_classification as classification

torch.set_num_threads(2)
H='sha256:'+'1'*64
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n');return gc.pointer(path)

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    task=tmp_path/'run/validation/tasks/group_norm';parent=task/'candidates/group_norm002';bundle=parent/'semantic-guards';bundle.mkdir(parents=True)
    oracle=task/'agent/reference/golden.py';oracle.parent.mkdir(parents=True);oracle.write_text('# reviewed fixture oracle\n')
    monkeypatch.setattr(classification,'REVIEWED_GROUP_NORM_GOLDEN',gc.pointer(oracle)['sha256'])
    cases=[];original=[]
    for i,name in enumerate(['retained','new_corner']):
        shape=[1,2,3];metadata={'shape':shape,'dtype':'float32','layout':'ND','attributes':{'num_groups':1,'epsilon':1e-5}}
        x=np.array([1,2,3,4,5,6],np.float32);gamma=np.ones(2,np.float32);beta=np.zeros(2,np.float32)
        expected=torch.nn.functional.group_norm(torch.from_numpy(x).reshape(shape),1,torch.from_numpy(gamma),torch.from_numpy(beta),1e-5).numpy()
        files={}
        for key,data in [('x',x),('gamma',gamma),('beta',beta),('expected',expected)]:
            p=bundle/'inputs'/name/(key+'.bin');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.tobytes());files[key]={'path':str(p.relative_to(bundle)),'sha256':gc.pointer(p)['sha256']}
        origin=None
        if i==0:
            old=task/'agent/boundary_inputs'/name;old.mkdir(parents=True)
            for key in files:(old/(key+'.bin')).write_bytes((bundle/files[key]['path']).read_bytes())
            origin=save(old/'guard.json',{'name':name,'expected_key':30})
            original.append({'name':name,'metadata':metadata,'expected_key':30})
        cases.append({'name':name,'metadata':metadata,'expected_key':33,'files':files,'retained_from':origin})
    original_ref=save(task/'agent/boundary_cases.json',{'operator':'group_norm','cases':original})
    plan={'schema_version':'1.0.0','dispatch_id':'gn-test','operator':'group_norm','source_hash':H,'architecture_profile_ref':H,'parallel_plan_ref':H,
          'entries':[{'group_id':'exact_small','tiling_key':33,'kernel_entry':'group_norm_exact_small','required_capabilities':[],
                      'conditions':[{'field':'dtype','op':'eq','value':'float32'},{'field':'attributes.group_elements','op':'le','value':128}]}],
          'fallback':{'group_id':'generic','tiling_key':0,'kernel_entry':'group_norm_generic','conditions':[],'required_capabilities':[]}}
    plan_ref=save(parent/'dispatch_plan.json',plan)
    oid='original-closed';original_cid='group_norm001'
    refs=[original_ref,gc.pointer(oracle),gc.pointer(task/'agent/boundary_inputs/retained/guard.json')]
    refs += [gc.pointer(task/'agent/boundary_inputs/retained'/(key+'.bin')) for key in ('x','gamma','beta','expected')]
    feedback={'operator':'group_norm','candidate_id':original_cid,'source_hash':H,'status':'source_attempt_failed','failure_classification':{'status':'source_attempt_failed','evidence':refs}}
    feedback_ref=save(task/'feedback/original.json',feedback)
    original_observation={'observation_id':oid,'feedback':feedback_ref}
    ledger_state={'observations':{oid:{'candidate_id':original_cid,'close_feedback':True,'report_ref':feedback_ref['sha256'],'feedback':feedback}},'candidates':{original_cid:{'source_hash':H,'observation_ids':[oid]}}}
    (task.parents[1]/'ledger').mkdir()
    import msprof_exploration_campaign
    monkeypatch.setattr(msprof_exploration_campaign,'Campaign',lambda _:SimpleNamespace(state={'tasks':{'group_norm':ledger_state}}))
    draft={'version':gc.DRAFT_VERSION,'operator':'group_norm','candidate_id':parent.name,'original_spec':original_ref,'original_observation':original_observation,'oracle':gc.pointer(oracle),'cases':cases}
    draft_ref=save(bundle/'draft.json',draft)
    def materialize():return gc.materialize(task,parent,gc.pointer(bundle/'draft.json'),H,gc.pointer(parent/'dispatch_plan.json'))
    return SimpleNamespace(task=task,parent=parent,bundle=bundle,draft=draft,draft_ref=draft_ref,plan=plan,plan_ref=plan_ref,materialize=materialize,ledger_state=ledger_state)

def test_materialized_revision_retains_inputs_and_adds_original_oracle_case(fixture):
    ref=fixture.materialize();contract=gc.checked_contract(ref,oracle=True,source_hash=H,dispatch_plan=fixture.plan_ref)
    assert len(contract['cases'])==2 and contract['cases'][0]['expected_key']==33
    assert json.loads((fixture.task/'agent/boundary_cases.json').read_text())['cases'][0]['expected_key']==30
    assert contract['script']['sha256']==gc.REVIEWED_RUNNER_SHA


def test_copied_runner_can_start_without_collector_on_pythonpath(tmp_path):
    import subprocess
    copied = tmp_path / 'boundary_guard.py'
    copied.write_bytes(Path(runner.__file__).read_bytes())
    result = subprocess.run([sys.executable, '-I', str(copied), '--help'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--repository' in result.stdout

@pytest.mark.parametrize('mutation',['remove_retained','metadata','old_input','old_golden','wrong_new_golden','duplicate','unknown_case_field','wrong_key','relative_escape','symlink','extra_file'])
def test_bad_author_draft_is_rejected_before_publication(fixture,mutation):
    d=copy.deepcopy(fixture.draft)
    if mutation=='remove_retained':d['cases']=d['cases'][1:]
    elif mutation=='metadata':d['cases'][0]['metadata']['attributes']['epsilon']=2e-5
    elif mutation in ('old_input','old_golden','wrong_new_golden'):
        row=d['cases'][1 if mutation=='wrong_new_golden' else 0];key='x' if mutation=='old_input' else 'expected';p=fixture.bundle/row['files'][key]['path'];p.write_bytes(bytes(p.stat().st_size));row['files'][key]['sha256']=gc.pointer(p)['sha256']
    elif mutation=='duplicate':d['cases'][1]=copy.deepcopy(d['cases'][0])
    elif mutation=='unknown_case_field':d['cases'][0]['threshold']=1
    elif mutation=='wrong_key':d['cases'][0]['expected_key']=30
    elif mutation=='relative_escape':d['cases'][1]['files']['x']['path']='../outside.bin'
    elif mutation=='symlink':
        p=fixture.bundle/d['cases'][0]['files']['x']['path'];data=p.read_bytes();p.unlink();target=fixture.parent/'outside';target.write_bytes(data);p.symlink_to(target)
    else:(fixture.bundle/'unexpected.txt').write_text('not bound')
    save(fixture.bundle/'draft.json',d)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):fixture.materialize()
    assert not (fixture.bundle/'contract.json').exists() and not (fixture.bundle/'boundary_guard.py').exists()

@pytest.mark.parametrize('name',['contract.json','draft.json','boundary_guard.py','inputs/new_corner/expected.bin','inputs/retained/x.bin'])
def test_frozen_bundle_any_byte_change_rejected(fixture,name):
    ref=fixture.materialize();p=fixture.bundle/name;p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises((ValueError,json.JSONDecodeError)):gc.checked_contract(ref)

def test_source_dispatch_candidate_and_canonical_path_are_bound(fixture):
    ref=fixture.materialize()
    with pytest.raises(ValueError):gc.checked_contract(ref,source_hash='sha256:'+'2'*64)
    with pytest.raises(ValueError):gc.checked_contract(ref,dispatch_plan={'path':'/wrong','sha256':H})
    for field,value in [('candidate_id','group_norm003'),('source_hash','sha256:'+'2'*64),('task',str(fixture.task.parent/'other'))]:
        original=json.loads((fixture.bundle/'contract.json').read_text());changed={**original,field:value};newref=save(fixture.bundle/'contract.json',changed)
        with pytest.raises((ValueError,FileNotFoundError)):gc.checked_contract(newref)
        save(fixture.bundle/'contract.json',original)

def test_no_implicit_guard_discovery_without_declaration(fixture):
    fixture.materialize()
    assert gc.resolve(fixture.task,fixture.parent,artifact=None) is None
    assert gc.resolve(fixture.task,fixture.parent) is None

def test_registered_contract_matches_proposal_and_ledger(fixture,monkeypatch):
    ref=fixture.materialize();proposal_ref=save(fixture.parent/'proposal.json',{'artifacts':{'semantic_guard_contract':ref}})
    ledger=fixture.task.parents[1]/'ledger';ledger.mkdir(exist_ok=True)
    state={'source_hash':H,'artifacts':{'semantic_guard_contract':ref,'proposal':proposal_ref}}
    import msprof_exploration_campaign
    monkeypatch.setattr(msprof_exploration_campaign,'Campaign',lambda _:SimpleNamespace(state={'tasks':{'group_norm':{**fixture.ledger_state,'candidates':{**fixture.ledger_state['candidates'],fixture.parent.name:state}}}}))
    assert gc.resolve(fixture.task,fixture.parent)['source_hash']==H
    save(fixture.parent/'proposal.json',{'artifacts':{}})
    with pytest.raises(ValueError):gc.resolve(fixture.task,fixture.parent)

def test_reviewed_runner_uses_bound_goldens_and_unchanged_threshold(fixture,monkeypatch,tmp_path):
    ref=fixture.materialize();out=tmp_path/'private-output'
    args=['guard','--repository',str(gc.ROOT),'--contract',ref['path'],'--output',str(out),'--plan',fixture.plan_ref['path']]
    monkeypatch.setattr(sys,'argv',args);runner.main()
    for case in fixture.draft['cases']:
        p=out/case['name'];(p/'output.bin').write_bytes((p/'expected.bin').read_bytes())
    monkeypatch.setattr(sys,'argv',args+['--verify']);runner.main()
    result=json.loads((out/'verification.json').read_text());assert all(r['passed'] and r['output']['threshold']==.005 for r in result['results'])
    (out/'new_corner/output.bin').write_bytes(bytes((out/'new_corner/output.bin').stat().st_size))
    with pytest.raises(SystemExit):runner.main()

@pytest.mark.parametrize('mutate_after_prepare',[False,True])
def test_collector_revision_and_resume_never_rerun_or_use_changed_inputs(fixture,monkeypatch,mutate_after_prepare):
    from contextlib import nullcontext,redirect_stdout
    import io
    import level2_boundaries as boundaries
    import level2_iteration as iteration
    import msprof_exploration_campaign
    ref=fixture.materialize();proposal=save(fixture.parent/'proposal.json',{'artifacts':{'semantic_guard_contract':ref}})
    state={'source_hash':H,'artifacts':{'semantic_guard_contract':ref,'proposal':proposal}}
    (fixture.task.parents[1]/'ledger').mkdir(exist_ok=True)
    monkeypatch.setattr(msprof_exploration_campaign,'Campaign',lambda _:SimpleNamespace(state={'tasks':{'group_norm':{**fixture.ledger_state,'candidates':{**fixture.ledger_state['candidates'],fixture.parent.name:state}}}}))
    binary=fixture.parent/'build/build/standalone';binary.parent.mkdir(parents=True);binary.write_bytes(b'cpu-mocked-native')
    save(fixture.parent/'build/build_manifest.json',{'standalone':gc.pointer(binary)})
    source=fixture.parent/'op';source.mkdir()
    run=fixture.task.parents[2]
    monkeypatch.setattr(boundaries,'task_paths',lambda *a:(run,'validation',fixture.task,fixture.parent,source))
    monkeypatch.setattr(boundaries,'exclusive_host',nullcontext)
    monkeypatch.setattr(boundaries,'health',lambda path:save(path,{'fixture':'no device'}))
    calls=[]
    def process(argv,cwd,directory,**kwargs):
        argv=list(map(str,argv));directory.mkdir(parents=True)
        if directory.name in ('prepare','verify'):
            monkeypatch.setattr(sys,'argv',['guard',*argv[3:]])
            stream=io.StringIO()
            with redirect_stdout(stream):runner.main()
            stdout=stream.getvalue()
            if directory.name=='prepare' and mutate_after_prepare:
                p=fixture.bundle/'inputs/new_corner/x.bin';p.write_bytes(p.read_bytes()+b'x')
        else:
            calls.append(argv);output=Path(argv[argv.index('--output')+1]);output.write_bytes((output.parent/'expected.bin').read_bytes())
            stdout='APROF_DISPATCH_JSON:'+json.dumps({'tiling_key':33,'kernel_entry':'group_norm_exact_small'})+'\n'
        save(directory/'execution.json',{'exit_status':0,'argv':argv});(directory/'stdout.log').write_text(stdout);(directory/'stderr.log').write_text('')
    monkeypatch.setattr(boundaries,'run_process',process)
    result=boundaries.collect(run,'group_norm',fixture.parent.name)
    assert result['version']==gc.REQUEST_VERSION
    if mutate_after_prepare:
        assert result['status']=='failed' and calls==[]
    else:
        assert result['status']=='passed' and len(calls)==2
        assert iteration.boundary_result(fixture.task,fixture.parent,'group_norm',fixture.parent.name)==result
        before=(fixture.parent/'boundary-validation/completion.json').read_bytes()
        with pytest.raises(FileExistsError):boundaries.collect(run,'group_norm',fixture.parent.name)
        assert len(calls)==2 and (fixture.parent/'boundary-validation/completion.json').read_bytes()==before

def test_materializer_preserves_optional_contract_in_final_proposal(fixture,monkeypatch):
    import level2_campaign as campaign
    import aprof_runtime.planning as planning
    from prepare_trace_pilot import create_source_snapshot
    from aprof_runtime.jsonio import content_hash
    run=fixture.task.parents[2]
    source=fixture.parent/'op'
    for folder in ['op_host','op_kernel']:(source/folder).mkdir(parents=True)
    (source/'op_host/group_norm.asc').write_text('int main(){return 0;}')
    (source/'op_kernel/kernel.asc').write_text('extern "C" void kernel(){}')
    create_source_snapshot(source,fixture.parent/'pre-registration-source.tar',root_label=fixture.parent.name)
    profile={'schema_version':'1.0.0','hardware_fingerprint':H,'architecture_id':'910c','soc_name':'Ascend910_9392','npu_arch':2201,'sdk_version':'9','probe_kind':'device','device_id':0,
             'core_counts':{'aic':24,'aiv':48},'memory_bytes':{k:196352 for k in planning.MEMORIES},'capabilities':{'vector':{'status':'supported','basis':'fixture','evidence_refs':[H]}},
             'provenance':{'probe_source_ref':H,'raw_probe_ref':H,'sdk_header_ref':H},'limitations':[]}
    save(fixture.task/'agent/architecture_profile.json',profile)
    evidence=save(fixture.task/'agent/reason.json',{'reason':'guard revision'})
    plan={'schema_version':'1.0.0','plan_id':'fixture','operator':'group_norm','source_hash':H,'architecture_profile_ref':content_hash(profile),'semantic_invariants':['original group norm'],'precision_invariants':['original tolerance'],
          'groups':[{'group_id':'exact_small','algorithm':'small','task_partition':'group','ownership':'group','reduction':'Welford','synchronization':'kernel','workspace_bytes':0,'workspace_formula':'0','required_capabilities':['vector'],'memory_requirements':{},'alternatives':[],'selection_evidence':[evidence['sha256']]}]}
    save(fixture.parent/'parallel_plan.json',plan);(fixture.parent/'dispatch_plan.json').unlink()
    save(fixture.parent/'dispatch_plan.proposed.json',fixture.plan);save(fixture.parent/'dispatch-sequences.proposed.json',{'33':{'kernels':['group_norm_exact_small']},'0':{'kernels':['group_norm_generic']}})
    save(run/'graph/v0002/graph.json',{'fixture':True})
    meta=save(fixture.task/'input.json',{'shape':[1,2,3],'dtype':'float32','num_groups':1,'epsilon':1e-5})
    save(fixture.task/'input-bindings.json',{'cases':[{'case_id':1,'metadata':meta}]})
    draft={'candidate_id':fixture.parent.name,'operator':'group_norm','semantic_guard_draft':fixture.draft_ref,'artifacts':{'ignored_by_design':'must not replace concrete artifacts'}}
    save(fixture.parent/'proposal.draft.json',draft)
    monkeypatch.setattr(campaign,'task_path',lambda *a:fixture.task)
    final=campaign.materialize_candidate(run,'group_norm',fixture.parent.name)
    result=json.loads(Path(final['path']).read_text())
    assert result['artifacts']['semantic_guard_contract']==gc.pointer(fixture.bundle/'contract.json')
    assert result['artifacts']['author_draft']==gc.pointer(fixture.parent/'proposal.draft.json')
    assert 'ignored_by_design' not in result['artifacts']
    gc.checked_contract(result['artifacts']['semantic_guard_contract'],source_hash=result['implementation_source_hash'])

def test_archive_includes_guard_input_and_execution_closure(fixture):
    import msprof_exploration_archive as archive
    ref=fixture.materialize();validation=fixture.parent/'boundary-validation'
    request=save(validation/'request.json',{'semantic_guard_contract':ref,'producer':gc.pointer(Path(gc.__file__))})
    save(validation/'completion.json',{'request':request})
    included=set()
    class Recorder:
        task_root=fixture.task.parent
        def audit_paths(self,value,owner,**kwargs):
            if isinstance(value,dict):
                if set(value)=={'path','sha256'}:included.add(str(gc.checked(value)))
                for v in value.values():self.audit_paths(v,owner)
            elif isinstance(value,list):
                for v in value:self.audit_paths(v,owner)
        def files(self,path,owner):included.update(str(p) for p in path.rglob('*') if p.is_file())
    rec=Recorder();candidate={'candidate_id':fixture.parent.name,'source_hash':H,'artifacts':{'semantic_guard_contract':ref,'dispatch_plan':fixture.plan_ref}}
    proposal={'artifacts':{'semantic_guard_contract':ref}}
    archive.Archive.candidate_guard(rec,'group_norm',candidate,proposal)
    expected={str(p) for p in fixture.bundle.rglob('*') if p.is_file()}|{str(validation/'request.json'),str(validation/'completion.json'),str(Path(gc.__file__)),str(fixture.task/'agent/boundary_cases.json'),str(fixture.task/'agent/reference/golden.py'),str(fixture.task/'agent/boundary_inputs/retained/guard.json')}
    assert expected<=included
    with pytest.raises(ValueError):archive.Archive.candidate_guard(rec,'group_norm',candidate,{'artifacts':{}})
    (fixture.bundle/'inputs/retained/x.bin').write_bytes(b'changed')
    with pytest.raises(ValueError):archive.Archive.candidate_guard(rec,'group_norm',candidate,proposal)

@pytest.mark.parametrize('name',['level2_guard_contract.py','level2_candidate_guard.py'])
def test_guard_helper_history_uses_attested_cas_only(tmp_path,monkeypatch,name):
    import msprof_exploration_provenance as provenance
    repository=tmp_path/'repository';scripts=repository/'scaffolding/collection/scripts';scripts.mkdir(parents=True)
    source=scripts/name;source.write_bytes(b'# original helper\n');ref=gc.pointer(source)
    runs=repository/'.aprof/runs';run=runs/'fresh-run';task=run/'validation/tasks/group_norm';task.mkdir(parents=True)
    manifest=save(task/'manifest.json',{'version':'msprof_task_time_exploration_v2','run_id':run.name,'operator':'group_norm','split':'validation','source_split':'validation','task_dir':str(task)})
    snapshot=run/'bootstrap/source-cas'/ref['sha256'][7:];snapshot.parent.mkdir(parents=True);snapshot.write_bytes(source.read_bytes())
    freeze=save(run/'bootstrap/frozen-engineering-001.json',{'files':[{**ref,'snapshot':str(snapshot)}],'task_manifests':[manifest]})
    source.write_bytes(b'# later helper version\n')
    monkeypatch.setattr(provenance,'CAMPAIGN_RUNS',runs);monkeypatch.setattr(provenance,'ENGINEERING_SCRIPTS',scripts)
    bindings=[];provenance.verify_pointer_tree({'producer':ref},evidence_path=task/'candidates/group_norm002/boundary-validation/request.json',producer_bindings=bindings)
    assert bindings[0]['origin']==ref and bindings[0]['snapshot']==gc.pointer(snapshot)
    snapshot.write_bytes(b'tampered')
    with pytest.raises(ValueError):provenance.verify_pointer_tree({'producer':ref},evidence_path=task/'candidates/group_norm002/boundary-validation/request.json')

@pytest.mark.parametrize('mutate',[False,True])
def test_registration_binds_materialized_contract_before_attempt(fixture,monkeypatch,mutate):
    import shutil
    import run_msprof_exploration_stage as stage
    import aprof_runtime.planning as planning
    test_materializer_preserves_optional_contract_in_final_proposal(fixture,monkeypatch)
    source=fixture.parent/'op';baseline=fixture.task/'baseline';shutil.copytree(source,baseline)
    (baseline/'op_host/group_norm.asc').write_text('int main(){return 1;}')
    proposal_path=fixture.parent/'proposal.json';proposal=json.loads(proposal_path.read_text())
    proposal.update(source_parent='baseline',decision_basis=[],optimization_stage='algorithm_parallel')
    save(proposal_path,proposal)
    if mutate:(fixture.bundle/'inputs/new_corner/expected.bin').write_bytes(b'tampered')
    registered=[]
    ledger=SimpleNamespace(config={'schema_version':'msprof_exploration_campaign_v2','tasks':{'group_norm':{'baseline_source_hash':H}}},state={'tasks':{'group_norm':fixture.ledger_state}},register=lambda **kwargs:registered.append(kwargs))
    run=fixture.task.parents[2]
    monkeypatch.setattr(stage,'Campaign',lambda _:ledger)
    monkeypatch.setattr(stage,'task_paths',lambda *a:(run,'validation',fixture.task,fixture.parent,source))
    monkeypatch.setattr(stage,'require_distinct_source',lambda *a:'fixture-content-identity')
    monkeypatch.setattr(stage,'fresh_dispatch_launch',lambda *a:None)
    monkeypatch.setattr(stage,'fresh_graph_bundle',lambda *a:[])
    monkeypatch.setattr(planning,'validate_planning_context',lambda *a,**k:None)
    if mutate:
        with pytest.raises(ValueError):stage.register_proposal(run,'group_norm',fixture.parent.name,proposal_path)
        assert registered==[]
    else:
        stage.register_proposal(run,'group_norm',fixture.parent.name,proposal_path)
        assert len(registered)==1 and registered[0]['artifacts']['semantic_guard_contract']==gc.pointer(fixture.bundle/'contract.json')
        assert registered[0]['source_hash']==gc.pointer(fixture.parent/'source.tar')['sha256']

@pytest.mark.parametrize('mutation',['layout','derived_count','case_id','bool_count'])
def test_added_case_must_declare_exact_canonical_metadata(fixture,mutation):
    d=copy.deepcopy(fixture.draft);metadata=d['cases'][1]['metadata']
    if mutation=='layout':metadata['layout']='NHWC'
    elif mutation=='derived_count':metadata['attributes']['group_elements']=128
    elif mutation=='case_id':metadata['attributes']['case_id']=1
    else:metadata['attributes']['group_count']=True
    save(fixture.bundle/'draft.json',d)
    with pytest.raises(ValueError):fixture.materialize()
    assert not (fixture.bundle/'contract.json').exists()

@pytest.mark.parametrize('trailing',[1,2,3])
def test_reviewed_runner_rejects_trailing_fractional_elements(fixture,monkeypatch,tmp_path,trailing):
    ref=fixture.materialize();out=tmp_path/'trailing-output'
    args=['guard','--repository',str(gc.ROOT),'--contract',ref['path'],'--output',str(out),'--plan',fixture.plan_ref['path']]
    monkeypatch.setattr(sys,'argv',args);runner.main()
    for case in fixture.draft['cases']:
        dest=out/case['name'];(dest/'output.bin').write_bytes((dest/'expected.bin').read_bytes())
    output=out/'new_corner/output.bin';output.write_bytes(output.read_bytes()+bytes(trailing))
    monkeypatch.setattr(sys,'argv',args+['--verify'])
    with pytest.raises(ValueError,match='byte size'):runner.main()

@pytest.mark.parametrize('target',['inputs/new_corner/output.bin','inputs/verification.json','verify/stdout.log','verify/execution.json','executions/new_corner/stdout.log','health-after.json','add_file','delete_file'])
def test_passed_replay_rejects_modified_full_execution_closure(fixture,monkeypatch,target):
    import level2_iteration as iteration
    test_collector_revision_and_resume_never_rerun_or_use_changed_inputs(fixture,monkeypatch,False)
    root=fixture.parent/'boundary-validation'
    if target=='add_file':(root/'unbound-note.json').write_text('{}')
    elif target=='delete_file':(root/'verify/stdout.log').unlink()
    else:
        path=root/target;path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):iteration.boundary_result(fixture.task,fixture.parent,'group_norm',fixture.parent.name)

@pytest.mark.parametrize('mutation',['rehash_roster','rehash_original_input','feedback_bytes','open_observation','wrong_source','missing_ref'])
def test_retained_authority_requires_closed_original_ledger_evidence(fixture,mutation):
    d=copy.deepcopy(fixture.draft);oid=d['original_observation']['observation_id'];obs=fixture.ledger_state['observations'][oid]
    if mutation=='rehash_roster':
        p=fixture.task/'agent/boundary_cases.json';value=json.loads(p.read_text());value['cases']=[]
        d['original_spec']=save(p,value);d['cases']=d['cases'][1:]
    elif mutation=='rehash_original_input':
        p=fixture.task/'agent/boundary_inputs/retained/x.bin';p.write_bytes(bytes(p.stat().st_size))
        q=fixture.bundle/d['cases'][0]['files']['x']['path'];q.write_bytes(p.read_bytes());d['cases'][0]['files']['x']['sha256']=gc.pointer(q)['sha256']
    elif mutation=='feedback_bytes':
        p=Path(d['original_observation']['feedback']['path']);value=json.loads(p.read_text());value['extra']='self rehashed';d['original_observation']['feedback']=save(p,value)
    elif mutation=='open_observation':obs['close_feedback']=False
    elif mutation=='wrong_source':fixture.ledger_state['candidates']['group_norm001']['source_hash']='sha256:'+'2'*64
    else:
        obs['feedback']=copy.deepcopy(obs['feedback']);obs['feedback']['failure_classification']['evidence']=[]
        d['original_observation']['feedback']=save(Path(d['original_observation']['feedback']['path']),obs['feedback']);obs['report_ref']=d['original_observation']['feedback']['sha256']
    save(fixture.bundle/'draft.json',d)
    with pytest.raises(ValueError):fixture.materialize()
    assert not (fixture.bundle/'contract.json').exists()
