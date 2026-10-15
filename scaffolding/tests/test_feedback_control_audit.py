"""Synthetic controls only: audit never launches hardware or writes evidence."""
import builtins
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import feedback_control_audit as audit
from test_cannbench_device_timing import single_context_measurement

H = 'sha256:'+'a'*64


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def wrapper(tmp_path, name='before', reverse=False, time=0, bias=1, drift=1):
    root = tmp_path/name
    raw = single_context_measurement(reverse=reverse)
    raw.update(operator='fixture', producer_sha256=H[7:], baseline_executable_sha256=H[7:], candidate_executable_sha256=H[7:],
               verification_protocol='in_process_reuse_v1', verifier_source_hash=H,
               timing_scope='complete_operator_device_event_interval')
    for row in raw['records']:
        row['candidate']['elapsed_ns'] = row['baseline']['elapsed_ns'] * bias
        for role in ('baseline', 'candidate'):
            row[role]['elapsed_ns'] *= drift; row[role]['operator']='fixture'
            for sample in row['preconditioning'][role]: sample['operator']='fixture'
    tree = dict(path='/fixture/source', operator='fixture', sources={'scripts/verify_result.py':H}, executable_sha256=H)
    request = dict(command='control', cases=[1,2], device=0, reverse=reverse, protocol=audit.PROTOCOL,
                   trees={'baseline':tree, 'candidate':copy.deepcopy(tree)}, inputs={'path':'/fixture/inputs', 'files':{'/fixture/input':H}},
                   controller_sha256=H, timing_producer_sha256=H, validator_sha256=H)
    start = f'2026-09-08T{time:02d}:00:00Z'; end = f'2026-09-08T{time:02d}:01:00Z'
    process = dict(status='passed', exit_status=0, error=None, host='fixture', physical_device=0,
                   logical_device=0, started_at=start, finished_at=end)
    save(root/'request.json', request)
    save(root/'process/execution.json', process)
    save(root/'measurement/raw_measurements.json', raw)
    save(root/'measurement/measurement_report.json', audit.summarize_multicase(raw,[1,2]))
    completion = dict(status='passed', error=None, request=request, host='fixture', physical_device=0,
                      started_at=start, finished_at=end, artifacts={name:audit.sha(root/name) for name in audit.FILES})
    save(root/'completion.json', completion)
    return root


def reseal(root):
    completion = audit.read(root/'completion.json')
    completion['artifacts'] = {name:audit.sha(root/name) for name in audit.FILES}
    save(root/'completion.json', completion)


def test_progressive_scope_and_read_only_execution(tmp_path, monkeypatch):
    before=wrapper(tmp_path)
    reverse=wrapper(tmp_path,'reverse',True,1)
    after=wrapper(tmp_path,'after',False,2)
    original_open=builtins.open; path_open=Path.open
    def guarded(path,mode='r',*args,**kwargs):
        assert not any(m in mode for m in 'wax+'), 'audit attempted write'
        return original_open(path,mode,*args,**kwargs)
    def guarded_path(path,mode='r',*args,**kwargs):
        assert not any(m in mode for m in 'wax+'), 'audit attempted write'
        return path_open(path,mode,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',guarded); monkeypatch.setattr(Path,'open',guarded_path)
    one=audit.audit(before,[1,2])
    assert one['accepted'] and not one['ready_for_candidate'] and not one['full_control_validation']
    two=audit.audit(before,[1,2],reverse)
    assert two['ready_for_candidate'] and not two['full_control_validation']
    three=audit.audit(before,[1,2],reverse,after)
    assert three['full_control_validation'] and not three['audit_hardware_executed'] and not three['writes_performed']
    assert three['controls']['before']['per_case'][0]['pair_count']==30
    assert 'shifts' in three['comparisons']['before/after']['per_case'][0]


@pytest.mark.parametrize('fault', ['binary','producer','report','source_roles','protocol','partial','missing','hash','inputs_changed','orientation'])
def test_tamper_missing_partial_fail_closed(tmp_path, fault):
    before=wrapper(tmp_path)
    reverse=wrapper(tmp_path,'reverse',True,1)
    raw=audit.read(reverse/'measurement/raw_measurements.json')
    request=audit.read(reverse/'request.json')
    if fault=='binary': raw['candidate_executable_sha256']='b'*64
    if fault=='producer': raw['producer_sha256']='b'*64
    if fault=='partial': raw['complete']=False
    if fault=='orientation': raw['reverse_startup']=False
    if fault=='report':
        report=audit.read(reverse/'measurement/measurement_report.json'); report['speedup']=9
        save(reverse/'measurement/measurement_report.json',report)
    if fault=='source_roles': request['trees']['candidate']['executable_sha256']='sha256:'+'b'*64
    if fault=='protocol': request['protocol']['pairs']=31
    if fault=='inputs_changed': request['inputs']['files']['/fixture/input']='sha256:'+'b'*64
    save(reverse/'request.json',request)
    completion=audit.read(reverse/'completion.json'); completion['request']=request; save(reverse/'completion.json',completion)
    save(reverse/'measurement/raw_measurements.json',raw)
    if fault=='partial': save(reverse/'measurement/measurement_report.json',audit.summarize_multicase(raw,[1,2]))
    reseal(reverse)
    if fault=='missing': (reverse/'completion.json').unlink()
    if fault=='hash': (reverse/'measurement/raw_measurements.json').write_text('{}')
    result=audit.audit(before,[1,2],reverse)
    assert not result['accepted'] and not result['ready_for_candidate'] and result['errors']


def test_stable_but_biased_and_drifting_controls_rejected(tmp_path):
    before=wrapper(tmp_path)
    biased=wrapper(tmp_path,'biased',True,1,bias=1.04)
    result=audit.audit(before,[1,2],biased)
    assert not result['accepted'] and result['controls']['reverse']['per_case'][0]['role_bias'] > .02
    drifted=wrapper(tmp_path,'drifted',True,1,drift=1.04)
    result=audit.audit(before,[1,2],drifted)
    assert not result['accepted'] and result['comparisons']['before/reverse']['per_case'][0]['shifts']['pooled']>.02


def test_frozen_cases_and_no_missing_reverse(tmp_path):
    before=wrapper(tmp_path)
    assert not audit.audit(before,[2,1])['accepted']
    assert not audit.audit(before,[1,2,3])['accepted']
    assert not audit.audit(before,[1,1])['accepted']
    assert not audit.audit(before,[1,2],after=before)['accepted']
