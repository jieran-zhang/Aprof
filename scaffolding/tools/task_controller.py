#!/usr/bin/env python3
"""Maintained command submission for graph-base/1.2.0 soft-target tasks.

The coordinator chooses commands. Runtime owns launch/terminal evidence; this
bridge never invents numerical results or runs a separate optimization scheduler.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def run_commands(package, root, requests, *, target=3120):
    package, root = Path(package).resolve(), Path(root).resolve()
    sys.path.insert(0, str(package/'runtime/src'))
    from aprof_runtime.execution_policy import local_path, append
    from aprof_runtime.local_evidence import LocalEvidence
    from aprof_runtime.local_archive import freeze_package_identity
    from aprof_runtime.task_budget import prepare_budget_plan, run_task
    local_path(root)
    local = LocalEvidence(root/'controller-records')
    package_ref = freeze_package_identity(local)
    scope = local.register_json({'kind':'command_sequence_v2', 'requests':requests, 'target_seconds':target})
    budget = local.register_json(prepare_budget_plan(task_id=root.name, scope_ref=scope, budget_seconds=target))
    prior, outcomes = [], {}
    started = time.monotonic()
    for item in requests:
        name = item['id']
        if name in outcomes:
            raise ValueError('duplicate command id')
        if any(outcomes.get(dep, {}).get('status') != 'passed' for dep in item.get('depends_on', [])):
            outcomes[name] = {'status':'not_evaluated', 'reason':'dependency_failed'}
            continue
        cwd = local_path(item['cwd'])
        if not cwd.is_relative_to(root):
            raise ValueError('command cwd outside task root')
        env = {k:v for k,v in os.environ.items() if k in ('PATH','LANG','LD_LIBRARY_PATH','ASCEND_HOME_PATH','ASCEND_OPP_PATH','ASCEND_AICPU_PATH','CMAKE_PREFIX_PATH')}
        env.update(item.get('env', {}))
        env.update(APROF_TASK_ROOT=str(root), TMPDIR=str(root/'tmp'), PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(package/'runtime/src'))
        (root/'tmp').mkdir(exist_ok=True)
        out = root/'commands'/name
        out.parent.mkdir(exist_ok=True)
        job = local.register_json({'argv':item['argv'], 'cwd':str(cwd), 'environment':env,
            'output_dir':str(out), 'timeout_seconds':item.get('target_seconds', target),
            'package_identity_ref':package_ref})
        result = run_task(local, budget_ref=budget, job_ref=job, destination=out, prior_terminal_refs=prior)
        prior.append(result['terminal_ref']); outcomes[name] = result
        append(root/'checkpoints.jsonl', {'event':'command_closed', 'id':name, **result})
        (root/'controller-results.json').write_text(json.dumps({'execution':outcomes,
            'elapsed_seconds':time.monotonic()-started, 'target_seconds':target,
            'budget_warnings':['target_exceeded'] if time.monotonic()-started>target else [],
            'performance_verdict':'not_evaluated', 'automatic_archive':False}, indent=2))
    return outcomes


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--skill-lib', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--requests', type=Path, required=True)
    p.add_argument('--target-seconds', type=float, default=3120)
    a=p.parse_args()
    outcomes=run_commands(a.skill_lib,a.workspace,json.loads(a.requests.read_text()),target=a.target_seconds)
    print(json.dumps(outcomes))
    return int(any(v['status']!='passed' for v in outcomes.values()))


if __name__=='__main__':
    raise SystemExit(main())
