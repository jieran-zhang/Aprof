#!/usr/bin/env python3
"""Close an unstarted source search after an evidenced method-quality failure.

This CPU-only operation does not retry measurement, create a source attempt,
change the ledger, or invoke a production gate. Candidate-bearing tasks require
their own feedback closure instead.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from shared_context_campaign import Ledger
from shared_context_report import verify_report


def load(path):
    from trace_v2_dataset import strict_loads
    return strict_loads(Path(path).read_bytes())


def close(run, operator):
    run = Path(run).resolve()
    ledger = Ledger(run / 'ledger')
    task = ledger.state['tasks'][operator]
    if task['candidates']:
        raise ValueError('Candidate-bearing task needs explicit source feedback closure')
    if any(s['attempts'][-1]['outcome'] is None for s in task['stages'].values()):
        raise ValueError('Cannot close a running task')
    directory = run / 'tasks' / operator
    result = load(directory / 'qualification-result.json')
    if result['status'] != 'quality_failed' or result.get('error') is not None:
        raise ValueError('This closure requires completed quality_failed evidence')
    stage = task['stages'][operator + '-baseline-qualification']
    if stage['attempts'][-1]['outcome'] != 'quality_failed':
        raise ValueError('Qualification result differs from ledger')
    q = directory / 'qualification'
    manifest, sessions, report = (load(q / name) for name in ('manifest.json', 'sessions.json', 'report.json'))
    verify_report(manifest, sessions, report)
    if manifest['task_id'] != operator or manifest['run_id'] != run.name:
        raise ValueError('Foreign qualification evidence')
    if report['measurement_quality']['observed_checks_pass']:
        raise ValueError('Passing qualification is not a method blocker')
    if result['failures'] != report['measurement_quality']['failures']:
        raise ValueError('Failure summaries differ')
    groups = Counter((f['check'], f['status']) for f in result['failures'])
    summary = [{'check': check, 'status': status, 'count': n}
               for (check, status), n in sorted(groups.items())]
    paths = [directory / n for n in ('qualification-result.json', 'agent-initial-review.json',
             'baseline-binding.json', 'input-bindings.json', 'baseline-memory-plan.json')]
    paths += [q / n for n in ('manifest.json', 'report.json', 'wrapper-started.json', 'memory-plan-binding.json')]
    evidence = [{'path': str(p), 'sha256': 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in paths]
    value = {'schema_version': 'shared_context_task_closure_v1', 'run_id': run.name,
             'operator': operator, 'split': ledger.config['tasks'][operator]['split'],
             'recorded_at': datetime.now(timezone.utc).isoformat(),
             'status': 'blocked_measurement_qualification',
             'reason': 'Completed baseline A/A failed its frozen qualification criteria; candidate benefit cannot be evaluated under this method scope.',
             'source_attempts': [], 'qualification': {'status': 'quality_failed', 'failure_groups': summary,
                 'case_ids': result['cases'], 'successful_sessions': result['successful_sessions'],
                 'actual_costs': result['actual_costs']},
             'candidate_performance': {'status': 'not_measured', 'speedup': None,
                 'missing_reason': 'baseline_method_not_qualified'},
             'production_admission': 'not_evaluated', 'graph_policy_eligible': False, 'episode_ref': None,
             'used': task['used'], 'remaining': ledger.status()['tasks'][operator]['remaining'],
             'decision': {'action': 'stop_this_source_search_continue_other_declared_tasks',
                 'automatic_retry': False, 'new_candidate': None},
             'next_questions': ['Which failed factor contrasts reflect bias, and which intervals lack precision? Diagnose from the retained raw sessions before planning any independent method experiment.'],
             'evidence': evidence, 'historical_verdicts_changed': False}
    target = directory / 'closure.json'
    with target.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--operator', required=True)
    args = parser.parse_args()
    value = close(args.run, args.operator)
    print(json.dumps({'operator': args.operator, 'status': value['status'],
                      'failure_groups': value['qualification']['failure_groups']}))
