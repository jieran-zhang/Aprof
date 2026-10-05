#!/usr/bin/env python3
"""Project already-recorded worker reads and diagnoses into the strict coordinator stream."""
import argparse
import json
from pathlib import Path
from collect_level1_traces import Campaign, text_items
from finalize_level1_campaign import Evidence
from aprof_runtime.traces import execution_record, register_json_artifact
from aprof_runtime.jsonio import content_hash


def import_worker(op):
    c=Campaign();task=c.task(op);store=c.store(op);writer=c.writer(op,store);evidence=Evidence(store,task)
    entries=[];read_refs=[]
    for name in ['knowledge/knowledge_reads.jsonl','worker_knowledge_reads.jsonl']:
        path=task/name
        if not path.exists():continue
        read_refs.append(evidence.file(path))
        for line in path.read_text().splitlines():
            row=json.loads(line);path=Path(row['path'])
            # CSV reads remain in the bound read index and raw profile CAS.
            if path.suffix in ('.csv','.log'):continue
            digest=evidence.recorded_file(path,row.get('content_hash',row.get('sha256')))
            entry={'path':str(path),'content_hash':digest,
                   'purpose':row.get('purpose',row.get('used_for','Recorded knowledge read'))+
                   ' [read at '+str(row.get('read_at',row.get('timestamp','not individually recorded')))+']'}
            if entry not in entries:entries.append(entry)
    # Later audit/qualification reads append to the read index. Keep the first
    # attestation immutable and import only new entries with a content-derived
    # identity; repeated imports cannot rewrite the original event or duplicate
    # an already attested read.
    stream = task / 'trace_events.jsonl'
    previous = [json.loads(line) for line in stream.read_text().splitlines()] if stream.exists() else []
    known = {content_hash(entry) for event in previous if event['event_type'] == 'knowledge_loaded'
             for entry in event['payload']['entries']}
    additions = [entry for entry in entries if content_hash(entry) not in known]
    if additions:
        payload = {'entries': additions}
        writer.append('knowledge_loaded',payload,artifact_refs=read_refs,
                      event_id=op+'-worker-knowledge-imported-'+content_hash(payload).split(':')[1][:24])
    accuracy_path=c.accuracy_report(op,'baseline')
    if accuracy_path.exists():
        accuracy=json.loads(accuracy_path.read_text())
        writer.append('baseline_validated',{'status':accuracy['status'],
            'case_count':accuracy['case_count'],'passed_count':accuracy['passed_count'],'execution':None,
            'reason':'Bound indexed prepared-input validation report; command execution is retained in stage events.'},
            artifact_refs=[evidence.file(accuracy_path)],event_id=op+'-baseline-validation-bound')
    for case in [1,8,14,20]:
        directory=task/'profiles/baseline'/f'case-{case:02d}'
        manifests=[directory/'normalized-current/normalization_manifest.json',directory/'normalized/normalization_manifest.json']
        manifest=next((p for p in manifests if p.exists()),None)
        report_path=task/'executions/baseline'/f'profile-{case:02d}/execution.json'
        if manifest is None or not report_path.exists():continue
        report=json.loads(report_path.read_text());ref=evidence.file(manifest)
        writer.append('profile_collected',{'stage':'baseline_sentinel_'+str(case),'status':report['status'],
            'profile_hash':ref,'execution':execution_record(argv=report['job']['argv'],cwd=report['job']['cwd'],
                host=report['host'],device=report['physical_device'],started_at=report['started_at'],
                finished_at=report['finished_at'],exit_status=report['exit_code'],log_ref=evidence.file(report['stdout']['path'])),
            'reason':'Actual msprof CSVs and normalized values collected earlier; this event binds the completed evidence.'},
            artifact_refs=[ref,evidence.file(report_path)],event_id=op+f'-baseline-profile-{case:02d}-bound')
    for path in sorted((task/'candidates').glob('*/candidate_plan.json')):
        plan=json.loads(path.read_text());support=[evidence.file(path)]
        for name in plan.get('supporting_evidence',[]):
            source=Path(name)
            if source.is_file():support.append(evidence.file(source))
        counter=[]
        if plan.get('contradicting_evidence'):
            counter.append(register_json_artifact(store,{'kind':'worker_source_counterarguments',
                'assessment_basis':'manual','candidate_id':plan['candidate_id'],
                'statements':plan['contradicting_evidence'],'candidate_plan_hash':support[0]}))
        payload={'symptoms':text_items(plan.get('symptoms',[plan['rationale']])),
                 'mechanisms':text_items(plan.get('mechanisms',[])), 'assessment_basis':'inferred',
                 'supporting_evidence':support,'contradicting_evidence':counter,
                 'missing_evidence':text_items(plan.get('missing_evidence',[])),
                 'source_anchors':text_items(plan.get('source_anchors',[]))}
        writer.append('diagnosis_recorded',payload,attempt_id=plan['candidate_id'],candidate_id=plan['candidate_id'],
                      artifact_refs=support+counter,event_id=plan['candidate_id']+'-diagnosis-imported')
    print(json.dumps({'operator':op,'knowledge_entries':len(entries),'status':'imported'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operator');import_worker(p.parse_args().operator)
