#!/usr/bin/env python3
"""Finalize a frozen serial measurement continuation without launching hardware.

The parent stores are opened read-only. Only referenced historical evidence is
copied; the new split stores contain exploration artifacts and zero episodes.
"""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
from copy import deepcopy
import csv
import datetime as dt
import difflib
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from aprof_runtime.errors import StoreError
from aprof_runtime.exploration import ExplorationGate, freeze_exploration_manifest, verify_exploration
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.store import EpisodeStore, default_object_directory
from aprof_runtime.traces import (TraceWriter, _hash_refs, _null_paths, _locked, _read_lines, _atomic_jsonl, _verify_records, export_episodes,
    merge_trace_streams, register_json_artifact, validate_optimization_trace,
    verify_optimization_traces, verify_trace, write_optimization_traces)
from cannbench_device_timing import summarize_multicase
from run_level1_serial import compare_controls
from finalize_level1_campaign import Finalizer, first_failure, read, rows, save, stage

CASES = list(range(1, 21))
HISTORICAL_ROLES = ('build_log', 'accuracy_report', 'candidate_plan', 'mechanism_report',
    'mechanism_plan', 'mechanism_binding', 'predeclared_contradicting_evidence', 'registration')


def append_trace_streams(inputs, output, store=None):
    """Merge whole attested streams while preserving every existing JSONL line."""
    output = Path(output)
    with _locked(output):
        existing = _read_lines(output)
        incoming = [record for path in inputs for record in _read_lines(Path(path))]
        by_id = {}
        for record in incoming:
            identifier = record['event_id']
            if identifier in by_id and canonical_json(by_id[identifier]) != canonical_json(record):
                raise StoreError('conflicting event in incremental stream merge')
            by_id[identifier] = record
        if any(record['event_id'] not in by_id or canonical_json(by_id[record['event_id']]) != canonical_json(record)
                for record in existing):
            raise StoreError('incremental export would discard or rewrite an existing event')
        present = {record['event_id'] for record in existing}
        if len(present) != len(existing):
            raise StoreError('duplicate existing event in incremental stream')
        merged = list(existing)
        for record in incoming:
            if record['event_id'] not in present:
                merged.append(record)
                present.add(record['event_id'])
        result = _verify_records(merged, store)
        if not output.exists() or len(merged) != len(existing):
            _atomic_jsonl(output, merged)
        return result


def empty_episodes(path):
    path = Path(path)
    if path.exists() and path.read_bytes():
        raise StoreError('exploration must not contain graph-policy episodes')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b'')


def replace_progress(path, value):
    """Mutable progress is deliberately separate from immutable final reports."""
    path = Path(path)
    payload = canonical_json(value) + '\n'
    if path.exists() and path.read_text() == payload:
        return
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix='.serial-progress-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def signature(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


class ExportStore(EpisodeStore):
    """One invocation's verified immutable bytes, invalidated by any stat change.

    This cache is local to this command, never persisted as a trust decision.
    Reopening for --verify-only rehashes every referenced object independently.
    """
    def __init__(self, path):
        super().__init__(path)
        self.verified = {}
        self.files = {}
        self.snapshots = {}

    def verify_artifact(self, digest):
        path = self.object_path(digest)
        current = signature(path) if path.exists() else None
        if self.verified.get(digest) == current and current is not None and not path.is_symlink():
            return path
        path = super().verify_artifact(digest)
        self.verified[digest] = signature(path)
        return path

    def install(self, source, expected=None):
        source = Path(source).resolve()
        current = signature(source)
        cached = self.files.get(source)
        digest = cached[1] if cached and cached[0] == current else file_hash(source)
        self.files[source] = (current, digest)
        if expected and digest != 'sha256:' + expected.removeprefix('sha256:'):
            raise StoreError(f'bound evidence changed: {source}')
        target = self.object_path(digest)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.incoming')
            try:
                shutil.copyfile(source, temporary)
                if file_hash(temporary) != digest:
                    raise StoreError(f'copied evidence differs: {source}')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            self.verified[digest] = signature(target)
        elif target.is_symlink():
            raise StoreError(f'CAS object is a symlink: {target}')
        self.connection.execute('INSERT OR IGNORE INTO artifacts(content_hash) VALUES (?)', (digest,))
        for uri in {target.resolve().as_uri(), source.as_uri()}:
            self.connection.execute('INSERT OR IGNORE INTO artifact_locations(content_hash,uri,size_bytes) VALUES (?,?,?)',
                (digest, uri, target.stat().st_size))
        self.connection.commit()
        self.verify_artifact(digest)
        return digest


class ParentClosure:
    """Import the reference closure, never walk a parent's large CAS directory."""
    def __init__(self, parent, split, store):
        database = parent / split / 'episodes.sqlite'
        self.connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
        self.objects = default_object_directory(database)
        self.store = store
        self.imported = set()
        self.membership = {}

    def known(self, digest):
        if digest not in self.membership:
            self.membership[digest] = bool(self.connection.execute(
                'SELECT 1 FROM artifacts WHERE content_hash=?', (digest,)).fetchone())
        return self.membership[digest]

    def add(self, digest):
        if digest in self.imported:
            return
        if not self.known(digest):
            raise StoreError(f'parent reference is not indexed: {digest}')
        hexvalue = digest.removeprefix('sha256:')
        path = self.objects / 'sha256' / hexvalue[:2] / hexvalue[2:]
        if path.is_symlink():
            raise StoreError('parent CAS reference is a symlink')
        self.store.install(path, digest)
        self.imported.add(digest)
        # JSON and provenance CSV may refer to further artifacts. Binary source
        # archives and input data are never decoded or traversed as directories.
        with path.open('rb') as stream:
            prefix = stream.read(256).lstrip()
        if prefix.startswith((b'{', b'[')):
            try:
                document = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                return
            for _, child in _hash_refs(document):
                # Embedded self-attestation hashes are values, not CAS links.
                if self.known(child):
                    self.add(child)
        elif b'aprof_source_hash' in prefix:
            with path.open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    child = row.get('aprof_source_hash')
                    if child:
                        self.add(child)

    def add_refs(self, value):
        for _, digest in _hash_refs(value):
            self.add(digest)

    def close(self):
        self.connection.close()


TIMER_HEADER = 'op_host/aprof_device_timer.h'


def source_snapshot(store, digest):
    """Decode and attest each manifest and archive member once per invocation."""
    path = store.verify_artifact(digest)
    current = signature(path)
    previous = store.snapshots.get(digest)
    if previous and previous[0] == current:
        return previous[1], previous[2]
    try:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            names = [m.name for m in members]
            if len(set(names)) != len(names) or 'APROF_SOURCE_SNAPSHOT.json' not in names:
                raise StoreError('source snapshot has duplicate members or no manifest')
            if any(not m.isfile() for m in members):
                raise StoreError('source snapshot contains a non-regular member')
            manifest = json.load(archive.extractfile('APROF_SOURCE_SNAPSHOT.json'))
            if manifest.get('kind') != 'aprof_source_snapshot_v1':
                raise StoreError('source snapshot manifest has an unsupported kind')
            entries = {x['path']: x for x in manifest['files']}
            if len(entries) != len(manifest['files']) or not entries:
                raise StoreError('source snapshot has duplicate or empty source inventory')
            if any(Path(p).is_absolute() or '..' in Path(p).parts or Path(p).as_posix() != p for p in entries):
                raise StoreError('source snapshot has an unsafe source path')
            if set(names) != {'APROF_SOURCE_SNAPSHOT.json', *('source/' + p for p in entries)}:
                raise StoreError('source snapshot members differ from its manifest')
            payloads = {}
            for relative, item in entries.items():
                member = archive.getmember('source/' + relative)
                payload = archive.extractfile(member).read()
                if (item['sha256'] != 'sha256:' + hashlib.sha256(payload).hexdigest()
                        or item['mode'] != member.mode & 0o777 or item['size_bytes'] != len(payload)):
                    raise StoreError('source snapshot manifest differs from source bytes or mode')
                payloads[relative] = payload
    except (tarfile.TarError, ValueError, KeyError, TypeError) as exc:
        raise StoreError(f'invalid source snapshot: {digest}') from exc
    store.snapshots[digest] = current, manifest, payloads
    return manifest, payloads


def verify_measurement_sources(entry, store):
    """Bind a separate harness tree to unchanged optimization-source snapshots."""
    binding = entry.get('measurement_source_binding')
    if binding is None:
        return {}
    if (set(binding) != {'kind', 'allowed_changed_paths', 'baseline', 'candidate'}
            or binding['kind'] != 'harness_only_measurement_continuation'
            or binding['allowed_changed_paths'] != [TIMER_HEADER]):
        raise StoreError('measurement source binding may allow only the timing header')
    artifacts, comparisons = {}, {}
    for label in ('baseline', 'candidate'):
        declared = binding[label]
        if set(declared) != {'source_snapshot_path', 'source_snapshot_sha256', 'harness_patch_path', 'harness_patch_sha256'}:
            raise StoreError('measurement source binding has an incomplete snapshot or patch identity')
        old_hash = entry['source_hashes'][label]
        old_manifest, old_payloads = source_snapshot(store, old_hash)
        new_hash = store.install(declared['source_snapshot_path'], declared['source_snapshot_sha256'])
        new_manifest, new_payloads = source_snapshot(store, new_hash)
        if new_manifest['excludes'] != old_manifest['excludes']:
            raise StoreError('measurement snapshot changed the source exclusion boundary')
        old = {x['path']: x for x in old_manifest['files']}
        new = {x['path']: x for x in new_manifest['files']}
        if set(old) != set(new) or TIMER_HEADER not in old or 'scripts/verify_result.py' not in old:
            raise StoreError('measurement snapshot added or deleted source files')
        changed = []
        for relative in old:
            if old[relative]['mode'] != new[relative]['mode']:
                raise StoreError('measurement source changed a protected file mode: ' + relative)
            if old[relative]['sha256'] != new[relative]['sha256']:
                changed.append(relative)
                if relative != TIMER_HEADER:
                    raise StoreError('measurement source changed protected source: ' + relative)
        tree = Path(entry[label])
        if not tree.is_absolute() or not tree.is_dir() or tree.is_symlink():
            raise StoreError('measurement tree must be an absolute regular directory')
        actual = {}
        for path in tree.rglob('*'):
            relative = path.relative_to(tree).as_posix()
            if any(fnmatch.fnmatchcase(relative, pattern) for pattern in old_manifest['excludes']):
                continue
            if path.is_symlink():
                raise StoreError('measurement source became a symlink: ' + relative)
            if path.is_file():
                actual[relative] = path
            elif not path.is_dir():
                raise StoreError('measurement source contains a non-regular file')
        if set(actual) != set(new):
            raise StoreError('actual measurement tree differs from the snapshot file inventory')
        for relative, path in actual.items():
            if path.stat().st_mode & 0o777 != new[relative]['mode']:
                raise StoreError('actual measurement source mode differs from snapshot: ' + relative)
            store.install(path, new[relative]['sha256'])
        try:
            before = old_payloads[TIMER_HEADER].decode('utf-8')
            after = new_payloads[TIMER_HEADER].decode('utf-8')
        except UnicodeError as exc:
            raise StoreError('timing header must have UTF-8 source bytes') from exc
        expected_patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
            fromfile='a/' + TIMER_HEADER, tofile='b/' + TIMER_HEADER)).encode('utf-8')
        patch_hash = store.install(declared['harness_patch_path'], declared['harness_patch_sha256'])
        if store.verify_artifact(patch_hash).read_bytes() != expected_patch:
            raise StoreError('harness patch does not exactly reproduce the original-to-measurement header change')
        artifacts['measurement_' + label + '_source_snapshot'] = new_hash
        artifacts['measurement_' + label + '_harness_patch'] = patch_hash
        comparisons[label] = dict(optimization_source_snapshot_ref=old_hash,
            measurement_source_snapshot_ref=new_hash, harness_patch_ref=patch_hash,
            optimization_harness_source_ref=old[TIMER_HEADER]['sha256'],
            measurement_harness_source_ref=new[TIMER_HEADER]['sha256'],
            changed_source_paths=sorted(changed), unchanged_source_file_count=len(old) - len(changed),
            source_file_modes_unchanged=True, precision_verifier_unchanged=True)
        # Make the separately named original header a real CAS reference too.
        old_header_ref = old[TIMER_HEADER]['sha256']
        if not store.object_path(old_header_ref).exists():
            import tempfile
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(old_payloads[TIMER_HEADER]); tmp.flush()
                store.install(tmp.name, old_header_ref)
        else:
            store.verify_artifact(old_header_ref)
    artifacts['measurement_source_verification'] = register_json_artifact(store, dict(
        kind='harness_only_measurement_source_verification', candidate_id=entry['candidate_id'],
        allowed_changed_paths=[TIMER_HEADER], comparisons=comparisons,
        optimization_source_identity_unchanged=True, new_optimization_attempt=False))
    return artifacts


def single_context_protocol_errors(manifest, raw):
    """Require the declared process lifecycle without changing gate statistics."""
    if not raw:
        return []
    declared = manifest.get('single_live_context') is True
    observed = raw.get('single_live_context') is True
    fields_present = any(key in raw for key in ('context_lifecycle', 'verification_output_scope'))
    invalid_flag = 'single_live_context' in raw and type(raw['single_live_context']) is not bool
    if declared != observed or invalid_flag or (fields_present and not declared):
        return ['Observed single-live-context mode differs from the frozen measurement manifest.']
    if declared and (raw.get('context_lifecycle') != 'one_process_per_role_sample'
            or raw.get('verification_output_scope') != 'last_process_output_per_role'):
        return ['Single-live-context lifecycle or output verification scope differs from the frozen protocol.']
    return []


def qualified_report(raw, report, calibration, correctness_passed, protocol_errors=()):
    """Keep descriptive raw observations while withholding unqualified reward."""
    recomputed = summarize_multicase(raw, CASES)
    if report is not None and canonical_json(recomputed) != canonical_json(report):
        raise StoreError('measurement report does not reproduce raw pairs')
    admitted = deepcopy(recomputed)
    reasons = list(protocol_errors)
    if not calibration['accepted']:
        reasons.append('Calibration rejected admission: ' + calibration['reason'])
    if not calibration['operator_health']['accepted']:
        reasons.append('Operator health rejected admission: ' + calibration['operator_health']['reason'])
    if not correctness_passed:
        reasons.append('Current prepared-output correctness is incomplete or failed.')
    if reasons:
        admitted['stable'] = False
        admitted['reasons'] = sorted(set(admitted['reasons'] + reasons))
        admitted['speedup'] = admitted['speedup_lcb_95'] = None
        admitted['performance_eligible'] = False
    if not admitted['stable']:
        admitted['gate_projection'] = dict(baseline_samples_ns=[], candidate_samples_ns=[], heldout_regressions=[])
    return recomputed, admitted


def execution_interval(record):
    try:
        start, finish = [dt.datetime.fromisoformat(record[key].replace('Z', '+00:00'))
            for key in ('started_at', 'finished_at')]
        if start.tzinfo is not None and finish.tzinfo is not None and finish >= start:
            return start, finish
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    return None


def execution_location_errors(manifest, raw, execution):
    reasons = []
    if execution is not None:
        for key in ('host', 'physical_device', 'logical_device'):
            if key in manifest and (execution.get(key) != manifest[key] or type(execution.get(key)) is not type(manifest[key])):
                reasons.append('Execution ' + key + ' differs from the frozen measurement manifest.')
    if raw:
        for key, field in (('host', 'host'), ('logical_device', 'device')):
            if key in manifest and (raw.get(field) != manifest[key] or type(raw.get(field)) is not type(manifest[key])):
                reasons.append('Raw measurement ' + field + ' differs from the frozen measurement manifest.')
    return reasons


class SerialFinalizer:
    def __init__(self, run):
        self.run = Path(run).resolve()
        self.manifest = read(self.run / 'run-manifest.json')
        self.parent = Path(self.manifest['parent_run'])
        if not self.parent.is_absolute() or self.parent.resolve() == self.run:
            raise StoreError('parent_run must name a different absolute run directory')
        self.parent = self.parent.resolve()
        self.parent_records = {item['identity']['candidate_id']: item
            for split in ('train', 'validation') for item in rows(self.parent / split / 'optimization_traces.jsonl')}
        self.operators = self.manifest['operators']
        expected = [x['candidate_id'] for op in self.operators for x in self.manifest['candidates'][op]]
        if len(expected) != len(set(expected)) or set(expected) != set(self.parent_records):
            raise StoreError('continuation must contain the entire parent candidate roster exactly once')
        if set(self.operators) != {x['identity']['operator'] for x in self.parent_records.values()}:
            raise StoreError('continuation operator roster differs from the parent')
        for op in self.operators:
            for entry in self.manifest['candidates'][op]:
                parent = self.parent_records[entry['candidate_id']]
                if parent['identity']['operator'] != op or parent['identity']['split'] != self.split(op):
                    raise StoreError('candidate operator or split differs from parent')
                if entry['source_hashes'] != {label: parent['provenance'][label + '_source_hash']
                                              for label in ('baseline', 'candidate')}:
                    raise StoreError('measurement continuation changed a candidate source identity')

    def split(self, op):
        return 'validation' if op in self.manifest['validation_operators'] else 'train'

    def attestation(self, op, store, create=False):
        """Persist the real retrospective recording time independently of source freeze."""
        task = self.run / 'tasks' / op
        path = task / 'attestation.json'
        freeze_path = self.parent / 'tasks' / op / 'frozen-roster.json'
        source_freeze = read(freeze_path)
        expected = dict(schema_version='1.0.0', run_id=self.run.name, task_id=op,
            mode='retrospective_measurement_continuation', parent_run=str(self.parent),
            run_created_at=self.manifest['created_at'], source_frozen_at=source_freeze['frozen_at'],
            producer_path=str(Path(__file__).resolve()), producer_ref=store.install(Path(__file__)),
            run_manifest_ref=store.install(self.run / 'run-manifest.json'),
            source_freeze_path=str(freeze_path), source_freeze_ref=store.install(freeze_path),
            reason='Retrospective attestation of a frozen source attempt and completed measurement evidence; '
                'event timestamps record attestation, while execution records retain actual start and finish times.')
        with _locked(path):
            if not path.exists() and not create:
                raise StoreError('sealed operator lacks its retrospective attestation')
            record = read(path) if path.exists() else dict(expected,
                attested_at=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'))
            if {k: v for k, v in record.items() if k != 'attested_at'} != expected:
                raise StoreError('retrospective attestation differs from the frozen run or source identity')
            interval = execution_interval(dict(started_at=record.get('attested_at'), finished_at=record.get('attested_at')))
            if interval is None or interval[0] > dt.datetime.now(dt.timezone.utc):
                raise StoreError('retrospective attestation has an invalid or future timestamp')
            attested = interval[0]
            for key in ('run_created_at', 'source_frozen_at'):
                if execution_interval(dict(started_at=record[key], finished_at=record['attested_at'])) is None:
                    raise StoreError('retrospective attestation precedes the run or source freeze')
            decision = read(task / 'calibration-decision.json')
            controls = [Path(p) if Path(p).is_absolute() else self.run / p for p in decision.get('artifact_paths', [])]
            executions = [p.parent / 'execution.json' for p in controls]
            executions += [task / 'measurements' / entry['identifier'] / 'execution.json'
                for entry in self.manifest['candidates'][op]]
            executions += [task / ('health-' + phase + '.json') for phase in ('before', 'after')]
            for execution_path in executions:
                if not execution_path.exists():
                    continue
                execution = read(execution_path)
                if not any(key in execution for key in ('started_at', 'finished_at')):
                    continue  # Minimal historical CPU fixtures have no execution timestamp envelope.
                actual = execution_interval(execution)
                if actual is None or actual[1] > attested:
                    raise StoreError('execution finishes after retrospective attestation or has an invalid interval: ' + str(execution_path))
            save(path, record)
        return record, store.install(path)

    def operator_health(self, op, store=None):
        """A calibration decision precedes final health collection in the controller."""
        artifacts, reasons, health_records = {}, [], {}
        for phase in ('before', 'after'):
            path = self.run / 'tasks' / op / ('health-' + phase + '.json')
            if not path.exists():
                return None, 'Operator health-' + phase + ' evidence is not closed.'
            record = read(path)
            if (type(record.get('exit_status')) is not int
                    or any(not isinstance(record.get(key), str) for key in
                        ('started_at', 'finished_at', 'stdout', 'stderr', 'host', 'cwd'))
                    or not record.get('started_at') or not record.get('finished_at')
                    or not isinstance(record.get('argv'), list)
                    or type(record.get('no_device_processes')) is not bool):
                return None, 'Operator health-' + phase + ' evidence has no complete terminal record.'
            health_records[phase] = record
            if execution_interval(record) is None:
                reasons.append('health-' + phase + ' has an invalid execution interval')
            if 'host' in self.manifest and record['host'] != self.manifest['host']:
                reasons.append('health-' + phase + ' host differs from the frozen measurement manifest')
            if record['argv'] != ['/usr/local/sbin/npu-smi', 'info']:
                reasons.append('health-' + phase + ' did not run the frozen process inventory command')
            count = record['stdout'].count('No running processes found in NPU')
            if record['exit_status'] != 0 or count != 8 or not record['no_device_processes']:
                reasons.append(f'health-{phase}: exit_status={record["exit_status"]}, empty_process_tables={count}, '
                    f'no_device_processes={record["no_device_processes"]}')
            if store is not None:
                artifacts['operator_health_' + phase] = store.install(path)
        if 'host' in self.manifest:
            decision = read(self.run / 'tasks' / op / 'calibration-decision.json')
            controls = [Path(path) if Path(path).is_absolute() else self.run / path
                for path in decision.get('artifact_paths', [])]
            execution_paths = [(path.parent / 'execution.json', True) for path in controls]
            execution_paths += [(self.run / 'tasks' / op / 'measurements' / entry['identifier'] / 'execution.json', False)
                for entry in self.manifest['candidates'][op]]
            control_intervals, intervals = [], []
            for path, control in execution_paths:
                if not path.exists() and not control:
                    continue
                interval = execution_interval(read(path)) if path.exists() else None
                if interval is None:
                    reasons.append('Missing or invalid execution interval for ' + str(path))
                    continue
                intervals.append(interval)
                if control:
                    control_intervals.append(interval)
            before = execution_interval(health_records['before'])
            after = execution_interval(health_records['after'])
            if not control_intervals:
                reasons.append('No control execution interval establishes the operator health boundary')
            elif before and before[1] > min(start for start, _ in control_intervals):
                reasons.append('health-before finished after the first control execution started')
            if after and intervals and after[0] < max(finish for _, finish in intervals):
                reasons.append('health-after started before the final control or candidate execution finished')
        return dict(accepted=not reasons,
            reason='; '.join(reasons) if reasons else 'Before and after inventories each report eight empty NPU process tables.',
            artifacts=artifacts), None

    def calibration(self, op, store):
        path = self.run / 'tasks' / op / 'calibration-decision.json'
        if not path.exists():
            path = self.run / 'calibration/selection.json'
            if not path.exists() or read(path).get('accepted') is not False:
                raise StoreError(f'operator calibration is unfinished: {op}')
        decision = read(path)
        if type(decision.get('accepted')) is not bool or not decision.get('reason'):
            raise StoreError('invalid calibration decision')
        refs = [store.install(path)]
        reports = []
        for artifact in decision.get('artifact_paths', []):
            artifact = Path(artifact)
            if not artifact.is_absolute():
                artifact = self.run / artifact
            refs.append(store.install(artifact))
            report = read(artifact)
            raw_path = artifact.parent / 'raw_measurements.json'
            raw = read(raw_path) if raw_path.exists() else None
            if raw is None or summarize_multicase(raw, report['case_ids']) != report:
                raise StoreError('calibration report does not reproduce raw measurements')
            if decision['accepted']:
                execution_path = artifact.parent / 'execution.json'
                execution = read(execution_path) if execution_path.exists() else None
                if execution_location_errors(self.manifest, raw, execution):
                    raise StoreError('accepted A/A controls have a host or device different from the frozen manifest')
                if single_context_protocol_errors(self.manifest, raw):
                    raise StoreError('accepted A/A controls use a different single-live-context lifecycle')
                if bool(raw.get('capture_replay')) != bool(self.manifest.get('capture_replay')):
                    raise StoreError('accepted A/A controls use a different capture/replay mode')
                if self.manifest.get('reuse_verifier') and raw.get('verification_protocol') != 'in_process_reuse_v1':
                    raise StoreError('accepted A/A controls use a different verifier protocol')
                expected_binary = self.manifest['candidates'][op][0]['baseline_executable_sha256'].removeprefix('sha256:')
                if raw.get('operator') != op or any(raw.get(label + '_executable_sha256', '').removeprefix('sha256:') != expected_binary
                        for label in ('baseline', 'candidate')):
                    raise StoreError('accepted A/A controls are not paired executions of the frozen baseline')
            reports.append(report)
            for name in ('raw_measurements.json', 'execution.json'):
                sibling = artifact.parent / name
                if sibling.exists():
                    refs.append(store.install(sibling))
        if decision['accepted']:
            if len(reports) != 3 or not compare_controls(reports[0], reports[1])['accepted'] or not compare_controls(reports[0], reports[2])['accepted']:
                raise StoreError('accepted calibration does not replay both startup and post-batch controls')
            for artifact in decision['artifact_paths']:
                execution = read(Path(artifact).parent / 'execution.json')
                if execution.get('exit_status') != 0:
                    raise StoreError('accepted calibration contains a failed execution')
        health, pending = self.operator_health(op, store)
        if pending:
            raise StoreError(pending)
        decision['operator_health'] = health
        refs.extend(health['artifacts'].values())
        refs = list(dict.fromkeys(refs))
        decision['artifact_refs'] = refs
        return decision, refs

    def method_history(self, store):
        """Import method studies as context events, never optimization attempts."""
        method = self.manifest.get('method_parent_run')
        visited, history = {self.run}, []
        while method is not None:
            directory = Path(method)
            if not directory.is_absolute() or directory.resolve() in visited:
                raise StoreError('method parent chain must use distinct absolute run directories')
            directory = directory.resolve()
            visited.add(directory)
            manifest_path = directory / 'run-manifest.json'
            manifest = read(manifest_path)
            refs = [store.install(manifest_path)]
            selection_paths = [p for p in (directory / 'selection.json', directory / 'calibration/selection.json') if p.exists()]
            if not selection_paths:
                raise StoreError('method parent has no recorded method selection or failure')
            selections = []
            for path in selection_paths:
                selection = read(path)
                selections.append(dict(path=str(path), artifact_ref=store.install(path),
                    accepted=selection.get('accepted'), reason=selection.get('reason')))
                refs.append(selections[-1]['artifact_ref'])
                declared = list(selection.get('artifact_paths', []))
                if selection.get('execution'):
                    declared.append(selection['execution'])
                for name in declared:
                    artifact = Path(name)
                    if not artifact.is_absolute():
                        artifact = directory / artifact
                    refs.append(store.install(artifact))
                    for sibling in ('raw_measurements.json', 'execution.json', 'stdout.log', 'stderr.log'):
                        path = artifact.parent / sibling
                        if path.exists():
                            refs.append(store.install(path))
            for path in sorted((directory / 'setup').glob('*.json')):
                refs.append(store.install(path))
            for path in [*directory.glob('health-*.json'), *(directory / 'calibration').glob('health-*.json')]:
                refs.append(store.install(path))
            for entries in manifest.get('candidates', {}).values():
                for entry in entries:
                    for label in ('baseline', 'candidate'):
                        source = entry.get('measurement_source_binding', {}).get(label)
                        if source:
                            for role in ('source_snapshot', 'harness_patch'):
                                refs.append(store.install(source[role + '_path'], source[role + '_sha256']))
            history.append(dict(run_directory=str(directory), manifest_ref=refs[0], selections=selections,
                evidence_refs=sorted(set(refs)), candidate_attempts_added=0,
                role='Measurement-method study; no optimization-candidate reward is inherited.'))
            method = manifest.get('method_parent_run')
        if not history:
            return None
        return register_json_artifact(store, dict(kind='measurement_method_history',
            method_studies=history, optimization_attempt_count=0, graph_policy_eligible=False))

    def historical(self, parent, gate, closure):
        record = deepcopy(parent)
        # Keep direct evidence that supports each inherited stage. The complete
        # old profiler command/log collection remains in the named parent run.
        roles = {key: value for key, value in gate['artifacts'].items() if key in HISTORICAL_ROLES}
        bindings = {'static_review': ['candidate_plan'], 'build': ['build_log'],
            'correctness': ['accuracy_report'], 'runtime': ['accuracy_report'],
            'profile': ['mechanism_report', 'mechanism_binding', 'mechanism_plan']}
        for name, keys in bindings.items():
            old = record['validation'][name]
            old['reason'] = 'Inherited from parent run ' + str(self.parent) + ': ' + (old['reason'] or 'Recorded historical evidence.')
            old['artifact_refs'] = sorted({roles[k] for k in keys if k in roles})
            if name == 'profile' and not old['artifact_refs']:
                old.update(status='not_run', reason='No compact inherited profile binding is available; consult parent run.')
        record['validation']['timing'] = stage(reason='No current serial timing has been admitted.')
        record['validation']['timing_case_ids'] = []
        excerpt = {key: deepcopy(record[key]) for key in
            ('identity', 'provenance', 'knowledge', 'workload', 'diagnosis', 'intervention', 'routing', 'validation')}
        excerpt.update(kind='parent_attempt_evidence_excerpt', parent_run=str(self.parent),
            parent_record_sha256=content_hash(parent).removeprefix('sha256:'),
            inherited_gate_artifacts=roles,
            limitation='Only stage-supporting evidence is imported; the full historical trace remains in parent_run.')
        closure.add_refs(excerpt)
        return record, roles, register_json_artifact(closure.store, excerpt)

    def measurement(self, op, entry, store, calibration):
        directory = self.run / 'tasks' / op / 'measurements' / entry['identifier']
        raw_path, report_path = directory / 'raw_measurements.json', directory / 'measurement_report.json'
        execution_path = directory / 'execution.json'
        raw = read(raw_path) if raw_path.exists() else {}
        execution = read(execution_path) if execution_path.exists() else None
        report = read(report_path) if report_path.exists() else None
        artifacts = verify_measurement_sources(entry, store)
        artifacts.update(calibration['operator_health']['artifacts'])
        refs = list(artifacts.values())
        if self.manifest.get('capture_replay') and not entry.get('measurement_source_binding'):
            raise StoreError('capture/replay requires an independently bound measurement harness')
        protocol_errors = single_context_protocol_errors(self.manifest, raw)
        protocol_errors.extend(execution_location_errors(self.manifest, raw, execution))
        if raw and bool(raw.get('capture_replay')) != bool(self.manifest.get('capture_replay')):
            protocol_errors.append('Observed capture/replay mode differs from the frozen measurement manifest.')
        reused = bool(self.manifest.get('reuse_verifier'))
        if raw and reused:
            if raw.get('verification_protocol') != 'in_process_reuse_v1' or not raw.get('verifier_source_hash'):
                protocol_errors.append('Observed verifier protocol differs from the frozen measurement manifest.')
            else:
                refs.append(store.install(Path(entry['baseline']) / 'scripts/verify_result.py', raw['verifier_source_hash']))
        if report is not None and not raw:
            raise StoreError('measurement report lacks raw evidence')
        if raw and execution is None:
            raise StoreError('raw measurements lack a terminal execution record')
        if execution:
            binding = execution['source_binding']
            if any(binding.get(k) != v for k, v in entry.items()):
                raise StoreError('execution source binding differs from frozen roster')
            if binding.get('actual_candidate', entry['candidate']) != entry['candidate'] or binding.get('actual_candidate_source_hash', entry['source_hashes']['candidate']) != entry['source_hashes']['candidate']:
                raise StoreError('timing executed a different candidate than the frozen source')
            if binding.get('input_bindings_sha256'):
                input_path = self.run / 'setup/input-bindings.json'
                refs.append(store.install(input_path, binding['input_bindings_sha256']))
                input_bindings = read(input_path)['inputs'][op]
                for case in CASES:
                    for path, digest in input_bindings[str(case)].items():
                        refs.append(store.install(path, digest))
            if execution.get('controller_sha256'):
                controller = read(self.run / 'setup/active-controller.json')
                refs.append(store.install(controller['path'], execution['controller_sha256']))
            if entry.get('registration_path'):
                refs.append(store.install(entry['registration_path'], entry['registration_sha256']))
            if execution.get('argv'):
                argv = execution['argv']
                for label in ('baseline', 'candidate'):
                    flag = '--' + label
                    if flag not in argv or argv[argv.index(flag) + 1] != entry[label]:
                        raise StoreError('execution argv differs from its source binding')
            artifacts['execution_manifest'] = store.install(execution_path)
            refs.append(artifacts['execution_manifest'])
            for label in ('baseline', 'candidate'):
                expected = entry[label + '_executable_sha256']
                if raw and raw.get(label + '_executable_sha256', '').removeprefix('sha256:') != expected.removeprefix('sha256:'):
                    raise StoreError('raw measurements identify a different executable')
                refs.append(store.install(Path(entry[label]) / 'build' / op, expected))
            producer = self.run / 'setup/cannbench_device_timing.py'
            expected_producer = execution['timing_producer_sha256']
            refs.append(store.install(producer, expected_producer))
            if raw and raw.get('producer_sha256', '').removeprefix('sha256:') != expected_producer.removeprefix('sha256:'):
                raise StoreError('raw measurements identify a different timing producer')
            for label in ('stdout', 'stderr'):
                if label in execution:
                    saved = directory / Path(execution[label]['path']).name
                    refs.append(store.install(saved, execution[label]['sha256']))
        if raw:
            artifacts['raw_measurements'] = store.install(raw_path)
            refs.append(artifacts['raw_measurements'])
            if report is not None:
                artifacts['observed_measurement_report'] = store.install(report_path)
                refs.append(artifacts['observed_measurement_report'])
        cases = []
        for item in raw.get('case_executions', []):
            case = item['case_id']
            metadata_path = Path(item['metadata_path'])
            refs.append(store.install(metadata_path, item['metadata_sha256']))
            metadata = read(metadata_path)
            for key, digest in item.get('input_hashes', {}).items():
                refs.append(store.install(metadata[key], digest))
            for session in item.get('context_sessions', []):
                label = session.get('label')
                if label not in ('baseline', 'candidate'):
                    continue  # The timing adapter withholds incomplete/invalid sessions.
                argv = session.get('argv')
                if argv and argv[0] != str(Path(entry[label]) / 'build' / op):
                    raise StoreError('context session command differs from the frozen executable')
                if session.get('cwd') and Path(session['cwd']).resolve() != Path(entry[label]).resolve():
                    raise StoreError('context session working directory differs from its frozen source tree')
                if session.get('log_path'):
                    log = directory / Path(session['log_path']).name
                    if log.exists():
                        refs.append(store.install(log))
                    elif session.get('exit_status') == 0:
                        protocol_errors.append('A completed context session is missing its archived execution log.')
            checks = []
            for label in ('baseline', 'candidate'):
                command = item.get('commands', {}).get(label)
                if command and command['argv'][0] != str(Path(entry[label]) / 'build' / op):
                    raise StoreError('raw case command differs from the frozen executable')
                for artifact in (directory / f'case-{case:02d}-{label}.bin',
                        directory / f'case-{case:02d}-{label}-verification/metadata.json'):
                    if artifact.exists():
                        refs.append(store.install(artifact))
                path = directory / f'case-{case:02d}-{label}-verify.log'
                if path.exists():
                    checks.append(store.install(path))
            refs.extend(checks)
            verification_statuses = [item.get('verifications', {}).get(label, {}).get('exit_status')
                for label in ('baseline', 'candidate')] if reused else [0, 0]
            passed = item.get('exit_status') == 0 and len(checks) == 2 and verification_statuses == [0, 0]
            failed = item.get('exit_status') not in (None, 0) or any(x not in (None, 0) for x in verification_statuses) or (bool(checks) and raw.get('error', {}).get('type') == 'CalledProcessError')
            cases.append(dict(case_id=case, status='passed' if passed else 'failed' if failed else 'interrupted',
                exit_status=item.get('exit_status'), verifier_log_refs=checks))
        outputs_passed = (bool(raw.get('complete')) and [item['case_id'] for item in cases] == CASES
            and all(item['status'] == 'passed' for item in cases))
        current_passed = outputs_passed and execution is not None and execution.get('exit_status') == 0
        observed, admitted = qualified_report(raw, report, calibration, current_passed, protocol_errors)
        artifacts['measurement_report'] = register_json_artifact(store, admitted)
        refs.append(artifacts['measurement_report'])
        correctness = None
        if raw or execution:
            correctness = dict(kind='serial_prepared_output_correctness', case_ids=CASES, case_count=20,
                passed_count=sum(x['status'] == 'passed' for x in cases), cases=cases,
                status='passed' if outputs_passed else 'failed' if any(x['status'] == 'failed' for x in cases) else 'interrupted',
                raw_measurements_ref=artifacts.get('raw_measurements'),
                contract='Inherited local baseline verifier; both prepared outputs checked independently per case.',
                verifier_protocol='in_process_reuse_v1' if reused else 'subprocess_per_output',
                verifier_source_ref=raw.get('verifier_source_hash') if reused else None,
                verification_output_scope=raw.get('verification_output_scope', 'final_prepared_output_per_role'))
            artifacts['accuracy_report'] = register_json_artifact(store, correctness)
            refs.append(artifacts['accuracy_report'])
        return dict(raw=raw, execution=execution, observed=observed, admitted=admitted,
                    correctness=correctness, artifacts=artifacts, refs=sorted(set(refs)))

    def finalize_operator(self, op, store, closure):
        task = self.run / 'tasks' / op
        parent_request = read(self.parent / 'tasks' / op / 'exploration_request.json')
        parent_evidence = {x['candidate_id']: x for x in parent_request['evidence']}
        calibration, calibration_refs = self.calibration(op, store)
        attestation, attestation_ref = self.attestation(op, store, create=True)
        writer = TraceWriter(task / 'trace_events.jsonl', run_id=self.run.name, task_id=op,
            session_id=op + '-serial-continuation', store=store, verify_history_artifacts=False)
        timestamp = attestation['attested_at']
        manifest_ref = store.install(self.run / 'run-manifest.json')
        method_ref = self.method_history(store)
        if method_ref:
            writer.append('next_step_decided', dict(action='record_measurement_method_history',
                reason='Retrospective attestation: previous A/A method studies explain the measurement protocol; they add zero optimization attempts and no inherited performance reward.',
                evidence_refs=[method_ref]), event_id=op + '-method-history', timestamp=timestamp, artifact_refs=[attestation_ref])
        setup_refs = [store.install(p) for p in sorted((self.run / 'setup').glob('*.json'))]
        if setup_refs:
            writer.append('next_step_decided', dict(action='record_setup_evidence',
                reason='Retrospective attestation: setup records, including any preflight failures, are infrastructure evidence and consume no source-attempt budget.',
                evidence_refs=setup_refs), event_id=op + '-setup', timestamp=timestamp, artifact_refs=[attestation_ref])
        writer.append('next_step_decided', dict(action='continue_frozen_measurements',
            reason='Retrospective attestation of measurement continuation of parent run ' + str(self.parent) + '; source attempts and candidate IDs are unchanged.',
            evidence_refs=[manifest_ref, attestation_ref]), event_id=op + '-continuation', timestamp=timestamp, artifact_refs=[attestation_ref])
        frozen, evidence, attempts = [], [], []
        existing_request_path = task / 'exploration_request.json'
        existing_request = read(existing_request_path) if existing_request_path.exists() else None
        for entry in self.manifest['candidates'][op]:
            cid = entry['candidate_id']
            original = self.parent_records[cid]
            gate = deepcopy(parent_evidence[cid])
            record, inherited, parent_ref = self.historical(original, gate, closure)
            measured = self.measurement(op, entry, store, calibration)
            record['identity'].update(run_id=self.run.name, session_id=writer.identity['session_id'],
                parent_attempt_id=original['identity']['attempt_id'])
            record['routing'].update(mode='exploration', route=None)
            record['provenance']['dependencies']['parent_run'] = str(self.parent)
            record['provenance']['dependencies']['continuation_kind'] = 'measurement_only_no_new_source_attempt'
            record['provenance']['dependencies']['measurement_attestation_ref'] = attestation_ref
            record['provenance']['dependencies']['parent_producer_hash'] = original['provenance']['producer_hash']
            record['provenance']['producer_hash'] = attestation['producer_ref']
            if entry.get('measurement_source_binding'):
                record['provenance']['dependencies']['measurement_source_kind'] = 'harness_only_measurement_continuation'
                for label in ('baseline', 'candidate'):
                    for name, role in (('source_snapshot', 'measurement_' + label + '_source_snapshot'),
                            ('harness_patch', 'measurement_' + label + '_harness_patch')):
                        digest = measured['artifacts'][role]
                        record['provenance']['dependencies'][role] = digest
                        record['knowledge']['loaded'].append(dict(
                            path=entry['measurement_source_binding'][label][name + '_path'], content_hash=digest,
                            purpose='Verified measurement harness artifact; original optimization source and precision verifier remain unchanged.'))
            refs = sorted(set(measured['refs'] + calibration_refs + [parent_ref, attestation_ref]))
            gate['artifacts'] = {**inherited, **measured['artifacts'], 'parent_attempt_excerpt': parent_ref,
                                 'calibration_decision': calibration_refs[0], 'measurement_attestation': attestation_ref}
            if method_ref:
                gate['artifacts']['measurement_method_history'] = method_ref
                refs.append(method_ref)
                record['provenance']['dependencies']['method_parent_run'] = str(self.manifest['method_parent_run'])
            gate.update(measured['admitted']['gate_projection'])
            validation = record['validation']
            if measured['correctness'] is not None:
                correctness = measured['correctness']
                validation['correctness'] = stage(correctness['status'], 'Current per-case baseline and candidate prepared outputs; see bound verifier logs.',
                    [measured['artifacts']['accuracy_report']])
                if self.manifest.get('single_live_context'):
                    validation['correctness']['reason'] += ' Only the last process output for each role is verified; earlier per-round outputs are not separately checked.'
                validation['case_count'], validation['passed_count'] = 20, correctness['passed_count']
                gate['accuracy'] = correctness['status'] if correctness['status'] != 'interrupted' else 'not_run'
                runtime_passed = measured['execution'].get('exit_status') == 0
                gate['runtime'] = 'passed' if runtime_passed else 'failed'
                validation['runtime'] = stage(gate['runtime'], 'Current serial timing command exit status.',
                    [measured['artifacts']['execution_manifest']])
            validation['timing_case_ids'] = [x['case_id'] for x in measured['observed']['per_case'] if x['pair_count']]
            timing_reason = '; '.join(measured['admitted']['reasons']) or 'All 20 cases and operator A/A calibration passed admission.'
            validation['timing'] = stage('passed' if measured['admitted']['stable'] else
                ('failed' if measured['raw'] else 'not_run'), timing_reason, refs)
            aid = record['identity']['attempt_id']
            def append(kind, payload, suffix):
                if 'reason' in payload:
                    payload = dict(payload, reason='Retrospective attestation: ' + payload['reason'])
                return writer.append(kind, payload, attempt_id=aid, candidate_id=cid,
                    event_id=cid + '-' + suffix, timestamp=timestamp, artifact_refs=[attestation_ref])
            append('next_step_decided', dict(action='inherit_source_attempt',
                reason='Parent attempt ' + aid + ' in ' + str(self.parent) + '; this event restates the frozen proposal for continuation attestation.',
                evidence_refs=[parent_ref]), 'inherit')
            append('diagnosis_recorded', record['diagnosis'], 'diagnosis')
            intervention = record['intervention']
            append('candidate_proposed', dict(mode='exploration', hypothesis=intervention['intent'],
                source_parent_hash=entry['source_hashes']['baseline'], patch_hash=record['provenance']['patch_hash'],
                handler_id=intervention['handler']['id'], handler_version=intervention['handler']['version'],
                parameters=intervention['parameters'], expected_effects=intervention['expected_effects'],
                alternatives=intervention['alternatives'], coverage_gap=record['routing']['coverage_gap']), 'proposal')
            for name in ('static_review', 'build', 'correctness', 'runtime', 'profile', 'timing'):
                actual = measured['execution']
                execution = None
                if name in ('correctness', 'runtime', 'timing') and actual and all(k in actual for k in
                        ('argv', 'cwd', 'host', 'started_at', 'finished_at')):
                    log = actual.get('stdout')
                    execution = dict(argv=actual['argv'], cwd=actual['cwd'], host=actual['host'],
                        device=str(actual.get('logical_device', 0)), started_at=actual['started_at'],
                        finished_at=actual['finished_at'], exit_status=actual['exit_status'],
                        log_ref='sha256:' + log['sha256'].removeprefix('sha256:') if log else None,
                        reason=None if log and actual['exit_status'] is not None else 'Interrupted command or no captured stdout.')
                    if validation[name]['status'] == 'passed' and actual['exit_status'] != 0:
                        execution = None  # Verified outputs can precede a later controller failure.
                append('stage_completed', dict(stage=name, execution=execution, **validation[name]), name)
            if existing_request:
                sealed = next(x['attempt_evidence_hash'] for x in existing_request['candidates'] if x['candidate_id'] == cid)
            else:
                sealed = writer.seal_attempt(aid)
            frozen.append(dict(candidate_id=cid, session_id=writer.identity['session_id'], source_hashes=entry['source_hashes'],
                patch_artifact_hash=record['provenance']['patch_hash'], handler_id=intervention['handler']['id'],
                handler_version=intervention['handler']['version'], parameters=intervention['parameters'],
                coverage_gap=record['routing']['coverage_gap'], attempt_evidence_hash=sealed))
            evidence.append(gate)
            attempts.append((record, measured, refs, sealed))
        frozen_hash = freeze_exploration_manifest(store, run_id=self.run.name, task_id=op, split=self.split(op),
            candidates=frozen, frozen_at=attestation['source_frozen_at'])
        request = dict(schema_version='1.0.0', frozen_manifest_hash=frozen_hash, candidates=frozen,
                       evidence=evidence, config=parent_request['config'])
        save(existing_request_path, request)
        outcomes = list(ExplorationGate().evaluate(request, store=store))
        save(task / 'exploration_outcomes.json', outcomes)
        summaries, reports = [], []
        for (record, measured, refs, sealed), outcome in zip(attempts, outcomes, strict=True):
            cid = record['identity']['candidate_id']
            outcome_ref = register_json_artifact(store, outcome)
            rewarded = measured['admitted']['stable'] and outcome['speedup'] > 0
            record['result'] = dict(verdict=outcome['verdict'], first_failed_stage=first_failure(record['validation'], outcome['verdict']),
                speedup=outcome['speedup'] if rewarded else None, speedup_lcb=outcome['speedup_lcb'] if rewarded else None,
                max_regression=measured['observed']['max_case_regression'] if rewarded else None,
                machine_outcome_ref=outcome_ref, exploration_outcome_ref=outcome_ref, episode_ref=None,
                graph_policy_eligible=False, attempt_evidence_hash=sealed)
            limitations = ['Only measurements were continued; optimization source, prior knowledge and profiler evidence are inherited from ' + str(self.parent),
                'Historical profiler counters are not fresh serial profiler measurements.',
                'Graph coverage gap remains; this exploration has no graph-policy episode.',
                'The local baseline accuracy contract is inherited; no upstream checker equivalence is asserted.']
            if self.manifest.get('single_live_context'):
                limitations.append('Current timing starts and fully closes one process per role/sample; only the final per-role process outputs are checked for each case. Results describe this process lifecycle.')
            if self.manifest.get('capture_replay'):
                limitations.append('Current timing uses captured complete-operator replay; it describes this execution mode and does not establish the same gain for legacy host-submitted launches.')
            if not rewarded:
                limitations.extend(measured['admitted']['reasons'])
                limitations.append('Performance gain and its lower bound remain unknown.')
            else:
                limitations.extend(outcome['reasons'])
            record['lesson'] = dict(status=('supported' if outcome['eligible'] else
                'refuted' if outcome['verdict'] in ('stable_no_gain', 'heldout_regression', 'accuracy_failed', 'build_failed') else 'inconclusive'),
                effective_conditions=[f"Measured suite speedup {outcome['speedup']:.9g}, gate LCB {outcome['speedup_lcb']:.9g}."] if rewarded else [],
                ineffective_conditions=outcome['reasons'] if not outcome['eligible'] else [],
                counterexamples=[f"case {x['case_id']}: regression {x['regression']:.9g} exceeds 3%"
                    for x in measured['observed']['per_case'] if rewarded and x['regression'] is not None and x['regression'] > .03],
                limitations=limitations, next_step='Retain machine-qualified candidate source.' if outcome['eligible'] else
                    'Retain baseline; resolve the recorded failed gate before any new source attempt.', evidence_refs=sorted(set(refs + [outcome_ref])))
            record['null_reasons'] = {p: ('Performance not admitted: ' + record['validation']['timing']['reason'])
                if p in ('$.result.speedup', '$.result.speedup_lcb', '$.result.max_regression') else
                'Exploration continuation has no graph episode or this inherited optional field was not collected.' for p in _null_paths(record)}
            validate_optimization_trace(record, store)
            summary_ref = register_json_artifact(store, record)
            writer.append('attempt_finished', dict(verdict=outcome['verdict'], summary_ref=summary_ref,
                reason='Retrospective attestation: ' + '; '.join(outcome['reasons'])), candidate_id=cid, attempt_id=record['identity']['attempt_id'],
                event_id=cid + '-finished', timestamp=timestamp, artifact_refs=[attestation_ref])
            summaries.append(record)
            reports.append(dict(candidate_id=cid, parent_attempt_id=record['identity']['parent_attempt_id'],
                measurement_admitted=rewarded, calibration_accepted=calibration['accepted'],
                calibration_reason=calibration['reason'], result=record['result'], machine_outcome=outcome,
                operator_health_accepted=calibration['operator_health']['accepted'],
                operator_health_reason=calibration['operator_health']['reason'],
                per_case=measured['observed']['per_case'], problem=record['diagnosis'], intervention=record['intervention'],
                inherited_correctness=record['validation']['correctness']['reason'].startswith('Inherited'),
                validation=record['validation'], lesson=record['lesson']))
        write_optimization_traces(task / 'optimization_traces.jsonl', summaries, store)
        eligible = [x for x in outcomes if x['eligible'] and x['verdict'] == 'production_safe_gain']
        best = min(eligible, key=lambda x: (-x['utility'], x['candidate_id'])) if eligible else None
        chosen = next(x for x in frozen if x['candidate_id'] == best['candidate_id']) if best else frozen[0]
        digest = chosen['source_hashes']['candidate' if best else 'baseline']
        Finalizer.copy_snapshot(store, digest, task / 'best_source')
        selection = dict(candidate_id=best['candidate_id'] if best else None, source_hash=digest,
            source_directory=str(task / 'best_source'), verdict=best['verdict'] if best else 'baseline_retained',
            graph_policy_eligible=False, reason='Highest utility among machine eligible outcomes.' if best else 'No machine eligible candidate; baseline retained.')
        save(task / 'best_source_selection.json', selection)
        performance = [x for x in outcomes if x['speedup_lcb'] >= 1.03 and next(
            item for item in reports if item['candidate_id'] == x['candidate_id'])['measurement_admitted']
            and next(item for item in reports if item['candidate_id'] == x['candidate_id'])['result']['max_regression'] <= .03]
        measured_best = min(performance, key=lambda x: (-x['utility'], x['candidate_id'])) if performance else None
        measured_selection = dict(candidate_id=None, qualification='no_admitted_performance_gain',
            production_safe=False, source_directory=None, source_hash=None, machine_verdict=None)
        if measured_best:
            measured_source = next(x['source_hashes']['candidate'] for x in frozen if x['candidate_id'] == measured_best['candidate_id'])
            Finalizer.copy_snapshot(store, measured_source, task / 'measured_best_source')
            measured_selection.update(candidate_id=measured_best['candidate_id'], qualification='best_measured_on_this_local_workload',
                production_safe=measured_best['eligible'], source_directory=str(task / 'measured_best_source'),
                source_hash=measured_source, machine_verdict=measured_best['verdict'])
        save(task / 'measured_best_source_selection.json', measured_selection)
        report = dict(schema_version='1.0.0', run_id=self.run.name, parent_run=str(self.parent), operator=op,
            split=self.split(op), attempt_count=len(reports), attempts=reports, best_source=selection,
            attestation=attestation, attestation_ref=attestation_ref,
            exploration_verification=verify_exploration(request, outcomes, store=store), graph_policy_eligible=False,
            episode_count_added=0, calibration=calibration, measured_best_source=measured_selection)
        save(task / 'finalization_report.json', report)
        writer.append('task_finished', dict(status='completed', reason='Retrospective attestation: all frozen candidates retained in the serial continuation export.',
            attempt_count=len(reports), summary_ref=register_json_artifact(store, report)),
            event_id=op + '-finished', timestamp=timestamp, artifact_refs=[attestation_ref])
        return report

    def ready_operators(self):
        ready, pending = [], {}
        for op in self.operators:
            task = self.run / 'tasks' / op
            decision_path = task / 'calibration-decision.json'
            if not decision_path.exists():
                pending[op] = 'Per-operator calibration decision is not closed.'
                continue
            decision = read(decision_path)
            if type(decision.get('accepted')) is not bool or not decision.get('reason'):
                raise StoreError('invalid calibration decision')
            _, health_pending = self.operator_health(op)
            if health_pending:
                pending[op] = health_pending
                continue
            unfinished = []
            for entry in self.manifest['candidates'][op]:
                directory = task / 'measurements' / entry['identifier']
                execution_path = directory / 'execution.json'
                if not execution_path.exists():
                    if decision['accepted'] or (directory.exists() and any(directory.iterdir())):
                        unfinished.append(entry['candidate_id'])
                    continue
                execution = read(execution_path)
                if type(execution.get('exit_status')) is not int:
                    unfinished.append(entry['candidate_id'])
                elif execution['exit_status'] == 0 and not (directory / 'raw_measurements.json').exists():
                    unfinished.append(entry['candidate_id'])
            if unfinished:
                pending[op] = 'Candidate executions are not closed: ' + ', '.join(unfinished)
            else:
                ready.append(op)
        return ready, pending

    def is_sealed(self, op):
        task = self.run / 'tasks' / op
        if not (task / 'finalization_report.json').exists():
            return False
        events = rows(task / 'trace_events.jsonl')
        return bool(events and events[-1]['event_type'] == 'task_finished')

    def run_export(self, ready_only=False):
        ready, pending = self.ready_operators()
        if not ready_only and pending:
            raise StoreError('full export requires all operators to close: ' + ', '.join(pending))
        sealed = [op for op in self.operators if self.is_sealed(op)]
        if set(sealed) - set(ready):
            raise StoreError('a previously sealed operator lost its terminal input evidence')
        selected = ready if ready_only else self.operators
        reports, verification = [], {}
        for split in ('train', 'validation'):
            with ExportStore(self.run / split / 'episodes.sqlite') as store:
                closure = None
                try:
                    op_checks = {}
                    for op in selected:
                        if self.split(op) != split:
                            continue
                        task = self.run / 'tasks' / op
                        if self.is_sealed(op):
                            # No parent CAS traversal or rewrite of sealed events.
                            empty_episodes(task / 'episodes.jsonl')
                            report = read(task / 'finalization_report.json')
                        else:
                            if closure is None:
                                closure = ParentClosure(self.parent, split, store)
                            report = self.finalize_operator(op, store, closure)
                            empty_episodes(task / 'episodes.jsonl')
                        reports.append(report)
                        op_checks[op] = self.verify_operator(op, store)
                        self.write_report({'operators': [report]}, output=task / 'serial_report.md')
                    verification[split] = self.export_split(split, store, selected)
                    verification[split]['operators'] = op_checks
                finally:
                    if closure is not None:
                        closure.close()
        incoming = [x for split in ('train', 'validation') for x in rows(self.run / split / 'optimization_traces.jsonl')]
        expected_root = {x['identity']['candidate_id']: x for x in incoming}
        previous_root = rows(self.run / 'optimization_traces.jsonl')
        if any(x['identity']['candidate_id'] not in expected_root or x != expected_root[x['identity']['candidate_id']] for x in previous_root):
            raise StoreError('root summaries contain an unclosed, changed or foreign candidate')
        write_optimization_traces(self.run / 'optimization_traces.jsonl', incoming)
        append_trace_streams([self.run / split / 'trace_events.jsonl' for split in ('train', 'validation')],
            self.run / 'trace_events.jsonl')
        empty_episodes(self.run / 'episodes.jsonl')
        merged = rows(self.run / 'optimization_traces.jsonl')
        summary = dict(schema_version='1.0.0', run_id=self.run.name, parent_run=str(self.parent),
            attempt_count=len(merged), new_source_attempt_count=0, measurement_continuation_count=len(merged),
            operators=reports, verification=verification, graph_policy_eligible=False, episode_count=0)
        checkpoint = dict(valid=True, run_id=self.run.name, attempt_count=len(merged), checks=verification,
            graph_policy_eligible=False, episode_count=0, completed_operators=list(selected), pending_operators=list(pending),
            verification_scope='Current split trace chains, strict summaries, full frozen batches for closed operators, current inputs and byte-verified referenced CAS closure.')
        if ready_only:
            summary.update(kind='serial_measurement_progress', status='ready_for_final_export' if not pending else 'in_progress',
                frozen_candidate_count=len(self.parent_records), completed_operators=list(selected),
                pending_operators=list(pending), pending_reasons=pending, final_delivery=False)
            replace_progress(self.run / 'serial_progress.json', summary)
            replace_progress(self.run / 'serial_checkpoint.json', checkpoint)
        else:
            save(self.run / 'serial_summary.json', summary)
            self.write_report(summary)
            save(self.run / 'serial_verification.json', checkpoint)
        return summary

    def export_split(self, split, store, operators=None):
        selected = self.operators if operators is None else operators
        paths = [self.run / 'tasks' / op for op in selected if self.split(op) == split]
        records = [x for p in paths for x in rows(p / 'optimization_traces.jsonl')]
        expected = {x['candidate_id'] for op in selected if self.split(op) == split
                    for x in self.manifest['candidates'][op]}
        if len(records) != len(expected) or {x['identity']['candidate_id'] for x in records} != expected:
            raise StoreError('split export differs from the complete closed-operator roster')
        existing = rows(self.run / split / 'optimization_traces.jsonl')
        if any(x['identity']['candidate_id'] not in expected for x in existing):
            raise StoreError('split export contains an unclosed or foreign operator')
        write_optimization_traces(self.run / split / 'optimization_traces.jsonl', records, store)
        events = append_trace_streams([p / 'trace_events.jsonl' for p in paths], self.run / split / 'trace_events.jsonl', store)
        episodes = export_episodes(store, self.run / split / 'episodes.jsonl')
        if episodes['episode_count']:
            raise StoreError('serial exploration must not create policy episodes')
        return dict(events=events, summaries=verify_optimization_traces(self.run / split / 'optimization_traces.jsonl', store),
                    episodes=episodes, store_chain_head=store.verify_integrity())

    def verify_operator(self, op, store, split_records=None):
        task = self.run / 'tasks' / op
        records = rows(task / 'optimization_traces.jsonl')
        expected = {x['candidate_id'] for x in self.manifest['candidates'][op]}
        if len(records) != len(expected) or {x['identity']['candidate_id'] for x in records} != expected:
            raise StoreError('operator export omitted or duplicated a frozen candidate')
        for record in records:
            identity = record['identity']
            original = self.parent_records[identity['candidate_id']]['identity']
            if (identity['run_id'] != self.run.name or identity['operator'] != op or identity['task_id'] != op
                    or identity['split'] != self.split(op) or identity['attempt_id'] != original['attempt_id']
                    or identity['parent_attempt_id'] != original['attempt_id']):
                raise StoreError('continuation lineage is incorrect')
        events = verify_trace(task / 'trace_events.jsonl', store)
        event_rows = rows(task / 'trace_events.jsonl')
        attestation, attestation_ref = self.attestation(op, store)
        for record in records:
            original = self.parent_records[record['identity']['candidate_id']]
            if (record['provenance']['producer_hash'] != attestation['producer_ref']
                    or record['provenance']['dependencies'].get('parent_producer_hash') != original['provenance']['producer_hash']):
                raise StoreError('summary producer differs from the current attestation or inherited parent producer')
        if any(event['timestamp'] != attestation['attested_at'] or attestation_ref not in event['artifact_refs']
                for event in event_rows):
            raise StoreError('operator event timestamp or artifact differs from its retrospective attestation')
        for event in event_rows:
            execution = event['payload'].get('execution') if event['event_type'] == 'stage_completed' else None
            if execution is not None and (execution_interval(execution) is None or execution_interval(
                    dict(started_at=execution['finished_at'], finished_at=attestation['attested_at'])) is None):
                raise StoreError('stage execution finishes after its retrospective attestation')
        if any(x['run_id'] != self.run.name or x['task_id'] != op for x in event_rows):
            raise StoreError('operator event stream contains a foreign task')
        finished = [x for x in event_rows if x['event_type'] == 'task_finished']
        report = read(task / 'finalization_report.json')
        if report.get('attestation') != attestation or report.get('attestation_ref') != attestation_ref:
            raise StoreError('retrospective attestation differs from the sealed operator report')
        if (len(finished) != 1 or finished[0] != event_rows[-1]
                or finished[0]['payload']['summary_ref'] != content_hash(report)):
            raise StoreError('operator finalization has no matching terminal event')
        if not (task / 'episodes.jsonl').exists() or (task / 'episodes.jsonl').read_bytes():
            raise StoreError('operator exploration episode export must be empty')
        summaries = verify_optimization_traces(task / 'optimization_traces.jsonl', store)
        if split_records is None:
            split_records = records
        request = read(task / 'exploration_request.json')
        frozen_manifest = read(store.verify_artifact(request['frozen_manifest_hash']))
        if frozen_manifest['frozen_at'] != attestation['source_frozen_at']:
            raise StoreError('source freezing time differs from the original source roster')
        if any(item['artifacts'].get('measurement_attestation') != attestation_ref for item in request['evidence']):
            raise StoreError('retrospective attestation differs from sealed gate evidence')
        expected_order = [x['candidate_id'] for x in self.manifest['candidates'][op]]
        if any([x['candidate_id'] for x in request[key]] != expected_order for key in ('candidates', 'evidence')):
            raise StoreError('sealed exploration batch differs from the complete frozen roster')
        exploration = verify_exploration(request, read(task / 'exploration_outcomes.json'), store=store)
        calibration, calibration_refs = self.calibration(op, store)
        sealed_evidence = {x['candidate_id']: x for x in request['evidence']}
        method_ref = self.method_history(store)
        if any(x['artifacts'].get('measurement_method_history') != method_ref for x in request['evidence']):
            raise StoreError('method exploration history differs from sealed evidence')
        task_report = read(task / 'finalization_report.json')
        if task_report['calibration'] != calibration:
            raise StoreError('current operator health or calibration differs from sealed evidence')
        report_attempts = {x['candidate_id']: x for x in task_report['attempts']}
        task_records = {x['identity']['candidate_id']: x for x in split_records if x['identity']['operator'] == op}
        if len(report_attempts) != len(task_report['attempts']) or set(report_attempts) != set(task_records):
            raise StoreError('finalization report differs from frozen candidate roster')
        for cid, item in report_attempts.items():
            if any(item[k] != task_records[cid][k] for k in ('result', 'validation', 'lesson', 'intervention')):
                raise StoreError('finalization report differs from strict summaries')
        if rows(task / 'optimization_traces.jsonl') != [x for x in split_records if x['identity']['operator'] == op]:
            raise StoreError('task summaries differ from split summaries')
        # Recheck current raw/report/binary bindings as well as CAS replay.
        for entry in self.manifest['candidates'][op]:
            current = self.measurement(op, entry, store, calibration)
            sealed = sealed_evidence[entry['candidate_id']]
            if sealed['artifacts']['calibration_decision'] != calibration_refs[0] or any(
                sealed['artifacts'].get(k) != v for k, v in current['artifacts'].items()) or any(
                sealed[k] != v for k, v in current['admitted']['gate_projection'].items()):
                raise StoreError('current measurement or calibration differs from sealed gate evidence')
            item = report_attempts[entry['candidate_id']]
            if item['per_case'] != current['observed']['per_case'] or item['calibration_accepted'] != calibration['accepted']:
                raise StoreError('report case data or calibration differs from raw evidence')
        outcomes = read(task / 'exploration_outcomes.json')
        production = [x for x in outcomes if x['eligible'] and x['verdict'] == 'production_safe_gain']
        performance = [x for x in outcomes if x['speedup_lcb'] >= 1.03
            and report_attempts[x['candidate_id']]['measurement_admitted']
            and report_attempts[x['candidate_id']]['result']['max_regression'] <= .03]
        for prefix, choices in (('best_source', production), ('measured_best_source', performance)):
            winner = min(choices, key=lambda x: (-x['utility'], x['candidate_id'])) if choices else None
            selection = read(task / (prefix + '_selection.json'))
            if selection['candidate_id'] != (winner['candidate_id'] if winner else None):
                raise StoreError('source selection differs from machine-ranked eligible set')
            if prefix == 'measured_best_source' and not winner:
                continue
            cid = winner['candidate_id'] if winner else self.manifest['candidates'][op][0]['candidate_id']
            source = self.parent_records[cid]['provenance'][('candidate' if winner else 'baseline') + '_source_hash']
            if selection['source_hash'] != source or not (task / prefix).is_dir():
                raise StoreError('selected source identity or directory is missing')
            Finalizer.copy_snapshot(store, source, task / prefix)
        return dict(events=events, summaries=summaries, exploration=exploration, episode_count=0)

    def verify(self, ready_only=False):
        ready, pending = self.ready_operators()
        selected = [op for op in self.operators if self.is_sealed(op)] if ready_only else self.operators
        if not ready_only and pending:
            raise StoreError('full verification requires all operators to close: ' + ', '.join(pending))
        if set(selected) - set(ready):
            raise StoreError('a sealed operator lost its terminal input evidence')
        checks = {}
        for split in ('train', 'validation'):
            with ExportStore(self.run / split / 'episodes.sqlite') as store:
                split_records = rows(self.run / split / 'optimization_traces.jsonl')
                expected = {x['candidate_id'] for op in selected if self.split(op) == split for x in self.manifest['candidates'][op]}
                if len(split_records) != len(expected) or {x['identity']['candidate_id'] for x in split_records} != expected:
                    raise StoreError('export omitted or duplicated a frozen candidate')
                for x in split_records:
                    if x['identity']['run_id'] != self.run.name or x['identity']['parent_attempt_id'] != self.parent_records[x['identity']['candidate_id']]['identity']['attempt_id']:
                        raise StoreError('continuation lineage is incorrect')
                checks[split] = dict(events=verify_trace(self.run / split / 'trace_events.jsonl', store),
                    summaries=verify_optimization_traces(self.run / split / 'optimization_traces.jsonl', store), operators={})
                for op in selected:
                    if self.split(op) != split:
                        continue
                    checks[split]['operators'][op] = self.verify_operator(op, store, split_records)
                count = store.connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
                if count or (self.run / split / 'episodes.jsonl').read_bytes():
                    raise StoreError('exploration exported a graph-policy episode')
                checks[split]['episode_count'] = count
                checks[split]['store_chain_head'] = store.verify_integrity()
        merged = [x for split in ('train', 'validation') for x in rows(self.run / split / 'optimization_traces.jsonl')]
        exported = rows(self.run / 'optimization_traces.jsonl')
        by_id = {x['identity']['candidate_id']: x for x in merged}
        if len(exported) != len(by_id) or {x['identity']['candidate_id']: x for x in exported} != by_id or (self.run / 'episodes.jsonl').read_bytes():
            raise StoreError('merged exports differ from verified split exports')
        verify_trace(self.run / 'trace_events.jsonl')
        split_events = {x['event_id']: x for split in ('train', 'validation') for x in rows(self.run / split / 'trace_events.jsonl')}
        root_events = rows(self.run / 'trace_events.jsonl')
        if len(root_events) != len(split_events) or {x['event_id']: x for x in root_events} != split_events:
            raise StoreError('merged events differ from verified split streams')
        return dict(valid=True, run_id=self.run.name, attempt_count=len(merged), checks=checks,
                    graph_policy_eligible=False, episode_count=0, completed_operators=selected,
                    pending_operators=[op for op in self.operators if op not in selected])

    def write_report(self, summary, output=None):
        lines = ['# Serial measurement continuation', '', f"Parent run: `{self.parent}`", '',
            'The original candidate and attempt IDs are retained. This run adds measurements and no source attempts.', '',
            '| Operator | Candidate | Admitted | Speedup | Gate LCB | Max regression | Machine verdict |',
            '|---|---|---|---|---|---|---|']
        for op in summary['operators']:
            for item in op['attempts']:
                result = item['result']
                values = [f'{result[k]:.6g}' if result[k] is not None else 'unknown'
                          for k in ('speedup', 'speedup_lcb', 'max_regression')]
                lines.append('| ' + ' | '.join([op['operator'], item['candidate_id'], str(item['measurement_admitted']),
                    *values, result['verdict']]) + ' |')
        for op in summary['operators']:
            lines += ['', '## ' + op['operator'], '', 'Calibration: ' + op['calibration']['reason'],
                '', 'Operator health: ' + op['calibration']['operator_health']['reason'],
                '', 'Source selection: ' + op['best_source']['verdict'], '',
                'Local workload performance selection: ' + str(op['measured_best_source']['candidate_id']) +
                '; machine verdict: ' + str(op['measured_best_source']['machine_verdict']) + '. Attribution and production qualification remain those of the machine gate.', '']
            for item in op['attempts']:
                lines += ['### ' + item['candidate_id'], '', 'Problem: ' + '; '.join(item['problem']['symptoms']),
                    '', 'Intervention: ' + item['intervention']['intent'], '', 'Rationale: ' + item['intervention']['rationale'],
                    '', 'Machine result: ' + item['result']['verdict'] + '. ' + '; '.join(item['machine_outcome']['reasons']),
                    '', 'Limits: ' + ' '.join(item['lesson']['limitations']), '',
                    '| Case | Pairs | Baseline ns | Candidate ns | Baseline CV | Candidate CV | Observed ratio |',
                    '|---|---|---|---|---|---|---|']
                for case in item['per_case']:
                    vals = [f'{case[k]:.6g}' if case[k] is not None else 'unknown' for k in
                        ('baseline_median_ns', 'candidate_median_ns', 'baseline_cv', 'candidate_cv', 'speedup')]
                    lines.append('| ' + ' | '.join([str(case['case_id']), str(case['pair_count']), *vals]) + ' |')
                lines += ['', 'Per-case ratios above are descriptive observations; only admitted suite results provide qualified gain evidence.', '']
        path = Path(output) if output is not None else self.run / 'serial_report.md'
        text = '\n'.join(lines) + '\n'
        if path.exists() and path.read_text() != text:
            raise StoreError('finalized serial report changed')
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--ready-only', action='store_true', help='Export or verify closed operators; preserve all other frozen candidates as pending.')
    args = parser.parse_args()
    finalizer = SerialFinalizer(args.run)
    result = finalizer.verify(ready_only=args.ready_only) if args.verify_only else finalizer.run_export(ready_only=args.ready_only)
    print(json.dumps(dict(run_id=args.run.name, valid=True, attempt_count=result['attempt_count'],
                         episode_count=0, report=str(args.run / ('serial_progress.json' if args.ready_only else 'serial_report.md'))), sort_keys=True))


if __name__ == '__main__':
    main()
