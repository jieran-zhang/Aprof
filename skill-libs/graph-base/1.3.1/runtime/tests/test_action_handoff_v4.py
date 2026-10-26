"""共同计划的 CPU 反例；decision/v3 的完整比较另由独立 contract 测试覆盖。"""
from copy import deepcopy
import json
import shutil

import pytest

from aprof_runtime import bindings, bindings_v4
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash, file_hash
from test_action_decision import package, make_decision
from test_action_handoff_v3 import write_json


@pytest.fixture(scope='module')
def v4_package(package):
    """冻结来源只验一次；每个用例仍执行真实 router、scope 和链校验。"""
    root, artifact = package
    artifacts, config = bindings._routing_inputs(root)
    original_inputs, original_artifacts = bindings._routing_inputs, bindings._artifacts
    def cached_inputs(candidate, *, artifacts=None, routing_config=None):
        if bindings_v4.Path(candidate).resolve() != root.resolve():
            return original_inputs(candidate, artifacts=artifacts, routing_config=routing_config)
        if artifacts is not None and not bindings._same(artifacts, frozen_artifacts):
            raise GraphError('fixture 知识身份改变')
        if routing_config is not None and not bindings._same(routing_config, config):
            raise GraphError('fixture routing 身份改变')
        return deepcopy(frozen_artifacts), deepcopy(config)
    frozen_artifacts = artifacts
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(bindings, '_routing_inputs', cached_inputs)
        patch.setattr(bindings, '_artifacts', lambda candidate:deepcopy(frozen_artifacts) if bindings_v4.Path(candidate).resolve()==root.resolve() else original_artifacts(candidate))
        yield root, artifact


def rebind(chain):
    c1, c2, c3 = chain
    members = c2['selection']['members']
    instances = {i['instance_id']: i for i in c1['reasoning']['action_instances']}
    for member in members:
        member['instance'] = deepcopy(instances[member['instance']['instance_id']])
        member['instance_hash'] = content_hash(member['instance'])
    bind_compatibility(c2['selection'])
    c2['parent_hash'] = content_hash(c1)
    if c3 is not None:
        for member in c3['execution']['members']:
            member['instance_hash'] = content_hash(instances[member['instance_id']])
        bind_compatibility(c2['selection'],c3['execution'])
        c3['execution']['selection_hash'] = content_hash(c2['selection'])
        c3['parent_hash'] = content_hash(c2)


def bind_compatibility(selection,execution=None):
    identity=bindings_v4.compatibility_configuration(selection,execution=execution)
    rows={r['instance_id']:r for r in identity['members']}
    members=selection['members'] if execution is None else execution['members']
    for member in members:
        identifier=member['instance']['instance_id'] if execution is None else member['instance_id']
        member['compatibility'].update(instance_hash=rows[identifier]['instance_hash'],
            parameters_hash=rows[identifier]['parameters_hash'],implementation_hash=identity['implementation_hash'],plan_hash=identity['plan_hash'])
    joint=selection['joint_compatibility'] if execution is None else execution['joint_compatibility']
    for row in joint:row.update(plan_hash=identity['plan_hash'],configuration_hash=content_hash(identity))


def synthetic_timing(task,chain,folder=None):
    """仅测 outcome contract 的完整合成结构；这些数值不是硬件测量。"""
    folder=task if folder is None else folder
    evidence=write_json(folder/'cpu-contract-evidence.json',{'kind':'synthetic_contract_only','hardware_executed':False})
    request={'schema_version':1,'operator':'paper','candidate_id':chain[2]['candidate_id'],'protocol':'single_role_l2_clean_task_v1',
        'baseline_source_sha256':chain[0]['reasoning']['current']['implementation_ref']['sha256'],
        'candidate_source_sha256':chain[2]['execution']['implementation_source_ref']['sha256'],
        'declaration':evidence,'baseline_captures':[evidence],'candidate_captures':[evidence],
        'baseline_correctness':evidence,'candidate_correctness':evidence}
    request_ref=write_json(folder/'request.json',request)
    measured={'schema_version':1,'kind':'unified_timing_result','protocol':request['protocol'],
        'metric':'msprof.Task_Duration.complete_call','operator':'paper','candidate_id':request['candidate_id'],'request':request_ref,
        'evaluated_at':'2026-10-21T00:00:00+00:00','verdict':'inconclusive','speedup':1.0,'max_case_regression':0.0,
        'thresholds':{'min_speedup':1.03,'max_case_regression':0.03,'max_within_process_cv':0.05},
        'cases':[{'case_id':1,'baseline_capture_ref':evidence['sha256'],'candidate_capture_ref':evidence['sha256'],
            'baseline_median_us':100,'candidate_median_us':100,'speedup':1.0,'regression':0.0,
            'baseline_within_process_cv':0.0,'candidate_within_process_cv':0.0,'ab_gap_seconds':0}],
        'reasons':['合成结构测试，不代表真实计时或有效性能结论'],'authority':'performance_engineering_only',
        'replication_recommended':False,'uncertainty':'CPU contract fixture，没有运行硬件'}
    measured['decision_hash']=content_hash(measured)
    ref=write_json(folder/'timing.json',measured)
    ref.update(candidate_id=request['candidate_id'],protocol=request['protocol'])
    return request,measured,ref


@pytest.fixture
def sample(v4_package, tmp_path, monkeypatch):
    root, artifact = v4_package
    for schema in ['knowledge-handoff-v4']:
        shutil.copy(bindings_v4.Path(__file__).resolve().parents[2] / f'schemas/{schema}.schema.json', root / 'schemas')
    task = tmp_path / 'task'
    _, old = make_decision(root, artifact, task)
    c1, old2, old3 = deepcopy(old)
    reasoning = c1['reasoning']
    original = reasoning['action_instances'][0]
    other = deepcopy(original)
    other.update(instance_id='action-instance.two', hypothesis_id='temporary.two')
    other['targets'] = {k: 'tensor.y' if v == 'tensor.x' else v for k, v in other['targets'].items()}
    other['scope']['target_ids'] = ['tensor.y']
    other['evidence_bindings'] = {k: 'second.' + v for k, v in other['evidence_bindings'].items()}
    for key, fact in list(reasoning['facts'].items()):
        value = deepcopy(fact)
        value['scope']['target_ids'] = ['tensor.y']
        value['evidence_id'] = 'second.' + key if value['kind'] == 'raw' else value['evidence_id']
        value['derived_from'] = ['second.' + k for k in value['derived_from']]
        if value.get('components'):
            value['components'] = ['second.' + k for k in value['components']]
        reasoning['facts']['second.' + key] = value
    candidate = deepcopy(reasoning['candidates'][0])
    candidate.update(hypothesis_id='temporary.two', targets=['tensor.y'])
    candidate['scope']['target_ids'] = ['tensor.y']
    for field in ['support', 'counter', 'unknown', 'excluded_by']:
        candidate[field] = ['second.' + key for key in candidate[field]]
    reasoning['candidates'].append(candidate)
    reasoning['action_instances'].append(other)
    reasoning['current']['objects'].append({'object_id':'tensor.y', 'kind':'tensor', 'description':'第二个独立目标'})
    reasoning['current']['scope']['target_ids'] = ['tensor.x', 'tensor.y']
    plan = deepcopy(old2['selection']['parent_plan'])
    plan['scope']['target_ids'] = ['tensor.x', 'tensor.y']
    for instance in reasoning['action_instances']:
        instance['parent_plan_hash'] = content_hash(plan)
    raw = next(fact for fact in reasoning['facts'].values() if fact['kind'] == 'raw')
    reasoning['facts']['joint.review'] = {**deepcopy(raw), 'predicate':'joint.review', 'evidence_id':'joint.review',
        'scope':deepcopy(plan['scope']), 'state':True, 'derived_from':[]}
    scheme = {'id':'scheme.complete', 'members':[
        {'action_instance_id':i['instance_id']} for i in reasoning['action_instances']],
        'steps':[{'id':'step.complete', 'action_instance_ids':[i['instance_id'] for i in reasoning['action_instances']],
            'depends_on':[], 'guarantees':[]}]}
    c1.update(schema_version='aprof.handoff/v4', scheme_id=scheme['id'], scheme_hash=content_hash(scheme),
        decision_ref=write_json(task/'decision-v3.json',{'schema_version':'aprof.action-decision/v3'}), artifacts=[])
    monkeypatch.setattr(bindings_v4, '_decision', lambda *args, **kwargs:(scheme,{
        'selection_mode':'experiment','missing_safety':[], 'failed_safety':[], 'pending_required_evidence':[],
        'member_readiness':[{'instance_id':i['instance_id'],'missing_safety':[],'failed_safety':[],
            'pending_required_evidence':[]} for i in reasoning['action_instances']]}))
    members=[]
    for instance in reasoning['action_instances']:
        hint=deepcopy(old2['selection']['routing_hint'])
        members.append({'instance':deepcopy(instance),'instance_hash':content_hash(instance),'routing_hint':hint,
            'parallel_route':bindings.route_parallel(root,reasoning,instance['instance_id'],hint,task_root=task),
            'parallel':{'mode':'KEEP','entry_id':None},'compatibility':{'fact_bindings':[instance['evidence_bindings']['constraint.paper_combination_review']], 'rationale':'本成员原访问和所有权合法', 'instance_hash':content_hash(instance),'plan_hash':content_hash(plan)}})
    ids=[i['instance_id'] for i in reasoning['action_instances']]
    joint=[{'dimension':key,'member_instance_ids':ids,'fact_bindings':['joint.review'],
        'rationale':'核对共同域的布局、owner、生命周期，不从各成员独立合法直接推导','plan_hash':content_hash(plan)} for key in sorted(bindings_v4.JOINT_DIMENSIONS)]
    selected={'schema_version':'aprof.scheme-selection/v1','scheme_id':scheme['id'],'scheme_hash':content_hash(scheme),
        'routing_config_hash':old2['selection']['routing_config_hash'],'parallel':{'mode':'KEEP'},'members':members,
        'parent_plan':deepcopy(plan),'confirmed_plan':plan,'confirmed_plan_ref':write_json(task/'joint-plan.json',plan),
        'joint_compatibility':joint,'resource_lifetimes':[{'allocation_id':'ub.shared','group_id':'all','memory':'UB',
            'bytes':4096,'start':0,'end':2,'member_instance_ids':ids,'evidence_ref':deepcopy(raw['ref']) | {'locator':raw['ref']['locator']},
            'locator':'source buffer declaration', 'rationale':'同一物理buffer覆盖两成员，不重复计费'}]}
    selected['resource_lifetimes'][0]['evidence_ref'].pop('locator',None)
    bind_compatibility(selected)
    c2={'schema_version':'aprof.handoff/v4','stage':'C2','task_id':c1['task_id'],'candidate_id':None,'parent_hash':content_hash(c1),'artifacts':[],'selection':selected}
    routes={r['instance_id']:r['route'] for r in bindings_v4.route_optimization(root,reasoning,selected,task_root=task)['members']}
    executed=[]
    for member in members:
        identifier=member['instance']['instance_id']
        oldexec=old3['execution']
        changes=deepcopy(oldexec['actual_changes'])
        changes[0]['target_id']=member['instance']['scope']['target_ids'][0]
        executed.append({'instance_id':identifier,'instance_hash':member['instance_hash'],'optimization_route':routes[identifier],
            'optimization':deepcopy(oldexec['optimization']),'actual_parameters':deepcopy(oldexec['actual_parameters']),
            'actual_changes':changes,'compatibility':deepcopy(member['compatibility'])})
    execution={'schema_version':'aprof.scheme-execution/v1','scheme_id':scheme['id'],'scheme_hash':content_hash(scheme),
        'selection_hash':content_hash(selected),'members':executed,'implementation_source_ref':deepcopy(old3['execution']['implementation_source_ref']),
        'dispatch_plan':deepcopy(old3['execution']['dispatch_plan']),'actual_contracts':deepcopy(plan['contracts']),
        'changes':[],'joint_compatibility':deepcopy(joint),'guarantee_checks':[],'result':'implemented','executed_instances':ids}
    bind_compatibility(selected,execution)
    c3={'schema_version':'aprof.handoff/v4','stage':'C3','task_id':c1['task_id'],'candidate_id':'joint-candidate','parent_hash':content_hash(c2),'artifacts':[],'execution':execution}
    return root,artifact,task,(c1,c2,c3),scheme


def check(sample, full=True):
    root,_,task,chain,_=sample
    return bindings.validate_chain(root,*chain[:3 if full else 2],task_root=task)


def test_complete_scheme_retains_each_instances_actual_docs(sample):
    result=check(sample)
    assert result['status']=='implemented'
    assert len(result['actual_combination']['members'])==2
    assert result['resource_peaks'][0]['peak_bytes']==4096
    for member in result['actual_combination']['members']:
        assert member['optimization']['entry_ids']==['implementation.memory-transfer.coalesce']
        assert member['optimization_snapshots'][0]['id']=='implementation.memory-transfer.coalesce'
    assert check(sample,False)['status']=='ready'


@pytest.mark.parametrize('damage',['missing_member','extra_member','borrow_instance','hint_facts','fake_route','foreign_recipe','wrong_target','plan_boundary','plan_ref','mixed_version','joint_missing','joint_partial','shared_duplicate','overlap','budget_missing','bad_interval','dispatch'])
def test_illegal_union_shared_resources_and_identity_are_rejected(sample,damage):
    _,_,_,chain,_=sample;c1,c2,c3=chain;s=c2['selection'];e=c3['execution']
    if damage=='missing_member':e['members'].pop()
    elif damage=='extra_member':e['members'].append(deepcopy(e['members'][0]))
    elif damage=='borrow_instance':e['members'][1]['instance_hash']=e['members'][0]['instance_hash']
    elif damage=='hint_facts':s['members'][0]['routing_hint']['facts']={'constraint.capacity':True}
    elif damage=='fake_route':e['members'][1]['optimization_route']=dict(e['members'][1]['optimization_route'],context_hash='sha256:'+'0'*64)
    elif damage=='foreign_recipe':e['members'][1]['optimization']['entry_ids']=['implementation.vector-api.cast']
    elif damage=='wrong_target':e['members'][1]['actual_changes'][0]['target_id']='tensor.x'
    elif damage=='plan_boundary':e['actual_contracts']['ownership']='other';e['changes']=[{'dimension':'ownership','before':'unchanged','after':'other'}]
    elif damage=='plan_ref':s['confirmed_plan_ref']['sha256']='sha256:'+'0'*64
    elif damage=='mixed_version':c3['schema_version']='aprof.handoff/v3'
    elif damage=='joint_missing':s['joint_compatibility'].pop()
    elif damage=='joint_partial':s['joint_compatibility'][0]['member_instance_ids']=[s['members'][0]['instance']['instance_id']]
    elif damage=='shared_duplicate':s['resource_lifetimes'].append(deepcopy(s['resource_lifetimes'][0]))
    elif damage=='overlap':
        row=deepcopy(s['resource_lifetimes'][0]);row['allocation_id']='ub.other';s['resource_lifetimes'].append(row)
    elif damage=='budget_missing':s['resource_lifetimes']=[]
    elif damage=='bad_interval':s['resource_lifetimes'][0]['end']=0
    elif damage=='dispatch':e['dispatch_plan']['fallback']['kernel_entry']='other'
    if damage not in {'mixed_version','borrow_instance','missing_member','extra_member'}:rebind(chain)
    with pytest.raises(GraphError):check(sample)


def test_disjoint_lifetimes_reuse_capacity_without_naive_sum(sample):
    _,_,_,chain,_=sample;s=chain[1]['selection'];row=s['resource_lifetimes'][0];row['end']=1
    other=deepcopy(row);other.update(allocation_id='ub.next',start=1,end=2)
    s['resource_lifetimes'].append(other);rebind(chain)
    assert check(sample)['resource_peaks'][0]['peak_bytes']==4096


def guarantee(sample,predicate='constraint.capacity',expected=True):
    _,_,task,chain,scheme=sample;c1,c2,c3=chain
    target=c1['reasoning']['action_instances'][1]
    fact_id=target['evidence_bindings'][predicate]
    c1['reasoning']['facts'][fact_id]['state']='unknown'
    target['status']='conditional';target['unknowns']=[predicate]
    candidate=next(c for c in c1['reasoning']['candidates'] if c['hypothesis_id']==target['hypothesis_id'])
    candidate['support'].remove(fact_id);candidate['unknown'].append(fact_id)
    g={'id':'guarantee.ready','predicate':predicate,'expected_state':expected,'target_instance_ids':[target['instance_id']],
       'check_method':'核对最终候选的声明和地址域'}
    scheme['steps'][0]['guarantees']=[g]
    c1['scheme_hash']=content_hash(scheme);c2['selection']['scheme_hash']=c1['scheme_hash'];c3['execution']['scheme_hash']=c1['scheme_hash']
    rebind(chain)
    c2['selection']['members'][1]['parallel_route']=bindings.route_parallel(sample[0],c1['reasoning'],target['instance_id'],c2['selection']['members'][1]['routing_hint'],task_root=task)
    routes={m['instance_id']:m['route'] for m in bindings_v4.route_optimization(sample[0],c1['reasoning'],c2['selection'],task_root=task)['members']}
    for member in c3['execution']['members']:member['optimization_route']=routes[member['instance_id']]
    c3['execution']['guarantee_checks']=[{'guarantee_id':g['id'],'step_id':scheme['steps'][0]['id'],'target_instance_id':target['instance_id'],
        'instance_hash':content_hash(target),'template_hash':target['template_hash'],'scope':deepcopy(target['scope']),
        'parameters_hash':content_hash(c3['execution']['members'][1]['actual_parameters']),'plan_hash':content_hash(c2['selection']['confirmed_plan']),
        'configuration_hash':bindings_v4.configuration_hash(c2['selection'],execution=c3['execution']),
        'implementation_ref':deepcopy(c3['execution']['implementation_source_ref']),'predicate':predicate,'expected_state':expected,
        'actual_state':expected,'source_locator':'lines:1','check_method':'阅读最终源码容量声明','rationale':'只核实该候选该实例，未自动证明C++'}]
    rebind(chain)


def test_unknown_enters_c2_but_only_precise_final_guarantee_can_authorize_c3(sample):
    guarantee(sample)
    assert check(sample,False)['status']=='conditional'
    assert check(sample)['status']=='implemented'
    sample[3][2]['execution']['guarantee_checks']=[];rebind(sample[3])
    with pytest.raises(GraphError,match='保证'):check(sample)


@pytest.mark.parametrize('damage',['wrong_scope','wrong_params','wrong_source','wrong_plan','wrong_predicate','wrong_state','wrong_instance','wrong_locator','false_precondition'])
def test_planned_guarantee_is_not_a_fact_and_cannot_borrow_readiness(sample,damage):
    guarantee(sample);_,_,_,chain,_=sample;c1,c2,c3=chain;item=c3['execution']['guarantee_checks'][0]
    if damage=='wrong_scope':item['scope']['target_ids']=['tensor.x']
    elif damage=='wrong_params':item['parameters_hash']='sha256:'+'0'*64
    elif damage=='wrong_source':item['implementation_ref']=deepcopy(c1['reasoning']['current']['implementation_ref'])
    elif damage=='wrong_plan':item['plan_hash']='sha256:'+'0'*64
    elif damage=='wrong_predicate':item['predicate']='constraint.other'
    elif damage=='wrong_state':item['actual_state']=False
    elif damage=='wrong_instance':item['target_instance_id']=c1['reasoning']['action_instances'][0]['instance_id']
    elif damage=='wrong_locator':item['source_locator']='lines:999'
    elif damage=='false_precondition':c1['reasoning']['facts']['second.constraint.capacity']['state']=False
    rebind(chain)
    with pytest.raises(GraphError):check(sample)


def test_all_keep_noop_and_plan_change_o_keep_are_distinct(sample):
    root,_,task,chain,_=sample;c1,c2,c3=chain
    for member in c3['execution']['members']:member['optimization']={'mode':'KEEP','entry_ids':[]};member['actual_changes']=[]
    c3['execution'].update(result='NOOP',executed_instances=[],implementation_source_ref=deepcopy(c1['reasoning']['current']['implementation_ref']))
    c3['candidate_id']=None
    source=c1['reasoning']['current']['implementation_ref']['sha256']
    c3['execution']['dispatch_plan'].update(source_hash=source,implementation_source_hash=source)
    rebind(chain)
    assert check(sample)['status']=='NOOP'
    c3['candidate_id']='fake';rebind(chain)
    with pytest.raises(GraphError,match='KEEP'):check(sample)


def test_result_link_preserves_scheme_all_member_docs_and_exact_source(sample):
    root,_,task,chain,_=sample
    request,measured,ref=synthetic_timing(task,chain)
    result=bindings_v4.link_result_v4(*chain,ref,root=root,task_root=task)
    assert len(result['executed_instances'])==2 and not result['causal_claim']
    assert result['attribution']=='scheme_level'
    assert len(result['actual_combination']['members'])==2
    request['candidate_source_sha256']='sha256:'+'0'*64
    measured['request']=write_json(task/'request.json',request)
    measured['decision_hash']=content_hash({k:v for k,v in measured.items() if k!='decision_hash'})
    ref.update(write_json(task/'timing.json',measured))
    with pytest.raises(GraphError,match='源码'):bindings_v4.link_result_v4(*chain,ref,root=root,task_root=task)


def test_wrong_expected_bool_cannot_fill_unknown_required_true(sample):
    guarantee(sample, expected=False)
    with pytest.raises(GraphError, match='期望 bool'):check(sample)


def test_changed_plan_with_member_o_keep_still_implements_plan(sample):
    _,_,task,chain,_=sample;c1,c2,c3=chain;s=c2['selection'];e=c3['execution']
    s['parallel']['mode']='CHANGE'
    for member in s['members']:member['parallel']={'mode':'CHANGE','entry_id':'planning.elementwise.continuous'}
    plan=s['confirmed_plan'];plan['contracts']['algorithm']='paper-new'
    plan['parallel_plan']['groups'][0]['algorithm']='paper-new'
    plan['dispatch_plan']['parallel_plan_ref']=content_hash(plan['parallel_plan'])
    s['confirmed_plan_ref']=write_json(task/'joint-plan.json',plan)
    e['actual_contracts']=deepcopy(plan['contracts'])
    e['dispatch_plan']=deepcopy(plan['dispatch_plan'])
    source=e['implementation_source_ref']['sha256']
    e['dispatch_plan'].update(source_hash=source,implementation_source_hash=source,plan_basis_source_hash=plan['scope']['parent_implementation_hash'])
    for member in e['members']:member['optimization']={'mode':'KEEP','entry_ids':[]}
    rebind(chain)
    routes=bindings_v4.route_optimization(sample[0],c1['reasoning'],s,task_root=task)
    for member,route in zip(e['members'],routes['members']):member['optimization_route']=route['route']
    assert check(sample)['status']=='implemented'


def test_relative_request_is_relative_to_result_not_ref_file_and_absolute_result_is_allowed(sample):
    root,_,task,chain,_=sample
    sub=task/'measure';sub.mkdir()
    request,measured,ref=synthetic_timing(task,chain,sub)
    ref['path']='measure/timing.json'
    ref_path=task/'timing-ref.json';write_json(ref_path,ref)
    assert bindings_v4.link_result_v4(*chain,ref,root=root,task_root=task,timing_ref=ref_path)['candidate_id']=='joint-candidate'
    ref['path']=str(sub/'timing.json')
    assert bindings_v4.link_result_v4(*chain,ref,root=root,task_root=task,timing_ref=ref_path)['candidate_id']=='joint-candidate'


# 下面两个测试不 mock decision；覆盖 D6、真实 v3 比较、真实路由与 v4 全链。
from test_action_decision_v3 import scheme_package, make_v3_decision, add_member, add_distinct_action
from test_action_decision import persist_reasoning


def real_chain(root,artifact,task,*,multiple,distinct=False,workload=None,routing_features=None,routing_structure=None):
    decision,chain=make_v3_decision(root,artifact,task,workload=workload,routing_features=routing_features,routing_structure=routing_structure)
    if multiple:
        if distinct:add_distinct_action(decision,chain,task,artifact,root=root)
        else:add_member(decision,chain,task)
    c1,old2,old3=chain
    reasoning=c1['reasoning'];scheme=decision['schemes'][0]
    ids=[m['action_instance_id'] for m in scheme['members']]
    fact=deepcopy(reasoning['facts']['constraint.paper_combination_review'])
    fact.update(predicate='joint.review',evidence_id='joint.review',scope=deepcopy(reasoning['current']['scope']))
    reasoning['facts']['joint.review']=fact
    persist_reasoning(decision,chain,task)
    c1.update(schema_version='aprof.handoff/v4',decision_ref=write_json(task/'decision-v3.json',decision),
        scheme_id=scheme['id'],scheme_hash=content_hash(scheme))
    c1['artifacts']=[c1['decision_ref']]
    old=old2['selection'];plan=deepcopy(old['confirmed_plan']);members=[]
    for instance in reasoning['action_instances']:
        if instance['instance_id'] not in ids:continue
        hint=bindings.default_hint(root,instance['action_id'])
        members.append({'instance':deepcopy(instance),'instance_hash':content_hash(instance),'routing_hint':hint,
            'parallel_route':bindings_v4.route_parallel(root,reasoning,instance['instance_id'],hint,task_root=task),
            'parallel':deepcopy(old['parallel']),'compatibility':dict(deepcopy(old['compatibility']),instance_hash=content_hash(instance),plan_hash=content_hash(plan))})
    joint=[{'dimension':d,'member_instance_ids':ids,'fact_bindings':['joint.review'],
        'rationale':'明确核对共同计划中本轮完整方案兼容性','plan_hash':content_hash(plan)} for d in sorted(bindings_v4.JOINT_DIMENSIONS)]
    selected={'schema_version':'aprof.scheme-selection/v1','scheme_id':scheme['id'],'scheme_hash':content_hash(scheme),
        'routing_config_hash':old['routing_config_hash'],'parallel':{'mode':'KEEP'},'members':members,
        'parent_plan':deepcopy(old['parent_plan']),'confirmed_plan':plan,'confirmed_plan_ref':deepcopy(old['confirmed_plan_ref']),
        'joint_compatibility':joint,'resource_lifetimes':[{'allocation_id':'ub.all','group_id':'all','memory':'UB','bytes':4096,
        'start':0,'end':2,'member_instance_ids':ids,'evidence_ref':{k:fact['ref'][k] for k in ('path','sha256')},
        'locator':'fixture buffer allocation','rationale':'共同allocation只计一次'}]}
    bind_compatibility(selected)
    c2={'schema_version':'aprof.handoff/v4','stage':'C2','task_id':c1['task_id'],'candidate_id':None,
        'parent_hash':content_hash(c1),'artifacts':[],'selection':selected}
    routes={r['instance_id']:r['route'] for r in bindings_v4.route_optimization(root,reasoning,selected,task_root=task)['members']}
    olde=old3['execution'];members_exec=[]
    for member in members:
        i=member['instance']['instance_id']
        members_exec.append({'instance_id':i,'instance_hash':member['instance_hash'],'optimization_route':routes[i],
            'optimization':deepcopy(olde['optimization']),'actual_parameters':deepcopy(olde['actual_parameters']),
            'actual_changes':deepcopy(olde['actual_changes']),'compatibility':dict(deepcopy(olde['compatibility']),instance_hash=member['instance_hash'],plan_hash=content_hash(plan))})
        if member['instance']['action_id']=='action.batch_writeback':
            members_exec[-1]['actual_changes'][0].update(description='同owner输出全部完成后合并连续写回，保留有效输出域',intended_effect='减少写回发射；新增存活计入共同容量')
    execution={'schema_version':'aprof.scheme-execution/v1','scheme_id':scheme['id'],'scheme_hash':content_hash(scheme),
        'selection_hash':content_hash(selected),'members':members_exec,'implementation_source_ref':deepcopy(olde['implementation_source_ref']),
        'dispatch_plan':deepcopy(olde['dispatch_plan']),'actual_contracts':deepcopy(olde['actual_contracts']),
        'changes':deepcopy(olde['changes']),'joint_compatibility':deepcopy(joint),'guarantee_checks':[],
        'result':'implemented','executed_instances':ids}
    bind_compatibility(selected,execution)
    c3={'schema_version':'aprof.handoff/v4','stage':'C3','task_id':c1['task_id'],'candidate_id':'real-v4-candidate',
        'parent_hash':content_hash(c2),'artifacts':[],'execution':execution}
    return decision,(c1,c2,c3)


@pytest.mark.parametrize('multiple',[False,True])
def test_d6_real_decision_routes_and_handoff_chain(scheme_package,tmp_path,multiple):
    root,artifact=scheme_package;task=tmp_path/'real-task'
    decision,chain=real_chain(root,artifact,task,multiple=multiple)
    result=bindings.validate_chain(root,*chain,task_root=task)
    assert result['status']=='implemented'
    assert len(result['actual_combination']['members'])==(2 if multiple else 1)
    decision['schema_version']='aprof.action-decision/v2'
    chain[0]['decision_ref']=write_json(task/'decision-v3.json',decision)
    chain[0]['artifacts']=[chain[0]['decision_ref']];rebind(chain)
    with pytest.raises(GraphError,match='decision/v3'):bindings.validate_chain(root,*chain,task_root=task)


def test_two_distinct_registered_actions_use_their_own_conditions_and_routes(scheme_package,tmp_path):
    root,artifact=scheme_package;task=tmp_path/'distinct-task'
    decision,chain=real_chain(root,artifact,task,multiple=True,distinct=True)
    result=bindings.validate_chain(root,*chain,task_root=task)
    assert result['status']=='implemented'
    assert {m['instance']['action_id'] for m in chain[1]['selection']['members']}=={'action.coalesce_contiguous_transfers','action.batch_writeback'}
    assert all(m['optimization_snapshots'][0]['id']=='implementation.memory-transfer.coalesce' for m in result['actual_combination']['members'])
    second=chain[0]['reasoning']['action_instances'][1]
    second['evidence_bindings']['constraint.output_ownership']=second['evidence_bindings']['constraint.capacity']
    rebind(chain)
    with pytest.raises(GraphError):bindings.validate_chain(root,*chain,task_root=task)


def test_parameters_within_freedom_require_updated_member_and_joint_review(sample):
    _,_,_,chain,_=sample;c1,c2,c3=chain;s=c2['selection'];e=c3['execution']
    e['members'][1]['actual_parameters']['tile']=128
    with pytest.raises(GraphError,match='兼容性'):check(sample)
    identity=bindings_v4.compatibility_configuration(s,execution=e)
    second=next(r for r in identity['members'] if r['instance_id']==e['members'][1]['instance_id'])
    e['members'][1]['compatibility']['parameters_hash']=second['parameters_hash']
    with pytest.raises(GraphError,match='配置'):check(sample)
    bind_compatibility(s,e)
    assert check(sample)['status']=='implemented'


def test_changed_source_cannot_reuse_prior_configuration_review(sample):
    _,_,task,chain,_=sample;s=chain[1]['selection'];e=chain[2]['execution']
    (task/'candidate-next.cpp').write_text('new complete implementation\n')
    e['implementation_source_ref']={'path':'candidate-next.cpp','sha256':file_hash(task/'candidate-next.cpp')}
    source=e['implementation_source_ref']['sha256']
    e['dispatch_plan'].update(source_hash=source,implementation_source_hash=source)
    with pytest.raises(GraphError,match='兼容性'):check(sample)
    bind_compatibility(s,e)
    assert check(sample)['status']=='implemented'


def test_keep_reuses_complete_plan_for_unmodified_targets_without_inventing_actions(sample):
    _,_,task,chain,scheme=sample;c1,c2,c3=chain;s=c2['selection'];e=c3['execution']
    selected=s['members'][0]['instance']['instance_id']
    scheme['members']=scheme['members'][:1];scheme['steps'][0]['action_instance_ids']=[selected]
    c1['scheme_hash']=content_hash(scheme);s['scheme_hash']=c1['scheme_hash'];e['scheme_hash']=c1['scheme_hash']
    s['members']=s['members'][:1];e['members']=e['members'][:1];e['executed_instances']=[selected]
    for rows in [s['joint_compatibility'],e['joint_compatibility']]:
        for row in rows:row['member_instance_ids']=[selected]
    s['resource_lifetimes'][0]['member_instance_ids']=[selected]
    rebind(chain)
    assert set(s['confirmed_plan']['scope']['target_ids'])=={'tensor.x','tensor.y'}
    assert check(sample)['status']=='implemented'
    # 保留完整计划不扩展这一个实例的可修改目标。
    e['members'][0]['actual_changes'][0]['target_id']='tensor.y'
    with pytest.raises(GraphError,match='其他目标'):check(sample)
    e['members'][0]['actual_changes'][0]['target_id']='tensor.x'
    # 也不能借复用计划超出当前工程理解范围。
    s['confirmed_plan']['scope']['target_ids'].append('tensor.outside')
    s['parent_plan']=deepcopy(s['confirmed_plan'])
    c1['reasoning']['action_instances'][0]['parent_plan_hash']=content_hash(s['parent_plan'])
    s['confirmed_plan_ref']=write_json(task/'joint-plan.json',s['confirmed_plan'])
    rebind(chain)
    with pytest.raises(GraphError,match='目标'):check(sample)


def test_v4_explicit_binding_resolves_duplicate_predicates_without_changing_reasoning(sample):
    root,artifact,task,chain,_=sample;reasoning=chain[0]['reasoning'];instance=reasoning['action_instances'][0]
    duplicate=deepcopy(reasoning['facts']['constraint.capacity'])
    duplicate.update(evidence_id='alternate.capacity',state='unknown')
    reasoning['facts']['alternate.capacity']=duplicate
    before=content_hash(reasoning)
    context=bindings_v4.routing_context(root,reasoning,instance,task_root=task,artifact=artifact)
    assert context['facts']['constraint.capacity']['state'] is True
    assert content_hash(reasoning)==before
    assert context['source_context_ref']==reasoning['source_context_ref']
    del instance['evidence_bindings']['constraint.capacity'];instance['status']='conditional';instance['unknowns']=['constraint.capacity']
    with pytest.raises(GraphError,match='显式消解'):bindings_v4.routing_context(root,reasoning,instance,task_root=task,artifact=artifact)


@pytest.mark.parametrize('damage',['incomplete_result','bad_result_hash','incomplete_request'])
def test_result_link_does_not_accept_minimal_or_modified_timing_json(sample,damage):
    root,_,task,chain,_=sample
    request,measured,ref=synthetic_timing(task,chain)
    if damage=='incomplete_result':del measured['cases']
    elif damage=='bad_result_hash':measured['speedup']=2.0
    else:
        del request['declaration'];measured['request']=write_json(task/'request.json',request)
        measured['decision_hash']=content_hash({k:v for k,v in measured.items() if k!='decision_hash'})
    ref.update(write_json(task/'timing.json',measured))
    with pytest.raises(GraphError):bindings_v4.link_result_v4(*chain,ref,root=root,task_root=task)


def test_real_v3_dependency_remains_unknown_until_final_c3_source_check(scheme_package,tmp_path):
    root,artifact=scheme_package;task=tmp_path/'real-guarantee'
    d,chain=real_chain(root,artifact,task,multiple=True,distinct=True)
    c1,c2,c3=chain;r=c1['reasoning'];s=d['schemes'][0];instance=r['action_instances'][1];op=d['opportunities'][1]
    predicate='constraint.capacity';fact_id=instance['evidence_bindings'][predicate]
    r['facts'][fact_id]['state']='unknown';instance['status']='conditional';instance['unknowns']=[predicate]
    unknown={'id':'u.writeback.capacity','kind':'implementation_safety','fact':predicate,'expected_state':True,
        'statement':'批量写回的同时存活未核实','affects':'新增buffer可能超预算','resolution':'check_before_implementation'}
    op['unknowns'].append(unknown)
    d['evidence_requests'].append({'id':'check.writeback.capacity','opportunity_ids':[op['id']],'unknown_ids':[unknown['id']],
        'method':'核对共同计划与最终源码的同时存活','discriminating_results':[{'outcome':'容量满足','decision_effect':'允许实施'},
        {'outcome':'容量超限','decision_effect':'返回C2缩块'}],'required_before_implementation':True,'status':'pending',
        'resolution':'not_run','result_ref':None,'finding':'C2保留unknown，计划保证不是事实','defer_reason':None})
    guarantee={'id':'guarantee.writeback.capacity','predicate':predicate,'expected_state':True,
        'target_instance_ids':[instance['instance_id']],'check_method':'在最终候选核对资源声明'}
    s['steps'][0]['guarantees']=[guarantee]
    d['reasoning_ref']=write_json(task/'reasoning.json',r);d['reasoning_hash']=content_hash(r)
    c1['decision_ref']=write_json(task/'decision-v3.json',d);c1['artifacts']=[c1['decision_ref']]
    c1['scheme_hash']=content_hash(s);c2['selection']['scheme_hash']=c1['scheme_hash'];c3['execution']['scheme_hash']=c1['scheme_hash']
    rebind(chain)
    for member in c2['selection']['members']:
        member['parallel_route']=bindings_v4.route_parallel(root,r,member['instance']['instance_id'],member['routing_hint'],task_root=task)
    routes={m['instance_id']:m['route'] for m in bindings_v4.route_optimization(root,r,c2['selection'],task_root=task)['members']}
    for member in c3['execution']['members']:member['optimization_route']=routes[member['instance_id']]
    rebind(chain)
    assert bindings.validate_chain(root,c1,c2,task_root=task)['status']=='conditional'
    with pytest.raises(GraphError):bindings.validate_chain(root,*chain,task_root=task)
    c3['execution']['guarantee_checks']=[{'guarantee_id':guarantee['id'],'step_id':s['steps'][0]['id'],
        'target_instance_id':instance['instance_id'],'instance_hash':content_hash(instance),'template_hash':instance['template_hash'],
        'scope':deepcopy(instance['scope']),'parameters_hash':content_hash(c3['execution']['members'][1]['actual_parameters']),
        'plan_hash':content_hash(c2['selection']['confirmed_plan']),'implementation_ref':deepcopy(c3['execution']['implementation_source_ref']),
        'configuration_hash':bindings_v4.configuration_hash(c2['selection'],execution=c3['execution']),
        'predicate':predicate,'expected_state':True,'actual_state':True,'source_locator':'lines:1',
        'check_method':guarantee['check_method'],'rationale':'CPU合成源声明绑定测试，不宣称证明任意C++或硬件性能'}]
    assert bindings.validate_chain(root,*chain,task_root=task)['status']=='implemented'
    assert r['facts'][fact_id]['state']=='unknown'


def test_producer_parameter_change_invalidates_consumers_old_guarantee(sample):
    guarantee(sample)
    assert check(sample)['status']=='implemented'
    selection=sample[3][1]['selection'];execution=sample[3][2]['execution']
    execution['members'][0]['actual_parameters']['tile']=128
    bind_compatibility(selection,execution)
    # 已重审成员/共同兼容，也必须重新核实依赖此生产步骤的消费者保证。
    with pytest.raises(GraphError,match='保证核实'):check(sample)
    execution['guarantee_checks'][0]['configuration_hash']=bindings_v4.configuration_hash(selection,execution=execution)
    assert check(sample)['status']=='implemented'
