#!/usr/bin/env python3
"""Finish only the machine gate after the local-evidence adapter failure.

No model, build, device execution, timing or profiling is performed here.
Both failed parent jobs remain immutable; this process has its own real exit.
"""
import argparse
import json
from pathlib import Path
import time

from task_rule_continuation import Evidence, finalize_gate, save
from task_rule_continuation_admission import retained_producer_scope
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.jsonio import file_hash
from timing_admission import read, require


class GateEvidence(Evidence, LocalEvidence):
    """Keep the runtime's LocalEvidence JSON path while reading retained bytes."""


def run(plan_path):
    started, mono = time.time(), time.monotonic()
    plan_path = Path(plan_path).resolve(strict=True)
    plan = json.loads(plan_path.read_text()); root = plan_path.parent
    require(plan['kind'] == 'exp_gate_completion_v1' and plan['directory'] == str(root), 'wrong gate-only plan')
    require(plan['actual_new_builds'] == plan['new_formal_timing_pairs'] == plan['actual_new_captures'] == 0,
            'gate completion cannot add hardware work')
    local = LocalEvidence(root / 'records')
    reader = GateEvidence(local, plan['object_roots'])
    for index_path in plan['local_indices']:
        other = LocalEvidence.from_index(index_path)
        for ref in other._paths:
            require(local.register_artifact(other.verify_artifact(ref)) == ref, 'retained local evidence changed')
    plan_ref = local.register_artifact(plan_path)
    launch = json.loads((root / 'launch.json').read_text())
    local.register_artifact(root / 'launch.json')
    require(launch['plan_ref'] == plan_ref and plan['created_at'] <= launch['started_at'] <= started,
            'gate completion launch changed')
    require(plan['total_budget_seconds'] == 5400 and plan['additional_budget_seconds'] ==
            5400 - plan['original_parent_seconds'] - plan['pmu_execution_seconds'], 'gate-only budget changed')
    deadline = launch['deadline_monotonic']
    require(deadline == launch['started_monotonic'] + plan['additional_budget_seconds'], 'gate deadline renewed')
    result = dict(schema_version=1, kind='exp_gate_completion_result_v1', status='failed',
        plan_ref=plan_ref, pmu_continuation_ref=plan['pmu_continuation_ref'], started_at=started,
        parent_status='failed', actual_new_builds=0, new_formal_timing_pairs=0, actual_new_captures=0,
        archive_performed=False, storage_mode='local_profile_only', error=None)
    try:
        for path, ref in plan['frozen_files'].items():
            require(file_hash(Path(path)) == ref, 'frozen gate input changed: ' + path)
            local.register_artifact(path)
        old_terminal = read(reader, plan['pmu_continuation_ref'])
        old_plan = read(reader, plan['pmu_plan_ref'])
        pmu = read(reader, old_terminal['child_result_ref'])
        require(old_terminal['status'] == pmu['status'] == 'failed'
                and pmu['error'] == {'type':'ValueError', 'message':
                    'continuation evidence not found: sha256:8302ca30e327e57d149ebd3aa5dde652b76923870a62a932a67b72404d4fa3e4'},
                'gate completion is restricted to the known local request registration failure')
        prefix = read(reader, plan['prefix_replay_ref'])
        require(prefix['valid'] is True and prefix['parent_status'] == 'failed', 'unverified retained prefix')
        for key in ('candidate_profile_ref', 'candidate_manifest_ref', 'candidate_oracle_ref',
                    'candidate_oracle_result_ref', 'candidate_output_hashes'):
            result[key] = pmu[key]
        require(time.monotonic() < deadline, 'gate budget exhausted')
        result['gate_started_at'] = time.time()
        with retained_producer_scope(reader, anchor_ref=old_plan['parent_anchor_ref'],
                                     trusted_review_refs=plan['trusted_review_refs']):
            result.update(finalize_gate(reader, dict(old_plan, plan_ref=plan_ref), prefix,
                                        read(reader, pmu['candidate_profile_ref'])))
        result['gate_finished_at'] = time.time()
        require(result['formal_outcome'] == 'production_safe_gain', 'final machine gate did not accept')
        for path, ref in plan['frozen_files'].items():
            require(file_hash(Path(path)) == ref, 'gate inputs changed during replay: ' + path)
        require(time.monotonic() < deadline, 'gate exceeded cumulative allowance')
        result['status'] = 'passed'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        result.update(finished_at=time.time(), duration_seconds=time.monotonic()-mono)
        result['cumulative_online_seconds'] = (plan['original_parent_seconds'] + plan['pmu_execution_seconds']
                                              + time.monotonic() - launch['started_monotonic'])
        save(root/'result.json', result); local.register_artifact(root/'result.json')
        local.write_index(root/'local-index.json')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();result=run(args.plan)
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['status']=='passed' else 2)
