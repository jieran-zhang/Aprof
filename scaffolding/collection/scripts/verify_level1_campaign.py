#!/usr/bin/env python3
"""Read-only verification of Level1 campaign evidence; never repair an artifact."""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
from datetime import datetime
import fnmatch
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tarfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from aprof_runtime.errors import StoreError
from aprof_runtime.exploration import verify_exploration
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.store import EpisodeStore, default_object_directory
from aprof_runtime.traces import verify_optimization_traces, verify_trace, utcnow
from collect_level1_traces import Campaign, DEFAULT_RUN

OPERATORS = {'foreach_norm', 'exp', 'masked_scale', 'foreach_addcdiv_scalar', 'mish', 'sigmoid', 'gelu'}
SAFE_GAINS = {'production_safe_gain', 'benchmark_specialized_gain'}
TIMING_ENVIRONMENT = ['APROF_TIMING', 'APROF_TIMING_INTERACTIVE', 'APROF_WARMUP', 'APROF_REPEAT', 'APROF_SAMPLES']


def read(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    path = Path(path)
    data = path.read_bytes()
    if data and not data.endswith(b'\n'):
        raise StoreError('incomplete final JSONL line: ' + str(path))
    return [json.loads(line) for line in data.splitlines()]


def require(condition, reason):
    if not condition:
        raise StoreError(reason)


class ReadOnlyStore(EpisodeStore):
    """Replay APIs may register canonical JSON; here that only verifies existence."""
    def __init__(self, path):
        require(not Path(path).is_symlink(), 'SQLite store must not be a symlink')
        self.path = Path(path).resolve()
        self.objects_path = default_object_directory(self.path)
        require(self.path.is_file() and not self.path.is_symlink(), 'missing/nonregular SQLite store: ' + str(self.path))
        require(self.objects_path.is_dir(), 'missing CAS directory: ' + str(self.objects_path))
        self.connection = sqlite3.connect('file:' + quote(str(self.path), safe='/') + '?mode=ro', uri=True)
        self.connection.execute('PRAGMA query_only=ON')

    def register_artifact(self, path, **kwargs):
        digest = file_hash(path)
        self.verify_artifact(digest)
        return digest

    def append(self, *args, **kwargs):
        raise StoreError('verification cannot append episodes')

    def append_many(self, *args, **kwargs):
        raise StoreError('verification cannot append episodes')


def verify_snapshot(store, digest, tree, *, registered_source=True):
    """Compare exact files, bytes and modes; never extract or repair a source."""
    tree = Path(tree)
    require(tree.is_dir() and not tree.is_symlink(), 'source directory is missing or a symlink: ' + str(tree))
    expected, excludes = {}, []
    with tarfile.open(store.verify_artifact(digest)) as archive:
        members = archive.getmembers()
        manifests = [member for member in members if member.name == 'APROF_SOURCE_SNAPSHOT.json']
        if registered_source:
            require(len(manifests) == 1, 'registered source snapshot lacks its exact file manifest')
        declared = None
        if manifests:
            manifest = json.load(archive.extractfile(manifests[0]))
            excludes = manifest['excludes'] if registered_source else []
            declared = {entry['path']: entry for entry in manifest['files']}
        for member in members:
            if member.name == 'APROF_SOURCE_SNAPSHOT.json':
                continue
            parts = Path(member.name).parts
            require(member.isfile() and len(parts) >= 2 and parts[0] == 'source' and '..' not in parts,
                    'unsafe or unexpected source snapshot member')
            rel = Path(*parts[1:]).as_posix()
            require(rel not in expected, 'duplicate source snapshot member: ' + rel)
            payload = archive.extractfile(member).read()
            expected[rel] = {'sha256': 'sha256:' + hashlib.sha256(payload).hexdigest(), 'mode': member.mode & 0o777, 'size': len(payload)}
        if declared is not None:
            require(set(declared) == set(expected), 'snapshot payload/manifest file sets differ')
            for rel, item in expected.items():
                require(declared[rel]['sha256'] == item['sha256'] and declared[rel]['mode'] == item['mode'], 'snapshot manifest digest/mode differs: ' + rel)
    actual = {}
    for path in tree.rglob('*'):
        rel = path.relative_to(tree).as_posix()
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in excludes):
            continue
        require(not path.is_symlink(), 'source contains a symlink: ' + str(path))
        if path.is_file():
            actual[rel] = path
    require(set(actual) == set(expected), 'source file set differs from snapshot: ' + str(tree))
    for rel, path in actual.items():
        item = expected[rel]
        require(file_hash(path) == item['sha256'] and path.stat().st_mode & 0o777 == item['mode'], 'source bytes/mode differ: ' + str(path))
    return {'file_count': len(expected), 'source_hash': digest}


class CampaignVerifier:
    def __init__(self, run):
        self.run = Path(run).resolve()
        self.checks = []
        self.tasks = {}
        self.stores = {}
        self.manifest = {}

    def check(self, scope, name, function):
        try:
            detail = function()
            self.checks.append({'scope': scope, 'name': name, 'status': 'passed', 'detail': detail})
            return detail
        except Exception as error:
            self.checks.append({'scope': scope, 'name': name, 'status': 'failed',
                'error_type': type(error).__name__, 'reason': str(error)})
            return None

    def manifest_check(self):
        self.manifest = read(self.run / 'run-manifest.json')
        ops = self.manifest['operators']
        train, validation = set(self.manifest['train_operators']), set(self.manifest['validation_operators'])
        require(set(ops) == OPERATORS and len(ops) == 7, 'campaign must declare exactly the seven Level1 operators')
        require(train.isdisjoint(validation) and train | validation == OPERATORS and validation == {'gelu'}, 'frozen train/validation partition differs')
        require(self.manifest.get('run_id', self.run.name) == self.run.name, 'run identity differs from directory')
        require(self.manifest['sentinel_case_ids'] == [1, 8, 14, 20] and self.manifest['acceptance_case_ids'] == list(range(1, 21)), 'frozen workload case sets differ')
        require(self.manifest.get('policy_updates') is False, 'campaign must not update graph policy')
        for name, floor in [('candidate_limit', 6), ('build_limit', 6), ('timing_limit', 6), ('full_profile_limit', 3)]:
            value = self.manifest['budget'][name]
            require(type(value) is int and 0 <= value <= floor, 'budget exceeds campaign ceiling: ' + name)
        return {'operator_count': 7, 'train': sorted(train), 'validation': sorted(validation)}

    def open_store(self, split):
        store = ReadOnlyStore(self.run / split / 'episodes.sqlite')
        self.stores[split] = store
        return {'path': str(store.path), 'read_only': True}

    def artifacts(self, store):
        digests = [row[0] for row in store.connection.execute('SELECT content_hash FROM artifacts ORDER BY content_hash')]
        for digest in digests:
            store.verify_artifact(digest)
        return {'verified_artifact_count': len(digests)}

    def sqlite_integrity(self, store):
        head = store.verify_integrity()
        require(not store.connection.execute('PRAGMA foreign_key_check').fetchall(), 'SQLite contains orphan foreign-key references')
        return {'episode_chain_head': head, 'foreign_key_check': 'passed'}

    def task_events(self, op, store):
        path = self.run / 'tasks' / op / 'trace_events.jsonl'
        result = verify_trace(path, store)
        events = jsonl(path)
        require(all(event['task_id'] == op and event['run_id'] == self.run.name for event in events), 'task stream contains another task or run')
        finishes = [event for event in events if event['event_type'] == 'task_finished']
        require(bool(finishes), 'task has neither finalization closure nor an explicit blocked task_finished event')
        last = finishes[-1]
        require(last['payload']['status'] in ('completed', 'blocked'), 'task closure is interrupted rather than completed/explicitly blocked')
        require(bool(last['payload']['reason']), 'task closure lacks a reason')
        self.tasks.setdefault(op, {}).update(events=events, closure=last['payload']['status'], finish=last)
        return {**result, 'closure': last['payload']['status'], 'reason': last['payload']['reason']}

    def roster_sources(self, op, store):
        task = self.run / 'tasks' / op
        registrations = [read(path) for path in sorted((task / 'candidates').glob('*/registration.json'))]
        plans = list((task / 'candidates').glob('*/candidate_plan.json'))
        require(len(plans) == len(registrations), 'candidate plans and registrations differ in count')
        require(len({item['candidate_id'] for item in registrations}) == len(registrations), 'duplicate registered candidate')
        roster_path = task / 'frozen-roster.json'
        blocked = self.tasks.get(op, {}).get('closure') == 'blocked'
        if not registrations and blocked:
            return {'candidate_count': 0, 'closure': 'blocked_before_registration'}
        roster = read(roster_path)
        require({item['candidate_id'] for item in roster['candidates']} == {item['candidate_id'] for item in registrations}, 'frozen roster omitted or invented an attempt')
        campaign = Campaign(self.run)  # Constructor only reads the manifest.
        for path in sorted((task / 'candidates').glob('*/registration.json')):
            registration = read(path)
            frozen = next(item for item in roster['candidates'] if item['candidate_id'] == registration['candidate_id'])
            require(all(frozen.get(key) == value for key, value in registration.items()), 'registration differs from frozen roster')
            require(file_hash(path.parent / 'candidate_plan.json') == frozen['frozen_plan_sha256'] == registration['plan_hash'], 'candidate plan digest changed after registration/freeze')
            plan = read(path.parent / 'candidate_plan.json')
            require(plan['candidate_id'] == registration['candidate_id'] == op + '-' + path.parent.name, 'candidate identity differs from task directory')
            for digest in [registration['plan_hash'], registration['patch_artifact_hash'], *registration['source_hashes'].values()]:
                store.verify_artifact(digest)
            verify_snapshot(store, registration['source_hashes']['baseline'], task / 'baseline')
            verify_snapshot(store, registration['source_hashes']['candidate'], path.parent / 'op')
            campaign.verify_candidate_boundary(op, path.parent.name)  # Read-only protected-file comparison.
        self.tasks.setdefault(op, {}).update(registrations=registrations, roster=roster)
        return {'candidate_count': len(registrations), 'protected_oracle_harness_boundary': 'verified'}

    def budgets(self, op):
        task = self.run / 'tasks' / op
        identifiers = {path.parent.name for path in (task / 'candidates').glob('*/registration.json')}
        built, timed, profiled = set(), set(), set()
        execution_ids = {path.name for path in (task / 'executions').glob('*') if path.is_dir() and path.name.isdigit()}
        profile_ids = {path.name for path in (task / 'profiles').glob('*') if path.is_dir() and path.name.isdigit()}
        for identifier in identifiers | execution_ids | profile_ids:
            executions = task / 'executions' / identifier
            for path in executions.rglob('execution.json'):
                stage = path.parent.name
                if stage in ('configure', 'build'):
                    built.add(identifier)
                if 'timing' in stage:
                    timed.add(identifier)
                if stage.startswith('profile'):
                    profiled.add(identifier)
            if any((task / 'profiles' / identifier).glob('case-*/raw/**/*.csv')):
                profiled.add(identifier)
        # Stage events also retain failed launches whose transport report lacked
        # a normal execution.json. Calibration and baseline work are excluded.
        for event in self.tasks.get(op, {}).get('events', []):
            candidate = event.get('candidate_id')
            if not candidate or not candidate.startswith(op + '-'):
                continue
            identifier = candidate[len(op) + 1:]
            stage = event['payload'].get('stage', '').replace('-', '_')
            if event['event_type'] not in ('stage_completed', 'execution_interrupted'):
                continue
            if stage in ('configure', 'build') or stage.endswith('/build') or stage.endswith('/configure'):
                built.add(identifier)
            if 'timing' in stage:
                timed.add(identifier)
            if 'profile' in stage:
                profiled.add(identifier)
        require((built | timed | profiled).issubset(identifiers), 'execution budget contains an unregistered candidate')
        counts = {'candidate_limit': len(identifiers), 'build_limit': len(built), 'timing_limit': len(timed), 'full_profile_limit': len(profiled)}
        for name, count in counts.items():
            require(count <= self.manifest['budget'][name], f'{op} exceeds {name}: {count}')
        self.tasks.setdefault(op, {})['budgets'] = counts
        return counts

    def sealed_hardware(self, op, store, *, recorded_read=None):
        """Read only sealed identity/provenance fields, never infer authorization."""
        task = self.run / 'tasks' / op
        summaries = jsonl(task / 'optimization_traces.jsonl')
        events = self.tasks.get(op, {}).get('events')
        if events is None:
            events = jsonl(task / 'trace_events.jsonl')
        finished = [event for event in events if event['event_type'] == 'attempt_finished']
        identifiers = [row['identity']['candidate_id'] for row in summaries]
        require(bool(summaries) and len(set(identifiers)) == len(identifiers)
                and set(identifiers) == {event['candidate_id'] for event in finished},
                'shared probe requires every sealed attempt summary')
        split = 'validation' if op in self.manifest['validation_operators'] else 'train'
        hardware = []
        for summary in summaries:
            identity = summary['identity']
            require(identity['operator'] == identity['task_id'] == op and identity['split'] == split,
                    'shared probe summary identity differs from its owner')
            digest = content_hash(summary)
            store.verify_artifact(digest)
            links = [event for event in finished if event['candidate_id'] == identity['candidate_id']]
            require(len(links) == 1 and links[0]['payload']['summary_ref'] == digest,
                    'shared probe summary lacks its sealed attempt_finished binding')
            if recorded_read:
                path, read_hash = recorded_read
                entries = [entry for entry in summary['knowledge']['loaded'] if entry.get('path') == str(path)]
                require(bool(entries) and all(entry.get('content_hash') == read_hash for entry in entries),
                        'shared probe read is not hash-bound by every sealed knowledge summary')
            fingerprint = summary['workload']['hardware_fingerprint']
            items = read(store.verify_artifact(fingerprint))
            require(isinstance(items, list), 'shared probe hardware fingerprint must contain a source list')
            hardware.append(items)
        return hardware

    def shared_device_identity_read(self, op, record, owner):
        """Narrow exception for the exact environment-bound probe stdout only.

        The historical knowledge manifest and knowledge_loaded events need not
        authorize this read. The existing sealed summaries bind the recorded
        bytes; the owner's sealed hardware fingerprint also binds execution
        bytes, because environment_manifest contains only an execution path.
        """
        def regular(value):
            path = Path(value)
            require(path.is_absolute() and path == path.resolve() and path.is_relative_to(self.run)
                    and path.is_file() and not any(part.is_symlink() for part in [path, *path.parents]),
                    'shared probe path must be a canonical regular file within the run')
            return path

        def digest(value):
            require(isinstance(value, str), 'shared probe read lacks a digest')
            return value if value.startswith('sha256:') else 'sha256:' + value

        def anchored(hardware, path):
            hashes = []
            for items in hardware:
                matches = [item for item in items if item.get('path') == str(path)]
                require(len(matches) == 1, 'shared probe source is absent/ambiguous in a sealed hardware fingerprint')
                hashes.append(matches[0]['content_hash'])
            require(len(set(hashes)) == 1, 'shared probe sealed hardware fingerprints disagree')
            return hashes[0]

        def bound_file(path, expected):
            require(file_hash(path) == expected, 'shared probe file differs from its bound digest: ' + str(path))
            return read(store.verify_artifact(expected))

        def instant(value):
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
            require(result.tzinfo is not None, 'shared probe timestamp must include a timezone')
            return result

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'shared probe output contains duplicate JSON fields')
                result[key] = value
            return result

        split = 'validation' if op in self.manifest['validation_operators'] else 'train'
        require(owner not in self.manifest['validation_operators'], 'shared probe exception cannot read a validation task')
        store = self.stores[split]
        path = regular(record['path'])
        require(path.name == 'stdout.log', 'shared probe exception permits only the bound stdout file')
        read_hashes = [digest(record[key]) for key in ('sha256', 'content_hash') if key in record]
        require(bool(read_hashes) and len(set(read_hashes)) == 1, 'shared probe read digests are missing or inconsistent')
        read_hash = read_hashes[0]
        require(file_hash(path) == read_hash, 'shared probe stdout differs from the recorded read digest')
        store.verify_artifact(read_hash)
        hardware = self.sealed_hardware(op, store, recorded_read=(path, read_hash))
        environment_path = regular(self.run / 'environment_manifest.json')
        environment_hash = anchored(hardware, environment_path)
        environment = bound_file(environment_path, environment_hash)
        hosts = [host for host in environment['hosts']
                 if Path(host['probe_execution']).parent / 'stdout.log' == path]
        require(len(hosts) == 1, 'shared probe stdout is not the unique environment identity source')
        host = hosts[0]
        execution_path = regular(host['probe_execution'])
        require(execution_path.name == 'execution.json' and execution_path.parent == path.parent
                and execution_path.is_relative_to(self.run / 'tasks' / owner / 'executions'),
                'shared probe execution path differs from the declared owner/output')
        owner_store = self.stores['train']
        owner_hardware = self.sealed_hardware(owner, owner_store)
        execution_hash = anchored(owner_hardware, execution_path)
        owner_store.verify_artifact(execution_hash)
        execution = bound_file(execution_path, execution_hash)
        job = execution['job']
        require(execution.get('kind') == 'aprof_execution_report' and execution.get('schema_version') == '1.0.0'
                and execution['status'] == 'passed' and type(execution['exit_code']) is int and execution['exit_code'] == 0,
                'shared probe execution did not complete successfully')
        require(job['argv'] == ['python3', str(ROOT / 'scaffolding/collection/scripts/probe_aprof_device.py')],
                'shared probe execution did not invoke the exact identity probe')
        require(job['output_dir'] == str(path.parent) and execution['stdout']['path'] == str(path)
                and execution['stdout']['sha256'] == read_hash,
                'shared probe execution stdout path/digest binding differs')
        require(instant(execution['started_at']) <= instant(execution['finished_at']) <= instant(record['read_at']),
                'shared probe read predates the completed execution')
        output = json.loads(path.read_text(), object_pairs_hook=unique_object,
                            parse_constant=lambda value: require(False, 'shared probe output contains nonfinite JSON'))
        require(isinstance(output, dict) and set(output) == {
            'attributes', 'host', 'logical_device', 'soc', 'visible_physical_devices'},
            'shared probe output is not strictly hardware identity data')
        require(all(output[key] == host.get(key) for key in output), 'shared probe output differs from the environment host identity')
        physical = execution['physical_device']
        require(type(physical) is int and physical >= 0 and type(job['physical_device']) is int
                and job['physical_device'] == physical and output['visible_physical_devices'] == str(physical)
                and type(output['logical_device']) is int and output['logical_device'] == 0
                and isinstance(output['host'], str) and bool(output['host']) and output['host'] == execution['host']
                and isinstance(output['soc'], str) and bool(output['soc']),
                'shared probe host/logical/physical device mapping differs')
        attributes = output['attributes']
        expected_attributes = {'ai_core_count': 101, 'cube_core_count': 102,
                               'vector_core_count': 201, 'ub_bytes_per_vector_core': 204}
        require(isinstance(attributes, dict) and set(attributes) == set(expected_attributes),
                'shared probe has unexpected hardware attribute fields')
        for name, attribute_id in expected_attributes.items():
            attribute = attributes[name]
            require(isinstance(attribute, dict) and set(attribute) == {'attribute_id', 'source', 'status_code', 'value'}
                    and type(attribute['attribute_id']) is int and attribute['attribute_id'] == attribute_id
                    and attribute['source'] == 'aclrtGetDeviceInfo' and type(attribute['status_code']) is int
                    and ((attribute['status_code'] == 0 and type(attribute['value']) is int and attribute['value'] >= 0)
                         or (attribute['status_code'] != 0 and attribute['value'] is None)),
                    'shared probe has invalid hardware attribute data: ' + name)
        return {'path': str(path), 'content_hash': read_hash, 'environment_hash': environment_hash,
                'execution_hash': execution_hash, 'host': output['host'], 'physical_device': physical,
                'classification': 'shared_hardware_identity_only',
                'authorization_note': 'Verifies existing sealed provenance and identity-only content; does not assert advance knowledge-manifest or knowledge_loaded-event authorization.'}

    def boundaries(self, op):
        task = self.run / 'tasks' / op
        split = 'validation' if op in self.manifest['validation_operators'] else 'train'
        events = self.tasks.get(op, {}).get('events', [])
        for event in events:
            if event['event_type'] == 'task_started':
                require(event['payload']['operator'] == op and event['payload']['split'] == split, 'task_started split/operator mismatch')
        read_records = []
        for path in (task / 'worker_knowledge_reads.jsonl', task / 'knowledge/knowledge_reads.jsonl'):
            if path.exists():
                read_records.extend(jsonl(path))
        shared_identity_reads = []
        for record in read_records:
            if not record.get('path'):
                continue
            path = Path(record['path']).resolve()
            require(not any(path.is_relative_to(self.run / partition) for partition in ('train', 'validation')), 'recorded worker read accessed outcome split/store: ' + str(path))
            for other in OPERATORS - {op}:
                if path.is_relative_to(self.run / 'tasks' / other):
                    try:
                        shared_identity_reads.append(self.shared_device_identity_read(op, record, other))
                    except Exception as error:
                        raise StoreError('recorded worker read crosses sealed task boundary: ' + str(path) + '; ' + str(error)) from error
        for phase in ('search', 'final'):
            for path in (task / 'timing' / phase).glob('*/case-*'):
                require(path.name.removeprefix('case-').isdigit(), 'invalid timing case directory')
                case = int(path.name.removeprefix('case-'))
                require(case in (self.manifest['sentinel_case_ids'] if phase == 'search' else self.manifest['acceptance_case_ids']), 'timing case escaped the frozen phase boundary')
        frozen = self.tasks.get(op, {}).get('roster', {}).get('frozen_at')
        if frozen:
            from datetime import datetime
            instant = datetime.fromisoformat(frozen.replace('Z', '+00:00'))
            for event in events:
                stage = event['payload'].get('stage', '').replace('-', '_')
                execution = event['payload'].get('execution')
                if 'final_timing' in stage and execution:
                    require(datetime.fromisoformat(execution['started_at'].replace('Z', '+00:00')) >= instant, 'acceptance timing started before roster freeze')
        return {'split': split, 'recorded_read_count': len(read_records), 'shared_hardware_identity_reads': shared_identity_reads,
            'limitation': 'Recorded reads and evidence boundaries are audited; unrecorded worker reads cannot be established from these artifacts.'}

    def finalized(self, op, store):
        task = self.run / 'tasks' / op
        data = self.tasks[op]
        if data['closure'] == 'blocked':
            require(bool(data['finish']['payload']['reason']), 'blocked task lacks an explicit reason')
            return {'closure': 'blocked', 'reason': data['finish']['payload']['reason']}
        report = read(task / 'finalization_report.json')
        summaries = jsonl(task / 'optimization_traces.jsonl')
        verify_optimization_traces(task / 'optimization_traces.jsonl', store)
        require(report['operator'] == op and report['run_id'] == self.run.name and report['status'] == 'completed', 'finalization report identity/status mismatch')
        require(data['finish']['payload']['summary_ref'] == content_hash(report), 'task_finished does not bind the finalization report')
        require(report['attempt_count'] == len(summaries) == len(data['registrations']), 'finalization omitted an attempt summary')
        expected_ids = {item['candidate_id'] for item in data['registrations']}
        require({row['identity']['candidate_id'] for row in summaries} == expected_ids, 'summary candidate set differs from frozen roster')
        expected_split = 'validation' if op in self.manifest['validation_operators'] else 'train'
        for summary in summaries:
            identity = summary['identity']
            require(identity['task_id'] == op and identity['operator'] == op and identity['split'] == expected_split, 'summary crosses task/split boundary')
            digest = content_hash(summary)
            store.verify_artifact(digest)
            finished = [event for event in data['events'] if event['event_type'] == 'attempt_finished' and event['candidate_id'] == identity['candidate_id']]
            require(len(finished) == 1 and finished[0]['payload']['summary_ref'] == digest, 'attempt_finished does not bind exactly one summary')
            fragment = read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
            require(not any(event['event_type'] == 'attempt_finished' for event in fragment['events']), 'sealed attempt contains a post-outcome event')
            require(all(event['sequence'] < finished[0]['sequence'] for event in fragment['events']), 'sealed attempt evidence does not precede its outcome link')
        request_path = task / 'exploration_request.json'
        if request_path.exists():
            verification = verify_exploration(read(request_path), read(task / 'exploration_outcomes.json'), store=store)
        else:
            verification = None
            require(all(summary['routing']['mode'] == 'graph' for summary in summaries), 'exploration traces lack their request/outcome replay batch')
        data.update(report=report, summaries=summaries)
        return {'attempt_count': len(summaries), 'exploration': verification}

    def measurements(self, op, store):
        from finalize_level1_campaign import Evidence
        task = self.run / 'tasks' / op
        if self.tasks[op].get('closure') == 'blocked':
            return {'status': 'not_required_for_blocked_closure'}
        evidence = Evidence(store, task)
        checked = 0
        request = read(task / 'exploration_request.json') if (task / 'exploration_request.json').exists() else {'evidence': []}
        gates = {item['candidate_id']: item for item in request['evidence']}
        for path in sorted((task / 'candidates').glob('*/registration.json')):
            identifier = path.parent.name
            gate = gates.get(read(path)['candidate_id'])
            for phase, cases, key in [('search', self.manifest['sentinel_case_ids'], 'search_measurement_report'),
                                      ('final', self.manifest['acceptance_case_ids'], 'measurement_report')]:
                directory = task / 'timing' / phase / identifier
                if not directory.exists():
                    continue
                report, digest, _ = evidence.measurement(directory, cases)
                if report is not None:
                    checked += 1
                    if gate and key in gate['artifacts']:
                        require(gate['artifacts'][key] == digest, 'current measurement report differs from finalized gate evidence')
        return {'measurement_reports_recomputed_from_raw': checked}

    def delivered_source(self, op, store):
        data = self.tasks[op]
        if data['closure'] == 'blocked':
            return {'status': 'not_delivered', 'reason': 'Explicitly blocked task.'}
        task = self.run / 'tasks' / op
        selected = read(task / 'best_source_selection.json')
        require(selected == data['report']['best_source'], 'delivered selection differs from finalization report')
        summaries = data['summaries']
        gains = [row for row in summaries if row['result']['verdict'] in SAFE_GAINS]
        if selected['candidate_id'] is None:
            require(not gains, 'baseline retained despite a verified selectable gain')
            digest = data['registrations'][0]['source_hashes']['baseline']
        else:
            chosen = next((row for row in gains if row['identity']['candidate_id'] == selected['candidate_id']), None)
            require(chosen is not None, 'selected candidate lacks a verified benchmark gain')
            outcomes = [read(store.verify_artifact(row['result']['machine_outcome_ref'])) for row in gains]
            winner = min(outcomes, key=lambda outcome: (-outcome['utility'], outcome['candidate_id']))
            require(selected['candidate_id'] == winner['candidate_id'], 'selected source is not the machine-utility winner')
            digest = chosen['provenance']['candidate_source_hash']
        require(selected['source_hash'] == digest, 'selected source digest is not the verified candidate/baseline')
        return verify_snapshot(store, digest, task / 'best_source', registered_source=False)

    def profile_execution_summary(self, op, store, complete, selected):
        """Distinguish planned, successfully dispatched, and complete profiles."""
        from recover_level1_profile_preflight import load_verified_recovery
        from run_level1_hardware_queue import execution_failed
        task = self.run / 'tasks' / op
        data = self.tasks[op]
        events = data['events']
        recovery = load_verified_recovery(Campaign(self.run), op, store)
        require(complete.get('controller_recovery_ref') == recovery['manifest_ref'],
            'diagnostic completion recovery reference is missing or unverified')
        ignored = set(recovery['ignored_event_ids'])
        cases = self.manifest.get('sentinel_case_ids', [1, 8, 14, 20])
        expected = [(identifier, case) for identifier in selected for case in cases]
        require(len(selected) == len(set(selected)), 'duplicate selected profile candidate')
        phase = read(task / 'queue/profiles-plan.json')
        rows = read(task / 'queue/profiles.json')
        require(phase['operator'] == op and phase['phase'] == 'profiles'
            and [tuple(item) for item in phase['items']] == expected,
            'profile phase plan differs from the immutable selected cases')
        require([tuple(row['item']) for row in rows] == expected
            and all(row['phase'] == 'profiles' and row['stage'] == 'profile' for row in rows),
            'profile queue omitted, duplicated or changed a selected case')
        phase_ref, rows_ref = content_hash(phase), content_hash(rows)
        store.verify_artifact(phase_ref)
        store.verify_artifact(rows_ref)
        require(any(event['payload'].get('action') == 'complete_bounded_phase'
            and {phase_ref, rows_ref}.issubset(event['payload'].get('evidence_refs', [])) for event in events),
            'profile queue terminal result lacks its phase/event CAS binding')
        profile_events = [event for event in events if event.get('candidate_id')
            and 'profile' in (event['payload'].get('stage') or '')
            and event['event_type'] in ('stage_completed', 'execution_interrupted')]
        failure_events = [event for event in profile_events if event['event_id'] not in ignored
            and (event['event_type'] == 'execution_interrupted' or event['payload']['status'] != 'passed')]
        failed = {event['candidate_id'] for event in failure_events}
        reports = {}
        for path in (task / 'executions').glob('*/profile-*/execution.json'):
            identifier = path.parent.parent.name
            if identifier == 'baseline':
                continue
            case = int(path.parent.name.removeprefix('profile-'))
            require((identifier, case) in expected, 'actual profiler execution escaped the immutable selected cases')
            report = read(path)
            digest = content_hash(report)
            store.verify_artifact(digest)
            linked = [event for event in profile_events if event['event_type'] == 'stage_completed'
                and event['candidate_id'] == op + '-' + identifier and digest in event['payload']['artifact_refs']]
            status = report['status'] if report['status'] in ('passed', 'failed') else 'interrupted'
            require(linked and all(event['payload']['status'] == status for event in linked),
                'profiler execution report lacks a matching candidate completion event')
            for event in linked:
                execution = event['payload'].get('execution')
                if execution:
                    require(execution['exit_status'] == report['exit_code'], 'profile event exit differs from its execution report')
            # Full hardware reports also bind the profiler command and job identity.
            if report.get('kind') == 'aprof_execution_report':
                require('job' in report, 'hardware profiler report lacks its job identity')
            if 'job' in report:
                job = report['job']
                require(job['job_id'] == f'{op}-{identifier}-profile-{case:02d}'
                    and job['argv'] and Path(job['argv'][0]).name == 'msprof', 'profile report belongs to another job or command')
                require(all(event['payload'].get('execution') is not None
                    and event['payload']['execution']['argv'] == job['argv'] for event in linked),
                    'profile event command differs from its execution report')
            if execution_failed(report):
                failed.add(op + '-' + identifier)
            reports[(identifier, case)] = (report, digest)
        passed = set()
        for row in rows:
            item = tuple(row['item'])
            report, digest = reports.get(item, (None, None))
            if row['status'] == 'skipped':
                require(not row.get('result_ref'), 'skipped profile queue row claims an execution result')
                continue
            if row['status'] == 'error':
                # Compression can fail after msprof exits successfully. Preserve
                # that execution, but this dispatch is not a successful profile.
                require(any(event['candidate_id'] == op + '-' + item[0]
                    and event['event_type'] == 'execution_interrupted'
                    and content_hash(row) in event['artifact_refs'] for event in failure_events),
                    'profile controller error lacks its non-whitelisted interruption evidence')
                continue
            require(report is not None and row.get('result_ref') == digest,
                'profile queue success/failure differs from its actual execution report')
            require(row.get('exit_code') == report.get('exit_code', report.get('exit_status')),
                'profile queue exit differs from its execution report')
            if row['status'] == 'passed':
                require(report['status'] == 'passed' and not execution_failed(report),
                    'profile queue claims success for a failed actual execution')
                passed.add(item)
            else:
                require(execution_failed(report), 'profile queue failure is unsupported by its execution report')
        profiled = sorted({identifier for identifier, case in passed})
        full = [identifier for identifier in selected if all((identifier, case) in passed for case in cases)]
        require(complete['profiled_candidate_ids'] == profiled,
            'profiled candidate list differs from successful actual dispatches')
        require(complete.get('full_profile_candidate_ids', []) == full,
            'full profile candidate list differs from the four successful selected cases')
        require(not {op + '-' + identifier for identifier in full} & failed,
            'full profile claim hides a real execution/controller failure')
        for summary in data.get('summaries', []):
            candidate = summary['identity']['candidate_id']
            profile = summary['validation']['profile']['status']
            if candidate in failed:
                require(profile in ('failed', 'interrupted'), 'summary hides a non-recovered profiler failure')
            if profile == 'passed':
                require(candidate.removeprefix(op + '-') in full,
                    'summary claims passed profiling without all four successful selected cases')
            if recovery['manifest_ref'] and candidate in recovery['per_candidate_event_ids']:
                require(recovery['manifest_ref'] in summary['lesson']['evidence_refs']
                    and all(warning in summary['lesson']['limitations'] for warning in recovery['warnings']),
                    'summary omitted its qualified recovery evidence or warning')
                fragment = read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
                require(any(event.get('candidate_id') == candidate
                    and event['payload'].get('action') == 'qualify_profile_controller_recovery'
                    and recovery['manifest_ref'] in event['payload'].get('evidence_refs', []) for event in fragment['events']),
                    'profile recovery authorization was not sealed with the attempt')
        return {'selected_profile_candidate_ids': selected, 'profiled_candidate_ids': profiled,
            'full_profile_candidate_ids': full, 'successful_profile_case_count': len(passed),
            'failed_profile_candidate_ids': sorted(failed), 'controller_recovery_ref': recovery['manifest_ref']}

    def blocked_measurements(self, op, store):
        task = self.run / 'tasks' / op
        path = task / 'queue/hardware_complete.json'
        if not path.exists() or read(path).get('measurement_status') != 'blocked':
            return {'measurement_status': 'not_declared_blocked'}
        from run_level1_blocked_diagnostics import calibration_failure_files, no_candidate_timing, DIAGNOSTIC_SLOTS
        complete = read(path)
        require(complete.get('collection_mode') == 'blocked_diagnostics' and complete.get('status') == 'completed'
            and complete.get('timing_qualification_claimed') is False, 'blocked diagnostics misrepresent timing qualification')
        files = calibration_failure_files(self.run)
        require([file_hash(source) for source in files] == complete['calibration_refs'], 'diagnostic calibration proof differs from terminal ladder evidence')
        proof = read(store.verify_artifact(complete['calibration_block_ref']))
        require(proof == read(task / 'queue/calibration_block.json') and proof['measurement_status'] == 'blocked'
            and proof['timing_qualification_claimed'] is False, 'diagnostic calibration block lost its CAS binding')
        require(proof['sources'] == [{'path': str(source), 'sha256': file_hash(source)} for source in files], 'calibration block does not bind every failed round')
        require(proof['diagnostic_slots'] == [{'host': host, 'physical_device': device} for host, device in DIAGNOSTIC_SLOTS], 'diagnostic slot list changed')
        plan = read(store.verify_artifact(complete['diagnostic_plan_ref']))
        selection = read(task / 'profile_selection.json')
        require(plan == read(task / 'queue/diagnostic_plan.json') and plan['measurement_status'] == 'blocked'
            and plan['calibration_block_ref'] == complete['calibration_block_ref'], 'diagnostic plan lost its immutable CAS binding')
        require(plan['frozen_roster_ref'] == content_hash(read(task / 'frozen-roster.json'))
            and plan['profile_selection_ref'] == content_hash(selection), 'diagnostic source/profile selection commitment changed')
        selected_profile_ids = complete.get('selected_profile_candidate_ids', complete['profiled_candidate_ids'])
        require(plan['profile_candidate_ids'] == selected_profile_ids == selection['candidate_ids']
            and len(selection['candidate_ids']) <= 3, 'diagnostic profile selection changed or exceeded its budget')
        for identifier, digest in plan['mechanism_plan_refs'].items():
            require(content_hash(read(task / 'candidates' / identifier / 'mechanism_plan.json')) == digest,
                'diagnostic mechanism plan changed after profiling')
            store.verify_artifact(digest)
        for digest in complete['calibration_refs']:
            store.verify_artifact(digest)
        no_candidate_timing(task)
        data = self.tasks[op]
        profile_summary = self.profile_execution_summary(op, store, complete, selected_profile_ids)
        expected = {row['candidate_id'] for row in data['registrations']}
        require({op + '-' + identifier for identifier in complete['candidate_ids']} == expected, 'diagnostic closure omitted a registered candidate')
        require(not any(row['result']['verdict'] in SAFE_GAINS or row['result'].get('speedup') is not None for row in data['summaries']),
            'timing-blocked diagnostics cannot claim a measured gain')
        require(data['report']['best_source']['candidate_id'] is None, 'timing-blocked diagnostics must retain baseline')
        complete_ref = content_hash(complete)
        store.verify_artifact(complete_ref)
        require(any(event['payload'].get('action') == 'hardware_collection_complete'
            and complete_ref in event['payload'].get('evidence_refs', []) for event in data['events']), 'diagnostic hardware closure is not event-bound')
        for summary in data['summaries']:
            candidate = summary['identity']['candidate_id']
            fragment = read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
            require(any(event.get('candidate_id') == candidate and event['payload'].get('action') == 'block_timing_after_calibration_failure'
                and complete['calibration_block_ref'] in event['payload'].get('evidence_refs', []) for event in fragment['events']),
                'timing admission block was not sealed with each attempt')
        data['measurement_status'] = 'blocked'
        return {'measurement_status': 'blocked', 'reason': complete['reason'], 'calibration_block_ref': complete['calibration_block_ref'],
            **profile_summary}

    def supplemental_exp006(self, store):
        data = self.tasks.get('exp', {})
        summary = next((row for row in data.get('summaries', []) if row['identity']['candidate_id'] == 'exp-006'), None)
        if summary is None or summary['result']['verdict'] not in SAFE_GAINS:
            return {'required_for_safe_gain': False, 'reason': 'No finalized exp-006 safe/selected gain is claimed.'}
        base = self.run / 'tasks/exp/qualification/zero_affine'
        path = base / 'hardware_validation.json'
        report = read(path)
        require(report['candidate_id'] == 'exp-006' and report['kind'] == 'supplemental_correctness_validation', 'supplemental validation identity mismatch')
        require(report['status'] == 'passed' and all(report[key] == 9 for key in ('case_count', 'attempted_count', 'passed_count')), 'exp006 supplemental hardware validation did not pass all nine cases')
        require(report['purpose'] == 'correctness_only_no_performance_feedback' and report.get('timing_environment_unset') == TIMING_ENVIRONMENT, 'supplemental correctness leaked timing or changed its purpose')
        require(report['first_failure'] is None and len(report['cases']) == 9, 'supplemental case set incomplete')
        case_ids = {f'zero-affine-{dtype}-n{size}' for dtype in ('float32', 'float16', 'bfloat16') for size in (17, 4097, 196673)}
        require({case['case_id'] for case in report['cases']} == case_ids, 'supplemental dtype/size coverage differs')
        manifest = read(store.verify_artifact(report['run_manifest_ref']))
        require(manifest['candidate_id'] == 'exp-006' and manifest['attempt'] == report['attempt'] and manifest['case_count'] == 9,
                'supplemental execution manifest identity differs')
        require(manifest['purpose'] == report['purpose'] and manifest['timing_environment_unset'] == TIMING_ENVIRONMENT,
                'supplemental manifest is not correctness-only')
        planned = {case['case_id']: case for case in manifest['cases']}
        require(len(manifest['cases']) == 9 and set(planned) == case_ids, 'supplemental execution manifest case coverage differs')
        for source in manifest['sources']:
            digest = 'sha256:' + source['sha256'].removeprefix('sha256:')
            require(digest in manifest['source_artifact_refs'], 'supplemental source lacks CAS binding')
            require(file_hash(source['path']) == digest, 'supplemental source changed: ' + source['path'])
            store.verify_artifact(digest)
        events = {event['event_id']: event for event in data['events']}
        env_prefix = ['/usr/bin/env'] + [token for name in TIMING_ENVIRONMENT for token in ('-u', name)]
        for case in report['cases']:
            require(case['status'] == 'passed', 'failed supplemental case')
            for stage in ('launch', 'verify'):
                execution = case[stage]
                require(execution['status'] == 'passed' and execution['exit_code'] == 0, 'supplemental launch/verifier failed')
                raw = read(store.verify_artifact(execution['execution_ref']))
                require(raw['status'] == 'passed' and raw['exit_code'] == 0, 'bound supplemental execution failed')
                argv = raw['job']['argv']
                require(argv == planned[case['case_id']][stage + '_argv'] and argv[:len(env_prefix)] == env_prefix,
                        'supplemental execution differs from frozen timing-free argv')
                require(not set(raw['job'].get('environment', {})) & set(TIMING_ENVIRONMENT), 'supplemental job sets a timing environment variable')
                event = events.get(execution['event_id'])
                require(event is not None and event['candidate_id'] == 'exp-006' and event['payload']['status'] == 'passed'
                        and execution['execution_ref'] in event['payload']['artifact_refs'], 'supplemental execution lacks its completion event binding')
                require(event['payload']['execution']['argv'] == argv and event['payload']['execution']['exit_status'] == 0,
                        'supplemental event disagrees with its bound execution')
            observation = read(store.verify_artifact(case['observation_ref']))
            require(observation.get('passed') is True and observation['case_id'] == case['case_id'] and observation['candidate_id'] == 'exp-006'
                    and observation['mismatch_count'] == 0, 'supplemental observation did not pass')
            require('sha256:' + observation['output_sha256'].removeprefix('sha256:') == case['output_ref'], 'supplemental observation output binding differs')
            for digest in [case['output_ref'], case['case_validation_ref'], *case['artifact_refs']]:
                store.verify_artifact(digest)
            require(read(store.verify_artifact(case['case_validation_ref'])) == {key: value for key, value in case.items() if key != 'case_validation_ref'},
                    'supplemental case checkpoint differs')
        body = {key: value for key, value in report.items() if key != 'summary_ref'}
        require(report['summary_ref'] == content_hash(body), 'supplemental summary self-binding mismatch')
        store.verify_artifact(report['summary_ref'])
        store.verify_artifact(report['run_manifest_ref'])
        binding = read(base / 'attempts' / report['attempt'] / 'binding.json')
        digest = binding['artifact_ref']
        require(store.verify_artifact(digest).read_bytes() == path.read_bytes(), 'supplemental report raw CAS binding differs')
        event = events.get(report['event_id'])
        require(event is not None and {digest, report['summary_ref'], report['run_manifest_ref']}.issubset(set(event['payload'].get('evidence_refs', []))), 'supplemental completion event lacks its report/summary/run binding')
        fragment = read(store.verify_artifact(summary['result']['attempt_evidence_hash']))
        require(event in fragment['events'], 'supplemental qualification was not sealed before the safe outcome')
        evidence = set(summary['lesson']['evidence_refs'])
        if (self.run / 'tasks/exp/exploration_request.json').exists():
            request = read(self.run / 'tasks/exp/exploration_request.json')
            evidence.update(next(item['artifacts'].values() for item in request['evidence'] if item['candidate_id'] == 'exp-006'))
        require(digest in evidence, 'safe exp006 trace did not retain supplemental_correctness evidence')
        return {'required_for_safe_gain': True, 'case_count': 9, 'supplemental_correctness_ref': digest}

    def exports(self, split, store):
        ops = [op for op in self.manifest['operators'] if ('validation' if op in self.manifest['validation_operators'] else 'train') == split]
        require(all(self.tasks.get(op, {}).get('closure') == 'completed' for op in ops), 'split export cannot be complete while a task is missing or blocked')
        directory = self.run / split
        events = jsonl(directory / 'trace_events.jsonl')
        verify_trace(directory / 'trace_events.jsonl', store)
        originals = [event for op in ops for event in self.tasks[op]['events']]
        require({event['event_id']: event for event in events} == {event['event_id']: event for event in originals} and len(events) == len(originals), 'merged event export changed or omitted worker events')
        summaries = jsonl(directory / 'optimization_traces.jsonl')
        verify_optimization_traces(directory / 'optimization_traces.jsonl', store)
        original_summaries = [row for op in ops for row in self.tasks[op]['summaries']]
        require(sorted(map(canonical_json, summaries)) == sorted(map(canonical_json, original_summaries)), 'split summary export changed/omitted task summaries')
        episodes = [json.loads(payload) for payload in store.iter_payloads()]
        require(jsonl(directory / 'episodes.jsonl') == episodes, 'episodes.jsonl differs from the replay-verified SQLite export')
        require(all(episode['context']['task_id'] in ops for episode in episodes), 'episode store contains a task from another split')
        return {'event_count': len(events), 'attempt_count': len(summaries), 'episode_count': len(episodes)}

    def campaign_exports(self):
        for name in ('optimization_traces.jsonl', 'episodes.jsonl'):
            expected = b''.join((self.run / split / name).read_bytes() for split in ('train', 'validation'))
            require((self.run / name).read_bytes() == expected, 'campaign concatenated export differs: ' + name)
        events = jsonl(self.run / 'trace_events.jsonl')
        verify_trace(self.run / 'trace_events.jsonl')
        expected_events = [event for split in ('train', 'validation') for event in jsonl(self.run / split / 'trace_events.jsonl')]
        require({event['event_id']: event for event in events} == {event['event_id']: event for event in expected_events} and len(events) == len(expected_events), 'campaign event merge differs from split exports')
        summary = read(self.run / 'campaign_summary.json')
        reports = [self.tasks[op]['report'] for op in self.manifest['operators']]
        require(summary['operators'] == reports and summary['operator_count'] == 7 and summary['attempt_count'] == sum(report['attempt_count'] for report in reports), 'campaign summary differs from operator closure reports')
        return {'operator_count': 7, 'attempt_count': summary['attempt_count']}

    def verify(self):
        self.check('campaign', 'frozen_manifest', self.manifest_check)
        if not self.manifest:
            return self.report()
        try:
            for split in ('train', 'validation'):
                self.check(split, 'read_only_store', lambda split=split: self.open_store(split))
                if split in self.stores:
                    store = self.stores[split]
                    self.check(split, 'sqlite_integrity_and_episode_replay', lambda store=store: self.sqlite_integrity(store))
                    self.check(split, 'all_indexed_artifact_digests', lambda store=store: self.artifacts(store))
            for op in sorted(set(self.manifest.get('operators', [])) & OPERATORS):
                split = 'validation' if op in self.manifest.get('validation_operators', []) else 'train'
                if split not in self.stores:
                    continue
                store = self.stores[split]
                self.check(op, 'event_chains_and_closure', lambda op=op, store=store: self.task_events(op, store))
                self.check(op, 'frozen_roster_source_harness_boundary', lambda op=op, store=store: self.roster_sources(op, store))
                self.check(op, 'candidate_execution_budgets', lambda op=op: self.budgets(op))
                self.check(op, 'split_and_recorded_sealed_task_boundary', lambda op=op: self.boundaries(op))
                self.check(op, 'attempt_summaries_and_gate_replay', lambda op=op, store=store: self.finalized(op, store))
                self.check(op, 'raw_measurement_and_source_bindings', lambda op=op, store=store: self.measurements(op, store))
                self.check(op, 'delivered_source_snapshot', lambda op=op, store=store: self.delivered_source(op, store))
                self.check(op, 'blocked_diagnostic_measurement_boundary', lambda op=op, store=store: self.blocked_measurements(op, store))
            if 'train' in self.stores:
                self.check('exp', 'supplemental_exp006_safety_evidence', lambda: self.supplemental_exp006(self.stores['train']))
            completed = all(self.tasks.get(op, {}).get('closure') == 'completed' for op in OPERATORS)
            total = sum(task.get('budgets', {}).get('candidate_limit', 0) for task in self.tasks.values())
            self.check('campaign', 'bounded_24_candidate_roster', lambda: (require(total <= 24 and (not completed or total == 24), 'completed campaign must contain 24 attempts; campaign ceiling is 24'), {'candidate_count': total})[1])
            if completed:
                for split, store in self.stores.items():
                    self.check(split, 'exact_compatibility_exports', lambda split=split, store=store: self.exports(split, store))
                self.check('campaign', 'combined_exports_and_report', self.campaign_exports)
        finally:
            for store in self.stores.values():
                store.close()
        return self.report()

    def report(self):
        failures = [check for check in self.checks if check['status'] == 'failed']
        blocked = {op: task['finish']['payload']['reason'] for op, task in self.tasks.items() if task.get('closure') == 'blocked'}
        complete = all(self.tasks.get(op, {}).get('closure') == 'completed' for op in OPERATORS)
        return {'schema_version': '1.0.0', 'kind': 'aprof_campaign_verification', 'run': str(self.run),
            'verified_at': utcnow(), 'valid': not failures and complete, 'integrity_valid': not failures,
            'status': 'failed' if failures else ('verified' if complete else 'blocked'),
            'campaign_complete': complete, 'blocked_tasks': blocked, 'failure_count': len(failures),
            'measurement_blocked_tasks': sorted(op for op, task in self.tasks.items() if task.get('measurement_status') == 'blocked'),
            'checks': self.checks, 'mutated_campaign_artifacts': False,
            'limitations': ['Verification audits existing recorded evidence; it neither launches hardware nor repairs missing artifacts.',
                'Unrecorded worker reads and exclusive mechanism causality cannot be established from this artifact set.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--output', type=Path, help='Write the report here; default RUN/localverification_report.json.')
    args = parser.parse_args()
    report = CampaignVerifier(args.run).verify()
    output = args.output or args.run / 'localverification_report.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(report) + '\n')
    print(json.dumps({'status': report['status'], 'valid': report['valid'], 'failure_count': report['failure_count'], 'output': str(output.resolve())}))
    return 0 if report['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
