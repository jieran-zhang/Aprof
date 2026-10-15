#!/usr/bin/env python3
"""Record a candidate-parent A/A with the existing Level2 cohort producer.

Fixed ledger controls only admit baseline identity. This coordinator gives a
validated candidate parent its own named, immutable A/A request and cost
receipt. It does not create a source attempt or a timing stage in the ledger.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from msprof_exploration_campaign import Campaign
from msprof_exploration_execute import (ALL_CASES, cohort_plan, collect_cohort,
                                         load, pointer, preflight_cohort, save, sha, task_paths)
from run_msprof_exploration_stage import actual_costs, timing_runner, verify_source_snapshot
from msprof_raw_storage import LOCAL

VERSION = 'level2_candidate_parent_aa_control_v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def prepare(run, operator, candidate, name, handoff):
    run, split, task, parent, source = task_paths(run, operator, candidate)
    root = task / 'parent-controls' / name
    require(candidate != 'baseline' and not root.exists(), 'new candidate parent control directory required')
    ledger = Campaign(run / split / 'ledger')
    item = ledger.state['tasks'][operator]['candidates'][candidate]
    require(item['feedback_closed'] and item['observation_ids'], 'parent feedback is not closed')
    observation = ledger.state['tasks'][operator]['observations'][item['observation_ids'][-1]]
    require(observation['close_feedback'] is True and observation['quality'].get('complete_measurement') is True,
            'parent has no complete measured feedback')
    feedback = task / 'feedback' / (candidate + '.json')
    require(pointer(feedback)['sha256'] == observation['report_ref'], 'parent feedback differs')
    archive = parent / 'source.tar'
    require(pointer(archive)['sha256'] == item['source_hash'], 'parent source hash differs')
    verify_source_snapshot(archive, source)
    for stage in ('build', 'correctness', 'runtime'):
        require(load(parent / 'stages' / stage / 'result.json')['status'] == 'passed',
                'parent ' + stage + ' did not pass')
    require(load(parent / 'boundary-validation/completion.json')['status'] == 'passed',
            'parent boundary guards did not pass')
    from level2_legacy_epoch import check
    epoch = check(handoff)['epoch']
    build = parent / 'build/build_manifest.json'
    plan = cohort_plan(task, build, timing_runner(run), ALL_CASES, 'aa', name, epoch=epoch,
                       capture_storage=LOCAL)
    preflight_cohort(plan)
    root.mkdir(parents=True)
    save(root / 'plan.json', plan)
    request = {'version': VERSION, 'operator': operator, 'candidate': candidate,
               'name': name, 'source': pointer(archive), 'build': pointer(build),
               'feedback': pointer(feedback), 'handoff': pointer(handoff),
               'plan': pointer(root / 'plan.json'), 'producer': pointer(__file__),
               'metric': 'operator_task_sum_us', 'capture_storage': 'local_tmp_full_copyback_v1',
               'source_attempt_added': False}
    save(root / 'request.json', request)
    return pointer(root / 'request.json')


def collect(request_path):
    request_path = Path(request_path).resolve()
    request = load(request_path)
    require(request.get('version') == VERSION and request.get('producer') == pointer(__file__),
            'parent control producer differs')
    root = request_path.parent
    require(request.get('plan') == pointer(root / 'plan.json')
            and request.get('source') == pointer(request['source']['path'])
            and request.get('build') == pointer(request['build']['path'])
            and request.get('feedback') == pointer(request['feedback']['path'])
            and request.get('handoff') == pointer(request['handoff']['path']),
            'parent control request changed')
    require(not (root / 'cohort').exists() and not (root / 'completion.json').exists(),
            'parent control already started; preserve incomplete evidence')
    plan = load(root / 'plan.json')
    preflight_cohort(plan)
    error = None
    try:
        report = collect_cohort(plan, root / 'cohort')
        require(report['evidence_status'] == 'verified_complete'
                and report['comparison_kind'] == 'aa'
                and report['case_ids'] == [str(c) for c in ALL_CASES],
                'parent control report is incomplete')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        cohort = root / 'cohort'
        receipt = {'version': VERSION, 'status': 'failed' if error else 'passed',
                   'request': pointer(request_path), 'error': error,
                   'group_completion': pointer(cohort / 'group-completion.json') if cohort.exists() else None,
                   'report': pointer(cohort / 'report.json') if (cohort / 'report.json').is_file() else None,
                   'actual_costs': actual_costs(cohort) if cohort.exists() else {},
                   'source_attempt_added': False}
        save(root / 'completion.json', receipt)
    return pointer(root / 'completion.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for key in ('run', 'operator', 'candidate', 'name', 'handoff'):
        p.add_argument('--' + key, required=True)
    p = sub.add_parser('collect'); p.add_argument('--request', required=True)
    args = parser.parse_args()
    result = (prepare(args.run, args.operator, args.candidate, args.name, args.handoff)
              if args.command == 'prepare' else collect(args.request))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
