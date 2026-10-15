"""CPU fixtures only: real original oracle, synthetic build and kernel executor."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import time

import numpy as np
import pytest
import torch

import task_rule_correctness as driver

adapter, bridge = driver.adapter, driver.bridge
# Bound CPU cost in this controlled executor; production controls remain outer-owned.
torch.set_num_threads(1)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def original_module(operator):
    path = adapter.ROUND / operator / 'baseline/scripts/verify_result.py'
    return runpy.run_path(str(path)), path


def write_output(operator, argv):
    arg = lambda key: argv[argv.index(key) + 1]
    dtype = arg('--dtype')
    module, _ = original_module(operator)
    with open(arg('--input'), 'rb') as stream:
        values = module['load_chunk'](stream, dtype, int(arg('--numel')))
    if operator == 'sigmoid':
        expected = module['torch_golden'](values, dtype)
    else:
        values = values * np.float32(arg('--scale')) + np.float32(arg('--shift'))
        if float(arg('--base')) > 0:
            values *= np.log(np.float32(arg('--base')))
        with np.errstate(all='ignore'):
            expected = module['quantize'](np.exp(values).astype(np.float32), dtype)
    output = arg('--' + arg('--aprof-mechanism-role') + '-output')
    if dtype == 'float32':
        expected.astype(np.float32).tofile(output)
    elif dtype == 'float16':
        expected.astype(np.float16).tofile(output)
    else:
        torch.from_numpy(expected).to(torch.bfloat16).view(torch.uint16).numpy().tofile(output)


class CPUExecutor:
    def __init__(self, operator, defect=None):
        self.operator, self.defect, self.calls = operator, defect, []

    def __call__(self, argv, cwd, output, timeout, store, *, environment):
        argv = list(map(str, argv)); self.calls.append(argv)
        started = time.time(); stdout, stderr = io.StringIO(), io.StringIO()
        code, error = 0, None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                if '--aprof-mechanism-role' in argv:
                    assert environment == {'APROF_SHARED_CYCLE': '0'}
                    assert argv.count('--aprof-mechanism-role') == 1
                    write_output(self.operator, argv)
                    if self.defect == 'wrong_output':
                        role = argv[argv.index('--aprof-mechanism-role') + 1]
                        path = Path(argv[argv.index('--' + role + '-output') + 1])
                        path.write_bytes(bytes(path.stat().st_size))
                    elif self.defect == 'mutate_input':
                        path = Path(argv[argv.index('--input') + 1]); path.write_bytes(bytes(path.stat().st_size))
                    elif self.defect == 'kernel_exit':
                        raise SystemExit(9)
                    print('controlled CPU kernel executor; not hardware evidence')
                else:
                    previous = sys.argv
                    try:
                        sys.argv = argv[1:]
                        runpy.run_path(argv[1], run_name='__main__')
                    finally:
                        sys.argv = previous
            except SystemExit as exc:
                code = int(exc.code or 0)
            except Exception as exc:
                code, error = 1, {'type': type(exc).__name__, 'message': str(exc)}
        logs = {}
        for label, data in (('stdout', stdout.getvalue()), ('stderr', stderr.getvalue())):
            path = Path(str(output) + '.' + label + '.log'); path.write_text(data)
            logs[label + '_hash'] = store.register_artifact(path)
        record = dict(argv=argv, cwd=str(cwd), started_at=started, ended_at=time.time(),
            exit_code=code, error=error, environment=environment, timeout_seconds=timeout,
            pid=os.getpid(), controlled_cpu_fixture=True, **logs)
        path = dump(Path(str(output) + '.execution.json'), record)
        record['log_hash'] = store.register_artifact(path)
        if code or error:
            raise RuntimeError('controlled executor failure')
        return record


def fixture(tmp_path, operator):
    assembly = tmp_path / 'assembly'
    sources = {r: adapter.ROUND / operator / r for r in adapter.ROLES}
    inventories = {r: adapter.base.inventory(adapter.source_tree(p)) for r, p in sources.items()}
    proof = adapter.assemble(operator, sources, assembly, expected_roles=inventories, expected_headers=adapter.HEADERS)
    binary = assembly / 'build' / operator
    binary.parent.mkdir(); binary.write_text('CPU fixture: no CANN build, no hardware')
    review_hash = bridge.file_hash(assembly / 'source-review.json')
    route = dump(tmp_path / 'cpu-route.json', {'purpose':'CPU fixture only', 'hardware':False})
    attempt = dump(assembly / 'build-attempt.json', dict(source_review_hash=review_hash,
        independent_review='CPU fixture only', route=driver.path_ref(route)))
    build_path = dump(assembly / 'build-receipt.json', dict(status='passed', error=None,
        source_review_hash=review_hash, binary=driver.path_ref(binary), attempt_ref=driver.path_ref(attempt),
        commands=[dict(argv=proof['commands'][stage], cwd=str(assembly / 'source'), exit_status=0, error=None)
                  for stage in ('configure', 'build')]))
    store = bridge.LocalEvidence(tmp_path / 'evidence')
    expected = dict(operator=operator, run_id='synthetic-cpu-wiring', candidate_id='not-hardware',
        source_hashes={r: proof['historical_source_binding']['roles'][r]['sha256'] for r in adapter.ROLES})
    prepared = tmp_path / 'prepared'
    inputs = {}
    for case_id in range(1, 21):
        directory = prepared / f'case_{case_id:02d}'; directory.mkdir(parents=True)
        dtype = list(driver.THRESHOLDS)[(case_id - 1) % 3]
        values = np.asarray([-1., 0., 1.], dtype=np.float32)
        input_path = directory / 'input.bin'
        if dtype == 'bfloat16': torch.from_numpy(values).to(torch.bfloat16).view(torch.uint16).numpy().tofile(input_path)
        else: values.astype(dtype).tofile(input_path)
        metadata = dict(case_id=case_id, shape=[3], dtype=dtype, numel=3,
            input=str(input_path), output=str(directory / 'unused.bin'))
        if operator == 'exp': metadata.update(base=-1., scale=1., shift=0.)
        metadata_path = dump(directory / 'metadata.json', metadata)
        for path in (input_path, metadata_path): inputs[str(path)] = store.register_artifact(path)
    tree = adapter.ROUND / operator
    plan_path = tree / 'boundary-plan.json'
    plan = json.loads(plan_path.read_text())
    for case in plan['cases']:
        for path, reference in case['input_files'].items():
            assert store.register_artifact(path) == reference
            inputs[path] = reference
        path = tree / 'boundary-inputs' / f"case_{case['case_id']}/metadata.json"
        inputs[str(path)] = store.register_artifact(path)
    for role in adapter.ROLES:
        store.register_artifact(proof['historical_source_binding']['roles'][role]['path'])
    oracles = {str(tree / 'baseline/scripts' / name): store.register_artifact(tree / 'baseline/scripts' / name)
               for name in ('verify_result.py', 'gen_data.py')}
    protocol = dict(schema_version=1, purpose='promotion', created_at=time.time(), **expected,
        binary_hashes={r: store.register_artifact(binary) for r in adapter.ROLES},
        input_inventory_ref=store.register_json(inputs), oracle_files=oracles,
        boundary_plan_ref=store.register_artifact(plan_path))
    return dict(assembly=assembly, build_receipt=build_path, prepared=prepared, store=store,
                expected=expected, protocol_ref=store.register_json(protocol)), protocol
