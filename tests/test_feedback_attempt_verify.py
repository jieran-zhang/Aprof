import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import feedback_attempt_verify as verify


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def tar_snapshot(path, files):
    rows = [{'path': p, 'sha256': verify.digest(b), 'mode': 420, 'size_bytes': len(b)} for p, b in files.items()]
    with tarfile.open(path, 'w') as archive:
        for name, data in [('APROF_SOURCE_SNAPSHOT.json', json.dumps({'files': rows}).encode()),
                           *[('source/' + p, b) for p, b in files.items()]]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 420
            archive.addfile(member, io.BytesIO(data))
    return verify.digest(path.read_bytes())


def reseal(directory):
    completion = verify.read(directory / 'completion.json')
    completion['request'] = verify.read(directory / 'request.json')
    completion['artifacts'] = {p.relative_to(directory).as_posix(): verify.digest(p.read_bytes())
                               for p in directory.rglob('*') if p.is_file() and p.name != 'completion.json'}
    write(directory / 'completion.json', completion)


@pytest.fixture
def attempt(tmp_path):
    files = {role: {'op_kernel/exp.asc': content, 'op_host/aprof_device_timer.h': b'harness\n'}
             for role, content in [('baseline', b'original\n'), ('parent', b'parent\n'), ('candidate', b'candidate\n')]}
    manifest = {'operator': 'exp', 'sources': {}, 'binaries': {}, 'harness_paths': ['op_host/aprof_device_timer.h'],
                'protocol': {}, 'inputs': {}, 'stages': []}
    for role in files:
        tar = tmp_path / (role + '.tar')
        manifest['sources'][role] = {'path': str(tar), 'sha256': tar_snapshot(tar, files[role]), 'tree_path': str(tmp_path / role)}
        binary = verify.digest((role + '-binary').encode())
        record = tmp_path / (role + '-binary.json')
        build = tmp_path / (role + '-build.json')
        write(record, {'path': str(tmp_path / role / 'build/exp'), 'sha256': binary})
        write(build, {'status': 'passed', 'exit_code': 0, 'job': {'cwd': str(tmp_path / role), 'argv': ['cmake', '--build', 'build']}})
        manifest['binaries'][role] = {'sha256': binary, 'record': str(record), 'build_reports': [str(build)]}
    patch = tmp_path / 'candidate.patch'
    patch.write_bytes(verify.expected_patch(files['parent'], files['candidate']))
    manifest['patch'] = {'path': str(patch), 'sha256': verify.digest(patch.read_bytes())}
    metadata, golden = '/frozen/case_01/metadata.json', '/frozen/case_01/golden.bin'
    inputs = {metadata: verify.digest(b'metadata'), golden: verify.digest(b'golden')}
    manifest['inputs']['1'] = {'metadata_path': metadata, 'files': inputs, 'input_hashes': {}}
    directory = tmp_path / 'correctness'
    request = {'command': 'correctness', 'cases': [1], 'reverse': False, 'device': 0, 'protocol': {},
               'inputs': {'files': inputs}, 'trees': {'opdir': {
                   'path': str(tmp_path / 'candidate'), 'operator': 'exp',
                   'sources': {p: verify.digest(b) for p, b in files['candidate'].items()},
                   'executable_sha256': manifest['binaries']['candidate']['sha256']}}}
    write(directory / 'request.json', request)
    write(directory / 'completion.json', {'request': request, 'status': 'passed', 'artifacts': {}})
    reseal(directory)
    manifest['stages'] = [{'path': str(directory), 'command': 'correctness', 'roles': {'opdir': 'candidate'}, 'cases': [1], 'reverse': False}]
    path = tmp_path / 'attempt.json'
    write(path, manifest)
    return path


def test_consistent_attempt_no_live_input_reads(attempt):
    result = verify.verify(attempt)
    assert result['integrity'] == 'passed', result
    assert result['gate_evaluated'] is False


@pytest.mark.parametrize('change,error', [('source', 'source/comparator'), ('comparator', 'source/comparator'),
                                         ('binary', 'executable mismatch'), ('golden', 'golden binding')])
def test_cross_file_mismatch(attempt, change, error):
    manifest = verify.read(attempt)
    directory = Path(manifest['stages'][0]['path'])
    request = verify.read(directory / 'request.json')
    if change == 'source':
        request['trees']['opdir']['sources']['op_kernel/exp.asc'] = verify.digest(b'wrong')
    elif change == 'comparator':
        manifest['stages'][0]['roles']['opdir'] = 'baseline'
        write(attempt, manifest)
    elif change == 'binary':
        request['trees']['opdir']['executable_sha256'] = verify.digest(b'wrong')
    else:
        request['inputs']['files']['/frozen/case_01/golden.bin'] = verify.digest(b'wrong')
    write(directory / 'request.json', request)
    reseal(directory)
    result = verify.verify(attempt)
    assert result['integrity'] == 'failed'
    assert error in result['error']


def test_patch_must_be_parent_relative(attempt):
    manifest = verify.read(attempt)
    patch = Path(manifest['patch']['path'])
    patch.write_text('valid looking but wrong parent diff\n')
    manifest['patch']['sha256'] = verify.digest(patch.read_bytes())
    write(attempt, manifest)
    assert 'parent-to-candidate' in verify.verify(attempt)['error']


def test_failed_runtime_is_reported_without_gate(attempt):
    manifest = verify.read(attempt)
    directory = Path(manifest['stages'][0]['path'])
    completion = verify.read(directory / 'completion.json')
    completion['status'] = 'failed'
    write(directory / 'completion.json', completion)
    result = verify.verify(attempt)
    assert result['integrity'] == 'passed'
    assert result['stages'][0]['runtime_status'] == 'failed'
    assert result['gate_evaluated'] is False


def test_tar_unsafe_member_rejected(tmp_path):
    path = tmp_path / 'bad.tar'
    with tarfile.open(path, 'w') as archive:
        member = tarfile.TarInfo('../escape')
        archive.addfile(member, io.BytesIO(b''))
    with pytest.raises(ValueError, match='unsafe'):
        verify.snapshot(path, verify.digest(path.read_bytes()))


def test_changed_harness_rejected(attempt):
    manifest = verify.read(attempt)
    spec = manifest['sources']['candidate']
    files, _ = verify.snapshot(Path(spec['path']), spec['sha256'])
    files['op_host/aprof_device_timer.h'] = b'changed timer\n'
    spec['sha256'] = tar_snapshot(Path(spec['path']), files)
    write(attempt, manifest)
    assert 'harness changed' in verify.verify(attempt)['error']


def test_measurement_raw_binary_crossbinding(attempt):
    manifest = verify.read(attempt)
    directory = Path(manifest['stages'][0]['path'])
    request = verify.read(directory / 'request.json')
    candidate = request['trees']['opdir']
    baseline_spec = manifest['sources']['baseline']
    _, hashes = verify.snapshot(Path(baseline_spec['path']), baseline_spec['sha256'])
    request.update(command='measure', timing_producer_sha256=verify.digest(b'producer'), trees={
        'baseline': dict(candidate, sources=hashes, path=baseline_spec['tree_path'],
                         executable_sha256=manifest['binaries']['baseline']['sha256']), 'candidate': candidate})
    manifest['stages'][0].update(command='measure', roles={'baseline': 'baseline', 'candidate': 'candidate'})
    write(attempt, manifest)
    write(directory / 'request.json', request)
    write(directory / 'measurement/raw_measurements.json', {
        'case_ids': [1], 'operator': 'exp', 'producer_sha256': request['timing_producer_sha256'],
        'baseline_executable_sha256': manifest['binaries']['baseline']['sha256'],
        'candidate_executable_sha256': verify.digest(b'incorrect binary')})
    reseal(directory)
    assert 'raw binary mismatch' in verify.verify(attempt)['error']
