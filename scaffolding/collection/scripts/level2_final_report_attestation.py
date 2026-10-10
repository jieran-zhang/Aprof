#!/usr/bin/env python3
"""Retrospective full-final-report audit. Never schedules native work or observes feedback.

This standalone prospective protocol does not itself grant storage admission.
A separate versioned authority reader must be reviewed before using its event.
"""
from __future__ import annotations

from aprof_layout import skill_lib
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

VERSION = 'level2_final_report_consistency_attestation_v2'
EVENT = 'final_report_consistency_attested'
ALL_CASES = list(range(1, 21))
CLAIM = 'Retained evidence and saved final reports were consistent at this retrospective audit; no earlier report authority is asserted.'
REVIEWED_STORAGE_PATCH = 'sha256:f33673d66637c9c257a9cb65a4bc31b4864ffa6ba9bebbd1f4adf336ccd07f9a'
STORAGE_PRODUCERS = {'level2_evidence_storage.py': 'sha256:47fa961ac340bee5fd19129628b3063c67e30f93b06a5c83493e548661a67772', 'level2_raw_archive_storage.py': 'sha256:5b4fd374e162e951ec6c53ed6987a75e9eb0ac9559a79dbe34d3abd1fd1b8c48', 'level2_verification_storage.py': 'sha256:8492ba1c4c2a03c4b9c9bbbfb8ed13efba4b8498a2a2b88b67669028cc18f1c9', 'level2_native_output_storage.py': 'sha256:3f8bfba87f4ad3e374627a9107b2d36a08f0af5e3c8243e47727e05e46fc15a2', 'msprof_exploration_report.py': 'sha256:4f9e48f76c703e4ac09641bf49a7d82fa36f1d4ccb5b2d700426a5512a21745c', 'msprof_raw_storage.py': 'sha256:6e71eb0460d6de76afc83b674ca437ee5abd670e539c1368aed60e53ca9185ed', 'cannbench_msprof_timing.py': 'sha256:bd6228b925135f033ea7d75a02aa9c2c59fd8c7a71ee3312951b462b700f6203'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def safe(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and path == path.resolve(), 'noncanonical evidence path')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink evidence')
    return path


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def syncdir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(path, data):
    path = safe(path)
    require(not path.exists(), 'immutable audit file already exists')
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def storage_profile(repository):
    """Explicit reviewed reader epoch, checked before importing any new code.

    The data-only final authority module is an explicit Runtime dependency and
    is bound by actual engineering/CAS discovery. Its SHA stays out of this
    static profile because its reviewed-writer table contains this writer SHA.

    These are trusted canonical source files, never paths or hashes selected by
    an archive seal. Engineering subsequently pins every actually loaded
    dependency and retained source snapshot as well.
    """
    repository = safe(repository)
    for name, expected in STORAGE_PRODUCERS.items():
        path = safe(repository / 'scaffolding/collection/scripts' / name)
        require(path.is_file() and digest(path.read_bytes()) == expected,
                'reviewed storage/capture producer differs: ' + name)
    return {'version': 'closed_evidence_facade_epoch_v1',
            'reviewed_patch_sha256': REVIEWED_STORAGE_PATCH,
            'expected_producer_sha256': dict(STORAGE_PRODUCERS)}


class Runtime:
    """Trusted canonical repository imports only; archived producers stay inert."""
    MODULES = ('msprof_exploration_campaign', 'msprof_exploration_report',
               'msprof_exploration_provenance', 'msprof_exploration_execute',
               'shared_context_build', 'run_msprof_exploration_stage',
               'level2_evidence_storage', 'level2_raw_archive_storage',
               'level2_verification_storage', 'level2_native_output_storage',
               'level2_final_report_authority', 'level2_stage_recovery',
               'msprof_raw_storage', 'cannbench_msprof_timing', 'run_level1_serial')

    def __init__(self, repository):
        self.repository = safe(repository)
        self.storage_profile = storage_profile(self.repository)
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(self.repository / 'scaffolding/collection/scripts'), str(skill_lib() / 'runtime/src')]
        self.modules = {name: importlib.import_module(name) for name in self.MODULES}
        for name, module in self.modules.items():
            require(safe(module.__file__) == self.repository / 'scaffolding/collection/scripts' / (name + '.py'),
                    'trusted module did not originate in the canonical repository')
        self.campaign = self.modules['msprof_exploration_campaign']
        self.report = self.modules['msprof_exploration_report']
        self.provenance = self.modules['msprof_exploration_provenance']
        self.storage = self.modules['level2_evidence_storage']
        self.build = self.modules['shared_context_build']
        self.stage = self.modules['run_msprof_exploration_stage']

    def ledger(self, directory):
        return self.campaign.Campaign(directory)

    def read(self, path):
        return self.storage.read_bytes(safe(path))

    def fingerprint(self, path):
        result = self.storage.fingerprint(safe(path))
        # Storage exposes (sha256, bytes), never materialize binary payloads.
        return result[0] if isinstance(result, tuple) else result['sha256']

    def reader_session(self):
        return self.storage.reader_session()

    def reverify(self):
        self.storage.reverify_cached()

    def binding(self, path, expected):
        return self.storage.evidence_binding(safe(path), expected)

    def host_lock(self):
        return self.modules['run_level1_serial'].exclusive_host()

    def analyze(self, directories, plan, calibration):
        self.observation_provenance = []
        return self.report.analyze_task_cohort(directories, plan, calibration,
                                               provenance_out=self.observation_provenance)

    def compare(self, saved, actual, path):
        proof = []
        result = self.report.compare_saved_report(saved, actual, evidence_path=path, provenance_out=proof)
        return {'comparison': result, 'historical_producers': proof}

    def source(self, archive, tree):
        self.stage.verify_source_snapshot(archive, tree)
        return self.build.source_hash(tree)

    def producer_paths(self):
        paths = {safe(__file__)}
        # Include every actually loaded repository Python dependency, even lazy
        # imports discovered only during a full replay. No optional omission.
        for module in tuple(sys.modules.values()):
            value = getattr(module, '__file__', None)
            if value and str(value).endswith('.py'):
                path = Path(value).resolve()
                if path.is_relative_to(self.repository / 'scaffolding/collection/scripts') or path.is_relative_to(skill_lib() / 'runtime/src'):
                    paths.add(safe(path))
        return sorted(paths)

    def historical_producer(self, ref, evidence_path):
        proof = self.provenance.frozen_producer(safe(ref['path']), ref['sha256'],
                                               evidence_path=evidence_path, semantic_path=('producer',))
        require(proof is not None, 'old finalizer producer lacks a frozen snapshot')
        return proof


class Evidence:
    def __init__(self, runtime):
        self.runtime = runtime
        self.refs = {}
        self.storage_bindings = {}

    def pointer(self, path):
        path = safe(path)
        value = {'path': str(path), 'sha256': self.runtime.fingerprint(path)}
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', value['sha256']), 'invalid content digest')
        self.refs[str(path)] = value
        binding = self.runtime.binding(path, value['sha256']) if hasattr(self.runtime, 'binding') else None
        if binding is not None:
            self.storage_bindings[str(path)] = binding
        return value

    def document(self, path):
        path = safe(path)
        data = self.runtime.read(path)
        require(len(data) <= 32 * 1024 * 1024, 'unexpected large metadata document')
        ref = {'path': str(path), 'sha256': digest(data)}
        prior = self.refs.get(str(path))
        require(prior is None or prior == ref, 'document changed during audit')
        self.refs[str(path)] = ref
        return decode(data)

    def checked(self, ref):
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'noncanonical pointer')
        require(self.pointer(ref['path']) == ref, 'bound evidence changed')
        return self.document(ref['path'])

    def tree(self, value):
        if isinstance(value, dict):
            if {'path', 'sha256'} <= value.keys():
                require(self.pointer(value['path'])['sha256'] == value['sha256'], 'evidence tree pointer changed')
            for item in value.values():
                self.tree(item)
        elif isinstance(value, list):
            for item in value:
                self.tree(item)

    def recheck(self):
        self.runtime.reverify()
        for ref in list(self.refs.values()):
            require(self.pointer(ref['path']) == ref, 'evidence changed before publication')


def compact_storage_bindings(bindings):
    """Preserve every logical identity without repeating full proof per member."""
    result = {'version': 'level2_attestation_storage_closure_v1',
              'origins': {}, 'archives': {}, 'closed_evidence': {}}
    for binding in bindings:
        require(set(binding) == {'version', 'origin', 'seal', 'archive', 'producer', 'closed_evidence'},
                'unknown storage binding shape')
        origin = binding['origin']; seal = binding['seal']['sha256']
        require(set(origin) == {'path', 'sha256'}, 'invalid logical storage origin')
        proof = binding['closed_evidence']; key = digest(canonical(proof))
        value = {k: v for k, v in binding.items() if k not in ('origin', 'closed_evidence')}
        value['closed_evidence_ref'] = key
        require(seal not in result['archives'] or result['archives'][seal] == value,
                'conflicting storage seal proof')
        result['archives'][seal] = value; result['closed_evidence'][key] = proof
        mapping = {'sha256': origin['sha256'], 'seal': seal}
        require(origin['path'] not in result['origins'] or result['origins'][origin['path']] == mapping,
                'conflicting logical storage identity')
        result['origins'][origin['path']] = mapping
    validate_storage_bindings(result)
    return result


def validate_storage_bindings(value):
    require(set(value) == {'version', 'origins', 'archives', 'closed_evidence'}
            and value['version'] == 'level2_attestation_storage_closure_v1', 'invalid storage closure')
    for origin, entry in value['origins'].items():
        safe(origin)
        require(set(entry) == {'sha256', 'seal'} and re.fullmatch(r'sha256:[0-9a-f]{64}', entry['sha256'])
                and entry['seal'] in value['archives'], 'invalid storage origin mapping')
    require(set(value['archives']) == {v['seal'] for v in value['origins'].values()}, 'unreferenced storage archive')
    for key, archive in value['archives'].items():
        require(set(archive) == {'version', 'seal', 'archive', 'producer', 'closed_evidence_ref'}
                and archive['seal']['sha256'] == key and archive['closed_evidence_ref'] in value['closed_evidence'],
                'invalid compact archive proof')
    require(set(value['closed_evidence']) == {v['closed_evidence_ref'] for v in value['archives'].values()},
            'unreferenced closed storage evidence')
    for key, proof in value['closed_evidence'].items():
        require(digest(canonical(proof)) == key, 'closed storage proof digest differs')


def task_path(run, operator):
    require(re.fullmatch(r'[a-z][a-z0-9_]*', operator), 'invalid operator')
    run = safe(run)
    found = [run / split / 'tasks' / operator for split in ('train', 'validation')
             if (run / split / 'tasks' / operator / 'manifest.json').is_file()]
    require(len(found) == 1, 'operator must have exactly one canonical task')
    return found[0]


def scope(runtime, run, operator, request_sha, evidence):
    task = task_path(run, operator)
    manifest = evidence.document(task / 'manifest.json')
    require(manifest.get('version') == 'msprof_task_time_exploration_v2'
            and manifest.get('operator') == operator and manifest.get('task_dir') == str(task), 'fresh task identity differs')
    ledger_dir = task.parent.parent / 'ledger'
    ledger = runtime.ledger(ledger_dir)
    require(ledger.config['schema_version'] == runtime.campaign.FRESH_SCHEMA, 'attestor requires a fresh Level2 campaign')
    require(not ledger.unsealed_checkpoints, 'unsealed ledger checkpoints')
    state = ledger.state['tasks'][operator]
    require(state['frozen'] and not runtime.campaign._active(ledger.state), 'final task is unfrozen or a ledger stage is active')
    request_path = task / 'finalization/request.json'
    require(evidence.pointer(request_path)['sha256'] == request_sha, 'externally pinned finalization request differs')
    request = evidence.document(request_path)
    require(request['version'] == 'level2_final_evaluation_v1' and request['operator'] == operator
            and request['campaign_config_hash'] == ledger.config_hash and request['case_ids'] == ALL_CASES,
            'finalization request scope differs')
    require(request.get('selection_policy') == 'all_correctness_runtime_boundary_qualified_candidates_without_timing_filter'
            and request.get('formal_admission') == 'not_evaluated' and request.get('episode_ref') is None
            and request.get('selected_candidate_id') is None and request.get('graph_policy_eligible') is False,
            'finalization request claims a winner or formal policy admission')
    require(state['freeze_reason'] == 'All safe candidates; no winner selected; finalization request ' + request_sha,
            'ledger freeze does not pin exact finalization request')
    require(len(state['candidates']) == state['new_source_attempts'] == state['new_rounds_started'] == 3,
            'exactly three closed source attempts are required')
    require([a['candidate_id'] for a in request['source_attempts']] == list(state['candidates']), 'source-attempt roster differs')
    sources = {}
    baseline = ledger.config['tasks'][operator]['baseline_source_hash']
    for cid in ['baseline', *state['candidates']]:
        parent = task if cid == 'baseline' else task / 'candidates' / cid
        archive = parent / ('baseline-source.tar' if cid == 'baseline' else 'source.tar')
        source_ref = evidence.pointer(archive)
        require(source_ref['sha256'] == (baseline if cid == 'baseline' else state['candidates'][cid]['source_hash']), 'source archive differs')
        sources[cid] = {'archive': source_ref, 'native_tree_hash': runtime.source(archive, parent / ('baseline' if cid == 'baseline' else 'op'))}
    qualified = []
    for attempt in request['source_attempts']:
        cid = attempt['candidate_id']; item = state['candidates'][cid]
        require(not item['inherited'] and item['observation_ids'], 'attempt is inherited or lacks observation')
        observed = state['observations'][item['observation_ids'][-1]]
        feedback = evidence.checked(attempt['feedback'])
        require(observed['candidate_id'] == cid and observed.get('close_feedback') is True
                and observed['report_ref'] == attempt['feedback']['sha256'] and observed['feedback'] == feedback,
                'attempt feedback differs from closed immutable observation')
        require(feedback.get('status') in ('measured', 'source_attempt_failed') and not feedback.get('measurement_error')
                and not observed.get('quality', {}).get('infrastructure_blocked')
                and feedback['source_hash'] == attempt['source_hash'] == item['source_hash']
                and feedback['source_parent'] == item['source_parent'], 'source attempt is unfinished or lineage differs')
        require(attempt['status'] == feedback['status'], 'request source status differs')
        original_stages = {sid: row for sid, row in state['stages'].items()
                           if row['candidate_id'] == cid and not (row['kind'] == 'timing' and row['plan'].get('purpose') == 'final')}
        require(set(attempt['stages']) == set(original_stages), 'request omits an executed source stage')
        observed_counts = {}
        for oid in item['observation_ids']:
            for sid, count in state['observations'][oid]['stage_attempts'].items():
                observed_counts[sid] = max(observed_counts.get(sid, 0), count)
        require(all(observed_counts.get(sid) == len(row['attempts']) for sid, row in original_stages.items()),
                'closed observations omit an executed stage attempt')
        for stage_id, ref in attempt['stages'].items():
            row = state['stages'][stage_id]
            require(row['candidate_id'] == cid and row['attempts'][-1]['outcome'] is not None
                    and row['attempts'][-1]['evidence']['result'] == ref, 'attempt stage does not match ledger finish')
            evidence.checked(ref)
        if attempt['semantic_guards'] is not None:
            guard = evidence.checked(attempt['semantic_guards'])
        else:
            guard = None
        safe_source = runtime.campaign._safe_source(state, cid) and guard is not None and guard.get('status') == 'passed'
        require(type(attempt['qualified']) is bool and attempt['qualified'] == safe_source, 'frozen qualified roster differs from safety evidence')
        if safe_source:
            require(feedback['status'] == 'measured', 'qualified candidate lacks measured closed feedback')
            qualified.append(cid)
        elif feedback['status'] == 'source_attempt_failed':
            classification = feedback.get('failure_classification')
            require(isinstance(classification, dict) and classification.get('status') == 'source_attempt_failed',
                    'frozen failed attempt lacks its positive recorded classification')
            evidence.tree(classification)
        # These are originally registered identities, not a new proposal.
        for ref in item.get('artifacts', {}).values():
            if isinstance(ref, dict) and set(ref) == {'path', 'sha256'}:
                require(evidence.pointer(ref['path']) == ref, 'registered candidate artifact differs')
    require(qualified == request['evaluation_candidate_ids'] == state['selection'], 'omitted or added final candidate')
    completion = evidence.document(task / 'finalization/completion.json')
    require(completion['request'] == evidence.pointer(request_path) and completion['operator'] == operator
            and completion['version'] == request['version'] and completion['source_attempt_count'] == 3
            and completion['evaluation_candidate_ids'] == qualified and completion['selected_candidate_id'] is None
            and completion['final_measurements_complete'] is True
            and completion['status'] == ('final_evaluations_completed' if qualified else 'closed_no_qualified_candidates'),
            'final completion identity or status differs')
    require([r['candidate_id'] for r in completion['comparisons']] == qualified, 'final completion roster differs')
    jobs = []
    for cid, completed in zip(qualified, completion['comparisons']):
        parent = task / 'candidates' / cid
        plan = evidence.checked(request['final_plans'][cid])
        require(plan == state['final_plans'][cid] == evidence.document(parent / 'stages/final/stage-plan.json'), 'frozen/executed final plan differs')
        require(plan['purpose'] == 'final' and plan['case_ids'] == ALL_CASES and plan['processes'] == 6, 'final coverage differs')
        comparison_manifest = safe(request['final_plans'][cid]['path']).parent / 'comparisons.json'
        require(evidence.pointer(comparison_manifest)['sha256'] == plan['manifest_ref']
                and evidence.document(comparison_manifest) == {'candidate_id': cid, 'cohorts': plan['cohorts'], 'case_ids': ALL_CASES},
                'final comparison manifest differs')
        stage = state['stages'][cid + '-final']
        if stage.get('prestart_recovery') is not None:
            from level2_stage_recovery import resolve_result
            recovery = resolve_result(parent / 'stages/final', stage, runtime.storage.read_bytes, require_success=True)
            evidence.tree(recovery['protected'])
            result_ref = recovery['current_result']
        else:result_ref = evidence.pointer(parent / 'stages/final/result.json')
        result = evidence.checked(result_ref)
        require(stage['kind'] == 'timing' and stage['candidate_id'] == cid and stage['plan'] == plan
                and stage['attempts'][-1]['outcome'] == 'success' and stage['attempts'][-1]['evidence']['result'] == result_ref
                and result['status'] == 'passed' and result.get('error') is None and completed['result'] == result_ref,
                'final stage is not successfully closed')
        item = state['candidates'][cid]
        controls = {'direct_parent': item['source_parent']['candidate_id'] or 'baseline'}
        if item['source_parent']['source_hash'] != baseline:
            controls['original_baseline'] = 'baseline'
        require(len(plan['cohorts']) == len(controls) and {v['relation'] for v in plan['cohorts']} == set(controls), 'final relation coverage differs')
        require([v['relation'] for v in completed['comparisons']] == [v['relation'] for v in plan['cohorts']], 'completion relations differ')
        for entry, done in zip(plan['cohorts'], completed['comparisons']):
            relation = entry['relation']; control = controls[relation]
            require(entry['control_candidate_id'] == done['control_candidate_id'] == control, 'comparison parent differs')
            directory = parent / 'stages/final' / relation
            require(done['report'] == evidence.pointer(directory / 'report.json')
                    and done['completion'] == evidence.pointer(directory / 'group-completion.json'), 'completion reports point outside canonical final relation')
            frozen = evidence.checked(entry['plan'])
            require(frozen == evidence.document(directory / 'plan.json') and frozen['case_ids'] == ALL_CASES
                    and frozen['comparison_kind'] == 'ab', 'final cohort plan differs')
            build = evidence.checked(frozen['identity_bindings']['role_build'])
            expected = {'A': sources[control]['native_tree_hash'], 'B': sources[cid]['native_tree_hash']}
            require(build['operator'] == operator and {r: build['roles'][r]['source_sha256'] for r in 'AB'} == expected, 'role source identity differs')
            calibration = entry.get('calibration_report', plan['calibration_report'])
            evidence.checked(calibration)
            jobs.append({'candidate_id': cid, 'relation': relation, 'control_candidate_id': control,
                         'directory': str(directory), 'plan': entry['plan'], 'report': done['report'],
                         'completion': done['completion'], 'stage_result': result_ref, 'calibration': calibration,
                         'source_hashes': expected})
    historical = []
    for ref in request['producers']:
        if runtime.fingerprint(ref['path']) == ref['sha256']:
            require(evidence.pointer(ref['path']) == ref, 'producer changed during read')
        else:
            proof = runtime.historical_producer(ref, request_path)
            evidence.tree({k: v for k, v in proof.items() if k != 'origin'})
            historical.append(proof)
    ledger_data = safe(ledger_dir / 'events.jsonl').read_bytes()
    require(len(ledger_data.splitlines()) == len(ledger.events), 'ledger changed during audit')
    return {'task': task, 'ledger_dir': ledger_dir, 'ledger': ledger, 'state': state,
            'request': request, 'completion': completion, 'jobs': jobs, 'sources': sources,
            'historical_producers': historical, 'ledger_bytes': ledger_data}


def engineering(evidence, runtime, path, task):
    run = task.parents[2]
    path = safe(path)
    require(path.parent == run / 'bootstrap' and re.fullmatch(r'frozen-engineering(?:-[a-zA-Z0-9_-]+)?\.json', path.name),
            'engineering manifest is outside canonical frozen bootstrap')
    value = evidence.document(path)
    require(value.get('version') == 'level2_frozen_engineering_v1', 'unsupported engineering protocol')
    require(value.get('campaign_manifest') == evidence.pointer(run / 'campaign-manifest.json'),
            'engineering campaign manifest binding differs')
    require(evidence.pointer(task / 'manifest.json') in value['task_manifests'], 'engineering does not pin this task')
    files = value['files']; require(len({v['path'] for v in files}) == len(files), 'duplicate engineering producer')
    result = []
    for producer in runtime.producer_paths():
        ref = evidence.pointer(producer)
        matches = [v for v in files if v['path'] == str(producer) and v['sha256'] == ref['sha256']]
        require(len(matches) == 1, 'actually loaded producer not frozen: ' + str(producer))
        snapshot = safe(matches[0]['snapshot'])
        require(snapshot == task.parents[2] / 'bootstrap/source-cas' / ref['sha256'][7:]
                and evidence.pointer(snapshot)['sha256'] == ref['sha256'], 'engineering source snapshot differs')
        result.append({'origin': ref, 'snapshot': evidence.pointer(snapshot)})
    return result


def replay(evidence, runtime, job, calibration_value=None):
    directory = safe(job['directory']); plan = evidence.checked(job['plan'])
    names = [row['name'] for row in plan['schedule']]
    require(len(names) == len(set(names)) == 6 and all(isinstance(n, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', n) and n not in ('.', '..') for n in names), 'six-process schedule differs')
    directories = [str(directory / name) for name in names]
    done = evidence.checked(job['completion'])
    require(done['status'] == 'passed' and done.get('error') is None and done['completed_sessions'] == directories, 'group completion differs')
    saved = evidence.checked(job['report'])
    require(saved.get('case_ids') == list(map(str, ALL_CASES)) and saved.get('evidence_status') == 'verified_complete', 'full saved report coverage absent')
    require(saved.get('source_hashes') == job['source_hashes'], 'saved report source hashes differ')
    require(saved.get('comparison_kind') == plan.get('comparison_kind') == job.get('comparison_kind', 'ab'),
            'saved report or plan comparison kind differs')
    cells = [(r.get('case_id'), r.get('buffer_config')) for r in saved.get('results', [])]
    require(len(cells) == 40 and set(cells) == {(str(c), b) for c in ALL_CASES for b in ('normal', 'swapped')},
            'saved report case/config result roster differs')
    actual = runtime.analyze(directories, plan, calibration_value)
    observation_provenance = list(getattr(runtime, 'observation_provenance', []))
    comparison = runtime.compare(saved, actual, job['report']['path'])
    for historical in comparison.get('historical_producers', []):
        evidence.tree({k: v for k, v in historical.items() if k != 'origin'})
    # Each logical artifact in the original report is a preserved byte identity.
    require(len(saved.get('sessions', [])) == 6 and [s['directory'] for s in saved['sessions']] == directories, 'report session roster differs')
    for session in saved['sessions']:
        require(isinstance(session.get('artifacts'), dict), 'report artifact roster missing')
        for logical, expected in session['artifacts'].items():
            if runtime.fingerprint(logical) == expected:
                require(evidence.pointer(logical)['sha256'] == expected, 'report logical artifact changed')
            else:
                matches = [proof for proof in observation_provenance if proof.get('origin') == {'path': logical, 'sha256': expected}]
                require(matches and all(proof.get('snapshot', {}).get('sha256') == expected for proof in matches),
                        'report artifact changed without same-replay historical producer proof')
                for proof in matches:
                    evidence.tree({k: v for k, v in proof.items() if k != 'origin'})
    return {'report': job['report'], 'plan': job['plan'], 'completion': job['completion'],
            'source_hashes': job['source_hashes'], 'saved_digest': digest(canonical(saved)),
            'replayed_digest': digest(canonical(actual)), 'comparison': comparison,
            'observation_producers': observation_provenance,
            'session_directories': directories}


def audit(runtime, run, operator, request_sha, engineering_path, *, full):
    with runtime.reader_session():
        evidence = Evidence(runtime)
        bound = scope(runtime, run, operator, request_sha, evidence)
        base = {'version': VERSION, 'operator': operator, 'campaign_config_hash': bound['ledger'].config_hash,
                'storage_profile': runtime.storage_profile,
                'finalization_request': evidence.pointer(bound['task'] / 'finalization/request.json'),
                'finalization_completion': evidence.pointer(bound['task'] / 'finalization/completion.json'),
                'sources': bound['sources'], 'jobs': bound['jobs'],
                'engineering': evidence.pointer(engineering_path),
                'historical_request_producers': bound['historical_producers']}
        calibrations = {}; comparisons = []
        if full:
            for job in bound['jobs']:
                ref = job['calibration']; key = (ref['path'], ref['sha256'])
                if key not in calibrations:
                    directory = safe(ref['path']).parent
                    cal = evidence.checked(ref)
                    require(cal['comparison_kind'] == 'aa', 'calibration is not an A/A report')
                    require(cal['source_hashes']['A'] == cal['source_hashes']['B'], 'calibration does not use a fixed source')
                    caljob = {'directory': str(directory), 'plan': evidence.pointer(directory / 'plan.json'),
                              'report': ref, 'completion': evidence.pointer(directory / 'group-completion.json'),
                              'source_hashes': cal['source_hashes'], 'comparison_kind': 'aa'}
                    calibration_replay = replay(evidence, runtime, caljob)
                    calibrations[key] = (cal, calibration_replay)
                cal, calproof = calibrations[key]
                # Match is interpreted by the unmodified analyzer. No scope or
                # quality upgrade is made even if the resulting status is invalidated.
                compared = replay(evidence, runtime, job, cal)
                comparisons.append({**{k: job[k] for k in ('candidate_id', 'relation', 'control_candidate_id')},
                                    **compared, 'calibration_replay': calproof})
        base['producers'] = engineering(evidence, runtime, engineering_path, bound['task'])
        evidence.recheck()
        fresh = runtime.ledger(bound['ledger_dir'])
        require(fresh.events == bound['ledger'].events and fresh.state == bound['ledger'].state, 'ledger changed during audit')
        base['evidence'] = sorted(evidence.refs.values(), key=lambda x: x['path'])
        return {'scope': base, 'comparisons': comparisons, 'ledger_bytes': bound['ledger_bytes'],
                'ledger_prefix': {'event_count': len(fresh.events), 'head_hash': fresh.events[-1]['hash'],
                                  'sha256': digest(bound['ledger_bytes'])},
                'costs': {op: value['used'] for op, value in fresh.state['tasks'].items()},
                'task': bound['task'], 'ledger_dir': bound['ledger_dir'], 'full_replay': full,
                'storage_bindings': compact_storage_bindings(evidence.storage_bindings.values())}


def task_events(task):
    path = safe(task / 'events.jsonl')
    data = path.read_bytes()
    require(not data or data.endswith(b'\n'), 'partial public event tail needs explicit recovery')
    rows = []; previous = None
    for i, line in enumerate(data.splitlines()):
        row = decode(line); payload = {k: v for k, v in row.items() if k != 'hash'}
        require(row['sequence'] == i and row['previous_hash'] == previous and row['hash'] == digest(canonical(payload)), 'task event chain differs')
        rows.append(row); previous = row['hash']
    return rows


def committed(task, directory):
    matches = [row for row in task_events(task) if row['kind'] == EVENT
               and row['value'].get('attestation_directory') == str(directory)]
    require(len(matches) <= 1, 'duplicate attestation event')
    return matches[0] if matches else None


def publish_directory(directory, files):
    require(not directory.exists(), 'attestation namespace exists')
    staging = Path(tempfile.mkdtemp(prefix='.' + directory.name + '-', dir=directory.parent))
    try:
        for name, data in files.items():
            write_new(staging / name, data)
        syncdir(staging)
        os.rename(staging, directory)
        syncdir(directory.parent)
    finally:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()


def validate_stored(runtime, current, directory, *, committed_event=False):
    ev = Evidence(runtime)
    request = ev.document(directory / 'request.json'); attestation = ev.document(directory / 'attestation.json')
    require(set(request) == {'version', 'scope', 'ledger_prefix', 'costs_before', 'attestation_id', 'storage_bindings'}
            and set(attestation) == {'version', 'status', 'kind', 'operator', 'attestation_id', 'audited_at', 'request', 'comparisons',
                                    'historical_report_authority', 'native_executed', 'costs_unchanged_during_audit',
                                    'formal_admission', 'graph_policy_eligible', 'episode_ref', 'selected_candidate_id', 'claim'},
            'stored audit shape differs')
    require(request['version'] == VERSION and attestation['version'] == VERSION and attestation['status'] == 'passed'
            and attestation['kind'] == 'retrospective_full_report_replay' and attestation['operator'] == current['scope']['operator']
            and attestation['attestation_id'] == request['attestation_id']
            and attestation['costs_unchanged_during_audit'] is True
            and attestation['graph_policy_eligible'] is False and attestation['episode_ref'] is None, 'stored audit protocol differs')
    require(request['scope'] == current['scope'] and attestation['request'] == ev.pointer(directory / 'request.json'), 'stored audit scope differs')
    prefix = safe(directory / 'ledger-prefix.jsonl').read_bytes()
    require(digest(prefix) == request['ledger_prefix']['sha256'] and current['ledger_bytes'].startswith(prefix), 'stored ledger prefix changed')
    rows = prefix.splitlines()
    require(len(rows) == request['ledger_prefix']['event_count'] and decode(rows[-1])['hash'] == request['ledger_prefix']['head_hash'], 'stored ledger prefix identity differs')
    ledger = runtime.ledger(current['ledger_dir'])
    historic = runtime.campaign._initial_state(ledger.config)
    for line in rows[1:]:
        event = decode(line)
        runtime.campaign._transition(historic, ledger.config, event['operation'], event['arguments'])
    require(request['costs_before'] == {op: value['used'] for op, value in historic['tasks'].items()},
            'stored original audit cost snapshot differs from its immutable ledger prefix')
    require(attestation['comparisons'] == current['comparisons'] if current['full_replay'] else True, 'stored full replay differs')
    validate_storage_bindings(request['storage_bindings']); validate_storage_bindings(current['storage_bindings'])
    if not committed_event:
        require(request['storage_bindings'] == current['storage_bindings'],
                'uncommitted audit storage closure is incomplete or changed')
    for catalog in ('origins', 'archives', 'closed_evidence'):
        require(all(current['storage_bindings'][catalog].get(k) == v
                    for k, v in request['storage_bindings'][catalog].items()), 'stored logical storage proof changed')
    require(attestation['claim'] == CLAIM, 'stored audit claim differs')
    require(attestation['historical_report_authority'] is False and attestation['native_executed'] is False
            and attestation['formal_admission'] == 'not_evaluated' and attestation['selected_candidate_id'] is None,
            'stored audit overclaims authority or selection')
    return request, attestation, ev.pointer(directory / 'attestation.json')


def attest(runtime, run, operator, request_sha, engineering_path, *, writers_closed):
    require(writers_closed is True, 'writers-closed attestation is required')
    task = task_path(run, operator)
    engineering_path = safe(engineering_path)
    # One namespace per original finalization request and pinned current engineering.
    identity = digest(canonical({'request': request_sha, 'engineering': runtime.fingerprint(engineering_path), 'protocol': VERSION}))
    directory = task / 'finalization' / ('report-attestation-' + identity[7:23])
    with runtime.host_lock():
        with safe(task.parent.parent / 'ledger/.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            prior_event = committed(task, directory)
            current = audit(runtime, run, operator, request_sha, engineering_path, full=True)
            if directory.exists():
                request, value, ref = validate_stored(runtime, current, directory, committed_event=prior_event is not None)
            else:
                require(prior_event is None, 'committed audit artifact is missing')
                request = {'version': VERSION, 'scope': current['scope'], 'ledger_prefix': current['ledger_prefix'],
                           'costs_before': current['costs'], 'attestation_id': identity, 'storage_bindings': current['storage_bindings']}
                request_ref = {'path': str(directory / 'request.json'), 'sha256': digest(canonical(request))}
                value = {'version': VERSION, 'status': 'passed', 'kind': 'retrospective_full_report_replay',
                         'operator': operator, 'attestation_id': identity, 'audited_at': datetime.now(timezone.utc).isoformat(),
                         'request': request_ref, 'comparisons': current['comparisons'],
                         'historical_report_authority': False, 'native_executed': False,
                         'costs_unchanged_during_audit': True, 'formal_admission': 'not_evaluated',
                         'graph_policy_eligible': False, 'episode_ref': None, 'selected_candidate_id': None,
                         'claim': CLAIM}
                publish_directory(directory, {'request.json': canonical(request), 'attestation.json': canonical(value),
                                              'ledger-prefix.jsonl': current['ledger_bytes']})
                request, value, ref = validate_stored(runtime, current, directory)
            require(request['attestation_id'] == identity, 'audit namespace identity differs')
            event_value = {'operator': operator, 'attestation_id': identity, 'attestation_directory': str(directory),
                           'finalization_request': current['scope']['finalization_request'], 'attestation': ref,
                           'authority_timing': 'retrospective_audit_now_not_original_measurement'}
            if prior_event:
                require(prior_event['value'] == event_value, 'committed attestation event differs')
                return {'status': 'already_attested', 'attestation': ref, 'event': prior_event, 'native_executed': False}
            # No event may authorize bytes that were not durably published.
            for name in ('request.json', 'attestation.json', 'ledger-prefix.jsonl'):
                with safe(directory / name).open('rb') as stream:
                    os.fsync(stream.fileno())
            syncdir(directory); syncdir(directory.parent)
            with safe(task / '.recorder.lock').open('rb') as recorder:
                fcntl.flock(recorder, fcntl.LOCK_EX)
                rows = task_events(task)
                require(not any(row['kind'] == EVENT and row['value'].get('attestation_directory') == str(directory) for row in rows), 'concurrent attestation event')
                # Amortize raw/native archive verification across logical members.
                # Its final revalidation must succeed BEFORE the typed event.
                with runtime.reader_session():
                    runtime.reverify()
                    check = Evidence(runtime)
                    for bound in current['scope']['evidence']:
                        require(check.pointer(bound['path']) == bound, 'evidence changed before event commit')
                require(safe(current['ledger_dir'] / 'events.jsonl').read_bytes() == current['ledger_bytes'], 'ledger changed before event commit')
                row = {'sequence': len(rows), 'recorded_at': datetime.now(timezone.utc).isoformat(), 'kind': EVENT,
                       'previous_hash': rows[-1]['hash'] if rows else None, 'value': event_value}
                row['hash'] = digest(canonical(row))
                with safe(task / 'events.jsonl').open('ab') as stream:
                    stream.write(canonical(row)); stream.flush(); os.fsync(stream.fileno())
                syncdir(task)
            return {'status': 'attested', 'attestation': ref, 'event': row, 'native_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'attest'))
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--engineering', type=Path, required=True)
    parser.add_argument('--writers-closed', action='store_true')
    args = parser.parse_args(); runtime = Runtime(args.repository)
    if args.command == 'attest':
        result = attest(runtime, args.run, args.operator, args.request_sha256, args.engineering, writers_closed=args.writers_closed)
    else:
        value = audit(runtime, args.run, args.operator, args.request_sha256, args.engineering, full=False)
        result = {'status': 'metadata_eligible_full_replay_not_run', 'scope': value['scope'], 'native_executed': False}
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
