#!/usr/bin/env python3
"""Read-only replay of two fixed offline profile-storage cost studies.

The result establishes provenance and storage cost only. It cannot admit a
kernel measurement or a publication. The old /tmp source may be reclaimed:
its bytes are read from the exact, previously double-hashed persistent copy.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / 'skill-libs/graph-base/0.5.1'
ARCHIVE_INDEX = REPO.parent / 'validation-graph-base-0.5.1-20261014/task-window-v2-10ms-design/pre-change/index.json'
ARCHIVE_INDEX_SHA256 = 'sha256:acefc7f3e51336db89cb4f94f39e2e7b860a05cf9ec0f3a6bd2bacba697959df'
ARCHIVED_PACKAGE = ARCHIVE_INDEX.parent / 'payload/graph-base/0.5.1'
PRODUCER_ROOTS = (PACKAGE / 'runtime/src', PACKAGE / 'skills/ascendc-aprof-profiling/scripts',
                  PACKAGE / 'skills/ascendc-aprof-profiling/assets')


def need(condition, message):
    if not condition:
        raise ValueError(message)


class Evidence:
    """One read-only hash cache shared by both studies."""

    def __init__(self):
        self.hashes = {}

    def hash(self, path):
        path = Path(path)
        need(path.is_file() and not path.is_symlink(), f"missing/unsafe file: {path}")
        before = path.stat()
        key = (str(path), before.st_dev, before.st_ino, before.st_size,
               before.st_mtime_ns, before.st_ctime_ns)
        if key not in self.hashes:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            after = path.stat()
            need((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                 == key[1:], f"file changed during replay: {path}")
            self.hashes[key] = 'sha256:' + digest.hexdigest()
        return self.hashes[key]

    def bind(self, reference, expected_path=None):
        need(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'invalid evidence reference')
        path = Path(reference['path'])
        need(path.is_absolute() and (expected_path is None or path == Path(expected_path)),
             'evidence path differs from frozen path')
        actual = resolve_fixed_cost_source(reference, self)
        need(self.hash(actual) == reference['sha256'], f"evidence bytes changed: {path}")
        return actual

    def read(self, reference, expected_path=None):
        return json.loads(self.bind(reference, expected_path).read_text())

    def tree(self, root, inventory):
        root = Path(root)
        need(root.is_dir() and not root.is_symlink(), f"profile tree missing/unsafe: {root}")
        found = {}
        for path in root.rglob('*'):
            need(not path.is_symlink(), f"profile symlink: {path}")
            if path.is_dir():
                continue
            need(path.is_file(), f"profile nonregular entry: {path}")
            found[path.relative_to(root).as_posix()] = path
        need(set(found) == set(inventory), 'profile file roster added or removed')
        for name, row in inventory.items():
            need(Path(name).as_posix() == name and not Path(name).is_absolute()
                 and '..' not in Path(name).parts and set(row) == {'bytes', 'sha256'}
                 and isinstance(row['bytes'], int) and row['bytes'] >= 0,
                 'invalid profile inventory row')
            need(found[name].stat().st_size == row['bytes']
                 and self.hash(found[name]) == row['sha256'], f"profile bytes changed: {name}")
        return found


def resolve_fixed_cost_source(reference, evidence):
    """Resolve only frozen package producer bytes from the fixed 213-file archive."""
    path = Path(reference['path'])
    need(path.is_absolute(), 'cost evidence source path is not absolute')
    if not (path.suffix in {'.py', '.h', '.hpp'}
            and any(path.is_relative_to(root) for root in PRODUCER_ROOTS)):
        return path
    need(evidence.hash(ARCHIVE_INDEX) == ARCHIVE_INDEX_SHA256,
         'fixed storage cost source archive index changed')
    index = json.loads(ARCHIVE_INDEX.read_text())
    need(index.get('schema_version') == 1 and index.get('not_a_release') is True
         and index.get('original_root') == str(PACKAGE)
         and index.get('archived_root') == str(ARCHIVED_PACKAGE),
         'fixed storage cost source archive identity differs')
    item = index['files'].get(str(path))
    expected = ARCHIVED_PACKAGE / path.relative_to(PACKAGE)
    need(isinstance(item, dict) and item.get('path') == str(expected)
         and item.get('sha256') == reference['sha256']
         and type(item.get('bytes')) is int and item['bytes'] >= 0,
         'cost producer absent or hash differs in fixed source archive')
    need(expected.stat().st_size == item['bytes'], 'archived cost producer size differs')
    return expected


def _reference(evidence, path):
    return {'path': str(path), 'sha256': evidence.hash(path)}


def _seconds(value):
    need(isinstance(value, (int, float)) and not isinstance(value, bool)
         and math.isfinite(value) and value >= 0, 'invalid cost seconds')
    return float(value)


def _close_seconds(saved, start, finish):
    need(abs(_seconds(saved) - (finish - start)) < .25, 'reported wall cost differs from timestamps')


def _iso(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def _execution(evidence, reference, job, *, budget):
    report = evidence.read(reference)
    need(report['job'] == job and report['status'] == 'passed' and report['exit_code'] == 0
         and report['physical_device'] is None and 0 < report['duration_seconds'] <= budget,
         'offline outer job changed or used a device')
    start, finish = _iso(report['started_at']), _iso(report['finished_at'])
    need(start < finish and abs(report['duration_seconds'] - (finish - start)) < 2,
         'outer job duration differs from timestamps')
    for stream in ('stdout', 'stderr'):
        evidence.bind(report[stream], Path(job['output_dir']) / f'{stream}.log')
    return start, finish, report


def _source(evidence, cas_plan, copy_plan):
    prior_ref = cas_plan['source_inventory_ref']
    need(prior_ref == copy_plan['prior_inventory_ref']
         and cas_plan['study_result_ref'] == copy_plan['prior_result_ref']
         and cas_plan['source_root'] == copy_plan['source_dir']
         and cas_plan['persistent_verified_root'] == copy_plan['persistent_counterpart'],
         'the two studies use different source identities')
    prior = evidence.read(prior_ref)
    prior_result = evidence.read(cas_plan['study_result_ref'])
    prior_plan = evidence.read(copy_plan['prior_plan_ref'])
    need(prior_result['complete'] is True and prior_result['slots'][1]['status'] == 'passed'
         and prior_result['slots'][1]['condition'] == 'summary'
         and prior['source_root'] == cas_plan['source_root']
         and prior['persistent_root'] == cas_plan['persistent_verified_root']
         and prior_plan['purpose'] == 'offline_summary_export_cost_study',
         'previous summary source proof differs')
    files = prior['files']
    digests = {name: item['sha256'] for name, item in files.items()}
    transfer = prior['transfer']
    need(all(transfer[key] == digests for key in
             ('source_inventory', 'persisted_inventory', 'source_after_inventory'))
         and transfer['source_dir'] == cas_plan['source_root']
         and transfer['destination_dir'] == cas_plan['persistent_verified_root']
         and prior_result['slots'][1]['persistence']['transfer'] == transfer,
         'previous source was not double-hash verified')
    need(files == evidence.read(copy_plan['source_inventory_ref'])
         and len(files) == cas_plan['expected_files'] == copy_plan['file_count']
         and sum(item['bytes'] for item in files.values())
         == cas_plan['expected_bytes'] == copy_plan['bytes_per_copy'],
         'source manifest or byte count differs')
    evidence.tree(prior['persistent_root'], files)
    return files


def _cas_index(evidence, database, source_root, inventory, slot):
    sqlite_ref = slot['sqlite_ref']
    evidence.bind(sqlite_ref, database)
    expected_hashes = {row['sha256'] for row in inventory.values()}
    expected_locations = set()
    expected_post = {}
    objects = database.parent / (database.name + '.objects') / 'sha256'
    for name, row in inventory.items():
        digest = row['sha256']
        destination = objects / digest[7:9] / digest[9:]
        need(destination.stat().st_size == row['bytes'] and evidence.hash(destination) == digest,
             f"CAS object differs: {name}")
        expected_post[name] = {'sha256': digest, 'bytes': row['bytes'], 'object': str(destination)}
        expected_locations.add((digest, destination.as_uri(), row['bytes']))
        expected_locations.add((digest, (Path(source_root) / name).as_uri(), row['bytes']))
    post = slot['postverify']
    need(post == {'files': expected_post, 'unique_objects': len(expected_hashes),
                  'sqlite_locations_checked': True}, 'saved CAS postverification differs')
    uri = 'file:' + quote(str(database)) + '?mode=ro&immutable=1'
    with sqlite3.connect(uri, uri=True) as conn:
        artifacts = {item[0] for item in conn.execute('SELECT content_hash FROM artifacts')}
        locations = set(conn.execute('SELECT content_hash,uri,size_bytes FROM artifact_locations'))
    need(artifacts == expected_hashes and locations == expected_locations,
         'SQLite artifact or source/CAS location rows differ')


def _cas(evidence, refs, files):
    root = Path(refs['plan']['path']).parent
    for key, name in {'plan': 'plan.json', 'script': 'compare_cas_persistence.py',
                      'anchor': 'root-anchor.json', 'job': 'job.json',
                      'execution': 'outer-execution/execution.json', 'result': 'result.json',
                      'source_inventory': root.parent / 'measurement-task-summary-export-cost-20261014-v1/slot-1-summary-inventory.json'}.items():
        evidence.bind(refs[key], root / name)
    plan, anchor, job, result = (evidence.read(refs[key]) for key in ('plan', 'anchor', 'job', 'result'))
    need(plan['schema_version'] == 1 and plan['purpose'] == 'offline_cas_persistence_parallel_cost'
         and plan['eligible_for_publication'] is False and plan['max_attempts_per_slot'] == 1
         and plan['stop_on_first_failure'] is True and plan['output_root'] == str(root)
         and plan['source_inventory_ref'] == refs['source_inventory']
         and plan['script_ref'] == refs['script']
         and anchor == {'schema_version': 1, 'purpose': plan['purpose'],
                        'plan_ref': refs['plan'], 'script_ref': refs['script']}
         and result['plan_ref'] == refs['plan'] and result['anchor_ref'] == refs['anchor']
         and result['script_ref'] == refs['script'] and result['purpose'] == plan['purpose']
         and result['complete'] is True and result['eligible_for_publication'] is False
         and result['hardware_executed'] is False,
         'CAS study preregistration/result differs')
    need(refs['store_source'] == plan['store_source_ref']
         and refs['prior_result'] == plan['study_result_ref'],
         'CAS producer/previous study references differ')
    evidence.bind(refs['store_source'])
    evidence.bind(refs['prior_result'])
    start, finish, report = _execution(evidence, refs['execution'], job, budget=900)
    need(job['argv'] == [job['argv'][0], str(refs['script']['path']), '--plan', str(refs['plan']['path']),
                         '--anchor', str(refs['anchor']['path']), '--execute']
         and job['cwd'] == str(root) and job['timeout_seconds'] == 900
         and result['stdout_ref'] == _reference(evidence, root / 'execution/stdout.log')
         and result['stderr_ref'] == _reference(evidence, root / 'execution/stderr.log')
         and start <= result['started_at'] <= result['finished_at'] <= finish,
         'CAS job or outer chronology differs')
    modes = ('sequential', 'parallel4', 'parallel4', 'sequential')
    need([row['mode'] for row in plan['slots']] == list(modes)
         and len(result['slots']) == 4, 'CAS fixed four-slot roster differs')
    previous = result['started_at']
    stdout = []
    for index, mode in enumerate(modes):
        spec, slot = plan['slots'][index], result['slots'][index]
        name = f'slot-{index}-{mode}'
        database = root / 'execution' / name / 'evidence.sqlite'
        need(spec == {'mode': mode, 'name': name, 'store_path': str(database)}
             and slot == evidence.read(refs['slots'][index], database.parent / 'result.json')
             and slot['name'] == name and slot['mode'] == mode and slot['status'] == 'passed'
             and slot['schema_version'] == 1 and slot['file_count'] == len(files)
             and slot['bytes'] == sum(item['bytes'] for item in files.values())
             and previous <= slot['started_at'] < slot['finished_at'] <= result['finished_at'],
             'CAS slot identity/chronology differs')
        previous = slot['finished_at']
        _close_seconds(slot['wall_seconds'], slot['started_at'], slot['finished_at'])
        stages = ['pre_read_hash_seconds', 'store_open_seconds', 'postverify_seconds']
        if mode == 'sequential':
            stages += ['register_artifacts_seconds']
            need(slot['parallel_persist_seconds'] is None and slot['parallel_index_seconds'] is None,
                 'sequential CAS cost format differs')
        else:
            stages += ['parallel_persist_seconds', 'parallel_index_seconds']
            need(slot['register_artifacts_seconds'] is None, 'parallel CAS cost format differs')
        need(sum(_seconds(slot[key]) for key in stages) <= slot['wall_seconds'] + .25,
             'CAS phases exceed recorded wall cost')
        need(slot['returned_refs'] == [files[name]['sha256'] for name in sorted(files)],
             'CAS returned artifact references differ')
        _cas_index(evidence, database, plan['source_root'], files, slot)
        stdout.append({'name': name, 'status': 'passed', 'wall_seconds': slot['wall_seconds']})
    actual_stdout = [json.loads(line) for line in evidence.bind(result['stdout_ref']).read_text().splitlines()]
    outer_stdout = [json.loads(line) for line in evidence.bind(report['stdout']).read_text().splitlines()]
    need(actual_stdout == stdout and outer_stdout == [{'complete': True, 'result': str(root / 'result.json')}]
         and evidence.bind(result['stderr_ref']).stat().st_size == 0
         and evidence.bind(report['stderr']).stat().st_size == 0,
         'CAS command stdout/stderr differs')
    return {'slots': len(modes), 'source_files': len(files), 'outer_seconds': report['duration_seconds'],
            'register_seconds': [row['register_artifacts_seconds'] for row in result['slots']],
            'parallel_seconds': [[row['parallel_persist_seconds'], row['parallel_index_seconds']]
                                 for row in result['slots']]}


def _copy(evidence, refs, files):
    root = Path(refs['plan']['path']).parent
    names = {'plan': root / 'plan.json', 'script': root / 'profile_copy_study.py',
             'anchor': Path(refs['anchor']['path']), 'job': root / 'campaign-job.json',
             'execution': root / 'execution/execution.json', 'result': root / 'result.json',
             'source_inventory': root / 'source-inventory.json', 'started': root / 'started.json'}
    for key, path in names.items():
        evidence.bind(refs[key], path)
    plan, anchor, job, result, started = (evidence.read(refs[key])
                                           for key in ('plan', 'anchor', 'job', 'result', 'started'))
    need(plan['schema_version'] == 1 and plan['purpose'] == 'offline_complete_profile_copy_cost_study'
         and plan['eligible_for_publication'] is False and plan['kernel_measurement'] is False
         and plan['conditions'] == ['serial', 'parallel4', 'parallel4', 'serial']
         and plan['max_attempts_per_slot'] == 1 and plan['stop_on_first_failure'] is True
         and plan['file_count'] == len(files) and plan['bytes_per_copy'] == sum(row['bytes'] for row in files.values())
         and plan['source_inventory_ref'] == refs['source_inventory']
         and plan['job_ref'] == refs['job'] and plan['prior_inventory_ref'] == refs['prior_inventory']
         and plan['prior_result_ref'] == refs['prior_result'] and plan['prior_plan_ref'] == refs['prior_plan']
         and anchor['purpose'] == 'root_anchored_' + plan['purpose']
         and anchor['plan_ref'] == refs['plan'] and anchor['eligible_for_publication'] is False
         and started['anchor_ref'] == refs['anchor'] and started['plan_ref'] == refs['plan']
         and result['purpose'] == plan['purpose'] and result['plan_ref'] == refs['plan']
         and result['complete'] is True and result['eligible_for_publication'] is False
         and result['kernel_measurement'] is False,
         'copy study preregistration/result differs')
    need(plan['dependencies'] == refs['dependencies']
         and plan['mountinfo_ref'] == refs['mountinfo'],
         'copy dependencies or mount evidence differ')
    for dependency in plan['dependencies']:
        evidence.bind(dependency)
    evidence.bind(plan['mountinfo_ref'])
    need(any(dependency == refs['script'] for dependency in plan['dependencies']),
         'copy script absent from frozen dependencies')
    start, finish, report = _execution(evidence, refs['execution'], job, budget=600)
    need(job['argv'] == [job['argv'][0], str(refs['script']['path']), 'run', '--anchor', str(refs['anchor']['path'])]
         and job['cwd'] == str(root) and job['timeout_seconds'] == 600
         and anchor_time(anchor) < start <= started['started_at'] <= finish
         and len(result['slots']) == len(plan['slots']) == 4,
         'copy job/anchor chronology differs')
    digests = {name: row['sha256'] for name, row in files.items()}
    previous = started['started_at']
    stdout = []
    for index, mode in enumerate(('serial', 'parallel4', 'parallel4', 'serial')):
        ident = f'{index}-{mode}'
        dest = root / f'slot-{ident}' / 'profile'
        spec, slot = plan['slots'][index], result['slots'][index]
        begun = evidence.read(refs['slot_starts'][index], root / f'{ident}-started.json')
        need(spec == {'id': ident, 'condition': mode, 'destination': str(dest)}
             and slot == evidence.read(refs['slots'][index], root / f'{ident}-result.json')
             and begun == {key: slot[key] for key in ('id', 'condition', 'destination', 'started_at')}
             and slot['status'] == 'passed' and slot['file_count'] == len(files)
             and slot['bytes'] == plan['bytes_per_copy']
             and previous <= slot['started_at'] <= slot['transfer']['started_at']
             <= slot['transfer']['finished_at'] <= slot['finished_at'] <= finish,
             'copy slot identity/chronology differs')
        previous = slot['finished_at']
        _close_seconds(slot['slot_seconds'], slot['started_at'], slot['finished_at'])
        need(0 < _seconds(slot['copy_seconds']) <= slot['slot_seconds'] + .05
             and slot['slot_seconds'] <= plan['slot_timeout_seconds']
             and slot['transfer']['source_dir'] == plan['source_dir']
             and slot['transfer']['destination_dir'] == str(dest)
             and all(slot['transfer'][key] == digests for key in
                     ('source_inventory', 'persisted_inventory', 'source_after_inventory')),
             'copy phase cost or complete three-way inventory differs')
        evidence.tree(dest, files)
        stdout.append({'id': ident, 'status': 'passed', 'slot_seconds': slot['slot_seconds']})
    actual_stdout = [json.loads(line) for line in evidence.bind(report['stdout']).read_text().splitlines()]
    need(actual_stdout == stdout and evidence.bind(report['stderr']).stat().st_size == 0,
         'copy command stdout/stderr differs')
    return {'slots': 4, 'source_files': len(files), 'outer_seconds': report['duration_seconds'],
            'copy_seconds': [row['copy_seconds'] for row in result['slots']]}


def anchor_time(anchor):
    return _iso(anchor['recorded_at_utc'])


def replay_profile_storage_cost(reference):
    """Replay the frozen experiments; never return publication admission."""
    evidence = Evidence()
    manifest = evidence.read(reference)
    need(manifest.get('schema_version') == 1
         and manifest.get('purpose') == 'offline_profile_storage_cost_evidence'
         and manifest.get('eligible_for_publication') is False
         and manifest.get('authority') == 'offline_storage_cost_only'
         and set(manifest) == {'schema_version', 'purpose', 'eligible_for_publication', 'authority',
                               'cas', 'copy'}, 'invalid storage cost evidence manifest')
    cas_refs, copy_refs = manifest['cas'], manifest['copy']
    cas_plan, copy_plan = evidence.read(cas_refs['plan']), evidence.read(copy_refs['plan'])
    need(cas_refs['source_inventory'] == cas_plan['source_inventory_ref']
         and copy_refs['source_inventory'] == copy_plan['source_inventory_ref']
         and copy_refs['prior_inventory'] == copy_plan['prior_inventory_ref']
         and copy_refs['prior_result'] == copy_plan['prior_result_ref']
         and copy_refs['prior_plan'] == copy_plan['prior_plan_ref'],
         'manifest source bindings differ from plans')
    files = _source(evidence, cas_plan, copy_plan)
    return {'valid': True, 'authority': 'offline_storage_cost_only',
            'eligible_for_publication': False, 'accepted': False,
            'source_files': len(files), 'source_bytes': sum(row['bytes'] for row in files.values()),
            'cas': _cas(evidence, cas_refs, files), 'copy': _copy(evidence, copy_refs, files)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    path = args.manifest
    ref = {'path': str(path.resolve(strict=True)), 'sha256': Evidence().hash(path)}
    print(json.dumps(replay_profile_storage_cost(ref), sort_keys=True))
