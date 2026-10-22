#!/usr/bin/env python3
"""Record idle/loaded baseline A/A before selecting physical-device concurrency."""
from __future__ import annotations
import concurrent.futures
import json
from pathlib import Path
from collect_level1_traces import Campaign, ROOT
from run_aprof_job import dump
from aprof_runtime.traces import verify_trace
from aprof_runtime.jsonio import content_hash


def run_calibration(campaign=None):
    c=campaign or Campaign(); op='exp'; base=c.task(op)/'baseline'
    root=c.run/'calibration'; root.mkdir(exist_ok=True)
    cases=[1,8,14,20]
    stream=c.task(op)/'trace_events.jsonl'
    verify_trace(stream,c.store(op))
    recorded={row['event_id']:row for row in (json.loads(line) for line in stream.read_text().splitlines())}
    def measure(host,device,phase,count=1):
        out=root/phase/host/f'device-{device:02d}'
        env={}
        if count>1:
            env={'APROF_CALIBRATION_BARRIER':str(root/phase/'barrier'),
                 'APROF_CALIBRATION_PARTICIPANT':f'{host}-{device}',
                 'APROF_CALIBRATION_COUNT':str(count)}
        argv=['python3',ROOT/'scaffolding/collection/scripts/cannbench_device_timing.py','measure',
              '--baseline',base,'--candidate',base,'--cases',','.join(map(str,cases)),
              '--device','0','--output',out,'--input-root',c.prepared(op),
              '--pairs','30','--warmup','10','--repeat','100','--external-lock']
        result=c.job(op,f'calibration/{phase}-{host}-{device}',argv,cwd=base,
                     host=host,device=device,timeout=1800,environment=env)
        event_id=result['job']['job_id']+'-completed'
        if event_id in recorded:
            if content_hash(result) not in recorded[event_id]['payload'].get('artifact_refs',[]):
                raise ValueError('recorded calibration execution differs from checkpoint')
        else:
            c.record(op,result,stage='concurrency_calibration')
        report=out/'measurement_report.json'
        return json.loads(report.read_text()) if report.exists() else {'stable':False,'per_case':[],'reasons':['execution failed']}
    # Two hosts are independent; each host has exactly one idle probe at a time.
    def idle_host(host):
        values={}
        for device in range(16):
            values[device]=measure(host,device,'idle')
            print('idle',host,device,values[device]['stable'],flush=True)
        return values
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        idle=dict(zip(['local','decode'],pool.map(idle_host,['local','decode'])))
    rounds=[]
    for width in [32,16,8,4,2,1]:
        # After the required 32/16 probes, use independently qualified idle
        # chips, with at most one chip per physical card. A noisy chip zero
        # must not invalidate every smaller topology by construction.
        by_host={}
        for host in ['local','decode']:
            evens=list(range(0,16,2))
            preferred=sorted(evens,key=lambda device:(not idle[host][device]['stable'],device))
            by_host[host]=list(range(16)) if width==32 else evens if width==16 else preferred[:max(1,width//2)]
        if width==1:by_host['decode']=[]
        participants=[(h,d) for h in ['local','decode'] for d in by_host[h]]
        outcomes=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
            futures={pool.submit(measure,h,d,f'loaded-{width}',width):(h,d) for h,d in participants}
            for future in concurrent.futures.as_completed(futures):
                host,device=futures[future]; loaded=future.result(); reference=idle[host][device]
                controls={r['case_id']:r for r in reference['per_case']}
                comparisons=[]
                for row in loaded['per_case']:
                    ref=controls.get(row['case_id'],{})
                    a,b=ref.get('baseline_median_ns'),row.get('baseline_median_ns')
                    shift=abs(b/a-1) if a and b else None
                    comparisons.append({'case_id':row['case_id'],'idle_median_ns':a,'loaded_median_ns':b,
                                        'relative_shift':shift,'passed':shift is not None and shift<=.02})
                good=bool(reference['stable'] and loaded['stable'] and len(comparisons)==4 and all(r['passed'] for r in comparisons))
                outcomes.append({'host':host,'physical_device':device,'passed':good,'cases':comparisons,
                                 'idle_stable':reference['stable'],'loaded_stable':loaded['stable']})
                print('loaded',width,host,device,good,flush=True)
        accepted=all(r['passed'] for r in outcomes)
        value={'schema_version':'1.0.0','width':width,'accepted':accepted,'outcomes':outcomes}
        dump(root/f'calibration-{width}.json',value); rounds.append(value)
        if accepted:
            selection={'schema_version':'1.0.0','accepted':True,'max_device_jobs':width,
                       'physical_devices_by_host':by_host,'calibration_ref':str(root/f'calibration-{width}.json'),
                       'protocol':{'cases':cases,'pairs':30,'warmup':10,'repeat':100,'max_cv':.05,'max_idle_shift':.02}}
            dump(root/'selection.json',selection); return selection
    selection={'schema_version':'1.0.0','accepted':False,'max_device_jobs':0,
               'reason':'All tested concurrency levels failed idle/loaded A/A CV or median-shift qualification'}
    dump(root/'selection.json',selection); return selection


if __name__=='__main__': print(json.dumps(run_calibration(),allow_nan=False))
