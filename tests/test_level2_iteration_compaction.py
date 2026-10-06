"""Storage maintenance stays synchronous and errors prevent the next operation."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_iteration as iteration
import level2_storage as storage


@pytest.mark.parametrize('failure',[None,'dedup','event','compact'])
def test_reclaim_outputs_orders_manifest_event_then_compaction_and_propagates(monkeypatch,tmp_path,failure):
    calls=[];run=tmp_path/'run';task=run/'train/tasks/maximum';parent=task/'candidates/maximum001'
    result={'manifest_path':str(run/'storage/dedup/txn.json'),'transaction':str(run/'storage/transactions/txn'),
            'reclaimed_bytes':123}
    def dedup(*args,**kwargs):
        calls.append(('dedup',args,kwargs))
        if failure=='dedup':raise OSError('dedup failed')
        return result
    def event(*args):
        calls.append(('event',args))
        if failure=='event':raise OSError('event failed')
    def compact(*args,**kwargs):
        calls.append(('compact',args,kwargs))
        if failure=='compact':raise OSError('compact failed')
        return {'status':'complete'}
    monkeypatch.setattr(storage,'deduplicate',dedup);monkeypatch.setattr(storage,'compact_journals',compact)
    monkeypatch.setattr(iteration,'event',event);monkeypatch.setattr(iteration,'pointer',lambda p:{'path':p,'sha256':'bound'})
    if failure:
        with pytest.raises(OSError,match=failure+' failed'):iteration.reclaim_outputs(run,task,parent,'search-01')
    else:iteration.reclaim_outputs(run,task,parent,'search-01')
    expected=['dedup','event','compact'];last=expected.index(failure)+1 if failure else 3
    assert [row[0] for row in calls]==expected[:last]
    assert calls[0][1:]==((run,parent/'stages/search-01'),{'kind':'stage','writers_closed':True,'apply':True})
    if len(calls)>1:
        assert calls[1][1][0:2]==(task,'closed_outputs_deduplicated')
        assert calls[1][1][2]['manifest']['path']==result['manifest_path']
    if len(calls)>2:assert calls[2][1:]==((run,Path(result['transaction'])),{'writers_closed':True,'apply':True})
