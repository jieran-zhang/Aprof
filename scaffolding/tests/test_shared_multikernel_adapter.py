"""Source/config integration only: no CANN build, profiler, NPU or tensor allocation."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from aprof_runtime import __version__
if __version__ != '0.2.3':
    pytest.skip('select graph-base/1.0.0 runtime 0.2.3', allow_module_level=True)

import shared_multikernel_adapter as adapter
import shared_validation_adapter as existing
from aprof_runtime.task_window_timing import case_task_config


def write(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def assembly(tmp_path, operator, mutate=None):
    values = adapter.prepared_baseline(operator)
    sources = {role: tmp_path / role for role in adapter.ROLES}
    for role in adapter.ROLES:
        files = dict(values)
        if role == 'candidate':
            files[adapter.kernel_file(operator)] += b'\n// independent CPU source identity\n'
            if mutate:
                mutate(files)
        write(sources[role], files)
    kwargs = {'expected_roles': {role: adapter.base.inventory(adapter.base.tree(path))
                                for role, path in sources.items()},
              'expected_headers': adapter.base.inventory({name: (adapter.base.ASSETS / name).read_bytes()
                                                         for name in adapter.base.HEADERS})}
    destination = tmp_path / 'assembly'
    proof = adapter.assemble(operator, sources, destination, **kwargs)
    return destination, proof


def config_build_fixture(assembly_path, proof):
    """Clearly synthetic receipts for config wiring; never execute a compiler."""
    def save(path, value):
        path.write_text(json.dumps(value))
        return {'path': str(path), 'sha256': adapter.bridge.file_hash(path)}
    binary = assembly_path / 'build' / proof['operator']
    binary.parent.mkdir()
    binary.write_bytes(b'CPU configuration placeholder; not an executable or hardware build')
    review = save(assembly_path / 'cpu-review.json', {'fixture': 'CPU config only'})
    source_hash = adapter.bridge.file_hash(assembly_path / 'source-review.json')
    attempt = save(assembly_path / 'build-attempt.json', {
        'source_review_hash': source_hash, 'independent_review': review, 'route': review})
    path = assembly_path / 'build-receipt.json'
    save(path, {'status': 'passed', 'error': None, 'source_review_hash': source_hash,
        'binary': {'path': str(binary), 'sha256': adapter.bridge.file_hash(binary)}, 'attempt_ref': attempt,
        'commands': [{'argv': proof['commands'][stage], 'cwd': str(assembly_path / 'source'),
                      'exit_status': 0, 'error': None} for stage in ('configure', 'build')]})
    return path


def metadata_fixture(tmp_path, operator):
    """All real case shapes/attrs; tiny files only satisfy CPU path identity checks."""
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    if operator == 'gqa':
        historical = adapter.REPO.parent / 'validation-graph-base-1.0.0-round2-20261014/evaluation-source-preparation/gqa/inputs'
        values = [json.loads((historical / f'case_{cid:02d}/metadata.json').read_text()) for cid in range(1, 21)]
    else:
        cases = adapter.REPO.parent / 'aprof-feat-aprofgraph/third_party/cann-bench/tasks/level3/weight_quant_batch_matmul/cases.yaml'
        raw = yaml.safe_load(cases.read_text())['cases']
        assert [value['case_id'] for value in raw] == list(range(1, 21))
        values = [dict(value, m=value['input_shape'][0][0], k=value['input_shape'][0][1],
                       n=value['input_shape'][1][1], output_shape=[value['input_shape'][0][0], value['input_shape'][1][1]])
                  for value in raw]
    for metadata in values:
        directory = prepared / f"case_{metadata['case_id']:02d}"
        directory.mkdir()
        def blob(name):
            path = directory / (name + '.bin')
            path.write_bytes(b'CPU config fixture; not actual input values')
            return str(path)
        if operator == 'gqa':
            metadata.update({name: blob(name) for name in ('query', 'key', 'value')})
        else:
            metadata['paths'] = {name: blob(name) for name, shape in
                zip(('x', 'weight', 'scale', 'offset', 'bias'), metadata['input_shape']) if shape is not None}
        metadata['output'] = str(directory / 'output.bin')
        (directory / 'metadata.json').write_text(json.dumps(metadata))
    return prepared, values


@pytest.mark.parametrize('operator', adapter.OPERATORS)
def test_source_proof_complete_task_and_single_role_callbacks(tmp_path, operator):
    destination, proof = assembly(tmp_path, operator)
    assert adapter.source_identity(destination) == proof
    assert proof['runtime_build'] == 'aprof-runtime/0.2.3'
    assert proof['task_protocol'] == 'shared_buffer_msprof_task_window_v5'
    assert proof['mechanism_entry']['calls'] == 1
    host = (destination / f'source/op_host/{operator}.asc').read_text()
    assert host.count('aprof::RunShared(') == host.count('task_profile.Start(') == 1
    assert 'mechanism capture cannot enable Task API profiling' in host
    stream, check = ('st', 'C') if operator == 'gqa' else ('stream', 'Check')
    assert f'if (mechanism_role == "baseline") launch_baseline({stream}, buffers);' in host
    assert f'else launch_candidate({stream}, buffers);' in host
    assert f'{check}(aclrtSynchronizeStream({stream}), "mechanism complete call");' in host
    assert f'snapshot(mechanism_role.c_str(), {stream}, buffers);' in host
    if operator == 'gqa':
        assert host.count('for(uint64_t z=0;z<t.B*t.Nkv;++z)') == 4  # Complete QK/PV loops per role.
        assert '3 + 2 * t.B * t.Nkv, 3 + 2 * t.B * t.Nkv' in host
    else:
        for role in adapter.ROLES:
            for stage in ('dequant', 'matmul', 'post'):
                for dtype in ('fp16', 'bf16'):
                    assert f'aprof_{role}::aprof_{role}_wq_{stage}_{dtype}<<<' in host
        assert b'for(uint32_t q=0;q<k;++q)' in (destination / 'source/compiled/candidate/weight_quant_batch_matmul_kernel.asc').read_bytes()
    original = adapter.prepared_baseline(operator)['scripts/verify_result.py'].decode()
    assert (destination / 'source/scripts/verify_result.py').read_text() == adapter.adapt_oracle(original, operator)
    (destination / f'source/op_host/{operator}.asc').write_text(host.replace('else launch_candidate(', 'else launch_baseline('))
    with pytest.raises(ValueError, match='regeneration'):
        adapter.source_identity(destination)


@pytest.mark.parametrize('change', ['host', 'oracle', 'cmake', 'export', 'include', 'layout'])
def test_protected_source_and_tiling_edits_rejected(tmp_path, change):
    def mutate(files):
        name = {'host': 'op_host/gqa.asc', 'oracle': 'scripts/verify_result.py',
                'cmake': 'CMakeLists.txt'}.get(change, 'op_kernel/gqa_kernel.asc')
        data = files[name]
        if change == 'export':
            data = data.replace(b'void gqa_qk_fp16(', b'void renamed_qk(')
        elif change == 'layout':
            data = data.replace(b'uint32_t blocks,dtype,causal;', b'uint64_t blocks,dtype,causal;')
        else:
            data += b'\n#include "extra.h"\n' if change == 'include' else b'\n// forbidden edit\n'
        files[name] = data
    with pytest.raises(ValueError):
        assembly(tmp_path, 'gqa', mutate)


@pytest.mark.parametrize('operator', adapter.OPERATORS)
def test_all_twenty_actual_case_contracts_bind_complete_v5_sequences(tmp_path, operator):
    destination, proof = assembly(tmp_path, operator)
    receipt = config_build_fixture(destination, proof)
    prepared, metadata = metadata_fixture(tmp_path, operator)
    profiler = tmp_path / 'msprof'; profiler.write_bytes(b'CPU-only non-executable profiler path')
    config = adapter.task_config(destination, receipt, prepared, tmp_path / 'scratch', run_id='cpu',
        session_id='cpu-case-contracts', candidate_id='candidate', physical_device=0, profiler=profiler)
    assert config['expected_case_ids'] == [case['case_id'] for case in config['cases']] == list(range(1, 21))
    seen_dtypes, counts = set(), set()
    for value, case in zip(metadata, config['cases'], strict=True):
        cid = str(value['case_id'])
        dtype = value['dtype'] if operator == 'gqa' else value['dtype'][0]
        suffix = 'fp16' if dtype == 'float16' else 'bf16'
        seen_dtypes.add(dtype)
        count = 3 + 2 * value['query_shape'][0] * value['key_shape'][2] if operator == 'gqa' else 3
        counts.add(count)
        selected = case_task_config(config, value['case_id'])
        for role in adapter.ROLES:
            sequence = config['task_profile']['role_kernel_names'][role][cid]
            assert config['roles'][role]['launches_per_operator'][cid] == len(sequence) == count
            assert selected['roles'][role]['launches_per_operator'] == count
            if operator == 'gqa':
                prefix = f'aprof_{role}_gqa_'; groups = (count - 3) // 2
                assert sequence == [prefix + 'reorder', *([prefix + 'qk_' + suffix] * groups),
                    prefix + 'softmax', *([prefix + 'pv_' + suffix] * groups), prefix + 'scatter']
            else:
                assert sequence == [f'aprof_{role}_wq_{stage}_{suffix}' for stage in ('dequant', 'matmul', 'post')]
            oracle = case['verify_commands'][role]
            assert oracle[oracle.index('--metadata') + 1] == str(prepared / f"case_{value['case_id']:02d}/metadata.json")
            assert oracle[oracle.index('--output') + 1] == case['output_files'][role][0]
        argv = dict(zip(case['command'][1::2], case['command'][2::2]))
        assert argv['--dtype'] == dtype
        if operator == 'gqa':
            assert list(map(int, argv['--query-shape'].split(','))) == value['query_shape']
            assert list(map(int, argv['--key-shape'].split(','))) == value['key_shape']
            assert float(argv['--scale']) == value['scaleValue']
            assert int(argv['--causal']) == int(value['is_causal'])
        else:
            assert [int(argv[key]) for key in ('--m', '--k', '--n')] == [value['m'], value['k'], value['n']]
    assert seen_dtypes == {'float16', 'bfloat16'}
    assert len(counts) > 1 if operator == 'gqa' else counts == {3}
    bad = prepared / 'case_20/metadata.json'
    value = json.loads(bad.read_text()); value['case_id'] = 19; bad.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='case identity'):
        adapter.task_config(destination, receipt, prepared, tmp_path / 'scratch', run_id='cpu',
            session_id='cpu-case-contracts', candidate_id='candidate', physical_device=0, profiler=profiler)


def test_private_instances_and_explicit_release_keep_dispatch_disabled():
    assert existing.OPERATORS == ('dynamic_quant', 'gelu', 'group_norm')
    assert adapter.base is not existing and adapter.bridge.adapter.base is adapter.base
    assert adapter.ENABLED_IN_1_0 is adapter.bridge.ENABLED_IN_1_0 is False
    assert adapter.build_once is adapter.bridge.build_once
    environment = dict(os.environ, APROF_SKILL_LIB=str(adapter.REPO / 'skill-libs/graph-base/0.5.1'),
                       PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-c', 'import shared_multikernel_adapter'],
        env=environment, cwd=adapter.REPO, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'explicitly selected graph-base/1.0.0' in result.stderr
