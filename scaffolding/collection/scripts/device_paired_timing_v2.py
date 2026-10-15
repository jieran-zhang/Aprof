#!/usr/bin/env python3
"""Two fresh ACL contexts per case, with explicit post-READY conditioning.

The frozen collector supplies validation, hashing, process cleanup and numerical
summaries. This collector changes lifecycle only; it never publishes a gate pass.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
RELEASE = (ROOT / 'skill-libs/graph-base/1.0.0').resolve()
V1_PATH = RELEASE / 'skills/ascendc-aprof-profiling/scripts/device_paired_timing.py'
_spec = importlib.util.spec_from_file_location('aprof_frozen_paired_timing_v1', V1_PATH)
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)
PROTOCOL = 'persistent_acl_event_two_epoch_primed_pairs_v2'
HEADER = ROOT / 'scaffolding/benchmarks/cannbench/harness/device_timer_v2.h'
ROLES = ('baseline', 'candidate')
device_lock = v1.device_lock
PREFIX = v1.PREFIX


def summarize(raw, config):
    report = v1.summarize(raw, config)
    report.update(schema_version='2.0.0', measurement_protocol=PROTOCOL)
    return report


def epoch_config(config, epoch):
    result = {key: deepcopy(value) for key, value in config.items() if key not in ('epochs', 'prime_repeat')}
    result['schema_version'] = '1.0.0'
    result['cases'] = [dict(case_id=case['case_id'], workload=deepcopy(case['workload']),
                            prepared_files=list(case['prepared_files']), **deepcopy(case['epochs'][epoch]))
                       for case in config['cases']]
    return result


def config_value(value):
    value = deepcopy(value)
    if not isinstance(value, dict) or value.get('schema_version') != '2.0.0':
        raise ValueError('v2 schema_version must be 2.0.0')
    value.setdefault('epochs', 2)
    value.setdefault('prime_repeat', 100)
    if type(value['epochs']) is not int or value['epochs'] != 2 or type(value['prime_repeat']) is not int or value['prime_repeat'] != 100:
        raise ValueError('v2 fixes two epochs and 100 complete operator calls per prime')
    cases = value.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('cases must be nonempty')
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'case_id', 'workload', 'prepared_files', 'epochs'}:
            raise ValueError('v2 case requires case_id, workload, prepared_files, epochs')
        if not isinstance(case['epochs'], list) or len(case['epochs']) != 2:
            raise ValueError('each case requires exactly two explicit epochs')
        if any(not isinstance(epoch, dict) or set(epoch) != set(ROLES) for epoch in case['epochs']):
            raise ValueError('each epoch requires both role commands')
    validated = [v1.config_value(epoch_config(value, i)) for i in range(2)]
    if validated[0]['pairs'] % 2 or validated[0]['pairs'] < 2:
        raise ValueError('pairs must be positive and even for two equal epochs')
    for key in ('operator', 'device', 'physical_device', 'expected_case_ids', 'mode', 'pairs', 'warmup', 'repeat', 'timeout_seconds', *ROLES):
        value[key] = validated[0][key]
    outputs = []
    for index, case in enumerate(value['cases']):
        case['prepared_files'] = validated[0]['cases'][index]['prepared_files']
        for epoch in range(2):
            for role in ROLES:
                item = validated[epoch]['cases'][index][role]
                case['epochs'][epoch][role] = item
                outputs += item['output_files']
    if len(outputs) != len(set(outputs)):
        raise ValueError('outputs must be distinct across every case, epoch and role')
    return value


class TimingChild(v1.TimingChild):
    def ready_receipt(self):
        before = time.monotonic_ns()
        self.ready()
        return dict(wait_started_monotonic_ns=before, ready_monotonic_ns=time.monotonic_ns(), pid=self.process.pid)

    def prime(self, config, case, role, index):
        before = time.monotonic_ns()
        self.process.stdin.write('prime\n')
        self.process.stdin.flush()
        ack = v1._json(self.until('APROF_PRIME_JSON:'))
        expected = dict(schema_version='2.0.0', operator=config['operator'], device=config['device'],
                        prime_index=index, repeat=100, launches_per_operator=case[role]['launches_per_operator'])
        if not isinstance(ack, dict) or set(ack) != set(expected) or any(type(ack[k]) is not type(v) or ack[k] != v for k,v in expected.items()):
            raise ValueError('prime acknowledgement identity/count mismatch')
        return dict(role=role, pid=self.process.pid, request_monotonic_ns=before,
                    response_monotonic_ns=time.monotonic_ns(), acknowledgement=ack)

    def timed_sample(self, config, case, role, index):
        before = time.monotonic_ns()
        sample = self.sample(config, case, role, index)
        return sample, dict(pid=self.process.pid, request_monotonic_ns=before,
                            response_monotonic_ns=time.monotonic_ns())


def collect(value, output):
    config = config_value(value)
    with v1.device_lock(config['physical_device'], config['timeout_seconds']):
        return _collect(config, output)


def _collect(config, output):
    output = Path(output).resolve()
    if any(output == Path(config[role]['source_dir']) or output.is_relative_to(Path(config[role]['source_dir'])) for role in ROLES):
        raise ValueError('evidence output must be outside source trees')
    output.mkdir(parents=True, exist_ok=False)
    v1.save(output / 'config.json', config)
    configs = [epoch_config(config, i) for i in range(2)]
    for case in config['cases']:
        for epoch in case['epochs']:
            for role in ROLES:
                for path in epoch[role]['output_files']:
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, APROF_TIMING_INTERACTIVE='1', APROF_TIMING_V2='1',
               APROF_WARMUP=str(config['warmup']), APROF_REPEAT=str(config['repeat']), APROF_PRIME_REPEAT='100')
    for key in ('APROF_CAPTURE_REPLAY', 'APROF_SAMPLES'):
        env.pop(key, None)
    raw = dict(schema_version='2.0.0', measurement_protocol=PROTOCOL, operator=config['operator'], host=socket.gethostname(),
               device=config['device'], physical_device=config['physical_device'], unit='ns', source='acl_event',
               timing_scope='complete_operator_device_event_interval', case_ids=config['expected_case_ids'],
               pairs=config['pairs'], warmup=config['warmup'], repeat=config['repeat'], epochs=2, prime_repeat=100,
               mode=config['mode'], config_hash=v1.content_hash(config), producer_hash=v1.file_hash(__file__),
               runtime_version=v1.RUNTIME_VERSION, records=[], case_executions=[], complete=False,
               environment={key:env.get(key) for key in ('APROF_TIMING_INTERACTIVE','APROF_TIMING_V2','APROF_WARMUP','APROF_REPEAT','APROF_PRIME_REPEAT','APROF_CAPTURE_REPLAY','ASCEND_RT_VISIBLE_DEVICES','ASCEND_VISIBLE_DEVICES','ASCEND_HOME_PATH','ASCEND_OPP_PATH','LD_LIBRARY_PATH')})
    try:
        runtime_root = Path(v1.runtime_gates.__file__).resolve().parent
        runtime_files = {p.relative_to(runtime_root).as_posix():v1.file_hash(p) for p in sorted(runtime_root.rglob('*.py'))}
        raw['producer_dependencies'] = {'frozen_collector':v1.file_hash(V1_PATH), 'device_timer_v2.h':v1.file_hash(HEADER),
                                       'profile_capture.py':v1.file_hash(v1.SCRIPTS/'profile_capture.py'),
                                       'runtime_source_files':runtime_files,'runtime_source_hash':v1.content_hash(runtime_files)}
        raw['case_identities'] = {str(case['case_id']):{'epochs':[v1.identities(configs[e], configs[e]['cases'][i]) for e in range(2)]}
                                  for i,case in enumerate(config['cases'])}
        for ci, original in enumerate(config['cases']):
            execution = dict(case_id=original['case_id'], workload=original['workload'], epochs=[], started_at=time.time(),
                             started_monotonic_ns=time.monotonic_ns(), finished_at=None, exit_status=None)
            raw['case_executions'].append(execution)
            try:
                for epoch in range(2):
                    ec, case = configs[epoch], configs[epoch]['cases'][ci]
                    expected = raw['case_identities'][str(case['case_id'])]['epochs'][epoch]
                    order = list(ROLES if epoch == 0 else reversed(ROLES))
                    state = dict(epoch=epoch, startup_order=order, identity_before=expected, identity_after=None,
                                 started_at=time.time(), started_monotonic_ns=time.monotonic_ns(), finished_at=None,
                                 commands={}, ready_receipts={}, prime_receipts=[], verifications={}, exit_status=None)
                    execution['epochs'].append(state)
                    children = {}
                    try:
                        for role in order:
                            v1.unchanged(ec, case, expected)
                            if any(Path(p).exists() or Path(p).is_symlink() for p in case[role]['output_files']):
                                raise ValueError('output appeared before its epoch/role started')
                            child = TimingChild(case[role]['command'],ec[role]['cwd'],env,
                                output/f"case-{case['case_id']:02d}-epoch-{epoch}-{role}.log",ec['timeout_seconds'])
                            children[role] = child
                            state['commands'][role] = child.receipt
                            state['ready_receipts'][role] = child.ready_receipt()
                            v1.unchanged(ec, case, expected)
                        if epoch and any(state['commands'][r]['pid'] in {p['pid'] for p in execution['epochs'][0]['commands'].values()} for r in ROLES):
                            raise RuntimeError('fresh epoch reused an earlier PID; identity would be ambiguous')
                        counts = {role:0 for role in ROLES}
                        for role in [order[0], order[1], order[1], order[0]]:
                            state['prime_receipts'].append(children[role].prime(ec,case,role,counts[role])); counts[role] += 1
                        half = config['pairs']//2
                        for local in range(half):
                            index = epoch*half+local
                            sample_order = list(ROLES if index%2 == 0 else reversed(ROLES))
                            record = dict(case_id=case['case_id'],round=index,epoch=epoch,local_round=local,
                                          order=sample_order,device=config['device'],baseline=None,candidate=None,sample_receipts={})
                            raw['records'].append(record)
                            for role in sample_order:
                                sample, receipt = children[role].timed_sample(ec,case,role,local)
                                record[role] = sample; record['sample_receipts'][role] = receipt
                            v1.save(output/'raw_measurements.json',raw)
                        for child in children.values(): child.close()
                        v1.unchanged(ec,case,expected)
                        outputs = {}
                        for role in ROLES:
                            for path in case[role]['output_files']:
                                if Path(path).is_symlink() or not Path(path).is_file(): raise ValueError('missing isolated epoch output')
                                outputs[path] = v1.file_hash(path)
                        state['output_hashes'] = outputs
                        for role in ROLES:
                            receipt={};state['verifications'][role]=receipt
                            v1.verify(case[role]['verify_command'],ec[role]['cwd'],
                                      output/f"case-{case['case_id']:02d}-epoch-{epoch}-{role}-verify.log",ec['timeout_seconds'],receipt)
                            if receipt['exit_status'] != 0: raise RuntimeError('epoch output verification failed')
                            v1.unchanged(ec,case,expected)
                            if any(Path(p).is_symlink() or v1.file_hash(p)!=digest for p,digest in outputs.items()):
                                raise ValueError('verifier modified timed output')
                        state['identity_after']=v1.unchanged(ec,case,expected);state['exit_status']=0
                    finally:
                        errors=[]
                        for child in children.values():
                            try: child.close(abort=True)
                            except Exception as error: errors.append(str(error))
                        state.update(finished_at=time.time(),finished_monotonic_ns=time.monotonic_ns())
                        if errors:
                            state['cleanup_errors']=errors
                            if sys.exc_info()[0] is None: raise RuntimeError('; '.join(errors))
                execution['exit_status']=0
            finally:
                execution.update(finished_at=time.time(),finished_monotonic_ns=time.monotonic_ns())
        raw['complete']=True
    except BaseException as error:
        raw['error']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        v1.save(output/'raw_measurements.json',raw)
        report=summarize(raw,config)
        v1.save(output/'measurement_report.json',report)
        v1.save(output/'timing_draft.json',dict(schema_version='2.0.0',kind='aprof_paired_timing_draft',measurement_protocol=PROTOCOL,
            mode=config['mode'],pair_count=config['pairs'],production_minimum_met=raw['complete'] and config['mode']=='formal' and config['pairs']>=v1.GateConfig.MIN_PAIRS and config['warmup']>=10,
            measurement_complete=raw['complete'],measurement_stable=report['stable'],raw_measurements_hash=v1.file_hash(output/'raw_measurements.json'),
            measurement_report_hash=v1.file_hash(output/'measurement_report.json'),baseline_samples_ns=report['gate_projection']['baseline_samples_ns'],
            candidate_samples_ns=report['gate_projection']['candidate_samples_ns'],full_correctness_required=True,authority=report['authority']))
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(argv)
    try: report=collect(v1._json(a.config.read_text()),a.output)
    except Exception as error: print(f'v2 device timing failed: {error}',file=sys.stderr);return 2
    print(json.dumps(dict(output=str(a.output),mode=report['mode'],measurement_stable=report['stable'],authority='draft_only')))
    return 0

if __name__=='__main__': raise SystemExit(main())
