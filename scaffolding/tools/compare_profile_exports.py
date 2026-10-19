#!/usr/bin/env python3
"""Controlled cold export from identical read-only raw trace copies in /dev/shm."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def module(package,label):
    for name in list(sys.modules):
        if name == 'aprof_runtime' or name.startswith('aprof_runtime.') or name == 'fast_task_samples':
            del sys.modules[name]
    script=package/'skills/ascendc-aprof-profiling/scripts/single_role_task.py'
    sys.path.insert(0,str(script.parent))
    spec=importlib.util.spec_from_file_location(label,script)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def compare(old,new,traces,output,python,exporter):
    output=Path(output).absolute()
    if output.resolve()!=output or not output.is_relative_to('/dev/shm'):
        raise ValueError('comparison output must be under /dev/shm')
    output.mkdir(parents=True,exist_ok=False)
    runners={'old':module(Path(old),'old_export'),'new':module(Path(new),'new_export')}
    raw={}
    for i,trace in enumerate(traces):
        trace=Path(trace)
        raw[i]={str(p.relative_to(trace)):digest(p) for p in trace.rglob('*') if p.is_file()
            and not any(x in p.relative_to(trace).parts for x in ('sqlite','summary','timeline','mindstudio_profiler_output','mindstudio_profiler_log'))
            and p.suffix not in ('.db','.csv')}
        for arm in ('old','new'):
            dest=output/arm/f'case_{i}'/trace.name
            for name,sha in raw[i].items():
                p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(trace/name,p)
                assert digest(p)==sha
    results=[]
    # Alternate order; both sides start without SQLite/CSV/derived cache.
    for i,trace in enumerate(traces):
        for arm in (('old','new') if i%2==0 else ('new','old')):
            cwd=output/arm/f'case_{i}';profile=cwd/Path(trace).name
            argv=[python,exporter,'export','summary','-dir',str(profile),'--format','csv']
            started=time.monotonic()
            import os
            runner=runners[arm]
            stage=runner.run_stage(cwd,'export',argv,dict(os.environ,TMPDIR=str(output)),time.monotonic()+600,runner.subprocess_runner)
            table_name,table=runner.selected_table(profile)
            parsed=runner.complete_calls(table if table_name=='kernel_details' else None,table if table_name=='op_summary' else None,['exp_kernel'])
            results.append({'arm':arm,'case_index':i,'seconds':time.monotonic()-started,'stage':stage,'values_us':parsed['values_us'],'raw_files':len(raw[i]),'derived_input_cache_used':False})
    for i in range(len(traces)):
        pairs=[r for r in results if r['case_index']==i]
        assert pairs[0]['values_us']==pairs[1]['values_us']
    value={'results':results,'raw_inventory':raw,'controlled_storage':'both /dev/shm','export_parameters_equal':True,
        'limits':'Exporter itself unchanged. This tests identical cold raw parsing and sample equivalence, not a causal JuiceFS comparison. Serial export only.'}
    (output/'comparison.json').write_text(json.dumps(value,indent=2))
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old',required=True);p.add_argument('--new',required=True)
    p.add_argument('--trace',action='append',required=True);p.add_argument('--output',required=True)
    p.add_argument('--python',required=True);p.add_argument('--exporter',required=True)
    a=p.parse_args();v=compare(a.old,a.new,a.trace,a.output,a.python,a.exporter)
    print(json.dumps([{'arm':x['arm'],'case':x['case_index'],'seconds':x['seconds']} for x in v['results']]))
