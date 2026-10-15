"""CPU contract/linkage tests; synthetic receipts never establish hardware qualification."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from aprof_runtime import planning as p
from aprof_runtime.contracts import Context, SourceHashes
from aprof_runtime.errors import ContractError,StoreError
from aprof_runtime.jsonio import content_hash,file_hash
from aprof_runtime.local_evidence import LocalEvidence
from test_planning import context_example
import task_baseline_context as builder
import task_baseline_qualification as baseline


def context_for(parallel,dispatch,profile,case):
    selected=p.select_dispatch(dispatch,case['workload'])
    return Context.from_dict(dict(schema_version='1.0.0',task_id='CPU unqualified',operator=dispatch['operator'],
        hardware_fingerprint=profile['hardware_fingerprint'],budget={},workload=dict(
            source_hash=dispatch['plan_basis_source_hash'],implementation_source_hash=dispatch['implementation_source_hash'],
            plan_basis_source_hash=dispatch['plan_basis_source_hash'],metadata=case['workload'],
            original_metadata_ref=case['metadata_ref'],workload_group=case['group_id'],complete_call_ref=content_hash(selected)),
        evidence=dict(optimization_stage='execution',architecture_profile=profile,architecture_profile_ref=content_hash(profile),
            parallel_plan=parallel,parallel_plan_ref=content_hash(parallel),dispatch_plan=dispatch,dispatch_plan_ref=content_hash(dispatch))))




@pytest.fixture
def linked(tmp_path):
    local=LocalEvidence(tmp_path/'records');ref=local.register_json
    source=tmp_path/'kernel.asc';source.write_text('CPU synthetic source, no compile')
    files={'kernel.asc':local.register_artifact(source)};source_ref=ref({'schema_version':'1.0.0','files':files})
    review=dict(operator='gqa',roles={r:dict(path=str(tmp_path/r),files=files) for r in ('baseline','candidate')})
    review_ref=ref(review)
    profile=deepcopy(context_example()['evidence']['architecture_profile']);profile_ref=ref(profile)
    parallel=deepcopy(context_example()['evidence']['parallel_plan']);parallel.update(operator='gqa',source_hash=source_ref,architecture_profile_ref=profile_ref)
    parallel_ref=ref(parallel);rows=[];cases=[];identity_cases={};names={r:{} for r in review['roles']};counts={r:{} for r in review['roles']}
    for i in range(1,21):
        metadata=dict(case_id=i,query_shape=[1,2,4,8],key_shape=[1,3,2,8],value_shape=[1,3,2,8],dtype='float16',is_causal=False)
        metadata_ref=ref(metadata);path=str(local.verify_artifact(metadata_ref));scope=baseline.case_scope('gqa',metadata)
        rows.append(dict(metadata_ref=metadata_ref,workload=p.workload_metadata('gqa',metadata),
            group_id=parallel['groups'][0]['group_id'],role_kernel_names=deepcopy(scope['role_kernel_names'])))
        cases.append(dict(case_id=i,prepared_files=[path]))
        identity_cases[str(i)]={'prepared_files':{path:metadata_ref}}
        for r in names:names[r][str(i)]=scope['role_kernel_names'][r];counts[r][str(i)]=scope['launches_per_call'][r]
    dispatch=dict(schema_version='1.0.0',dispatch_id='CPU only',mode=p.UNKEYED_MODE,scope='declared_workloads_only',
        operator='gqa',source_hash=source_ref,plan_basis_source_hash=source_ref,implementation_source_hash=source_ref,
        architecture_profile_ref=profile_ref,parallel_plan_ref=parallel_ref,source_review_ref=review_ref,declared_workloads=rows)
    binary=tmp_path/'binary';binary.write_text('CPU not an executable')
    binary_ref=local.register_artifact(binary)
    build=dict(status='passed',error=None,binary={'sha256':binary_ref},source_review_hash=review_ref,CPU_fixture_only=True)
    build_ref=ref(build);window_ref=ref(dict(kind='reviewed_candidate_build',receipt_ref=build_ref,CPU_fixture_only=True))
    receipts={str(local.verify_artifact(review_ref)):review_ref,str(local.verify_artifact(build_ref)):build_ref}
    config=dict(operator='gqa',expected_case_ids=list(range(1,21)),cases=cases,
        build={'receipt_files':list(receipts)},task_profile={'role_kernel_names':names},
        roles={r:dict(source_dir=review['roles'][r]['path'],launches_per_operator=counts[r]) for r in names})
    registration={'identity':{'cases':identity_cases,'build':{'receipt_refs':receipts,'binary_ref':binary_ref}}}
    sources={r:source_ref for r in names};draft=SimpleNamespace(source_hashes=SourceHashes(**sources),candidate_id='CPU',
        transformation_id='transformation.narrow_sync_scope',parameters={})
    def pack():
        proof_ref=ref(dict(protocol='shared_buffer_msprof_task_window_v5',source_hashes=sources,
            config_ref=ref(config),registration_ref=ref(registration)))
        completion_ref=ref(dict(protocol='shared_buffer_msprof_task_window_v5',status='passed',error=None,
            source_hashes=sources,candidate_id='CPU',proof_ref=proof_ref,CPU_fixture_only=True))
        return context_for(parallel,dispatch,profile,rows[0]),SimpleNamespace(artifacts={
            'measurement_admission':completion_ref,'build_window':window_ref})
    return SimpleNamespace(**locals())


def test_final_linkage_keeps_repeated_sequence_and_needs_no_live_paths(linked):
    f=linked;context,evidence=f.pack()
    assert f.rows[0]['role_kernel_names']['baseline'].count('aprof_baseline_gqa_qk_fp16')==2
    p.verify_unkeyed_task_binding(context,f.draft,evidence,f.local.verify_artifact)
    assert not Path(f.review['roles']['baseline']['path']).exists()
    assert not list(f.tmp_path.rglob('*.sqlite'))


@pytest.mark.parametrize('defect',['missing20','key','single_kernel','duplicate_scope','case_selector','source','architecture',
    'metadata','task_order','task_count','dtype','review','binary','build_failure','prepared_roster'])
def test_unkeyed_rejects_schema_and_final_binding_tampering(linked,defect):
    f=linked
    if defect=='missing20':f.dispatch['declared_workloads'].pop()
    elif defect=='key':f.dispatch['tiling_key']=0
    elif defect=='single_kernel':f.dispatch['kernel_entry']='host_callback'
    elif defect=='duplicate_scope':
        for r in f.rows[1]['role_kernel_names']:f.rows[1]['role_kernel_names'][r].reverse()
    elif defect=='case_selector':f.rows[0]['workload']['attributes']['case_id']=1
    elif defect=='source':f.dispatch['implementation_source_hash']='sha256:'+'0'*64
    elif defect=='architecture':f.dispatch['architecture_profile_ref']='sha256:'+'0'*64
    elif defect=='metadata':f.rows[0]['metadata_ref']=f.rows[1]['metadata_ref']
    elif defect=='task_order':f.config['task_profile']['role_kernel_names']['baseline']['1'].reverse()
    elif defect=='task_count':f.config['roles']['baseline']['launches_per_operator']['1']+=1
    elif defect=='dtype':
        for r in f.names:
            f.rows[0]['role_kernel_names'][r]=[n.replace('fp16','bf16') for n in f.rows[0]['role_kernel_names'][r]]
    elif defect=='review':f.dispatch['source_review_ref']=f.local.register_json({**f.review,'operator':'gelu'})
    elif defect=='binary':f.registration['identity']['build']['binary_ref']='sha256:'+'0'*64
    elif defect=='build_failure':
        ref=f.local.register_json({**f.build,'status':'failed'})
        f.window_ref=f.local.register_json(dict(kind='reviewed_candidate_build',receipt_ref=ref))
        # pack closes over the original wrapper; corrupt its actual referenced bytes.
        f.local.verify_artifact(f.build_ref).write_text(json.dumps({**f.build,'status':'failed'}))
    else:f.config['cases'][0]['prepared_files']=[]
    with pytest.raises((ContractError,ValueError,StoreError)):
        context,evidence=f.pack();p.verify_unkeyed_task_binding(context,f.draft,evidence,f.local.verify_artifact)


def test_duplicate_metadata_is_allowed_only_with_identical_scope(linked):
    f=linked;p.validate_planning_contract('dispatch_plan',f.dispatch)
    assert len(f.dispatch['declared_workloads'])==20
    assert p.select_dispatch(f.dispatch,f.rows[0]['workload'])['scope']=='declared_workloads_only'


def test_actual_build_must_use_the_bound_mechanical_review(linked):
    f=linked
    changed=f.local.register_json({**f.build,'source_review_hash':'sha256:'+'0'*64})
    del f.receipts[str(f.local.verify_artifact(f.build_ref))]
    f.receipts[str(f.local.verify_artifact(changed))]=changed
    f.config['build']['receipt_files']=list(f.receipts)
    context,evidence=f.pack()
    evidence.artifacts['build_window']=f.local.register_json(dict(kind='reviewed_candidate_build',receipt_ref=changed))
    with pytest.raises(ContractError,match='actual build'):
        p.verify_unkeyed_task_binding(context,f.draft,evidence,f.local.verify_artifact)


def test_prebuild_uses_existing_mechanical_verifier_without_build_dependency(linked,monkeypatch):
    f=linked;calls=[]
    plan=dict(operator='gqa',source_review_ref=f.review_ref,source_hashes=f.sources,cases=[dict(
        case_id=i+1,metadata_ref=row['metadata_ref'],workload=json.loads(f.local.verify_artifact(row['metadata_ref']).read_text()),
        role_kernel_names=row['role_kernel_names']) for i,row in enumerate(f.rows)])
    monkeypatch.setattr(builder.baseline,'checked_plan',lambda *args:plan)
    import task_baseline_build
    def checked(*args):calls.append('actual source_identity boundary');return plan,f.review
    monkeypatch.setattr(task_baseline_build,'_assembly',checked)
    result=builder.prepare_unkeyed_dispatch(f.local,plan_ref='CPU plan boundary',parallel_plan_ref=f.parallel_ref,dispatch_id='CPU')
    assert calls==['actual source_identity boundary'] and json.loads(f.local.verify_artifact(result).read_text())['source_review_ref']==f.review_ref
    assert not list(f.tmp_path.rglob('build-attempt.json'))


def test_staged_schema_preserves_original_keyed_shape():
    release=Path(__file__).resolve().parents[2]/'skill-libs/graph-base'
    base=json.loads((release/'0.5.1/schemas/dispatch-plan.schema.json').read_text())
    original={k:v for k,v in base.items() if k not in ('$schema','$id')}
    assert p.DISPATCH_PLAN==original
    assert json.loads((release/'1.0.0/schemas/dispatch-plan.schema.json').read_text())==p.schema('dispatch_plan')
    value=context_example()
    assert p.validate_planning_contract('dispatch_plan',value['evidence']['dispatch_plan'])==value['evidence']['dispatch_plan']
    selected=p.select_dispatch(value['evidence']['dispatch_plan'],value['workload']['metadata'])
    assert set(selected)=={'tiling_key','kernel_entry','group_id','fallback'}
    p.validate_planning_context(Context.from_dict(value),execution=True)


def test_unkeyed_scope_never_creates_predicates_or_unlocks_a_route(linked):
    from aprof_runtime.graph import load_snapshot,route_graph
    from aprof_runtime.jsonio import to_primitive
    from aprof_layout import skill_lib
    f=linked;context,_=f.pack();value=to_primitive(context)
    graph,_=load_snapshot(skill_lib()/'skillgraph/versions/v0002')
    value['evidence']['predicate_states']={item['id']:'unknown' for item in graph['predicates']}
    route=route_graph(graph,Context.from_dict(value))
    assert next(item.target_id for item in route.candidates if item.edge_id==route.selected_edge_id)=='transformation.noop'
    value['workload']['complete_call_ref']='sha256:'+'0'*64
    with pytest.raises(ContractError,match='declared original'):p.validate_planning_context(Context.from_dict(value),execution=True)
    value['workload']['tiling_key']=0
    with pytest.raises(ContractError,match='cannot claim'):p.validate_planning_context(Context.from_dict(value),execution=True)
