"""Local controller joins with real indexing/recorder; device/model stages mocked."""
import json
from pathlib import Path
import time

import pytest

import task_rule_controller as controller
from aprof_runtime.errors import ContractError
from aprof_runtime.measurement_entry import replay_current_measurement_admission


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def test_frozen_candidate_and_actual_task_binding_use_identical_source_refs(tmp_path):
    local = controller.LocalEvidence(tmp_path / 'records')
    workspace, output = tmp_path/'workspace', tmp_path/'proposal'
    output.mkdir()
    for role, value in [('baseline',1), ('candidate',2)]:
        path = workspace/role/'op_kernel/test.asc'
        path.parent.mkdir(parents=True)
        path.write_text(f'int tile = {value};\n')
    write(workspace/'candidate_plan.json', {'actual_parent':'original baseline','intent':'CPU join test',
        'source_anchors':[{'path':'op_kernel/test.asc','line':1,'why':'CPU fixture parameter'}]})
    choice = dict(case_id=1,kernel='exp_kernel',metric='cost',expected_direction='decrease')
    frozen = controller.freeze_candidate(controller._api(),local,workspace,output,'exp','cpu',choice,
        split='train',handler_id='CPU-only',coverage_gap='CPU fixture; no legal route')
    binary = tmp_path/'binary'; binary.write_bytes(b'not executed')
    receipt = write(tmp_path/'build.json',{'CPU':'fixture'})
    config = {'roles':{r:{'source_dir':str(workspace/r)} for r in controller.ROLES},
        'build':{'source_dir':str(workspace/'baseline'),'binary':str(binary),'receipt_files':[str(receipt)]},'cases':[]}
    identity = controller.bridge.timing.shared.bind_identity(config,
        {'files':{str(path):controller.bridge.file_hash(path) for path in (binary,receipt)}},local)
    assert frozen['candidate']['source_hashes'] == identity['source_hashes']
    # The runtime rejects a pretty-JSON alias even when its source map is equal.
    role = 'baseline'; payload = json.loads(local.verify_artifact(identity['source_hashes'][role]).read_text())
    alias_path = tmp_path/'pretty.json'; alias_path.write_text(json.dumps(payload,indent=2)+'\n')
    alias = local.register_artifact(alias_path)
    assert alias != identity['source_hashes'][role]
    completion = dict(schema_version='1.0.0',kind='local_measurement_completion',protocol=controller.TASK_PROTOCOL,
        operator='exp',run_id='cpu',session_id='cpu-candidate',candidate_id='cpu-candidate',
        source_hashes=identity['source_hashes'],proof_ref=local.register_json({}),measurement_report_ref=local.register_json({'CPU':True}),
        started_at=1,finished_at=2,elapsed_seconds=1,timeout_seconds=30,status='passed',error=None)
    with pytest.raises(ContractError,match='source_hashes'):
        replay_current_measurement_admission(local,local.register_json(completion),
            expected={'source_hashes':{**identity['source_hashes'],role:alias}})


@pytest.mark.parametrize('failure', [None,'preflight','correctness','screen','task_measurement'])
def test_controller_registers_binary_and_stops_after_failed_stage(tmp_path, monkeypatch, failure):
    """No stage mock is admission evidence; this tests API keys and local handoff."""
    directory = tmp_path/'trial'; directory.mkdir()
    local = controller.LocalEvidence(directory/'records')
    workspace = directory/'worker/root/work'
    roles = {}
    source_hashes = {}
    for role in controller.ROLES:
        path = workspace/role/'scripts/verify_result.py'; path.parent.mkdir(parents=True)
        path.write_text('# CPU fixture oracle; not executed\n')
        roles[role] = {'path':str(workspace/role),'files':{'scripts/verify_result.py':local.register_artifact(path)}}
        source_hashes[role] = local.register_json(dict(schema_version='1.0.0',files=roles[role]['files']))
    assembly = directory/'assembly'; (assembly/'source').mkdir(parents=True)
    proof = {'operator':'exp','roles':roles,'role_kernel_names':{r:[f'aprof_{r}_exp_kernel'] for r in controller.ROLES},
        'historical_source_binding':{'roles':{r:{'sha256':source_hashes[r]} for r in controller.ROLES}}}
    source_review = write(assembly/'source-review.json',proof)
    choice = dict(case_id=1,kernel='exp_kernel',metric='cost',expected_direction='decrease')
    plan = {'directory':str(directory),'release':str(controller.bridge.RELEASE),'model':controller.MODEL,
        'boundary_oracle_files':{},
        'assembly':str(assembly),'launch_path':str(directory/'launch.json'),'physical_device':0,
        'profiler':'/CPU/msprof','scratch_dir':str(directory/'scratch'),'prepared_dir':str(directory/'prepared'),
        'boundary_dir':str(directory/'boundary-inputs'),'review_inputs':{},'worker_qualification':{}}
    job_ref = local.register_json({'timeout_seconds':3600})
    anchor = dict(schema_version=1,protocol=controller.PROTOCOL,task_protocol=controller.TASK_PROTOCOL,
        purpose='promotion',operator='exp',run_id='cpu',candidate_id='cpu-candidate',source_hashes=source_hashes,
        budget_seconds=3600,created_at=time.time()-1,job_ref=job_ref,controller_plan_ref=local.register_json(plan),
        source_review_ref=local.register_artifact(source_review),history_refs=[local.register_json({'prior':'failed fixture'})],
        campaign_ref=local.register_json({'CPU':'finite campaign fixture'}),
        input_inventory_ref=local.register_json({}),boundary_plan_ref=local.register_json({'CPU':'boundary'}),
        screen_plan_ref=local.register_json({'CPU':'screen'}),
        profile_plan_ref=local.register_json({'choice':choice,'specs':{'cost':{'unit':'ns'}}}))
    anchor_path = write(directory/'anchor.json',anchor); anchor_ref = local.register_artifact(anchor_path)
    write(directory/'launch.json',{'schema_version':1,'anchor_ref':anchor_ref,'job_ref':job_ref,
        'started_at':time.time()-0.1,'monotonic_deadline':time.monotonic()+60})
    index = local.write_index(directory/'initial-index.json')
    calls = []
    reviews = []
    monkeypatch.setattr(controller.screen,'source_identity',lambda path: proof)
    def review(*args):
        reviews.append('review');args[-1].update(reviewer={'status':'completed'})
    monkeypatch.setattr(controller,'review_candidate',review)
    monkeypatch.setattr(controller,'_register_review',lambda store,*a: (store.register_json({'CPU':'review'}),7))
    frozen = {'run_id':'cpu','candidate':{'candidate_id':'cpu-candidate','session_id':'cpu-candidate',
        'source_hashes':source_hashes},'frozen_manifest_hash':anchor_ref}
    monkeypatch.setattr(controller,'freeze_candidate',lambda *a,**kw:frozen)
    build_value = {}
    def build(assembly,work,commands,**kwargs):
        calls.append('build')
        binary = assembly/'build/exp'; binary.parent.mkdir(); binary.write_bytes(b'CPU build output')
        attempt = write(assembly/'build-attempt.json',{'CPU':'attempt'})
        log = assembly/'compiler.log'; log.write_text('CPU fixture; no compiler executed')
        ptr = controller.reference(log)
        build_value.update(binary=controller.reference(binary),attempt_ref=controller.reference(attempt),
            commands=[{'stdout':ptr,'stderr':ptr}])
        return write(assembly/'build-receipt.json',build_value)
    monkeypatch.setattr(controller.bridge,'build_teacher_rule_once',build)
    monkeypatch.setattr(controller.screen,'checked_build',lambda *a:(proof,build_value))
    config = {'roles':{r:{'source_dir':roles[r]['path']} for r in controller.ROLES},'physical_device':0,
        'cases':[{'case_id':1,'workload':{'numel':1},'command':['/CPU/binary','--output','{cycle_dir}/out']}],
        'expected_case_ids':list(range(1,21))}
    monkeypatch.setattr(controller.bridge,'task_config',lambda *a,**kw:config)
    import task_outer_admission as outer
    def preflight(*args,**kwargs):
        if failure=='preflight':
            calls.append('preflight');raise ValueError('CPU missing boundary generator fixture')
    monkeypatch.setattr(outer.correctness,'preflight_boundary_plan',preflight)
    def correctness(*args,stage,**kwargs):
        calls.append(stage)
        if stage == failure: raise RuntimeError('CPU stop '+stage)
        return {'report_ref':args[4].register_json({'status':'passed','CPU':stage})}
    monkeypatch.setattr(outer.correctness,'collect_correctness',correctness)
    def screen(*args,**kwargs):
        calls.append('screen')
        out = args[3]; out.mkdir()
        reader = controller.LocalEvidence(out/'records')
        report = write(out/'screen-result.json',{'status':'failed' if failure=='screen' else 'passed','CPU':'screen'})
        return {'status':'failed' if failure=='screen' else 'passed','report':str(report),
            'report_ref':reader.register_artifact(report),'local_index':str(reader.write_index(out/'local-index.json')),
            'eligible_for_formal_admission':False,'gate_projection':{}}
    monkeypatch.setattr(controller.screen,'collect_screen',screen)
    def task(config,out,**kwargs):
        calls.append('task_measurement'); out.mkdir()
        reader = controller.LocalEvidence(out/'records')
        report = {'gate_projection':{'baseline_samples_ns':[1]*30,'candidate_samples_ns':[1]*30,'heldout_regressions':[0]*20},
            'max_case_regression':0,'CPU':'measurement fixture'}
        proof = dict(config_ref=reader.register_json(config),registration_ref=reader.register_json({'CPU':'registration'}),
            raw_ref=reader.register_json({'CPU':'raw'}),measurement_report_ref=reader.register_json(report))
        completion = {'proof_ref':reader.register_json(proof),'CPU':'completion fixture'}
        return {'status':'failed' if failure=='task_measurement' else 'passed','report':report,
            'measurement_admission_ref':reader.register_json(completion),
            'local_index':str(reader.write_index(out/'local-index.json'))}
    # Keep collect_task and merge_index real; only native collection is mocked.
    monkeypatch.setattr(controller.bridge.timing,'collect_local',task)
    def profile(*args,**kwargs):
        calls.append('profile'); reader = args[6]
        hardware = reader.register_json({'CPU':'hardware'})
        result = {}
        for role in controller.ROLES:
            value = {'metrics':{'cost':{'value':1 if role=='baseline' else 0.9}}}
            result[role] = {'profile':value,'digest':reader.register_json(value),'hardware':hardware}
        return result
    monkeypatch.setattr(controller.bridge,'capture_mechanism',profile)
    def gate(reader,frozen,artifacts,report):
        calls.append('online_admission')
        for key in ('build_log','accuracy_report','measurement_report','measurement_admission','mechanism_report'):
            reader.verify_artifact(artifacts[key])
        completion = controller.read(reader,artifacts['measurement_admission'])
        proof = controller.read(reader,completion['proof_ref'])
        assert proof['measurement_report_ref'] == artifacts['measurement_report']
        assert proof['raw_ref'] == artifacts['timing_raw']
        return {'CPU':'request'}, {'verdict':'inconclusive'}
    monkeypatch.setattr(controller,'_gate',gate)
    monkeypatch.setattr(controller,'_trace',lambda *a:{'CPU':'trace; not admission evidence'})
    result = controller.run(anchor_path,index)
    assert len(reviews)==(failure!='preflight')
    if failure:
        assert result['status'] == 'failed'
        assert calls[-1] == failure
        assert 'online_admission' not in calls
    else:
        assert result['status'] == 'passed', result
        assert calls == ['build','correctness','boundary','screen','task_measurement','profile','online_admission']
    restored = controller.LocalEvidence.from_index(directory/'controller-local-index.json')
    if failure!='preflight':
        assert restored.verify_artifact(build_value['binary']['sha256']) == Path(build_value['binary']['path'])
    assert result['archive_performed'] is False and result['actual_builds'] == (failure!='preflight')
