#!/usr/bin/env python3
"""Execute a frozen, finite msprof method-study schedule once, serially."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from cannbench_msprof_timing import load, summarize
from cannbench_shared_context_profile import save, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    plan=load(args.plan)
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'plan.json',plan)
    tool=Path(__file__).with_name('cannbench_msprof_timing.py')
    shutil.copyfile(tool,out/tool.name)
    shutil.copyfile(__file__,out/Path(__file__).name)
    bindings={str(p):sha(p) for p in [args.plan,tool,__file__,*[s['request'] for s in plan['schedule']]]}
    save(out/'bindings.json',bindings)
    started=time.time();completed=[];error=None
    env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
    try:
        for entry in plan['schedule']:
            name=entry['name']
            if not name or Path(name).name!=name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
                raise ValueError('unsafe session name')
            for p in [str(tool),entry['request']]:
                if sha(p)!=bindings[p]:raise ValueError('study input changed: '+p)
            target=out/name
            print(json.dumps(dict(event='start',name=name,time=time.time())),flush=True)
            with (out/(name+'.controller.log')).open('x') as log:
                process=subprocess.run([sys.executable,str(tool),'collect','--request',entry['request'],'--output',str(target)],env=env,stdout=log,stderr=subprocess.STDOUT)
            if process.returncode:
                raise RuntimeError(f'{name}: collection failed; retained evidence, no automatic retry')
            completed.append(dict(**entry,output=str(target)))
            print(json.dumps(dict(event='complete',name=name,count=len(completed),time=time.time())),flush=True)
        for cohort in sorted({e['cohort'] for e in completed}):
            summary=summarize([e['output'] for e in completed if e['cohort']==cohort])
            save(out/(cohort+'-summary.json'),summary)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc))
        raise
    finally:
        save(out/'completion.json',dict(status='failed' if error else 'passed',started_at=started,ended_at=time.time(),
             completed=completed,planned=len(plan['schedule']),error=error,formal_admission='not_evaluated'))


if __name__=='__main__':main()
