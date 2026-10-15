"""Reviewer final JSON: actual protocol probe plus bounded event-chain negatives."""
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil

import pytest

import eval_tool_broker as broker
import qualify_eval_tools as qualification


def review_events(obligations, *, total=7):
    message = {'type':'agentMessage','id':'answer','phase':'final_answer',
               'text':json.dumps({'obligations':obligations})}
    return [
        {'method':'item/completed','params':{'threadId':'thread','turnId':'turn','item':message}},
        {'method':'thread/tokenUsage/updated','params':{'threadId':'thread','turnId':'turn',
            'tokenUsage':{'total':{'totalTokens':total}}}},
        {'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'turn','status':'completed','items':[message]}}},
    ]


def obligations():
    return {name:{'status':'pass','reason':'CPU fixture only',
            'anchors':[{'path':'candidate/op_kernel/test.asc','line':1}]} for name in broker.REVIEW_OBLIGATIONS}


def test_final_answer_binds_actual_events_and_unknown_rejects():
    values=obligations(); events=review_events(values)
    answer, binding=broker.final_review(events)
    assert answer['accepted'] and binding['protocol']=='final_json_review_v1'
    for name, index in [('message',0),('usage',1),('completed',2)]:
        assert binding[name+'_event_sha256']==broker.digest(events[index])
    assert broker.final_review(review_events(values,total=80001))[0]['accepted'] is True
    values['dynamic_tails']['status']='unknown'
    assert broker.final_review(review_events(values))[0]['accepted'] is False


@pytest.mark.parametrize('defect', ['missing','multiple','stale_usage','same_total','wrong_turn',
    'wrong_thread','interrupted','submit_tool','bad_json','missing_obligation'])
def test_final_answer_rejects_incomplete_or_unbound_submission(defect):
    events=review_events(obligations())
    if defect=='missing': events.pop(0)
    elif defect=='multiple': events.insert(0,copy.deepcopy(events[0]))
    elif defect=='stale_usage': events[0],events[1]=events[1],events[0]
    elif defect=='same_total': events.insert(0,copy.deepcopy(events[1]))
    elif defect=='wrong_turn': events[1]['params']['turnId']='other'
    elif defect=='wrong_thread': events[-1]['params']['threadId']='other'
    elif defect=='interrupted': events[-1]['params']['turn']['status']='interrupted'
    elif defect=='submit_tool': events.insert(0,{'method':'item/tool/call','params':{'tool':'submit_review'}})
    elif defect=='bad_json': events[0]['params']['item']['text']='not JSON'
    elif defect=='missing_obligation': events[0]['params']['item']['text']='{"obligations":{}}'
    with pytest.raises(Exception): broker.final_review(events)


def test_installed_mock_provider_final_schema_single_completed_response(tmp_path):
    if not shutil.which('codex'):
        pytest.skip('installed app-server required for local mock protocol proof')
    cache=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'models_cache.json'
    metadata=[item for item in json.loads(cache.read_text())['models'] if item['slug']=='gpt-6-sol']
    assert len(metadata)==1
    catalog=tmp_path/'catalog.json';catalog.write_text(json.dumps(qualification.restricted_catalog({'models':metadata})))
    row=asyncio.run(qualification.probe(tmp_path/'capture','gpt-6-sol',catalog=broker.pointer(catalog),effort='max',review=True))
    requests=json.loads(broker.checked(row['request_ref']).read_text())
    events=[json.loads(line) for line in broker.checked(row['events_ref']).read_text().splitlines()]
    assert len(requests)==1 and 'submit_review' not in qualification.names(requests[0]['tools'])
    assert requests[0]['text']['format']['schema']==broker.review_output_schema()
    assert broker.final_review(events)[0]['accepted'] is False
    changed=copy.deepcopy(requests);changed[0]['text']['format']['schema']={'type':'object'}
    with pytest.raises(ValueError,match='schema'):
        qualification.verify_capture(changed,events,model='gpt-6-sol',effort='max',review=True,wiki=False)


@pytest.mark.parametrize('defect,expected', [(None,'completed'),('stale','invalid_review_submission'),
    ('missing_answer','invalid_review_submission'),('missing_usage','missing_usage_receipt')])
def test_worker_uses_schema_and_actual_final_usage_without_token_cap(tmp_path,monkeypatch,defect,expected):
    import isolated_eval_worker as worker
    work=tmp_path/'work';(work/'candidate/op_kernel').mkdir(parents=True)
    (work/'candidate/op_kernel/test.asc').write_text('// source fixture\n')
    (work/'prompt.txt').write_text('Return one final JSON review.')
    catalog=tmp_path/'catalog.json';catalog.write_text('{}')
    qualification_path=tmp_path/'qualification.json'
    qualification_path.write_text(json.dumps({'model_catalog':broker.pointer(catalog)}))
    sent=[]
    class Input:
        def __init__(self,output): self.output=output
        def write(self,line):
            request=json.loads(line);sent.append(request)
            method=request.get('method')
            if method=='initialize': events=[{'id':request['id'],'result':{}}]
            elif method=='thread/start': events=[{'id':request['id'],'result':{'model':'CPU','reasoningEffort':'max','thread':{'id':'thread'}}}]
            elif method=='turn/start':
                values=review_events(obligations(),total=80001)
                if defect=='stale': values[0],values[1]=values[1],values[0]
                elif defect=='missing_answer': values.pop(0)
                elif defect=='missing_usage': values.pop(1)
                events=[{'id':request['id'],'result':{}},*values]
            else: events=[]
            for event in events: self.output.feed_data((json.dumps(event)+'\n').encode())
            if method=='turn/start': self.output.feed_eof()
        async def drain(self): pass
    async def create(*args,**kwargs):
        class Process:
            returncode=0
            stdout=asyncio.StreamReader()
        process=Process();process.stdin=Input(process.stdout)
        return process
    def make_root(workspace,output):
        root=output/'root';shutil.copytree(workspace,root/'work')
        (root/'aprof-bin').mkdir();auth=root/'auth';auth.mkdir()
        return root,auth
    monkeypatch.setattr(worker,'make_root',make_root)
    monkeypatch.setattr(worker.asyncio,'create_subprocess_exec',create)
    monkeypatch.setattr(worker,'require_worker_build_budget_enforcement',lambda *a,**kw:None)
    result=asyncio.run(worker.run(work,tmp_path/'output','CPU','max',None,30,
        qualification=broker.pointer(qualification_path),review=True))
    assert result['status']==expected and result['budget_policy']=='time_only_v1'
    turn=next(row['params'] for row in sent if row.get('method')=='turn/start')
    assert turn['outputSchema']==broker.review_output_schema()
    thread=next(row['params'] for row in sent if row.get('method')=='thread/start')
    assert {row['name'] for row in thread['dynamicTools']}=={'list_files','read_file','search_text'}
    assert not any('result' in row for row in sent)  # No invented submission tool reply.
    if defect is None:
        assert result['usage']['totalTokens']==80001 and result['submission']['accepted']
        assert result['review_submission']['protocol']=='final_json_review_v1'
    else:
        assert result['submission'] is None


@pytest.mark.parametrize('seconds',[0,-1,float('inf'),float('nan'),3601,True])
def test_worker_rejects_invalid_shared_remaining_time(tmp_path,seconds):
    import isolated_eval_worker as worker
    with pytest.raises(ValueError,match='remaining time'):
        asyncio.run(worker.run(tmp_path,tmp_path/'output','CPU','max',None,seconds))


def test_worker_filesystem_startup_consumes_existing_deadline(tmp_path,monkeypatch):
    import isolated_eval_worker as worker
    import time
    def setup(workspace,output):
        time.sleep(0.02)
        return output/'root',output/'auth'
    monkeypatch.setattr(worker,'make_root',setup)
    monkeypatch.setattr(worker,'require_worker_build_budget_enforcement',lambda *a,**kw:None)
    with pytest.raises(TimeoutError,match='filesystem setup'):
        asyncio.run(worker.run(tmp_path,tmp_path/'output','CPU','max',None,0.01))
