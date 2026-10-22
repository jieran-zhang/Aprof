"""Preserve prior failures when moving from Event to Task Duration timing."""
from pathlib import Path

from replay_timing_diagnosis import Evidence, read, replay_diagnosis, require


def replay_task_history(reference):
    evidence = Evidence()
    evidence.bind(reference['path'], reference['sha256'])
    history = read(reference['path'])
    if history.get('purpose') == 'retained_history_for_local_task_duration_method_qualification':
        return replay_local_task_history(reference, history, evidence)
    require(isinstance(history, dict) and set(history) == {
        'schema_version', 'purpose', 'protocol', 'previous_campaign', 'task_diagnostic',
        'shared_buffer_anchor', 'event_method_transition'}, 'invalid Task method history')
    require(history['schema_version'] == 1
        and history['purpose'] == 'retained_history_for_task_duration_method_qualification'
        and history['protocol'] == 'shared_buffer_msprof_task_v1', 'wrong Task history authority')
    from replay_measurement_transition import replay_transition
    older = replay_transition(history['event_method_transition'])
    require(older['valid'] is True and older['accepted'] is False,
            'older Event failures and duration study were not preserved')
    from run_shared_timing_confirmation import replay_confirmation_campaign
    previous = history['previous_campaign']
    require(set(previous) == {'directory', 'roster', 'source_archives'}, 'invalid previous campaign reference')
    evidence.bind(previous['roster']['path'], previous['roster']['sha256'])
    campaign = replay_confirmation_campaign(Path(previous['roster']['path']),
        qualification_dir=Path(previous['directory']), source_archive_refs=previous['source_archives'])
    require(campaign['complete'] is True and campaign['accepted'] is False
        and campaign['eligible_for_publication'] is False, 'previous Event campaign cannot qualify Task timing')
    expected = {'exp-confirmation': 'failed', 'exp-timeline-01': 'not_run', 'exp-timeline-09': 'not_run',
                'sigmoid-confirmation': 'passed', 'sigmoid-timeline-01': 'passed', 'sigmoid-timeline-04': 'passed'}
    require({key: row['status'] for key, row in campaign['slots'].items()} == expected,
            'old failed, skipped or passed attempts were omitted')
    from diagnose_task_duration import replay
    diagnostic = history['task_diagnostic']
    require(set(diagnostic) == {'directory', 'anchor', 'source_archives'}, 'invalid Task diagnostic reference')
    evidence.bind(diagnostic['anchor']['path'], diagnostic['anchor']['sha256'])
    task = replay(Path(diagnostic['directory']), Path(diagnostic['anchor']['path']),
                  source_archive_refs=diagnostic['source_archives'])
    require(task['complete_diagnostic_only'] is True and task['accepted'] is False
        and task['publication_acceptance'] is False and task['eligible_for_publication'] is False
        and task['events'] == 30 and task['complete_kernel_tasks'] == 220222,
        'Task diagnostic is incomplete or was relabeled as formal acceptance')
    anchor = history['shared_buffer_anchor']
    evidence.bind(anchor['path'], anchor['sha256'])
    shared = replay_diagnosis(Path(anchor['path']))
    require(shared['shared_buffer_entry_qualified'] is True, 'shared-buffer entry did not qualify')
    return {'valid': True, 'eligible_for_publication': False,
        'purpose': 'history_preservation_only_new_hardware_qualification_required',
        'history': reference, 'previous_campaign_statuses': expected,
        'event_transition': history['event_method_transition'],
        'task_diagnostic_summary': task['summary'], 'shared_buffer_anchor': anchor,
        'resolved_producers': campaign['resolved_producers'] | task['resolved_producers'],
        'files': {path: item['sha256'] for path, item in evidence.files.items()}}


def replay_local_task_history(reference, history, evidence):
    require(set(history) == {'schema_version', 'purpose', 'protocol', 'previous_history',
            'cancelled_task_attempt', 'native_facility', 'cost_observations'}
            and history['schema_version'] == 1
            and history['protocol'] == 'shared_buffer_msprof_task_v2', 'invalid local Task history')
    previous = history['previous_history']
    evidence.bind(previous['path'], previous['sha256'])
    require(read(previous['path']).get('purpose') ==
            'retained_history_for_task_duration_method_qualification', 'missing original Task history')
    older = replay_task_history(previous)
    require(older['valid'] is True and older['eligible_for_publication'] is False,
            'previous Task history cannot grant native admission')
    from replay_task_cancellation import replay_task_cancellation
    cancelled = history['cancelled_task_attempt']
    require(set(cancelled) == {'audit', 'producer_archive'}, 'incomplete cancellation history')
    cancellation = replay_task_cancellation(cancelled['audit'],
        producer_archive_ref=cancelled['producer_archive'])
    require(cancellation['valid'] is True and cancellation['complete'] is False
            and cancellation['eligible_for_publication'] is False, 'cancelled attempt gained admission')
    from probe_native_task_profile import replay
    facility = history['native_facility']
    require(set(facility) == {'directory', 'anchor', 'source_archives'}, 'incomplete native facility history')
    evidence.bind(facility['anchor']['path'], facility['anchor']['sha256'])
    probe = replay(Path(facility['directory']), Path(facility['anchor']['path']),
                   source_archive_refs=facility['source_archives'])
    require(probe['facility_complete'] is True and probe['eligible_for_publication'] is False,
            'native facility is incomplete or was relabeled as admission')
    require(isinstance(history['cost_observations'], list) and history['cost_observations'],
            'missing retained cost observations')
    for item in history['cost_observations']:
        require(set(item) == {'path', 'sha256'}, 'invalid cost observation reference')
        evidence.bind(item['path'], item['sha256'])
    return {'valid': True, 'eligible_for_publication': False,
        'purpose': 'history_preservation_only_new_hardware_qualification_required',
        'history': reference, 'previous_history': previous,
        'cancellation': cancellation, 'native_facility': probe,
        'cost_observations': history['cost_observations'],
        'files': {path: item['sha256'] for path, item in evidence.files.items()}}
