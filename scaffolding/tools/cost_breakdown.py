#!/usr/bin/env python3
"""Summarize existing local receipts without running an oracle or adding nested costs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def union_seconds(rows):
    intervals=sorted((r['started_monotonic'],r['finished_monotonic']) for r in rows)
    total=0.;end=None
    for a,b in intervals:
        if b<a:raise ValueError('negative monotonic interval')
        total+=max(0,b-max(a,end if end is not None else a));end=max(b,end if end is not None else b)
    return total


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def summarize(root):
    root=Path(root).resolve()
    if not root.is_relative_to(Path('/dev/shm')):raise ValueError('runtime reports must stay in /dev/shm')
    top=read_rows(root/'operations.jsonl');stages=defaultdict(list)
    for row in top:stages[row['workflow_stage']].append(row)
    result={'schema_version':'aprof.cost-breakdown/v1', 'root':str(root),
        'workflow_stage_union_seconds':{k:union_seconds(v) for k,v in stages.items()},
        'top_operation_union_seconds':union_seconds(top),
        'model_wait_seconds':None,'model_generation_seconds':None,'tokens':None,
        'cost_semantics':'Stage totals are interval unions; operation/native/cache costs are contained, never add to stage totals.',
        'operations':top,'collections':{},'cache':{}}
    for path in sorted(root.rglob('collection_costs.json')):
        folder=path.parent;stage_cost=defaultdict(float);counts=Counter();native=defaultdict(float)
        for receipt in folder.glob('case_*/execution_receipt.json'):
            for name,value in json.loads(receipt.read_text()).get('stages',{}).items():
                stage_cost[name]+=value.get('elapsed_seconds',0);counts[name]+=1
        for log in folder.glob('case_*/logs/native.stdout'):
            for line in log.read_text(errors='replace').splitlines():
                marker='APROF_NATIVE_COST_JSON:'
                if marker in line:
                    for key,value in json.loads(line.split(marker,1)[1]).items():
                        if isinstance(value,(float,int)):native[key]+=value
        result['collections'][str(folder.relative_to(root))]={**json.loads(path.read_text()),
            'contained_stage_seconds':dict(stage_cost),'stage_invocations':dict(counts),
            'contained_native_costs':dict(native)}
    events=read_rows(root/'validation-cache/events.jsonl')
    result['cache']={'events':len(events),'kinds':dict(Counter(r['kind'] for r in events)),
        'oracle_executions':sum(r.get('oracle_executions',0) for r in events),
        'seconds_by_kind':{kind:sum(r.get('elapsed_seconds',0) for r in events if r['kind']==kind) for kind in {r['kind'] for r in events}}}
    terminal=root/'task-result.json'
    if terminal.exists():
        t=json.loads(terminal.read_text());result['task_terminal']=t
        if 'elapsed_seconds' in t:
            result['unattributed_in_task_seconds']=t['elapsed_seconds']-result['top_operation_union_seconds']
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.output.absolute().is_relative_to(a.root.resolve()) or a.output.resolve()!=a.output.absolute():raise ValueError('output must remain in task root')
    a.output.write_text(json.dumps(summarize(a.root),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
