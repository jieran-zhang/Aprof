#!/usr/bin/env python3
"""Validate masked manual/LLM annotations and compute deterministic fact scores."""
from pathlib import Path
import collections, json, sys
ROOT=Path(__file__).resolve().parents[2]

def score(annotation):
    assert 'condition' not in annotation and 'arm' not in annotation,'Grade masked answers only'
    case=annotation['case']
    gold=json.loads((ROOT/'private/gold'/f'{case}.json').read_text())
    facts={x['id']:x for x in gold['facts']}
    given=annotation['facts']
    assert len(given)==len(facts) and {x['id'] for x in given}==set(facts),'Need each fact exactly once'
    weights={'correct':1,'partial':0.5,'wrong':0,'omitted':0,'unsupported':0}
    totals={d:0.0 for d in gold['dimensions']}
    counts=collections.Counter()
    for item in given:
        status=item['status'];assert status in weights,status
        assert item.get('rationale'),'Every judgment needs a rationale'
        if status!='omitted':assert item.get('answer_span'),'Explicit claim statuses need an answer span'
        f=facts[item['id']];totals[f['dimension']]+=f['points']*weights[status];counts[status]+=1
    critical={x['id']:x for x in gold['critical_errors']}
    triggered=annotation.get('critical_errors',[])
    assert len({x['id'] for x in triggered})==len(triggered)
    for item in triggered:
        assert item['id'] in critical,item['id']
        assert item.get('answer_span') and item.get('rationale'),'Critical caps need explicit evidence'
        c=critical[item['id']];totals[c['dimension']]=min(totals[c['dimension']],c['cap'])
    assert all(0<=v<=10 for v in totals.values())
    return {'answer_id':annotation['answer_id'],'case':case,'dimension_scores':totals,'total':sum(totals.values()),
            'status_counts':dict(counts),'critical_errors':[x['id'] for x in triggered],'max_score':30}

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--template':
        case=sys.argv[2];g=json.loads((ROOT/'private/gold'/f'{case}.json').read_text())
        print(json.dumps({'answer_id':'masked-id','case':case,'facts':[{'id':f['id'],'status':'omitted','rationale':'Not stated','answer_span':''} for f in g['facts']],'critical_errors':[]},ensure_ascii=False,indent=2))
    else:
        assert len(sys.argv)==2,'Usage: score_answer.py ANNOTATION.json | --template case-01'
        print(json.dumps(score(json.loads(Path(sys.argv[1]).read_text())),ensure_ascii=False,indent=2))
