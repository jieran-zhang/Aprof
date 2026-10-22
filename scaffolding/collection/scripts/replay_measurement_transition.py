"""Audit the prospective duration-method change and its retained failed history."""
from datetime import datetime
from pathlib import Path

from replay_timing_diagnosis import Evidence, read, require


def replay_transition(reference, *, qualification_dir=None):
    evidence = Evidence()
    evidence.bind(reference['path'], reference['sha256'])
    transition = read(reference['path'])
    require(transition.get('schema_version') == 1
            and transition.get('purpose') == 'prospective_calibrated_shared_buffer_v2'
            and transition.get('protocol') == 'shared_buffer_acl_event_v2',
            'unregistered measurement-method transition')
    if qualification_dir is not None:
        require(Path(transition['qualification_dir']).resolve() == Path(qualification_dir).resolve(),
                'method transition targets another qualification campaign')
    require(transition['calibration'] == {
        'pilot_processes_per_case': 1, 'pilot_baseline_samples': 3, 'pilot_repeat': 100,
        'target_ms': 50, 'repeat_floor': 100, 'repeat_cap': 100000,
        'formula': 'max(100,100*ceil(50/median(pilot_elapsed_ms)))',
        'over_cap': 'fail_without_clipping', 'recalibration': 'none'}, 'calibration policy changed')
    require(transition['unchanged_controls'] == {'cv': .05, 'role_bias': .02, 'before_after_shift': .02,
        'cycles': 6, 'pairs_per_phase_per_cycle': 5, 'scope': 'each_cycle_and_all_cycles'},
        'method transition changes control thresholds')
    require(transition['production_changes'] == ['baseline_only_pilot_warmup', 'fixed_persistent_python_oracle'],
            'unregistered production changes beyond the duration study')
    refs = transition['source_archives']
    require(len(refs) == 2, 'both historical source snapshots are required')
    for item in refs:
        evidence.bind(item['path'], item['sha256'])
    study = transition['duration_study']
    for name in ('anchor', 'replay', 'summary'):
        evidence.bind(study[name]['path'], study[name]['sha256'])
    anchor = read(study['anchor']['path'])
    amendment = anchor['amendment']
    evidence.bind(amendment['path'], amendment['sha256'])
    repair = read(amendment['path'])
    require(repair['purpose'] == 'zero_native_anchor_hash_format_correction', 'unknown study entrance repair')
    for name in ('old_anchor', 'failed_execution', 'failed_stderr'):
        evidence.bind(repair[name]['path'], repair[name]['sha256'])
    failed = read(repair['failed_execution']['path'])
    require(failed['exit_code'] != 0 and 'root anchor does not bind study plan'
            in Path(repair['failed_stderr']['path']).read_text(), 'missing original zero-native entrance failure')
    previous_end = datetime.fromisoformat(failed['finished_at']).timestamp()
    require(previous_end <= anchor['created_at'], 'study repair predates its entrance failure')
    for stage, limit in (('pilot', 1200), ('confirm', 2400)):
        job_ref = anchor['replacement_jobs'][stage]
        execution_ref = study[stage + '_execution']
        evidence.bind(job_ref['path'], job_ref['sha256'])
        evidence.bind(execution_ref['path'], execution_ref['sha256'])
        job, execution = read(job_ref['path']), read(execution_ref['path'])
        require(execution['job'] == job and job['timeout_seconds'] == limit and execution['exit_code'] == 0
                and job['argv'][-2:] == ['--anchor', study['anchor']['path']], 'study bounded execution differs')
        begin = datetime.fromisoformat(execution['started_at']).timestamp()
        end = datetime.fromisoformat(execution['finished_at']).timestamp()
        require(max(previous_end, anchor['created_at']) <= begin <= end
                and execution['duration_seconds'] <= limit, 'study execution order/budget differs')
        for name in ('stdout', 'stderr'):
            evidence.bind(execution[name]['path'], execution[name]['sha256'])
        previous_end = end
    from run_event_duration_study import replay
    result = replay(Path(study['directory']), Path(study['anchor']['path']), source_archive_refs=refs)
    require(result == read(study['replay']['path']) and result['research_controls_passed'] is True,
            'four-case duration study did not independently replay')
    terminal = read(Path(study['directory']) / 'confirmation-terminal.json')
    require(terminal['finished_at'] <= transition['created_at'], 'transition predates the completed duration study')
    prior = transition['previous_failed_campaign']
    evidence.bind(prior['roster']['path'], prior['roster']['sha256'])
    evidence.bind(prior['replay']['path'], prior['replay']['sha256'])
    from run_shared_timing_confirmation import replay_confirmation_campaign
    previous = replay_confirmation_campaign(Path(prior['roster']['path']),
        qualification_dir=Path(prior['directory']), source_archive_refs=refs)
    require(previous['complete'] is True and previous['accepted'] is False,
            'previous rejected campaign was not preserved')
    require({k: v['status'] for k, v in previous['slots'].items()} == {
        'exp-confirmation': 'failed', 'sigmoid-confirmation': 'failed',
        'exp-timeline-01': 'not_run', 'exp-timeline-09': 'not_run',
        'sigmoid-timeline-01': 'not_run', 'sigmoid-timeline-04': 'not_run'},
        'previous failed/blocked attempt inventory changed')
    require(read(prior['replay']['path'])['accepted'] is False, 'previous saved decision changed')
    return {'valid': True, 'accepted': False, 'purpose': 'entry_to_new_full_qualification_only',
            'transition': reference, 'duration_study': result,
            'retained_failed_campaign': prior['roster'], 'source_archives': refs}
