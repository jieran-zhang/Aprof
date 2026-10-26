"""v2 比较真正绑定 workload/分析项；性能未知不拒绝，反馈不能冒充收益。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime import action_decision
from aprof_runtime.action_decision_v2 import validate_analysis, workload_case_ids
from aprof_runtime.errors import GraphError
from aprof_runtime.knowledge import validate_schema
from aprof_runtime.jsonio import file_hash
from test_action_decision import make_decision, package, r2, safety_unknown
from test_action_handoff_v3 import write_json


def v2_fields(decision, reasoning):
    """只补合成分析样例，不改动原机会的 Problem/Action；生产回放须自行填写源码分析。"""
    decision = deepcopy(decision)
    decision['schema_version'] = 'aprof.action-decision/v2'
    fact = decision['opportunities'][0]['source_fact_ids'][0]
    quantity = {'mode':'symbolic','expression':'N/B','unit':'calls',
                'symbols':[{'name':'N','meaning':'连续元素数','unit':'elements'},
                           {'name':'B','meaning':'合并粒度','unit':'elements/call'}],
                'basis':'source_logical','fact_ids':[fact]}
    work = {'id':'base','stage_id':'copy','domain_ids':['all'],'change':'baseline',
            'quantity':quantity,'explanation':'按源码循环计算调用数，不是实际时间'}
    decision['path_overview'] = {'workload_ref':deepcopy(reasoning['current']['workload_ref']),
        'case_ids':['singleton'], 'domains':[{'id':'all','case_ids':['singleton'],
        'predicate':'全部当前连续输入','supported_scope':'同连续布局且容量满足','fact_ids':[fact]}],
        'stages':[{'id':'copy','domain_ids':['all'],'fact_ids':[fact],'behavior':'连续段复制'}],
        'baseline_work':[work]}
    for o in decision['opportunities']:
        o['case_ids']=['singleton']
        reduced=deepcopy(work);reduced.update(id='reduction',change='reduced')
        o['analysis']={'intent_gap':None,'work_delta':[reduced],
            'coverage':[{'id':'coverage.all','domain_id':'all','status':'affected','region':'本段复制循环','fact_ids':[fact]}],
            'tradeoffs':[{'id':'ub','domain_ids':['all'],'dimension':'UB同时存活',
                'change':dict(quantity,mode='qualitative',expression='更大连续块可能增加片上驻留',unit='bytes',symbols=[]),
                'consequence':'容量超限时收缩块，收益未知不阻断分析'}],
            'residuals':[], 'no_alternative_reason':'已审阅当前完整路径，只有一个独立复制阶段；不凑候选数量'}
    selected=decision['selection']['opportunity_id']
    decision['selection']['comparison_basis']=[{'opportunity_id':selected,'item_ids':[item],
        'role':role,'decision_effect':effect,'reversal_condition':'容量增大超过预算则回 C2 缩块'}
        for item,role,effect in [('reduction','benefit','减少可数调用，值得试验'),
                                ('ub','cost','先验证容量后才实施'),('coverage.all','coverage','当前域全部受影响，不宣称其余布局收益')]]
    return decision


def attempt_identity(decision):
    a=decision['previous_feedback']['reassessment']['attempt']
    return {'parent_implementation_hash':a['parent_ref']['sha256'],'implementation_hash':a['implementation_ref']['sha256'] if a['implementation_ref'] else None,'workload_hash':a['workload_ref']['sha256']}


def feedback_fields(decision):
    decision['previous_feedback']['reassessment']={
        'attempt':{'parent_ref':deepcopy(decision['current_parent_ref']),'implementation_ref':None,'change_ref':None,'workload_ref':deepcopy(decision['path_overview']['workload_ref'])},
        'structure':{'state':'not_implemented','evidence_refs':[],'finding':'尚无实际补丁'},
        'correctness':{'state':'not_tested','evidence_refs':[],'finding':'未运行原oracle'},
        'measured_domain_ids':[], 'measured_case_ids':[],
        'mechanisms':[{'hypothesis_id':decision['opportunities'][0]['hypothesis_id'],
            'judgement':'undetermined','basis':'static','evidence_refs':[],'finding':'来源足以计划，尚无实验'}],
        'attribution':{'kind':'unmeasured','limits':'不将源码工作减少等同于收益'},
        'next_step':{'kind':'collect_evidence','return_to':'C1','retained':'原始实现',
            'reopened':'最小合法容量与残余工作', 'opportunity_ids':[decision['opportunities'][0]['id']],
            'discriminating_prediction_ids':[],'reason':'未测时先完成源码静态核查'}}
    return decision


@pytest.fixture
def sample(package,tmp_path,monkeypatch):
    root,artifact=package
    task=tmp_path/'task'
    d,chain=make_decision(root,artifact,task)
    d=v2_fields(d,chain[0]['reasoning'])
    # 所有身份/冻结来源/实例/false前提仍走真实v1共享链；只隔离测试发布版本策略。
    monkeypatch.setattr(action_decision,'required_decision_version',lambda artifact:'aprof.action-decision/v2')
    return root,artifact,task,d,chain


def check(sample,implementation=False):
    root,_,task,d,_=sample
    return action_decision.validate_decision(root,d,task_root=task,implementation=implementation)


def test_v2_source_known_performance_unknown_can_implement(sample):
    assert check(sample,True)['status']=='ready'


def test_version_dispatch_is_explicit():
    assert action_decision.required_decision_version({'version':'v0004'}) is None
    assert action_decision.required_decision_version({'version':'v0005'})=='aprof.action-decision/v1'
    assert action_decision.required_decision_version({'version':'v0006'})=='aprof.action-decision/v2'
    with pytest.raises(GraphError): action_decision.decision_schema({'schema_version':'unknown'})


@pytest.mark.parametrize('mutation', ['missing_case','overlap','missing_domain','wrong_role','missing_cost','wrong_fact','wrong_workload','wrong_case_coverage','no_units','symbol_no_definition','untracked_stage'])
def test_comparison_is_not_unbound_form_fields(sample,mutation):
    d=sample[3];a=d['opportunities'][0]['analysis'];p=d['path_overview']
    if mutation=='missing_case': p['case_ids']=['other']
    if mutation=='overlap': p['domains'].append(dict(p['domains'][0],id='also'))
    if mutation=='missing_domain': a['coverage'][0]['domain_id']='missing'
    if mutation=='wrong_role': d['selection']['comparison_basis'][0]['item_ids']=['ub']
    if mutation=='missing_cost': d['selection']['comparison_basis'].pop(1)
    if mutation=='wrong_fact': a['work_delta'][0]['quantity']['fact_ids']=['not-present']
    if mutation=='wrong_workload': p['workload_ref']['sha256']='sha256:'+'0'*64
    if mutation=='wrong_case_coverage': d['opportunities'][0]['case_ids']=['other']
    if mutation=='no_units': a['work_delta'][0]['quantity']['unit']=''
    if mutation=='symbol_no_definition': a['work_delta'][0]['quantity']['symbols']=[]
    if mutation=='untracked_stage': p['stages'].append(dict(p['stages'][0],id='unreviewed'))
    with pytest.raises(GraphError): check(sample)


def test_partial_coverage_retains_residual_and_affects_selection(sample):
    d=sample[3];a=d['opportunities'][0]['analysis'];a['coverage'][0]['status']='partial'
    with pytest.raises(GraphError,match='残余'): check(sample)
    a['residuals']=[{'id':'remaining','domain_ids':['all'],'remaining_work':'尾部仍走原路径',
                    'next_step':'比较尾部占比和补齐代价','fact_ids':d['opportunities'][0]['source_fact_ids']}]
    with pytest.raises(GraphError,match='残余'): check(sample)
    d['selection']['comparison_basis'].append({'opportunity_id':d['opportunities'][0]['id'],
        'item_ids':['remaining'],'role':'residual','decision_effect':'先优化主体，后续审查尾部',
        'reversal_condition':'尾部主导时改选更完整方案'})
    assert check(sample)['status']=='ready'


def test_unregistered_alternative_is_compared_but_cannot_enter_po(sample):
    d=sample[3];main=d['opportunities'][0];alt=deepcopy(main)
    alt.update(id='unregistered',action_id=None,action_instance_id=None,performance_hypotheses=[],unknowns=[],
               disposition='considered',strongest_alternative_id=main['id'])
    alt['analysis']['intent_gap']='需要独立语义，现有 Action 不足'
    main['strongest_alternative_id']=alt['id'];d['opportunities'].append(alt)
    with pytest.raises(GraphError,match='最强替代'): check(sample)
    d['selection']['comparison_basis'].append({'opportunity_id':alt['id'],'item_ids':['reduction'],
        'role':'alternative','decision_effect':'先做已注册合法方向；此意图提交提案',
        'reversal_condition':'独立意图审查完成且覆盖更优则重新选择'})
    assert check(sample)['opportunity_count']==2
    main['disposition']='considered';alt['disposition']='selected';d['selection'].update(opportunity_id=alt['id'],action_instance_id=None)
    for b in d['selection']['comparison_basis']:
        b['opportunity_id']=alt['id'] if b['role']!='alternative' else main['id']
    d['knowledge_use'][0]['opportunity_ids'].append(alt['id'])
    with pytest.raises(GraphError,match='未注册'): check(sample)
    d['selection']['mode']='collect_evidence'
    assert check(sample)['status']=='conditional'


def test_unknown_safety_still_blocks_implementation(sample):
    root,_,task,d,chain=sample
    safety_unknown(d,chain,task)
    assert check(sample)['status']=='conditional'
    with pytest.raises(GraphError): check(sample,True)


def test_r2_unmeasured_reopens_comparison_without_forced_action_change(sample):
    root,_,task,d,chain=sample
    next_d=feedback_fields(r2(d,task));sample=(root,sample[1],task,next_d,chain)
    assert check(sample)['selection_mode']=='conditional_plan'
    next_d['previous_feedback']['reassessment']['next_step'].update(kind='continue',discriminating_prediction_ids=['fewer_calls'])
    with pytest.raises(GraphError,match='继续须有'): check(sample)
    next_d['opportunities'][0]['predictions'][0]['statement']='改变粒度后检查是否新增尾部搬运'
    assert check(sample)['status']=='conditional'


def test_r2_failed_correctness_cannot_support_performance(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));f=d['previous_feedback']
    attempt=f['reassessment']['attempt']
    attempt['implementation_ref']=write_json(task/'candidate.json',{'task_id':d['task_id'],'changed':True})
    attempt['change_ref']=write_json(task/'patch.json',{'task_id':d['task_id'],'changes':['source work']})
    f['reassessment']['structure']['state']='unknown'
    f['reassessment']['correctness']={'state':'failed','evidence_refs':[write_json(task/'failure.json',{'task_id':d['task_id'],'correct':False,'attempt_identity':attempt_identity(d)})],'finding':'原oracle失败'}
    sample=(root,sample[1],task,d,chain)
    assert check(sample)['status']=='conditional'
    f['prediction_updates'][1]['judgement']='supported'
    with pytest.raises(GraphError): check(sample)


def test_r2_replan_must_return_c2_and_mechanism_is_not_action_readiness(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    nxt=d['previous_feedback']['reassessment']['next_step'];nxt.update(kind='replan',return_to='C3')
    with pytest.raises(GraphError,match='返回 C2'): check(sample)
    nxt['return_to']='C2';assert check(sample)['status']=='conditional'


def test_workload_exhaustiveness_does_not_depend_on_case_order():
    assert workload_case_ids({'cases':[{'id':'B'},{'id':'A'}]})=={'A','B'}
    with pytest.raises(GraphError): workload_case_ids({'cases':[{'id':'A'},{'id':'A'}]})
    with pytest.raises(GraphError): workload_case_ids({'cases':[{'shape':[1]}]})


@pytest.mark.parametrize('mode,value,valid',[('exact',3,True),('exact',None,False),('range',{'lower':1,'upper':8},True),('range',{'lower':8,'upper':1},False)])
def test_quantities_require_real_exact_or_range_values(sample,mode,value,valid):
    q=sample[3]['opportunities'][0]['analysis']['work_delta'][0]['quantity']
    q.update(mode=mode,symbols=[])
    if value is not None: q['value' if mode=='exact' else 'bounds']=value
    if valid: assert check(sample)['status']=='ready'
    else:
        with pytest.raises(GraphError): check(sample)


def test_retained_work_cannot_masquerade_as_selected_benefit(sample):
    sample[3]['opportunities'][0]['analysis']['work_delta'][0]['change']='retained'
    with pytest.raises(GraphError,match='角色'): check(sample)


def test_inapplicable_alternative_can_be_empty_without_being_selected(sample):
    d=sample[3];main=d['opportunities'][0];alt=deepcopy(main)
    alt.update(id='other',case_ids=[],disposition='rejected',strongest_alternative_id=main['id'])
    for unknown in alt['unknowns']:
        unknown['id'] = 'other.' + unknown['id']
    for hypothesis in alt['performance_hypotheses']:
        if hypothesis['unknown_id'] is not None:
            hypothesis['unknown_id'] = 'other.' + hypothesis['unknown_id']
    main['strongest_alternative_id']=alt['id']
    alt['analysis']['coverage'][0]['status']='inapplicable'
    alt['analysis']['work_delta'][0]['change']='retained'
    alt['analysis']['residuals']=[{'id':'rest','domain_ids':['all'],'remaining_work':'未修改当前域',
       'next_step':'仅适用于其他布局，保留当前方案','fact_ids':main['source_fact_ids']}]
    d['opportunities'].append(alt)
    d['selection']['comparison_basis'].append({'opportunity_id':'other','item_ids':['coverage.all'],
        'role':'alternative','decision_effect':'范围不匹配，不采用',
        'reversal_condition':'若另一个源码域满足前提则重新分析'})
    assert check(sample)['opportunity_count']==2


def test_untested_prediction_can_continue_with_new_static_evidence(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    r=d['previous_feedback']['reassessment']
    r['next_step'].update(kind='continue',discriminating_prediction_ids=['time'])
    r['structure']['evidence_refs']=[write_json(task/'new-analysis.json',{'task_id':d['task_id'],'finding':'新核算已确认缓存容量有余量，收益仍未测','attempt_identity':attempt_identity(d)})]
    assert check(sample)['status']=='conditional'


def test_correctness_repair_does_not_require_new_performance_prediction(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    r=d['previous_feedback']['reassessment']
    r['attempt']['implementation_ref']=write_json(task/'candidate.json',{'task_id':d['task_id'],'changed':True})
    r['attempt']['change_ref']=write_json(task/'patch.json',{'task_id':d['task_id'],'change':'尾块'})
    r['structure']['state']='unknown'
    r['correctness']={'state':'failed','evidence_refs':[write_json(task/'failed.json',{'task_id':d['task_id'],'case':'tail','attempt_identity':attempt_identity(d)})],'finding':'未满足尾块合法性'}
    r['next_step'].update(kind='repair',return_to='C3',discriminating_prediction_ids=[])
    assert check(sample)['status']=='conditional'
    r['next_step'].update(kind='continue',discriminating_prediction_ids=['time'])
    assert check(sample)['status']=='conditional'


def test_invalid_measurement_can_retry_same_untested_prediction(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    f=d['previous_feedback'];f['measurement']='invalid'
    f['result_ref']=write_json(task/'invalid.json',{'task_id':d['task_id'],'reason':'CPU合成状态夹具，无真实计时'})
    f['reassessment']['next_step'].update(kind='continue',discriminating_prediction_ids=['time'])
    assert check(sample)['status']=='conditional'


def test_r2_collect_evidence_cannot_bypass_repeat_experiment_gate(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    d['selection']['mode']='experiment'
    with pytest.raises(GraphError,match='补证据决定'): check(sample,True)
    d['selection']['mode']='conditional_plan'
    d['previous_feedback']['reassessment']['next_step']['opportunity_ids']=[]
    with pytest.raises(GraphError,match='所选机会'): check(sample)


def test_r2_evidence_cannot_be_borrowed_from_another_attempt(sample):
    root,_,task,d,chain=sample
    d=feedback_fields(r2(d,task));sample=(root,sample[1],task,d,chain)
    identity=attempt_identity(d);identity['implementation_hash']='sha256:'+'1'*64
    d['previous_feedback']['reassessment']['structure']['evidence_refs']=[write_json(task/'wrong-attempt.json',{'task_id':d['task_id'],'attempt_identity':identity})]
    with pytest.raises(GraphError,match='其他候选'): check(sample)


@pytest.mark.parametrize('workload_binding', ['matching', 'different_shape', 'missing_mapping', 'different_oracle'])
def test_valid_v2_feedback_replays_absolute_request_and_exact_case_scope(sample, workload_binding):
    from aprof_runtime.unified_timing import finalize_timing
    from aprof_runtime.jsonio import content_hash
    from test_unified_timing import campaign
    from test_action_decision import persist_reasoning
    import shutil
    root,artifact,task,d,chain=sample
    measurement=task/'measurement';measurement.mkdir()
    request_path,config=campaign(measurement)  # FakeRunner，明确无 NPU。
    request=json.loads(request_path.read_text())
    sources={}
    for role in ('baseline','candidate'):
        cp=measurement/request[role+'_captures'][0]['path']
        capture=json.loads(cp.read_text())
        source=task/(role+'-source.json')
        shutil.copyfile(cp.parent/capture['artifacts']['source']['path'],source)
        sources[role]={'path':source.name,'sha256':file_hash(source)}
    reasoning=chain[0]['reasoning'];reasoning['current']['implementation_ref']=sources['baseline']
    measured_workload=deepcopy(config['cases'][0]['workload'])
    if workload_binding=='different_shape': measured_workload['shape']=[64]
    if workload_binding=='different_oracle': measured_workload['oracle_limits']['atol']=0.1
    # 同一语义域包含未测 case 2；完整 payload 在 R1 决策之前冻结。
    workload_value={'cases':[{'case_id':2,'workload':dict(measured_workload,shape=[128])},
                             {'case_id':1,'workload':measured_workload}]}
    if workload_binding=='missing_mapping': workload_value={'case_ids':['1','2']}
    workload=write_json(task/'workload.json',workload_value)
    reasoning['current']['workload_ref']=workload
    scope=reasoning['current']['scope'];scope['parent_implementation_hash']=sources['baseline']['sha256'];scope['workload_hash']=workload['sha256']
    for row in list(reasoning['facts'].values())+reasoning['candidates']+reasoning['action_instances']:
        row['scope']=deepcopy(scope)
    ctx_path=task/reasoning['source_context_ref']['path'];ctx=json.loads(ctx_path.read_text());ctx['operator']=request['operator']
    reasoning['source_context_ref']=write_json(ctx_path,ctx)
    reasoning['context_snapshot']['source_context_ref']=deepcopy(reasoning['source_context_ref'])
    reasoning['context_hash']=content_hash(reasoning['context_snapshot'])
    d['context_hash']=reasoning['context_hash'];d['current_parent_ref']=deepcopy(sources['baseline'])
    persist_reasoning(d,chain,task)
    d['path_overview']['workload_ref']=workload
    d['path_overview']['case_ids']=['1','2'];d['path_overview']['domains'][0]['case_ids']=['1','2'];d['opportunities'][0]['case_ids']=['1','2']
    d=feedback_fields(r2(d,task));f=d['previous_feedback'];r=f['reassessment']
    result_path=measurement/'result.json';finalize_timing(request_path,result_path)
    f.update(measurement='valid',result_ref={'path':str(result_path.relative_to(task)),'sha256':file_hash(result_path)})
    r['attempt']['implementation_ref']=sources['candidate'];r['attempt']['change_ref']=write_json(task/'change.json',{'task_id':d['task_id'],'changes':['CPU fake source']})
    evidence=write_json(task/'feedback-evidence.json',{'task_id':d['task_id'],'attempt_identity':attempt_identity(d),'source_refs':[f['result_ref']]})
    r['structure']={'state':'realized','evidence_refs':[evidence],'finding':'CPU夹具结构回执'}
    r['correctness']={'state':'passed','evidence_refs':[evidence],'finding':'CPU FakeRunner原oracle链'}
    r.update(measured_domain_ids=['all'],measured_case_ids=['1'],attribution={'kind':'single_change','limits':'只有case 1，不推及同域case 2'})
    f['prediction_updates'][1].update(judgement='supported',evidence_refs=[f['result_ref']],reason='只在匹配的已测 workload 内支持性能预测，CPU合成回放不代表设备收益')
    sample=(root,artifact,task,d,chain)
    if workload_binding!='matching':
        message='完整测量映射' if workload_binding=='missing_mapping' else '冻结完整 payload'
        with pytest.raises(GraphError,match=message): check(sample)
        return
    assert check(sample)['status']=='conditional'
    r['measured_case_ids']=['1','2']
    with pytest.raises(GraphError,match='测量 case'): check(sample)
    r['measured_case_ids']=['1'];r['attempt']['implementation_ref']=sources['baseline']
    with pytest.raises(GraphError,match='计时候选'): check(sample)


def test_prediction_update_cannot_borrow_other_attempt_evidence(sample):
    root, _, task, d, chain = sample
    d = feedback_fields(r2(d, task))
    identity = attempt_identity(d)
    identity['implementation_hash'] = 'sha256:' + '2' * 64
    ref = write_json(task / 'borrowed-static.json', {'task_id': d['task_id'],
                                                  'attempt_identity': identity})
    update = next(u for u in d['previous_feedback']['prediction_updates'] if u['prediction_id'] == 'fewer_calls')
    update.update(judgement='supported', evidence_refs=[ref])
    with pytest.raises(GraphError, match='其他候选'):
        action_decision.validate_decision(root, d, task_root=task)
