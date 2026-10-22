"""Join rejected hardware history and offline cost evidence; never grant admission."""
import json
from pathlib import Path

from measurement_source_archive import HistoricalEvidence
from replay_offline_task_export import IDS, execution, load, replay_offline_study
from replay_task_sampling_window_history import replay_task_sampling_window_history
from replay_timing_diagnosis import read, require

PURPOSE = 'retained_history_for_task_window_method_qualification'
PROTOCOL = 'shared_buffer_msprof_task_window_v1'


def replay_cpu_cost(evidence, source):
    directory = Path(source['directory'])
    plan = load(evidence, source['plan_ref']); result = load(evidence, source['result_ref'])
    actual = load(evidence, source['execution_ref']); job = load(evidence, source['job_ref'])
    require(Path(source['plan_ref']['path']) == directory / 'fixed-plan.json'
            and Path(source['result_ref']['path']) == directory / 'comparison.json'
            and plan['purpose'] == 'single CPU-only old-then-new CAS-cost comparison'
            and plan['attempts_per_arm'] == 1 and plan['request_count_per_arm'] == 10
            and plan['trial_order'] == ['old', 'new'] and result['fixed_plan_ref'] == source['plan_ref']['sha256']
            and result['scope'] == 'one CPU-only ten-request run per source; no hardware or publication claim',
            'CPU cost observation identity differs')
    require(job['argv'][1:] == [str(directory / 'probe.py'), 'run'] and job['cwd'] == str(directory)
            and job['output_dir'] == str(directory / 'execution') and job['timeout_seconds'] == 900,
            'CPU observation command differs')
    start, end = execution(evidence, actual, job)
    evidence.bind(job['argv'][0], plan['interpreter_ref'])
    for name, key in [('probe.py', 'runner_ref'), ('verifier.py', 'verifier_ref'), ('prepared.json', 'prepared_ref')]:
        evidence.bind(directory / name, plan[key])
    evidence.bind(Path(__file__).resolve().parents[3] / 'skill-libs/graph-base/0.5.1/runtime/src/aprof_runtime/store.py',
                  plan['store_ref'])
    evidence.bind(plan['source_archive_index'], plan['source_archive_index_ref'])
    for ref in plan['source_refs'].values():
        evidence.bind(ref['path'], ref['sha256'])
    require(Path(actual['stdout']['path']).read_text().strip() == "completed arms: ['old', 'new']",
            'CPU cost run did not complete the fixed arms')
    previous = start; outputs = {}; costs = {}
    for arm in plan['trial_order']:
        summary = result['arms'][arm]
        evidence.bind(directory / arm / 'request-plan.json', plan['request_plan_refs'][arm])
        arm_path = directory / arm / 'arm-run.json'
        evidence.bind(arm_path, summary['arm_run_ref']); run = read(arm_path)
        require(run['arm'] == arm and run['error'] is None and run['source_ref'] == plan['source_refs'][arm]['sha256']
                and len(run['receipts']) == len(run['request_seconds']) == 10
                and run['total_seconds'] == summary['total_seconds']
                and run['request_seconds'] == summary['request_seconds'], 'CPU arm receipt differs')
        outputs[arm] = []; times = []
        for index, receipt in enumerate(run['receipts']):
            request_dir = directory / arm / f'request-{index:02d}'
            saved = evidence.json(directory / arm / f'request-{index:02d}-cost.json')
            require(saved['receipt'] == receipt and saved['seconds'] == run['request_seconds'][index]
                    and receipt['request_index'] == index and receipt['exit_status'] == 0
                    and previous <= receipt['started_at'] <= receipt['finished_at'] <= end,
                    'CPU request receipt, cost or chronology differs')
            expected_output = str(request_dir / 'output.bin')
            require(receipt['output_refs'] == {expected_output: plan['output_refs'][arm][expected_output]},
                    'CPU output binding differs')
            outputs[arm].append(evidence.bind(expected_output, receipt['output_refs'][expected_output])['sha256'])
            for name, key in [('result.json', 'result_ref'), ('stdout.log', 'log_ref'), ('stderr.log', 'stderr_ref')]:
                evidence.bind(request_dir / name, receipt[key])
            times.append(saved['seconds']); previous = receipt['finished_at']
        require(set(plan['output_refs'][arm]) == {str(directory / arm / f'request-{i:02d}/output.bin') for i in range(10)},
                'CPU fixed output roster differs')
        costs[arm] = {'recorded_total_seconds': run['total_seconds'], 'request_seconds_sum': sum(times),
                      'request_count': len(times)}
    require(outputs['old'] == outputs['new'] and result['all_ten_results_identical'] is True,
            'CPU comparison output bytes differ')
    return {'authority': 'cpu_cost_observation_only', 'eligible_for_publication': False,
            'hardware_samples': 0, 'outer_seconds': actual['duration_seconds'], 'arms': costs,
            'scope': 'Synthetic CPU verifier cost observation; no hardware or numerical-oracle admission.'}


def replay_task_window_method_history(reference):
    # This single cache covers all offline studies; shared original files are read once.
    history = read(reference['path'])
    require(isinstance(history, dict) and isinstance(history.get('source_archive_refs'), list),
            'method history lacks explicit producer archives')
    evidence = HistoricalEvidence(history['source_archive_refs'], logical_paths=True)
    evidence.bind(reference['path'], reference['sha256'])
    require(set(history) == {'schema_version', 'purpose', 'protocol', 'not_a_release', 'eligible_for_publication',
                           'prior_window_history_ref', 'source_archive_refs', 'offline_export_studies',
                           'oracle_cpu_cost', 'proposal_ref'}
            and history['schema_version'] == 1 and history['purpose'] == PURPOSE and history['protocol'] == PROTOCOL
            and history['not_a_release'] is True and history['eligible_for_publication'] is False,
            'method history is not a historical-only source chain')
    load(evidence, history['proposal_ref'])
    require(tuple(item['id'] for item in history['offline_export_studies']) == IDS,
            'offline predecessor roster is incomplete or reordered')
    prior = replay_task_sampling_window_history(history['prior_window_history_ref'])
    require(prior['valid'] is True and prior['accepted'] is False and prior['eligible_for_publication'] is False,
            'prior rejected history did not replay')
    studies = [replay_offline_study(evidence, item, index)
               for index, item in enumerate(history['offline_export_studies'])]
    cpu = replay_cpu_cost(evidence, history['oracle_cpu_cost'])
    return {'valid': True, 'authority': 'historical_task_window_method', 'accepted': False,
            'eligible_for_publication': False, 'protocol': PROTOCOL, 'history': reference,
            'prior_rejected_history': prior, 'offline_export_studies': studies, 'oracle_cpu_cost': cpu,
            'cost_scope': 'Execution wall clocks are recomputed; clone/persistence monotonic costs are bound original observations.',
            'files': evidence.semantic_files(), 'resolved_files': evidence.resolved_files}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(replay_task_window_method_history({'path': str(args.history.resolve()),
                                                     'sha256': args.expected_sha256}), sort_keys=True))
