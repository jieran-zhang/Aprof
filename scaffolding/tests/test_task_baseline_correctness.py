"""Original source/oracles with explicitly tiny CPU tensors, never original input generation."""
import contextlib
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import runpy
import sys

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
import task_baseline_build as builder
import task_baseline_correctness as correctness
import task_baseline_qualification as baseline
from test_task_baseline_build import setup as build_setup, Commands as BuildCommands


class OracleCommands(BuildCommands):
    """Synthetic native output; execute each exact unmodified Python oracle on CPU."""
    def __init__(self, original):
        self.__dict__.update(original.__dict__)
        self.stop_at = None
        self.shorten = False

    def run(self, label, argv, cwd):
        if label in ('configure', 'build'):
            return super().run(label, argv, cwd)
        self.calls.append(label)
        destination = self.directory / label
        destination.mkdir(parents=True)
        stdout, stderr = io.StringIO(), io.StringIO()
        code, error = 0, None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if label.endswith('-kernel'):
                role = argv[argv.index('--aprof-mechanism-role') + 1]
                key = 'output-y' if self.operator == 'dynamic_quant' else 'output'
                first = Path(argv[argv.index('--' + role + '-' + key) + 1])
                metadata = json.loads((first.parent / 'metadata.json').read_text())
                for name, size in correctness._output_sizes(self.operator, metadata).items():
                    Path(metadata[name]).write_bytes(bytes(size - int(self.shorten)))
                print('CPU placeholder complete callback; no device execution')
            else:
                previous = sys.argv
                try:
                    sys.argv = list(argv[1:])
                    runpy.run_path(argv[1], run_name='__main__')
                except SystemExit as exc:
                    code = 0 if exc.code is None else exc.code
                finally:
                    sys.argv = previous
        if self.stop_at == label:
            code, error = -15, {'type': 'TimeoutError', 'message': 'CPU fixture process timeout'}
        self.clock.elapsed += .25
        for name, value in (('stdout', stdout), ('stderr', stderr)):
            (destination / (name + '.log')).write_text(value.getvalue())
        record = {'argv': list(argv), 'cwd': str(cwd), 'duration_seconds': .25,
                  'exit_status': code, 'error': error,
                  **{name: {'path': str(destination / (name + '.log')),
                            'sha256': file_hash(destination / (name + '.log'))} for name in ('stdout', 'stderr')}}
        (destination / 'execution.json').write_text(json.dumps(record))
        return record


def tiny_inputs(root, source, operator):
    """Preserve original case id/dtype/attrs/IEEE ranges, shrink tensor shapes only."""
    spec = importlib.util.spec_from_file_location('cpu_original_case_table', source / 'scripts/cases.py')
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)
    for cid in range(1, 21):
        folder = root / f'case_{cid:02d}'
        folder.mkdir(parents=True)
        metadata = copy.deepcopy(cases.get_case(cid))
        def blob(name, n, byte_width):
            path = folder / (name + '.bin')
            path.write_bytes(bytes(n * byte_width))
            return str(path)
        if operator in ('dynamic_quant', 'gelu'):
            metadata.update(shape=[2, 4], numel=8, input=blob('input', 8, 4 if metadata['dtype']=='float32' else 2))
            if operator == 'dynamic_quant':
                metadata.update(row_length=4,token_count=2,attrs={},golden_y=blob('golden_y',8,1),
                    golden_scale=blob('golden_scale',2,4),output_y=str(folder/'output_y.bin'),
                    output_scale=str(folder/'output_scale.bin'))
            else:
                metadata['output'] = str(folder/'output.bin')
        elif operator == 'group_norm':
            # Keep each original group count and epsilon, including IEEE ranges.
            channels=metadata['num_groups']*2
            width=4 if metadata['dtype']=='float32' else 2
            metadata.update(shape=[1,channels,2],numel=channels*2,x=blob('x',channels*2,width),
                gamma=blob('gamma',channels,width),beta=blob('beta',channels,width),output=str(folder/'output.bin'))
        elif operator == 'gqa':
            metadata.update(query_shape=[1,2,4,2],key_shape=[1,2,2,2],value_shape=[1,2,2,2],
                output_shape=[1,2,4,2],query=blob('query',16,2),key=blob('key',8,2),
                value=blob('value',8,2),output=str(folder/'output.bin'))
        else:
            shapes=[[2,4],[4,2],[2],*[None if shape is None else [2] for shape in metadata['input_shape'][3:]]]
            paths={}
            for name,shape,dtype in zip(('x','weight','scale','offset','bias'),shapes,metadata['dtype']):
                if shape is not None:
                    paths[name]=blob(name,math.prod(shape),1 if dtype=='int8' else 4 if dtype=='float32' else 2)
            metadata.update(input_shape=shapes,m=2,k=4,n=2,output_shape=[2,2],paths=paths,output=str(folder/'output.bin'))
        (folder/'metadata.json').write_bytes(correctness._native(metadata))


def prepared(tmp_path, monkeypatch, operator='gelu'):
    local, initial, _, old_commands, _, clock = build_setup(tmp_path, monkeypatch, operator)
    monkeypatch.setattr(correctness, 'time', clock)
    original = tmp_path/'inputs'
    tiny_inputs(original, Path(initial['roles']['baseline']['path']), operator)
    toolchain=dict(initial['toolchain_refs'])
    python=str(Path(sys.executable).resolve())
    toolchain[python]=local.register_artifact(python)
    monkeypatch.setattr(builder,'PROFILE_DEPENDENCY_PATHS',tuple(toolchain))
    monkeypatch.setattr(baseline,'PROFILE_DEPENDENCY_PATHS',tuple(toolchain))
    producers={name:local.register_artifact(name) for name in [*initial['producer_refs'],correctness.__file__]}
    monkeypatch.setattr(baseline,'producer_paths',lambda:set(producers))
    first=json.loads((original/'case_01/metadata.json').read_text())
    scope=baseline.case_scope(operator,first)
    profile={'case_id':1,'kernels':[scope['role_kernel_names']['baseline'][0].removeprefix('aprof_baseline_')],
        'metrics':{'aic_time':{'unit':'us','file':'op_summary*.csv','format':'csv','field':'aicore_time(us)',
                          'row_aggregation':'median','aggregation':'median'}}}
    plan_ref=baseline.prepare_baseline_plan(local,operator=operator,
        sources={r:initial['roles'][r]['path'] for r in builder.ROLES},assembly=initial['assembly_dir'],
        prepared_inputs=original,scratch_root=tmp_path/'scratch',preparation_ref=initial['preparation_ref'],
        profile=profile,job_ref=initial['job_ref'],identity={'run_id':'CPU','session_id':'CPU','candidate_id':'CPU'},
        physical_device=2,created_at=clock.time()-1,toolchain_refs=toolchain,producer_refs=producers)
    commands=OracleCommands(old_commands)
    build_ref=builder.build_baseline_once(local,plan_ref=plan_ref,commands=commands)
    return local,plan_ref,build_ref,commands,clock


def collect(values,tmp_path):
    local,plan_ref,build_ref,commands,_=values
    return correctness.collect_baseline_correctness(local,plan_ref=plan_ref,build_receipt_ref=build_ref,
        commands=commands,destination=tmp_path/'correctness')


@pytest.mark.parametrize('operator',builder.OPERATORS)
def test_all_original_case_descriptors_full_roles_and_real_original_oracles(tmp_path,monkeypatch,operator):
    values=prepared(tmp_path,monkeypatch,operator)
    local,plan_ref,build_ref,commands,clock=values
    reference=collect(values,tmp_path)
    before=local._sequence
    verified=correctness.verify_baseline_correctness(local,plan_ref=plan_ref,build_receipt_ref=build_ref,report_ref=reference)
    assert local._sequence==before and verified['valid'] and not verified['qualification_granted']
    report=json.loads(local.verify_artifact(reference).read_text())
    assert [(r['case_id'],r['role']) for r in report['rows']]==[(c,r) for c in range(1,21) for r in builder.ROLES]
    assert len(commands.calls)==82 and all(row['correct'] for row in report['rows'])
    assert all(set(row['outputs'])==({'output_y','output_scale'} if operator=='dynamic_quant' else {'output'}) for row in report['rows'])
    assert all(row['verification']['passed'] for row in report['rows'])
    for row in report['rows']:
        metadata=json.loads(local.verify_artifact(row['metadata_ref']).read_text())
        original=json.loads(local.verify_artifact(row['original_metadata_ref']).read_text())
        assert correctness._native(metadata['value_range'])==correctness._native(original['value_range'])
        record=json.loads(local.verify_artifact(row['executions'][0]['execution_ref']['sha256']).read_text())
        assert record['argv'][-2:]==['--aprof-mechanism-role',row['role']]
    assert 'NaN' in (tmp_path/'correctness/case_13/baseline/metadata.json').read_text() if operator=='gelu' else True


def test_native_metadata_infinity_nan_and_signed_zero_are_not_strings():
    metadata={'value_range':[float('-inf'),float('inf'),float('nan'),-0.0],'ordinary':'NaN'}
    value=json.loads(correctness._native(metadata))
    assert isinstance(value['value_range'][0],float) and math.isinf(value['value_range'][0])
    assert math.isnan(value['value_range'][2]) and math.copysign(1,value['value_range'][3])==-1
    assert correctness._native(value)==correctness._native(metadata)
    assert correctness._native(value)!=correctness._native({'value_range':['-Infinity','Infinity','NaN',0.0],'ordinary':'NaN'})


def test_correctness_cannot_reset_the_build_deadline(tmp_path,monkeypatch):
    values=prepared(tmp_path,monkeypatch)
    commands,clock=values[3:]
    commands.deadline=clock.monotonic()+3600
    with pytest.raises(ValueError,match='original build/job deadline'):
        collect(values,tmp_path)
    assert commands.calls==['configure','build']


@pytest.mark.parametrize('defect',['missing_case','short_output','failed_kernel','deadline'])
def test_failure_stops_once_and_partial_evidence_is_retained(tmp_path,monkeypatch,defect):
    values=prepared(tmp_path,monkeypatch)
    local,plan_ref,build_ref,commands,clock=values
    if defect=='missing_case':
        (tmp_path/'inputs/case_20/metadata.json').unlink()
        with pytest.raises((ValueError,StoreError,FileNotFoundError)):
            collect(values,tmp_path)
        assert len(commands.calls)==2
        return
    if defect=='short_output':commands.shorten=True
    elif defect=='failed_kernel':commands.stop_at='correctness-case-01-baseline-kernel'
    else:clock.elapsed=commands.deadline-10000.0-.2
    with pytest.raises(correctness.CorrectnessFailure) as raised:
        collect(values,tmp_path)
    report=json.loads(local.verify_artifact(raised.value.report_ref).read_text())
    assert report['status']=='failed' and report['error'] and len(commands.calls)==3
    assert len(report['rows'])==1 and not report['rows'][0]['correct']
    with pytest.raises((FileExistsError,TimeoutError)):collect(values,tmp_path)
    assert len(commands.calls)==3


@pytest.mark.parametrize('defect',['row_order','missing_output','metadata_cast','output','exit','late'])
def test_replay_rejects_omission_metadata_output_and_execution_tamper(tmp_path,monkeypatch,defect):
    values=prepared(tmp_path,monkeypatch)
    local,plan_ref,build_ref,commands,clock=values
    reference=collect(values,tmp_path)
    path=local.verify_artifact(reference)
    report=json.loads(path.read_text())
    if defect=='row_order':report['rows'][0],report['rows'][1]=report['rows'][1],report['rows'][0]
    elif defect=='missing_output':report['rows'][0]['outputs']={}
    elif defect=='metadata_cast':
        row=report['rows'][24]
        metadata_path=local.verify_artifact(row['metadata_ref'])
        metadata=json.loads(metadata_path.read_text());metadata['value_range']=['NaN','NaN']
        metadata_path.write_bytes(correctness._native(metadata));row['metadata_ref']=local.register_artifact(metadata_path)
    elif defect=='output':
        Path(report['rows'][0]['outputs']['output']['path']).write_bytes(b'changed output')
    elif defect=='exit':
        operation=report['rows'][0]['executions'][0]
        execution_path=Path(operation['execution_ref']['path'])
        record=json.loads(execution_path.read_text());record['exit_status']=143
        execution_path.write_text(json.dumps(record));operation['execution_ref']['sha256']=local.register_artifact(execution_path)
    else:report['finished_monotonic']=report['deadline_monotonic']+1
    path.write_text(json.dumps(report,allow_nan=False));reference=local.register_artifact(path)
    with pytest.raises((ValueError,StoreError)):
        correctness.verify_baseline_correctness(local,plan_ref=plan_ref,build_receipt_ref=build_ref,report_ref=reference)
