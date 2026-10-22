"""Independent post-task collection and verified handoff to scratch cleanup."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time
import tomllib

from . import __version__
from .jsonio import file_hash
from .errors import ContractError
from .local_evidence import LocalEvidence
from .measurement_admission import _release_root
from .store import EpisodeStore, _ReadOnlyArtifacts, default_object_directory
from .task_budget import replay_task_terminal

PROTOCOL = 'local_evidence_archive_v1'
PACKAGE = _release_root()
def identity_files():
    excluded = {'.runtime-env', '__pycache__', '.pytest_cache', 'tests', '.git', '.cursor',
                'build', 'dist', '.eggs', 'wiki', 'experience'}
    suffixes = {'.py', '.json', '.toml', '.sh', '.h', '.hpp', '.c', '.cc', '.cpp', '.cmake'}
    names = []
    for directory, folders, files in os.walk(PACKAGE):
        folders[:] = [name for name in folders if name not in excluded and not name.endswith('.egg-info')]
        for name in files:
            path = Path(directory)/name
            if (path.suffix in suffixes or name in {'aprofctl', 'CMakeLists.txt'}) and name != 'release.json':
                names.append(path.relative_to(PACKAGE).as_posix())
    return tuple(sorted(names))


RECEIPT_KEYS = {'schema_version', 'kind', 'protocol', 'owner', 'cost_scope', 'admission_authority',
    'archive_complete', 'task_id', 'completion_ref', 'completion_kind', 'completion_protocol',
    'terminal_status', 'task_cost_seconds', 'local_index', 'local_index_sha256', 'store',
    'store_sha256', 'artifact_refs', 'artifact_bytes', 'package_identity', 'started_at', 'finished_at',
    'started_monotonic', 'finished_monotonic', 'elapsed_seconds'}


def _need(value, message):
    if not value:
        raise ContractError('local archive: ' + message)


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'non-finite cost/timestamp')
    return value


def _read(path):
    try:
        return json.loads(Path(path).read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as error:
        raise ContractError('local archive: invalid immutable JSON') from error


def package_identity(*, expected_release_version=None, expected_runtime_version=None):
    for name in identity_files():
        if name.startswith('runtime/src/aprof_runtime/'):
            module_name = 'aprof_runtime' + ('' if Path(name).stem == '__init__' else '.' + Path(name).stem)
            loaded = sys.modules.get(module_name)
            _need(loaded is None or file_hash(loaded.__file__) == file_hash(PACKAGE/name),
                  'installed archive runtime differs from its package source')
    release = _read(PACKAGE / '.codex-plugin/plugin.json')['version']
    runtime = tomllib.loads((PACKAGE / 'runtime/pyproject.toml').read_text())['project']['version']
    _need(runtime == __version__, 'loaded runtime version differs from selected package')
    _need(expected_release_version in (None, release) and expected_runtime_version in (None, runtime),
          'explicit release/runtime version differs from this archive handler')
    return dict(release_version=release, runtime_version=runtime,
        files={name: file_hash(PACKAGE/name) for name in identity_files()})


def freeze_package_identity(local):
    """Bind the actual handler/runtime bytes before a generic task is launched."""
    identity = package_identity()
    for name, ref in identity['files'].items():
        _need(local.register_artifact(PACKAGE/name) == ref, 'package changed during task preparation')
    return local.register_json(identity)


def verify_package_identity(reader, reference, *, live=True):
    identity = _read(reader.verify_artifact(reference))
    _need(isinstance(identity, dict) and set(identity) == {'release_version', 'runtime_version', 'files'}
          and isinstance(identity['files'], dict) and set(identity['files']) == set(identity_files()),
          'frozen task package identity schema differs')
    for ref in identity['files'].values(): reader.verify_artifact(ref)
    release = _read(reader.verify_artifact(identity['files']['.codex-plugin/plugin.json']))['version']
    runtime = tomllib.loads(reader.verify_artifact(identity['files']['runtime/pyproject.toml']).read_text())['project']['version']
    _need(identity['release_version'] == release and identity['runtime_version'] == runtime,
          'retained task release/runtime metadata differs')
    if live:
        _need(identity == package_identity(), 'task belongs to another package/archive handler')
    return identity


def _child_index_closure(reader, result, parent_artifacts):
    executions = [result['execution']]
    for ref in result['budget']['prior_terminal_refs']:
        terminal = _read(reader.verify_artifact(ref))
        executions.append(_read(reader.verify_artifact(terminal['execution_ref'])))
    for execution in executions:
        for row in execution.get('evidence_indices', []):
            if row['status'] == 'merged':
                child = _read(reader.verify_artifact(row['index_ref']))
                _need(row['index_ref'] in parent_artifacts and set(child['artifacts']) <= parent_artifacts,
                      'parent index omitted merged child evidence')


def _completion(reader, ref, task_id, *, before, parent_artifacts):
    terminal = _read(reader.verify_artifact(ref))
    _need(isinstance(terminal, dict) and terminal.get('status') in ('passed', 'failed')
          and 0 < _number(terminal.get('finished_at')) <= before, 'task has not completed before collection')
    if terminal.get('kind') == 'task_terminal_v1':
        launch = _read(reader.verify_artifact(terminal['launch_ref']))
        result = replay_task_terminal(reader, ref, task_id=task_id, budget_ref=launch['budget_ref'])
        job = result['budget']['job']
        _need('package_identity_ref' in job, 'task lacks a frozen package identity; use its historical archive handler')
        verify_package_identity(reader, job['package_identity_ref'])
        _child_index_closure(reader, result, parent_artifacts)
        cost = result['cumulative_seconds']
    elif terminal.get('kind') == 'local_measurement_completion':
        raise ContractError('local archive: legacy measurement has no frozen task package; use its historical archive handler')
    else:
        raise ContractError('local archive: unsupported task completion kind')
    return dict(completion_kind=terminal['kind'], completion_protocol=terminal.get('protocol', terminal['kind']),
                terminal_status=terminal['status'], task_cost_seconds=cost)


@contextmanager
def archive_reader(store_path):
    """Resolve only indexed immutable CAS bytes; never mutate a completed archive."""
    store_path = Path(store_path)
    _need(store_path.is_file() and not store_path.is_symlink(), 'archive database is missing or indirect')
    connection = sqlite3.connect(store_path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        yield _ReadOnlyArtifacts(connection, default_object_directory(store_path))
    finally:
        connection.close()


def _outside(path, scratch):
    path = Path(path).absolute()
    _need(path.resolve() == path and not path.is_relative_to(scratch),
          'archive destination must be canonical and outside task scratch')
    return path


def archive(index, completion, store_path, receipt, *, task_id=None,
            expected_release_version=None, expected_runtime_version=None):
    """Copy the complete original index only after an independently verified terminal."""
    started_at, started = time.time(), time.monotonic()
    identity = package_identity(expected_release_version=expected_release_version,
                                expected_runtime_version=expected_runtime_version)
    index = Path(index).resolve(strict=True); original_index_ref = file_hash(index)
    local = LocalEvidence.from_index(index)
    completion_ref = file_hash(completion)
    terminal = _read(local.verify_artifact(completion_ref))
    if task_id is None:
        task_id = (_read(local.verify_artifact(terminal['launch_ref']))['task_id']
                   if terminal.get('kind') == 'task_terminal_v1' else terminal.get('run_id'))
    _need(isinstance(task_id, str) and bool(task_id), 'missing task identity')
    saved = _read(index)
    completed = _completion(local, completion_ref, task_id, before=started_at,
                            parent_artifacts=set(saved['artifacts']))
    scratch = local.directory.parent
    store_path, receipt = (_outside(path, scratch) for path in (store_path, receipt))
    _need(not store_path.exists() and not default_object_directory(store_path).exists()
          and not receipt.exists() and store_path != receipt, 'archive destinations must be fresh')
    refs = sorted(saved['artifacts'])
    _need(file_hash(index) == original_index_ref, 'local index changed before collection')
    artifact_bytes = 0
    with EpisodeStore(store_path) as store:
        for ref in refs:
            source = local.verify_artifact(ref)
            artifact_bytes += source.stat().st_size
            _need(store.register_artifact(source) == ref, 'original artifact changed during collection')
        for ref in refs:
            store.verify_artifact(ref)
        _need(store.register_artifact(index) == original_index_ref, 'local index changed during collection')
    _need(file_hash(index) == original_index_ref, 'local index changed after collection')
    result = dict(schema_version=1, kind='local_evidence_archive_receipt', protocol=PROTOCOL,
        owner='trace_collection', cost_scope='post_task_archive', admission_authority=False,
        archive_complete=True, task_id=task_id, completion_ref=completion_ref, **completed,
        local_index=str(index), local_index_sha256=original_index_ref,
        store=str(store_path), store_sha256=file_hash(store_path), artifact_refs=refs,
        artifact_bytes=artifact_bytes, package_identity=identity, started_at=started_at,
        finished_at=time.time(), started_monotonic=started, finished_monotonic=time.monotonic())
    result['elapsed_seconds'] = result['finished_monotonic'] - started
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    return result


def verify_archive_receipt(receipt_path, *, local_index, completion_ref, task_id):
    """Verify the complete durable handoff before an independent caller removes scratch."""
    receipt_path = Path(receipt_path).absolute()
    _need(receipt_path.is_file() and not receipt_path.is_symlink(), 'receipt is absent or indirect')
    receipt = _read(receipt_path)
    _need(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS
          and type(receipt['schema_version']) is int and receipt['schema_version'] == 1
          and receipt['kind'] == 'local_evidence_archive_receipt' and receipt['protocol'] == PROTOCOL
          and receipt['owner'] == 'trace_collection' and receipt['cost_scope'] == 'post_task_archive'
          and receipt['admission_authority'] is False and receipt['archive_complete'] is True,
          'receipt schema/authority differs')
    _need(receipt['task_id'] == task_id and receipt['completion_ref'] == completion_ref
          and receipt['package_identity'] == package_identity(), 'task or archive handler identity differs')
    store_path = Path(receipt['store'])
    _need(file_hash(store_path) == receipt['store_sha256'], 'archive database bytes changed')
    start, finish, mono_start, mono_end, elapsed = (_number(receipt[key]) for key in
        ('started_at', 'finished_at', 'started_monotonic', 'finished_monotonic', 'elapsed_seconds'))
    _need(0 < start <= finish <= time.time() and mono_start < mono_end and elapsed == mono_end-mono_start,
          'independent archive cost/chronology differs')
    with archive_reader(store_path) as reader:
        saved = _read(reader.verify_artifact(receipt['local_index_sha256']))
        _need(isinstance(saved, dict) and set(saved) == {'schema_version','kind','directory','artifacts'}
              and saved['schema_version'] == 1 and saved['kind'] == 'local_evidence_index'
              and isinstance(saved['artifacts'], dict), 'retained local index schema differs')
        if local_index is not None:
            index = Path(local_index).resolve(strict=True)
            _need(receipt['local_index'] == str(index) and receipt['local_index_sha256'] == file_hash(index)
                  and saved == _read(index), 'original local index binding differs')
        scratch = Path(saved['directory']).parent
        _outside(receipt_path, scratch); _outside(store_path, scratch)
        _need(receipt['artifact_refs'] == sorted(saved['artifacts'])
              and completion_ref in saved['artifacts'], 'archive does not retain the complete original index')
        completed = _completion(reader, completion_ref, task_id, before=start,
                                parent_artifacts=set(saved['artifacts']))
        _need(all(receipt[key] == value for key, value in completed.items()), 'original task outcome/cost differs')
        sizes = sum(reader.verify_artifact(ref).stat().st_size for ref in receipt['artifact_refs'])
        _need(type(receipt['artifact_bytes']) is int and sizes == receipt['artifact_bytes'],
              'archived object byte count differs')
    _need(file_hash(store_path) == receipt['store_sha256'], 'archive changed during verification')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'completion', 'store', 'receipt'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--task-id')
    parser.add_argument('--release-version', required=True)
    parser.add_argument('--runtime-version', required=True)
    args = parser.parse_args(argv)
    result = archive(args.index, args.completion, args.store, args.receipt, task_id=args.task_id,
        expected_release_version=args.release_version, expected_runtime_version=args.runtime_version)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
