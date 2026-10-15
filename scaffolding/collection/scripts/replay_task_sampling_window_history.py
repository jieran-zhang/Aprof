"""Join the fixed window diagnosis to prior rejected history without admission."""
from datetime import datetime
import json
from pathlib import Path

from replay_local_task_history_supplement import replay_local_task_history_supplement
from replay_timing_diagnosis import Evidence, read, require

PURPOSE = 'historical_task_sampling_window_diagnostic_with_prior_failures'


def _load(evidence, reference):
    evidence.bind(reference['path'], reference['sha256'])
    return read(reference['path'])


def _check_saved_replay(saved, execution, terminal, plan, window, evidence):
    require(saved.get('complete') is True and saved.get('accepted') is False
            and saved.get('eligible_for_publication') is False and saved.get('slots') == 24,
            'saved window replay cannot grant admission')
    from diagnose_task_sampling_window import ROOT
    script = ROOT / 'scaffolding/collection/scripts/diagnose_task_sampling_window.py'
    require(execution['job']['argv'] == [plan['interpreter']['path'], str(script), 'replay',
            '--output', window['directory'], '--anchor', window['root_anchor']['path']]
            and execution['job']['cwd'] == str(ROOT) and execution['exit_code'] == 0
            and execution['status'] == 'passed' and 0 < execution['duration_seconds'] <= 1200
            and terminal['finished_at'] <= datetime.fromisoformat(execution['started_at']).timestamp()
            <= datetime.fromisoformat(execution['finished_at']).timestamp(),
            'independent diagnostic replay execution differs')
    for name in ('stdout', 'stderr'):
        evidence.bind(execution[name]['path'], execution[name]['sha256'])
    require(json.loads(Path(execution['stdout']['path']).read_text()) == saved,
            'independent diagnostic result differs from actual stdout')


def replay_task_sampling_window_history(reference):
    evidence = Evidence(); history = _load(evidence, reference)
    require(set(history) == {'schema_version', 'purpose', 'not_a_release', 'eligible_for_publication',
                            'previous_history_supplement', 'window'}
            and history['schema_version'] == 1 and history['purpose'] == PURPOSE
            and history['not_a_release'] is True and history['eligible_for_publication'] is False,
            'window history is not a historical-only source chain')
    window = history['window']
    require(set(window) == {'directory', 'plan', 'freeze', 'root_anchor', 'terminal', 'analysis',
                           'independent_replay', 'independent_execution', 'source_archive'},
            'window history has missing or unknown sources')
    values = {key: _load(evidence, value) for key, value in window.items() if key != 'directory'}
    root = Path(window['directory']).resolve(strict=True)
    for key, relative in {'plan': 'plan.json', 'freeze': 'freeze.json',
                          'terminal': 'campaign/terminal.json', 'analysis': 'campaign/analysis.json'}.items():
        require(Path(window[key]['path']) == root / relative, 'window evidence escaped its registered directory')
    require(values['freeze']['plan'] == window['plan']
            and values['root_anchor']['freeze'] == window['freeze']
            and values['terminal']['analysis'] == window['analysis']
            and values['source_archive']['plan_ref'] == window['plan']
            and values['source_archive']['freeze_ref'] == window['freeze']
            and values['source_archive']['analysis_ref'] == window['analysis']
            and values['source_archive']['terminal_ref'] == window['terminal']
            and values['source_archive']['independent_replay_ref'] == window['independent_replay']
            and values['source_archive']['independent_replay_execution_ref'] == window['independent_execution'],
            'window archive, anchor or analysis provenance chain differs')
    _check_saved_replay(values['independent_replay'], values['independent_execution'],
                        values['terminal'], values['plan'], window, evidence)
    prior_ref = history['previous_history_supplement']
    evidence.bind(prior_ref['path'], prior_ref['sha256'])
    require(prior_ref in values['plan']['history'], 'window did not freeze this predecessor supplement')
    # Each recursive stage executes its verifier once; a saved success is never
    # used as a substitute for the original CSV, oracle or cancellation replay.
    prior = replay_local_task_history_supplement(prior_ref)
    require(prior['valid'] is True and prior['eligible_for_publication'] is False, 'prior rejected history failed')
    from diagnose_task_sampling_window import replay
    actual = replay(root, Path(window['root_anchor']['path']), source_archive_refs=[window['source_archive']])
    require({key: actual[key] for key in values['independent_replay']} == values['independent_replay']
            and actual['authority'] == 'historical_diagnostic_only', 'fresh diagnostic replay differs')
    return {'valid': True, 'authority': 'historical_task_sampling_window', 'accepted': False,
            'eligible_for_publication': False, 'history': reference,
            'prior_rejected_history': prior, 'window_diagnostic': actual,
            'files': {path: value['sha256'] for path, value in evidence.files.items()}}
