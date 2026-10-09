#!/usr/bin/env python3
"""Read-only cross-file integrity verification, never a performance gate.

Manifest contract: operator; sources {baseline,parent,candidate: {path,sha256,
tree_path}}; patch {path,sha256}; binaries {role: {sha256,record,build_reports}};
inputs {case_id: {metadata_path,files:{absolute_path:sha256},input_hashes:{field:sha256}}};
protocol (exact feedback_hardware timing protocol); harness_paths (nonempty);
stages [{path,command,roles:{wrapper_role:source_role},cases,reverse,
profile_protocol (optional exact object)}]. All manifest paths resolve relative
to the manifest directory. Binaries record files contain {path,sha256}. Build
reports are native run_aprof_job or wrapper execution reports. Input file hashes
are compared as frozen maps: live prepared input bytes are deliberately not read.
Patch bytes must equal sorted difflib.unified_diff parent -> candidate, labels
'a/PATH', 'b/PATH', with splitlines(keepends=True), including additions/deletions.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def normalized(value):
    return value if value.startswith('sha256:') else 'sha256:' + value


def safe_name(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == name, f'unsafe archive path: {name}')


def snapshot(path, expected):
    require(digest(path.read_bytes()) == expected, f'snapshot digest mismatch: {path}')
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        require(len(names) == len(set(names)), 'duplicate archive member')
        for member in members:
            safe_name(member.name)
            require(member.isfile(), f'nonregular archive member: {member.name}')
        require('APROF_SOURCE_SNAPSHOT.json' in names, 'missing snapshot manifest')
        manifest = json.load(archive.extractfile('APROF_SOURCE_SNAPSHOT.json'))
        declared = manifest['files']
        require(len({row['path'] for row in declared}) == len(declared), 'duplicate snapshot file')
        require(set(names) == {'APROF_SOURCE_SNAPSHOT.json'} | {'source/' + r['path'] for r in declared}, 'snapshot member set mismatch')
        files, hashes = {}, {}
        for row in declared:
            safe_name(row['path'])
            member = archive.getmember('source/' + row['path'])
            content = archive.extractfile(member).read()
            require(len(content) == row['size_bytes'] and member.mode & 0o777 == row['mode'], 'snapshot size/mode mismatch')
            require(digest(content) == row['sha256'], f'snapshot content mismatch: {row["path"]}')
            files[row['path']] = content
            hashes[row['path']] = row['sha256']
    return files, hashes


def expected_patch(parent, candidate):
    chunks = []
    for name in sorted(set(parent) | set(candidate)):
        if parent.get(name) == candidate.get(name):
            continue
        chunks.extend(difflib.unified_diff(parent.get(name, b'').decode().splitlines(True),
                      candidate.get(name, b'').decode().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
    return ''.join(chunks).encode()


def verify(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = read(manifest_path)
    base = manifest_path.parent
    def path(value):
        return (base / value).resolve()
    statuses = []
    result = dict(kind='feedback_attempt_integrity', integrity='failed', gate_evaluated=False, stages=statuses)
    try:
        require(set(manifest['sources']) == {'baseline', 'parent', 'candidate'}, 'three explicit source roles required')
        sources, hashes = {}, {}
        for role, spec in manifest['sources'].items():
            sources[role], hashes[role] = snapshot(path(spec['path']), spec['sha256'])
        require(bool(manifest['harness_paths']), 'explicit unchanged harness paths required')
        for name in manifest['harness_paths']:
            require(all(name in files for files in sources.values()), f'missing harness: {name}')
            require(len({files[name] for files in sources.values()}) == 1, f'harness changed: {name}')
        patch = path(manifest['patch']['path']).read_bytes()
        require(digest(patch) == manifest['patch']['sha256'], 'patch digest mismatch')
        require(patch == expected_patch(sources['parent'], sources['candidate']), 'patch is not exact parent-to-candidate diff')
        binary_hashes = {}
        for role, spec in manifest['binaries'].items():
            require(role in sources, 'unknown binary source role')
            record = read(path(spec['record']))
            require(record['sha256'] == spec['sha256'], f'binary record mismatch: {role}')
            tree = path(manifest['sources'][role]['tree_path'])
            require(path(record['path']) == tree / 'build' / manifest['operator'], f'binary path/source role mismatch: {role}')
            require(bool(spec['build_reports']), f'missing build evidence: {role}')
            saw_build = False
            for report_path in spec['build_reports']:
                report = read(path(report_path))
                require(report['status'] == 'passed', f'build not passed: {role}')
                job = report.get('job', report)
                require(path(job['cwd']) == tree, f'build cwd/source role mismatch: {role}')
                require(report.get('exit_code', report.get('exit_status')) == 0, f'build exit mismatch: {role}')
                saw_build |= '--build' in job['argv']
            require(saw_build, f'no native build invocation: {role}')
            binary_hashes[role] = spec['sha256']
        require(bool(manifest['stages']), 'no completed stages')
        for stage in manifest['stages']:
            directory = path(stage['path'])
            completion = read(directory / 'completion.json')
            statuses.append(dict(path=str(directory), runtime_status=completion['status']))
            actual = {}
            for artifact in directory.rglob('*'):
                require(not artifact.is_symlink(), 'archive artifact symlink')
                if artifact.is_file() and artifact.name != 'completion.json':
                    actual[artifact.relative_to(directory).as_posix()] = digest(artifact.read_bytes())
            require(actual == completion['artifacts'], f'archive artifact mismatch: {directory}')
            request = completion['request']
            require(read(directory / 'request.json') == request, 'request/completion mismatch')
            require(request['command'] == stage['command'], 'stage command mismatch')
            require(request['cases'] == stage['cases'] and request['reverse'] == stage['reverse'], 'case/startup mismatch')
            require(request['device'] == 0, 'unexpected physical device')
            require(request['protocol'] == manifest['protocol'], 'protocol mismatch')
            require(set(request['trees']) == set(stage['roles']), 'wrapper role set mismatch')
            if stage['command'] == 'control':
                require(set(stage['roles']) == {'baseline', 'candidate'} and
                        stage['roles']['baseline'] == stage['roles']['candidate'], 'control must bind identical comparator roles')
            if stage['command'] == 'measure':
                require(set(stage['roles']) == {'baseline', 'candidate'} and
                        stage['roles']['baseline'] in ('baseline', 'parent') and
                        stage['roles']['candidate'] == 'candidate', 'measurement comparator roles must be explicit')
            for wrapper_role, role in stage['roles'].items():
                require(role in hashes, 'unknown stage source role')
                tree = request['trees'][wrapper_role]
                require(tree['sources'] == hashes[role], f'source/comparator mismatch: {wrapper_role} -> {role}')
                require(path(tree['path']) == path(manifest['sources'][role]['tree_path']), f'tree path/role mismatch: {role}')
                require(tree['operator'] == manifest['operator'], 'operator mismatch')
                if request['command'] != 'build':
                    require(tree['executable_sha256'] == binary_hashes[role], f'executable mismatch: {role}')
            if request['command'] != 'build':
                expected_inputs = {}
                for case in stage['cases']:
                    row = manifest['inputs'][str(case)]
                    require(row['metadata_path'] in row['files'], 'metadata missing from input binding')
                    require(any(Path(p).name == 'golden.bin' for p in row['files']), 'golden missing from frozen input binding')
                    for key, value in row['files'].items():
                        require(key not in expected_inputs or expected_inputs[key] == value, 'conflicting input hash')
                        expected_inputs[key] = value
                require(request['inputs']['files'] == expected_inputs, 'prepared input/golden binding mismatch')
            if stage['command'] == 'profile' and 'profile_protocol' in stage:
                require(request.get('profile_protocol') == stage['profile_protocol'], 'profile protocol mismatch')
            raw_path = directory / 'measurement/raw_measurements.json'
            if stage['command'] in ('measure', 'control') and raw_path.exists():
                raw = read(raw_path)
                require(raw['case_ids'] == stage['cases'] and raw['operator'] == manifest['operator'], 'raw case/operator mismatch')
                require(normalized(raw['producer_sha256']) == request['timing_producer_sha256'], 'raw producer mismatch')
                for wrapper_role, role in stage['roles'].items():
                    require(normalized(raw[wrapper_role + '_executable_sha256']) == binary_hashes[role], 'raw binary mismatch')
                for key in ('pairs', 'warmup', 'repeat', 'precondition_samples', 'single_live_context', 'checkpoint_every_pair'):
                    require(raw[key] == manifest['protocol'][key], f'raw protocol mismatch: {key}')
                require(raw.get('capture_replay', False) == manifest['protocol']['capture_replay'], 'raw capture protocol mismatch')
                require(raw['reverse_startup'] == stage['reverse'], 'raw startup mismatch')
                verifier_role = stage['roles']['baseline']
                require(normalized(raw['verifier_source_hash']) == hashes[verifier_role]['scripts/verify_result.py'], 'raw verifier source mismatch')
                require((raw.get('verification_protocol') == 'in_process_reuse_v1') == manifest['protocol']['reuse_verifier'], 'raw verifier protocol mismatch')
                for row in raw['case_executions']:
                    inputs = manifest['inputs'][str(row['case_id'])]
                    require(row['metadata_path'] == inputs['metadata_path'], 'raw metadata path mismatch')
                    require(normalized(row['metadata_sha256']) == inputs['files'][inputs['metadata_path']], 'raw metadata hash mismatch')
                    require({k: normalized(v) for k, v in row['input_hashes'].items()} == inputs['input_hashes'], 'raw input hash mismatch')
                if completion['status'] == 'passed':
                    require(raw['complete'] is True, 'passed timing stage has incomplete raw evidence')
                    require([row['case_id'] for row in raw['case_executions']] == stage['cases'], 'raw case execution coverage mismatch')
                    require(all(row['exit_status'] == 0 for row in raw['case_executions']), 'passed timing stage contains runtime failure')
            elif stage['command'] in ('measure', 'control') and completion['status'] == 'passed':
                raise ValueError('passed timing stage has no raw evidence')
        result['integrity'] = 'passed'
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        result['error'] = f'{type(error).__name__}: {error}'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.manifest)
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        with args.output.open('x') as stream:
            stream.write(text)
    print(text, end='')
    return 0 if result['integrity'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
