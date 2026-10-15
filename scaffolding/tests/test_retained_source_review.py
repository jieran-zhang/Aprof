"""Tiny stored mock captures, never a provider call or hardware qualification."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'scaffolding/collection/scripts'
import eval_tool_broker as broker
import review_packet
from test_review_final_submission import review_events


def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


@pytest.fixture
def api():
    import retained_source_review, qualify_eval_tools, eval_candidate_evidence
    return {module.__name__:module for module in
            (retained_source_review, qualify_eval_tools, eval_candidate_evidence)}


class Reader:
    def __init__(self, root):
        self.root=root;root.mkdir();self.paths={}
    def add(self, data):
        ref=digest(data);path=self.root/ref.removeprefix('sha256:')
        if not path.exists():path.write_bytes(data)
        self.paths[ref]=path;return ref
    def verify_artifact(self, ref):
        path=self.paths[ref]
        if digest(path.read_bytes())!=ref:raise ValueError('retained bytes changed')
        return path


@pytest.fixture
def make_fixture(tmp_path, api):
    def make(*, version=4, defect=None, delete=True):
        root=tmp_path/f'fixture-{len(list(tmp_path.iterdir()))}';root.mkdir()
        original=root/'original';original.mkdir();reader=Reader(root/'objects');files={}
        trial=original/'trial';work=trial/'worker/root/work';review_work=trial/'review-input'
        release=original/'repo/skill-libs/graph-base/1.0.0';frozen={}
        def blob(path,data):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            ref=reader.add(data);files[str(path)]={'path':str(reader.paths[ref]),'sha256':ref,'bytes':len(data)}
            return {'path':str(path),'sha256':ref}
        def save(path,value):return blob(path,json.dumps(value,sort_keys=True).encode())
        def record(value):return reader.add(json.dumps(value,sort_keys=True).encode())
        retained=api['retained_source_review'];qual=api['qualify_eval_tools']
        producer_refs=[]
        old_sources=REPO.parent/'validation-graph-base-1.0.0/task-v5-time-only-json-rejection-20261015/producers/scaffolding/collection/scripts'
        previous=json.loads((REPO.parent/'validation-graph-base-1.0.0/task-v5-exp-mechanism-stream-rejection-20261015/producer-index.json').read_text())['files']
        for name in retained.PRODUCER_ORDER:
            if version < 2:
                location = old_sources/name if name != 'eval_tool_broker.py' or version == 0 else SCRIPTS/name
            elif version == 2 or version == 3 and name == 'eval_candidate_evidence.py':
                location = Path(previous[str(SCRIPTS/name)]['path'])
            else:
                location = SCRIPTS/name
            data=location.read_bytes()
            if defect=='mixed_producer' and name=='eval_tool_broker.py':data=(old_sources/name).read_bytes()
            if defect=='unknown_producer' and name=='eval_tool_broker.py':data+=b'\n# unknown fixture revision\n'
            if defect=='unknown_packet_producer' and name=='review_packet.py':data+=b'\n# unreviewed packet revision\n'
            pointer=blob(original/'repo/scaffolding/collection/scripts'/name,data)
            producer_refs.append(pointer);frozen[pointer['path']]=pointer['sha256']
        broker_source=reader.verify_artifact(next(p['sha256'] for p in producer_refs if Path(p['path']).name=='eval_tool_broker.py')).read_text()
        instructions=next(ast.literal_eval(n.value) for n in ast.parse(broker_source).body
                          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASE_INSTRUCTIONS' for t in n.targets))
        required=['CMakeLists.txt','op_host/exp.asc','op_kernel/exp_kernel.asc','op_kernel/exp_tiling.h',
                  'op_host/aprof_device_timer.h','op_host/data_utils.h','scripts/verify_result.py','scripts/gen_data.py','scripts/cases.py']
        sources={}
        for role in ('baseline','candidate'):
            inventory={}
            for name in required+['docs/historical-results.md']:
                pointer=blob(work/role/name,('// CPU source '+role+'\n').encode())
                inventory[name]=pointer['sha256'];frozen[pointer['path']]=pointer['sha256']
                if broker.review_source_path(name):blob(review_work/role/name,reader.verify_artifact(pointer['sha256']).read_bytes())
            sources[role]=record({'schema_version':'1.0.0','files':inventory})
        candidate_plan=save(work/'candidate_plan.json',{'intent':'CPU fixture'})
        frozen[candidate_plan['path']]=candidate_plan['sha256']
        documents={
            'contract.json':{'operator':'exp','cases':[{'case_id':1,'dtype':'float32'}]},
            'boundaries.json':{'cases':[{'case_id':101,'numel':1}]},
            'checklist.json':{'critical_obligations':dict.fromkeys(broker.REVIEW_OBLIGATIONS,'CPU source obligation')},
        }
        review_inputs={};attachments={}
        for name,value in documents.items():
            p=save(review_work/name,value);attachments[name]=p
            original_pointer=save(original/'inputs'/name,value);frozen[original_pointer['path']]=original_pointer['sha256']
            review_inputs[{'contract.json':'review_contract','checklist.json':'review_checklist','boundaries.json':'review_boundaries'}[name]]=original_pointer
        blob(review_work/'diff.txt',b'CPU-only source difference\n')
        packet=review_packet.build_review_packet(review_work,expected_inventory=broker.inventory(review_work))
        packet_producer=next(p for p in producer_refs if Path(p['path']).name=='review_packet.py')
        packet_source=reader.verify_artifact(packet_producer['sha256']).read_text()
        packet_instructions=next(ast.literal_eval(n.value) for n in ast.parse(packet_source).body
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVIEW_INSTRUCTIONS' for t in n.targets))
        packet['prompt']=packet_instructions+packet['prompt'][len(review_packet.REVIEW_INSTRUCTIONS):]
        if defect=='wrong_instruction_prefix':
            packet['prompt']='Unregistered review instruction\n'+packet['prompt']
        packet['binding'].update(producer_sha256=packet_producer['sha256'],
            packet_sha256=digest(packet['prompt'].encode()),packet_bytes=len(packet['prompt'].encode()))
        if defect=='packet_hash':packet['binding']['packet_sha256']='sha256:'+'0'*64
        prompt=blob(review_work/'prompt.txt',packet['prompt'].encode())
        obligations={key:{'status':'pass','reason':'CPU fixture only',
             'anchors':[{'path':'candidate/op_kernel/exp_kernel.asc','line':1}]} for key in broker.REVIEW_OBLIGATIONS}
        if defect=='bad_anchor':obligations['dynamic_tails']['anchors'][0]['line']=99
        if defect=='unknown_obligation':obligations['dynamic_tails']['status']='unknown'
        events=review_events(obligations,total=84978)
        if defect=='incomplete_usage':events.pop(1)
        # Preserve a syntactically recorded receipt even for malformed actual events.
        decision,binding=broker.final_review(review_events(obligations,total=84978))
        metadata={'models':[{'slug':'gpt-6-sol','supported_reasoning_levels':[{'effort':'max'}]}]}
        catalog=save(original/'qualification/model-catalog.json',qual.restricted_catalog(metadata))
        installed=save(original/'qualification/installed-model-metadata.json',metadata)
        probes=[]
        for i,(review,wiki) in enumerate(((False,False),(False,True),(True,False))):
            tools=[{'type':'function','name':p['name'],'description':p['description'],'parameters':p['inputSchema']}
                   for p in broker.tool_specs(review=review,wiki=wiki)]
            request={'model':'gpt-6-sol','reasoning':{'effort':'max'},'instructions':instructions,'tools':tools}
            if review:request['text']={'format':{'type':'json_schema','strict':True,'schema':broker.review_output_schema()}}
            captures=[deepcopy(request) for _ in range(1 if review else 2)]
            if defect=='forbidden_tool' and i==0:captures[0]['tools'].append({'type':'function','name':'exec_command'})
            probe_events=review_events(obligations) if review else [
                {'method':'item/tool/call','params':{'tool':'list_files','arguments':{'path':'.'}}},
                {'method':'turn/completed','params':{'turn':{'status':'completed'}}}]
            probes.append(dict(review=review,wiki=wiki,request_ref=save(original/f'qualification/{i}/requests.json',captures),
                events_ref=blob(original/f'qualification/{i}/events.jsonl',''.join(json.dumps(e)+'\n' for e in probe_events).encode()),
                dynamic_tools_sha256=broker.digest(broker.tool_specs(review=review,wiki=wiki))))
        qualification=save(original/'qualification/qualification.json',dict(schema_version=1,kind='local_mock_provider_tool_capture',
            review_submission_protocol=broker.REVIEW_SUBMISSION_PROTOCOL,budget_policy=broker.BUDGET_POLICY,config=broker.CONFIG,
            producers=producer_refs,binary={'path':'/opt/codex','sha256':retained.CODEX_HASH},model='gpt-6-sol',reasoning_effort='max',
            model_catalog=catalog,installed_model_metadata=installed,catalog_overrides=qual.CATALOG_OVERRIDES,probes=probes))
        frozen[qualification['path']]=qualification['sha256']
        worker=save(trial/'reviewer/worker.json',dict(role='reviewer',status='completed',model='gpt-6-sol',reasoning_effort='max',
            usage={'totalTokens':84978},budget_policy=broker.BUDGET_POLICY,qualification_ref=qualification,
            config=broker.CONFIG,worker_builds=0,submission=decision,review_submission=binding,
            events_ref=blob(trial/'reviewer/events.jsonl',''.join(json.dumps(e)+'\n' for e in events).encode()),
            broker_ref=blob(trial/'reviewer/broker.jsonl',b'')))
        review=save(work/'candidate_review.json',dict(schema_version=1,review_source_policy=broker.REVIEW_SOURCE_POLICY,
            baseline_inventory=broker.inventory(work/'baseline'),candidate_inventory=broker.inventory(work/'candidate'),
            plan_sha256=candidate_plan['sha256'],worker_receipt_ref=worker,input_inventory=broker.inventory(review_work),
            review_packet_binding=packet['binding'],decision=decision,contract_ref=attachments['contract.json'],
            checklist_ref=attachments['checklist.json'],boundaries_ref=attachments['boundaries.json'],prompt_ref=prompt))
        frozen_ref=record(frozen)
        plan=record(dict(schema_version=1,directory=str(trial),release=str(release),model={'name':'gpt-6-sol','reasoning_effort':'max'},
            frozen_files_ref=frozen_ref,worker_qualification=qualification,review_inputs=review_inputs))
        anchor=save(trial/'anchor.json',dict(schema_version=1,protocol='rule_task_admission_v1',task_protocol='shared_buffer_msprof_task_window_v5',
            purpose='promotion',operator='exp',controller_plan_ref=plan,source_hashes=sources))
        snapshot=record(dict(owner='trace_collection',cost_scope='post_task',kind='frozen_task_producer_source_archive',
            source_anchors={'exp':anchor},frozen_files_refs={'exp':frozen_ref},files={p['path']:files[p['path']] for p in producer_refs}))
        if defect=='missing_source':files.pop(str(work/'candidate/op_kernel/exp_kernel.asc'))
        if defect=='extra_input':blob(review_work/'results.json',b'{}')
        archive=record(dict(owner='trace_collection',cost_scope='post_task',producer_index_ref={'path':'/post-task/producer-index.json','sha256':snapshot},files=files))
        args=dict(anchor_ref=anchor['sha256'],source_review_ref=review['sha256'],archive_inventory_ref=archive,producer_snapshot_ref=snapshot)
        if delete:shutil.rmtree(original)
        return reader,args,original,qualification,files
    return make


@pytest.mark.parametrize('version',[0,1,2,3,4])
def test_current_and_old_pinned_review_survive_original_path_deletion(api,make_fixture,version):
    reader,args,original,_,_=make_fixture(version=version)
    result=api['retained_source_review'].replay_retained_source_review(reader,**args)
    assert result['accepted'] is True and not original.exists()
    assert not result['admission_authority'] and not result['eligible_for_publication']
    assert not result['binary_bytes_replayed'] and result['source_review_ref']['sha256']==args['source_review_ref']


@pytest.mark.parametrize('defect',['unknown_producer','mixed_producer','unknown_packet_producer','missing_source',
    'extra_input','bad_anchor','incomplete_usage','forbidden_tool','wrong_instruction_prefix','packet_hash'])
def test_unknown_sources_and_original_review_checks_still_reject(api,make_fixture,defect):
    reader,args,_,_,_=make_fixture(defect=defect)
    with pytest.raises(Exception):api['retained_source_review'].replay_retained_source_review(reader,**args)


def test_unknown_review_stays_rejected(api,make_fixture):
    reader,args,_,_,_=make_fixture(defect='unknown_obligation')
    assert api['retained_source_review'].replay_retained_source_review(reader,**args)['accepted'] is False


def test_corrupt_retained_bytes_and_wrong_snapshot_reject(api,make_fixture):
    reader,args,_,_,files=make_fixture()
    reference=next(v['sha256'] for p,v in files.items() if p.endswith('candidate/op_kernel/exp_kernel.asc'))
    reader.paths[reference].write_bytes(b'corrupt')
    with pytest.raises(ValueError):api['retained_source_review'].replay_retained_source_review(reader,**args)
    reader,args,_,_,_=make_fixture();snapshot=json.loads(reader.verify_artifact(args['producer_snapshot_ref']).read_text())
    snapshot['source_anchors']['exp']['sha256']='sha256:'+'0'*64
    args['producer_snapshot_ref']=reader.add(json.dumps(snapshot).encode())
    with pytest.raises(ValueError):api['retained_source_review'].replay_retained_source_review(reader,**args)


def test_current_launch_does_not_accept_retained_context_or_stale_sources(api,make_fixture):
    reader,args,_,qualification,_=make_fixture(version=0,delete=False)
    with pytest.raises((ValueError,FileNotFoundError)):
        api['qualify_eval_tools'].verify_qualification(qualification,model='gpt-6-sol',effort='max')
    with pytest.raises(ValueError,match='verified archive context'):
        api['qualify_eval_tools'].verify_qualification(qualification,retained=object())


def test_retained_replay_does_not_discover_later_installed_producers(api,make_fixture,monkeypatch):
    reader,args,_,_,_=make_fixture(version=0)
    def unavailable(*args,**kwargs):
        raise AssertionError('historical replay inspected a later live installation')
    monkeypatch.setattr(api['qualify_eval_tools'],'sources',unavailable)
    monkeypatch.setattr(api['qualify_eval_tools'].shutil,'which',unavailable)
    result=api['retained_source_review'].replay_retained_source_review(reader,**args)
    assert result['accepted'] is True and result['eligible_for_publication'] is False


def test_current_packet_builder_still_rejects_instruction_override(tmp_path):
    with pytest.raises(ValueError,match='canonical packet instructions'):
        review_packet.build_review_packet(tmp_path,expected_inventory={},instructions='historical override')
