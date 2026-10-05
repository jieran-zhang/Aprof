#!/usr/bin/env python3
"""Freeze baseline-only counter predictions, then bind complete robust profile evidence.

This is a CPU-only adapter. It never invokes profiling or changes runtime gates.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import _profile_metric, mechanism_alignment_from_artifacts
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact, utcnow, validate_trace_contract, verify_trace
from collect_level1_traces import Campaign, DEFAULT_RUN
from normalize_aprof_profile import normalize_profile, _COMPRESSOR

FOPS = 'ArithmeticUtilization/aiv_vec_fops'
SCALAR = 'PipeUtilization/aiv_scalar_time(us)'
VECTOR_STALL = 'PipeUtilization/aiv_scalar_vector_stall_time(us)'
INPUT_STALL = 'PipeUtilization/aiv_scalar_mte2_stall_time(us)'
COPIES = 'Memory/aiv_mte2_instructions'
BANDWIDTH = 'Memory/aiv_gm_to_ub_bw(GB/s)'
BLOCKS = 'OpBasicInfo/Block Dim'

# These are explicit source-hypothesis mappings, not a fit to candidate results.
SPECS = {
    'foreach_norm.minimum_tile_budget_dynamic_split': ('foreach_norm_partial_kernel', [(BLOCKS, 'increase')], 'all', 'More independent partial tasks should increase the launched block count.'),
    'foreach_norm.algebraic_common_orders': ('foreach_norm_partial_kernel', [(FOPS, 'decrease')], 'norm_common', 'Runtime p=1,2,4 removes generic Power arithmetic; other orders are controls.'),
    'foreach_norm.vector_resident_sequential_accumulator': ('foreach_norm_partial_kernel', [(SCALAR, 'decrease'), (VECTOR_STALL, 'decrease')], 'norm_sum', 'The vector-resident accumulator removes scalar GetValue feedback and its scalar/vector synchronization.'),
    'exp.attribute_identity_dispatch': ('exp_kernel', [(FOPS, 'decrease')], 'exp_identity', 'Identity affine attributes remove vector operations under the exact host multiplier/shift formula.'),
    'exp.localize_tiling_and_split_tail': ('exp_kernel', [(SCALAR, 'decrease')], 'all', 'Caching tiling fields and moving tail control reduces scalar issue work.'),
    'exp.double_buffer_prolog_steady_drain': ('exp_kernel', [(INPUT_STALL, 'decrease')], 'all', 'Input prefetch predicts less scalar waiting for MTE2; this is a stall proxy, not direct overlap proof.'),
    'exp.capacity_adaptive_transfer_tiles': ('exp_kernel', [(COPIES, 'decrease')], 'all', 'Larger contiguous tiles should require fewer per-core MTE2 instructions.'),
    'exp.align_core_dma_boundaries': ('exp_kernel', [(BANDWIDTH, 'increase')], 'all', 'Source alignment predicts higher observed GM-to-UB bandwidth; cache and scheduling can also affect this counter.'),
    'exp.zero_affine_exp_identity': ('exp_kernel', [(FOPS, 'decrease')], 'exp_zero', 'The effective zero affine argument removes Exp arithmetic while preserving nonfinite input propagation.'),
    'masked_scale_prefetch_double_buffer': ('masked_scale_kernel', [(INPUT_STALL, 'decrease')], 'all', 'Input prefetch predicts less exposed input waiting; a stall counter does not establish overlap causality.'),
    'masked_scale_elide_fp32_materialization': ('masked_scale_kernel', [(FOPS, 'decrease')], 'masked_fp32', 'FP32 queue aliasing removes identity arithmetic only in the affected dtype branches.'),
    'masked_scale_dtype_aware_ub_tiling': ('masked_scale_kernel', [(COPIES, 'decrease')], 'all', 'Larger UB-bounded tiles reduce copy instruction count per core.'),
    'foreach_addcdiv_scalar.align_core_copy32': ('foreach_addcdiv_scalar_kernel', [(BANDWIDTH, 'increase')], 'all', 'Aligned source ownership predicts higher transfer bandwidth; already aligned workloads can remain inconclusive.'),
    'foreach_addcdiv_scalar.prefetch_fifo_double_buffer': ('foreach_addcdiv_scalar_kernel', [(INPUT_STALL, 'decrease')], 'all', 'One-tile input prefetch predicts less MTE2 waiting, without claiming a measured overlap timeline.'),
    'foreach_addcdiv_scalar.ub_bounded_contiguous_batch': ('foreach_addcdiv_scalar_kernel', [(COPIES, 'decrease')], 'all', 'Larger contiguous batches predict fewer MTE2 instructions per core.'),
    'mish.reuse_negative_tail_exponential': ('mish_kernel', [(FOPS, 'decrease')], 'all', 'Reusing the stable-softplus exponential removes one Exp computation per tile.'),
    'mish.prefetch_double_buffer': ('mish_kernel', [(INPUT_STALL, 'decrease')], 'all', 'Input prefetch predicts less scalar waiting for MTE2; zero baseline stalls cannot establish a reduction.'),
    'mish.direct_fp32_input': ('mish_kernel', [(FOPS, 'decrease')], 'fp32', 'Direct FP32 input consumption removes one identity Adds operation; narrower dtypes are controls.'),
    'sigmoid.align_block_ownership': ('sigmoid_kernel', [(BANDWIDTH, 'increase')], 'unaligned_core_ownership32', 'Aligning per-core source ownership to 32 bytes predicts higher observed GM-to-UB bandwidth where baseline starts are unaligned; this transfer proxy does not prove exclusive causality.'),
    'sigmoid.double_buffer_prefetch': ('sigmoid_kernel', [(INPUT_STALL, 'decrease')], 'all', 'Lookahead input prefetch predicts reduced scalar waiting for MTE2; a zero baseline stall counter cannot support a decrease.'),
    'sigmoid.coalesce_dma_chunks': ('sigmoid_kernel', [(COPIES, 'decrease')], 'all', 'Coalescing 8192-element DMA tiles while retaining 4096-element compute chunks predicts fewer MTE2 instructions, not fewer vector operations.'),
    'gelu_prefetch_double_buffer': ('gelu_kernel', [(INPUT_STALL, 'decrease')], 'all', 'One-tile input prefetch predicts reduced scalar waiting for MTE2; this counter is a stall proxy rather than a measured overlap timeline.'),
    'gelu_capacity_batched_tiles': ('gelu_kernel', [(COPIES, 'decrease')], 'all', 'Capacity-bounded larger tiles predict fewer per-core MTE2 copy instructions while preserving logical traffic.'),
    'gelu_hoist_launch_invariants': ('gelu_kernel', [(SCALAR, 'decrease')], 'all', 'Caching tiling fields and hoisting mode dispatch predicts less scalar issue work inside the unchanged tile loop.'),
}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, document, *, immutable=True):
    path = Path(path)
    data = canonical_json(document) + '\n'
    if path.exists():
        if path.read_text() == data:
            return
        if immutable:
            raise StoreError(f'immutable mechanism evidence differs: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.mechanism-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def applicable(rule, metadata):
    if rule == 'all':
        return True
    if rule == 'unaligned_core_ownership32':
        block_dim = metadata.get('__baseline_block_dim')
        numel = metadata.get('numel')
        item_bytes = {'float32': 4, 'float16': 2, 'bfloat16': 2}.get(metadata.get('dtype'))
        if not isinstance(numel, int) or not isinstance(block_dim, (int, float)) or block_dim <= 0 or not item_bytes:
            return None  # Missing source geometry is not an aligned negative control.
        block_length = (numel + int(block_dim) - 1) // int(block_dim)
        return block_length * item_bytes % 32 != 0
    if rule == 'norm_common':
        return metadata.get('scalar') in (1.0, 2.0, 4.0)
    if rule == 'norm_sum':
        return math.isfinite(metadata.get('scalar', math.inf))
    if rule == 'fp32':
        return metadata.get('dtype') == 'float32'
    if rule == 'masked_fp32':
        return metadata.get('x_dtype') == 'float32' or metadata.get('mask_dtype') == 'float32'
    if rule in ('exp_identity', 'exp_zero'):
        base = metadata.get('base', -1.0)
        factor = math.log(base) if base > 0 else 1.0
        multiplier = metadata.get('scale', 1.0) * factor
        shift = metadata.get('shift', 0.0) * factor
        return (multiplier == 1.0 or shift == 0.0) if rule == 'exp_identity' else (multiplier == 0.0 and shift == 0.0)
    raise ContractError('unknown explicit applicability rule: ' + rule)


def profile_path(case_directory, kernel):
    for name in ('normalized-current', 'normalized'):
        path = Path(case_directory) / name / kernel / 'normalized_profile.json'
        if path.exists():
            return path
    return None


def import_profile(path, raw, store):
    """Register original/combined CSVs; callers replay each declared metric."""
    path, raw = Path(path), Path(raw)
    profile = read(path)
    validate_trace_contract('normalized-profile', profile)
    digest = content_hash(profile)
    try:
        # Already-normalized campaign profiles are immutable CAS documents.
        # The caller still replays every requested counter and original cell;
        # unrelated tables need not be re-imported for each prediction.
        store.verify_artifact(digest)
    except StoreError:
        pass
    else:
        return profile, digest
    normalized = path.parent.parent
    for directory in (raw, normalized):
        for source in sorted(directory.rglob('*.csv')):
            store.register_artifact(source, media_type='text/csv')
    digest = register_json_artifact(store, profile)
    return profile, digest


def invocation_medians(store, profile, metric):
    """Reduce recorded core rows by invocation, avoiding pseudo-replication."""
    groups = {}
    with store.verify_artifact(metric['source_artifact_hash']).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if profile['kernel'] != '*' and profile['kernel'] not in row.values():
                continue
            cell = row.get(metric['field'], '')
            if cell in ('', 'N/A', 'NA', '--', None):
                continue
            invocation = row.get('aprof_invocation')
            if not invocation:
                raise ContractError('robustness requires normalized invocation provenance')
            groups.setdefault(invocation, []).append(float(cell))
    return [statistics.median(values) for _, values in sorted(groups.items())]


def replay_profile(path, raw, store, *, kernel=None):
    """Read existing normalization and verify it still covers current raw files.

    Unlike import_profile/normalize_profile this never registers or writes bytes.
    New raw data without corresponding normalization requires a fresh bind first.
    """
    raw = Path(raw)
    current = {p.relative_to(raw).as_posix(): p for p in raw.rglob('*.csv')
               if _COMPRESSOR._csv_kind(p) is not None}
    if path is None and not current:
        return None, None
    if path is None:
        normalized = next((raw.parent / name for name in ('normalized-current', 'normalized')
                           if (raw.parent / name / 'normalization_manifest.json').exists()), None)
        if normalized is None:
            raise StoreError('current raw profiles require normalization and a fresh mechanism bind')
    else:
        path = Path(path)
        normalized = path.parent.parent
    manifest = read(normalized / 'normalization_manifest.json')
    artifacts = manifest['raw_artifacts']
    if len(artifacts) != len(current) or {item['path'] for item in artifacts} != set(current):
        raise StoreError('normalization does not cover the current raw profile set')
    for item in artifacts:
        if file_hash(current[item['path']]) != item['content_hash']:
            raise StoreError('current raw profile differs from its normalization manifest')
    for item in manifest['combined_tables']:
        if file_hash(normalized / item['path']) != item['content_hash']:
            raise StoreError('combined profile table differs from its normalization manifest')
    if path is None:
        if any(item['kernel'] == kernel for item in manifest['profiles']):
            raise StoreError('manifest declares a kernel whose normalized profile is missing')
        return None, None
    profile = read(path)
    validate_trace_contract('normalized-profile', profile)
    digest = content_hash(profile)
    if read(store.verify_artifact(digest)) != profile:
        raise StoreError('normalized profile differs from its CAS document')
    entries = [item for item in manifest['profiles'] if item['kernel'] == profile['kernel']]
    if (len(entries) != 1 or entries[0]['content_hash'] != digest
            or (normalized / entries[0]['path']).resolve() != path.resolve()
            or manifest['case_id'] != profile['case_id']):
        raise StoreError('normalized profile identity differs from its manifest')
    return profile, digest


def compare_distributions(before, after, direction, *, relative_floor=.01, min_invocations=3):
    if len(before) < min_invocations or len(after) < min_invocations:
        return 'inconclusive', 'Fewer than three recorded invocation medians on one side.'
    baseline, candidate = statistics.median(before), statistics.median(after)
    delta = candidate - baseline
    floor = relative_floor * max(abs(baseline), abs(candidate), 1e-12)
    supported = min(after) > max(before) if direction == 'increase' else max(after) < min(before)
    refuted = max(after) < min(before) if direction == 'increase' else min(after) > max(before)
    if abs(delta) <= floor:
        return 'inconclusive', 'Median change does not exceed the predeclared 1% relative floor.'
    if supported:
        return 'supported', 'Expected direction exceeds the relative floor and full invocation-median ranges do not overlap.'
    if refuted:
        return 'refuted', 'Opposite direction exceeds the relative floor and full invocation-median ranges do not overlap.'
    return 'inconclusive', 'Invocation-median ranges overlap; the measured direction is within observed spread.'


class MechanismBinder:
    def __init__(self, run=DEFAULT_RUN):
        self.campaign = Campaign(run)

    def identifiers(self, op, candidates=None):
        available = [path.parent.name for path in sorted((self.campaign.task(op) / 'candidates').glob('*/candidate_plan.json'))]
        selected = candidates or available
        if not selected or len(set(selected)) != len(selected) or not set(selected).issubset(available):
            raise ContractError('candidate selection must be a nonempty unique subset of the operator roster')
        return selected

    def prepare(self, op, identifier, cases, specification=None):
        task = self.campaign.task(op)
        directory = task / 'candidates' / identifier
        target = directory / 'mechanism_plan.json'
        candidate = read(directory / 'candidate_plan.json')
        if not cases or len(set(cases)) != len(cases) or not set(cases).issubset(self.campaign.manifest['sentinel_case_ids']):
            raise ContractError('mechanism profiling is restricted to unique frozen sentinel cases')
        if target.exists():
            frozen = read(target)
            if frozen['candidate_plan_hash'] != file_hash(directory / 'candidate_plan.json') or frozen['requested_case_ids'] != cases:
                raise StoreError('mechanism plan candidate/case binding changed')
            if specification is not None and frozen['specification'] != specification:
                raise StoreError('explicit mechanism specification changed after freeze')
            with self.campaign.store(op) as store:
                self.verify_plan_event(op, frozen, store)
            return frozen
        if any(path.is_file() for path in (task / 'profiles' / identifier).rglob('*')) or any((task / 'executions' / identifier).glob('profile-*/execution.json')):
            raise StoreError('mechanism predictions must be frozen before candidate profiling results exist')
        if specification is None:
            item = SPECS.get(candidate['handler_id'])
            if item is None:
                raise ContractError('no explicit metric mapping for handler; provide a reviewed --spec before profiling: ' + candidate['handler_id'])
            kernel, metrics, rule, rationale = item
            specification = {'kernel': kernel, 'metrics': [{'name': name, 'expected_direction': direction} for name, direction in metrics],
                'applicability': rule, 'rationale': rationale}
        self.validate_specification(specification)
        predictions, controls = [], []
        with self.campaign.store(op) as store:
            for case in cases:
                metadata_path = self.campaign.prepared(op) / f'case_{case:02d}' / 'metadata.json'
                metadata = read(metadata_path)
                metadata_hash = store.register_artifact(metadata_path)
                case_directory = task / 'profiles/baseline' / f'case-{case:02d}'
                path = profile_path(case_directory, specification['kernel'])
                profile, digest = import_profile(path, case_directory / 'raw', store) if path else (None, None)
                geometry = dict(metadata)
                if profile and BLOCKS in profile['metrics']:
                    _profile_metric(store, digest, BLOCKS)
                    geometry['__baseline_block_dim'] = profile['metrics'][BLOCKS]['value']
                is_applicable = applicable(specification['applicability'], geometry)
                if is_applicable is not True:
                    controls.append({'case_id': case, 'metadata_hash': metadata_hash, 'baseline_profile_hash': digest,
                        'reason': 'The frozen source predicate does not change this workload geometry or branch; this case is a control.' if is_applicable is False else
                            'Applicability cannot be established from the baseline geometry metadata; no directional claim is possible.'})
                    continue
                for metric_spec in specification['metrics']:
                    metric = profile['metrics'].get(metric_spec['name']) if profile else None
                    note = None
                    if metric:
                        if metric['unit'] == 'unspecified':
                            raise ContractError('mechanism counter must have a declared unit')
                        _profile_metric(store, digest, metric_spec['name'])
                        if metric['value'] <= 0:
                            note = 'Baseline counter is not positive; the declared relative decrease/increase cannot provide a reliable positive-baseline comparison.'
                    else:
                        note = 'Declared baseline metric/profile is missing; no alternative is chosen from candidate results.'
                    predictions.append({'case_id': case, 'kernel': specification['kernel'], **metric_spec,
                        'metadata_hash': metadata_hash, 'baseline_profile_hash': digest,
                        'baseline_profile_path': str(path) if path else None,
                        'unit': metric['unit'] if metric else None, 'baseline_value': metric['value'] if metric else None,
                        'limitation': note})
            plan = {'schema_version': '1.0.0', 'kind': 'aprof_frozen_mechanism_plan', 'run_id': self.campaign.run.name,
                'operator': op, 'candidate_id': candidate['candidate_id'], 'candidate_plan_hash': store.register_artifact(directory / 'candidate_plan.json'),
                'prepared_at': utcnow(), 'requested_case_ids': cases, 'specification': specification,
                'hypothesis_basis': candidate.get('hypothesis_basis', 'heuristic'), 'predictions': predictions, 'control_cases': controls,
                'robustness': {'relative_median_floor': .01, 'minimum_invocations': 3, 'range_rule': 'full_invocation_median_ranges_must_not_overlap',
                    'admission_rule': 'every_predeclared_metric_must_robustly_support_expected_direction'},
                'limitations': ['Invocation spread checks are conservative descriptive evidence, not a causal proof or a statistical confidence interval.',
                    'Counter direction does not establish exclusive attribution; throughput depends on traffic, cache and scheduling.'],
                'producer_hash': store.register_artifact(Path(__file__))}
            digest = register_json_artifact(store, plan)
            self.campaign.writer(op, store).append('next_step_decided', {
                'action': 'freeze_mechanism_predictions',
                'reason': 'Freeze exact counter directions, applicable cases and robustness criteria before candidate profiling.',
                'evidence_refs': [digest]}, candidate_id=plan['candidate_id'], attempt_id=plan['candidate_id'],
                event_id=plan['candidate_id'] + '-mechanism-plan-frozen')
            write(target, plan)
            return plan

    def verify_plan_event(self, op, plan, store):
        path = self.campaign.task(op) / 'trace_events.jsonl'
        verify_trace(path, store)
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        found = [event for event in events if event['event_id'] == plan['candidate_id'] + '-mechanism-plan-frozen']
        if len(found) != 1 or found[0]['payload'].get('evidence_refs') != [content_hash(plan)]:
            raise StoreError('mechanism plan differs from the pre-profile event/CAS commitment')
        frozen = found[0]
        if any(event['candidate_id'] == plan['candidate_id'] and event['event_type'] == 'stage_completed'
                and event['payload']['stage'] == 'profile' and event['sequence'] < frozen['sequence'] for event in events):
            raise StoreError('mechanism declaration followed candidate profiling evidence')

    @staticmethod
    def validate_specification(spec):
        if set(spec) != {'kernel', 'metrics', 'applicability', 'rationale'} or not all(isinstance(spec[key], str) and spec[key] for key in ('kernel', 'applicability', 'rationale')):
            raise ContractError('explicit spec requires kernel, metrics, applicability, rationale')
        if not 1 <= len(spec['metrics']) <= 2:
            raise ContractError('declare one or two specific counters per applicable case')
        if len({item['name'] for item in spec['metrics']}) != len(spec['metrics']):
            raise ContractError('duplicate declared counter')
        for item in spec['metrics']:
            if set(item) != {'name', 'expected_direction'} or item['expected_direction'] not in ('increase', 'decrease'):
                raise ContractError('counter requires name and expected_direction')
            if '/' not in item['name'] or any(word in item['name'].lower() for word in ('duration', 'aiv_time(', 'aic_time(')):
                raise ContractError('whole-kernel duration is not mechanism evidence')
        applicable(spec['applicability'], {})

    def _evaluate_binding(self, op, identifier, plan, store, *, readonly):
        """One deterministic comparison implementation for binding and replay."""
        task = self.campaign.task(op)
        directory = task / 'candidates' / identifier
        if plan['candidate_plan_hash'] != file_hash(directory / 'candidate_plan.json'):
            raise StoreError('candidate plan changed after its mechanism prediction freeze')
        comparisons, strict_metrics = [], []
        plan_hash = content_hash(plan)
        profiles, baselines = {}, {}
        for prediction in plan['predictions']:
            case, kernel, name = prediction['case_id'], prediction['kernel'], prediction['name']
            item = {**prediction, 'status': 'inconclusive', 'reason': prediction['limitation'], 'candidate_profile_hash': None,
                'candidate_value': None, 'baseline_invocation_medians': [], 'candidate_invocation_medians': []}
            if prediction['baseline_profile_hash'] is None:
                comparisons.append(item)
                continue
            baseline_path = Path(prediction['baseline_profile_path'])
            if baseline_path not in baselines:
                loader = replay_profile if readonly else import_profile
                baselines[baseline_path] = loader(baseline_path, baseline_path.parents[2] / 'raw', store)
            baseline, baseline_hash = baselines[baseline_path]
            if baseline_hash != prediction['baseline_profile_hash']:
                raise StoreError('baseline normalization changed after prediction freeze')
            case_directory = task / 'profiles' / identifier / f'case-{case:02d}'
            if (case, kernel) not in profiles:
                # Existing normalized-current wins. Otherwise normalize the
                # actual raw CSVs through the same provenance-preserving API.
                path = profile_path(case_directory, kernel)
                if not readonly and any((case_directory / 'raw').rglob('*.csv')):
                    normalize_profile(case_directory / 'raw', case_directory / 'normalized-current', case, store)
                    path = profile_path(case_directory, kernel)
                profiles[(case, kernel)] = (replay_profile(path, case_directory / 'raw', store, kernel=kernel) if readonly else
                    import_profile(path, case_directory / 'raw', store) if path else (None, None))
            candidate, candidate_hash = profiles[(case, kernel)]
            if candidate is None or name not in candidate['metrics']:
                item['reason'] = 'A predeclared candidate case/kernel/metric is missing; the report cannot use a favorable subset.'
                comparisons.append(item)
                continue
            if baseline['case_id'] != case or candidate['case_id'] != case or baseline['kernel'] != kernel or candidate['kernel'] != kernel:
                raise StoreError('mechanism profiles do not have the same declared case and exact kernel')
            _, before = _profile_metric(store, baseline_hash, name)
            _, after = _profile_metric(store, candidate_hash, name)
            if before['unit'] != prediction['unit'] or after['unit'] != prediction['unit'] or before['field'] != after['field'] or before['aggregation'] != after['aggregation']:
                raise StoreError('mechanism profile units, source field or aggregation differ')
            if before['value'] != prediction['baseline_value']:
                raise StoreError('baseline metric differs from its frozen value')
            a, b = invocation_medians(store, baseline, before), invocation_medians(store, candidate, after)
            status, reason = compare_distributions(a, b, prediction['expected_direction'],
                relative_floor=plan['robustness']['relative_median_floor'], min_invocations=plan['robustness']['minimum_invocations'])
            follows = after['value'] > before['value'] if prediction['expected_direction'] == 'increase' else after['value'] < before['value']
            if prediction['limitation']:
                status, reason = 'inconclusive', prediction['limitation']
            if status == 'supported' and not follows:
                status, reason = 'inconclusive', 'Normalized row-median direction disagrees with invocation-median direction.'
            item.update(status=status, reason=reason, candidate_profile_hash=candidate_hash, candidate_value=after['value'],
                baseline_invocation_medians=a, candidate_invocation_medians=b)
            comparisons.append(item)
            strict_metrics.append({'name': name, 'baseline': before['value'], 'candidate': after['value'],
                'expected_direction': prediction['expected_direction'], 'unit': before['unit'],
                'baseline_profile_hash': baseline_hash, 'candidate_profile_hash': candidate_hash})
        admitted = bool(comparisons) and all(item['status'] == 'supported' for item in comparisons)
        statuses = {item['status'] for item in comparisons}
        status = 'supported' if admitted else ('refuted' if statuses == {'refuted'} else 'inconclusive')
        report = None
        if admitted:
            report = {'schema_version': '1.0.0', 'candidate_id': plan['candidate_id'],
                'hypothesis_basis': plan['hypothesis_basis'], 'metrics': strict_metrics}
            validate_trace_contract('mechanism-report', report)
        report_hash = content_hash(report) if report else None
        binding = {'schema_version': '1.0.0', 'kind': 'aprof_mechanism_binding', 'candidate_id': plan['candidate_id'],
            'mechanism_plan_hash': plan_hash, 'status': status, 'mechanism_report_hash': report_hash,
            'comparisons': comparisons, 'declared_comparison_count': len(plan['predictions']),
            'admitted_comparison_count': len(strict_metrics) if admitted else 0,
            'reason': 'Every predeclared applicable counter robustly supports its expected direction.' if admitted else
                'The complete frozen prediction set did not provide robust directional support; no mechanism report is admitted.',
            'limitations': plan['limitations']}
        return binding, report

    def verify_binding(self, op, identifier, plan, binding, store):
        """Replay every status against current raw evidence, without any writes.

        The caller separately verifies the pre-profile plan/event commitment.
        """
        expected, _ = self._evaluate_binding(op, identifier, plan, store, readonly=True)
        if binding != expected:
            raise StoreError('mechanism binding does not replay from current raw profiles; run a fresh bind')
        return expected

    def bind(self, op, identifier):
        directory = self.campaign.task(op) / 'candidates' / identifier
        plan = read(directory / 'mechanism_plan.json')
        with self.campaign.store(op) as store:
            self.verify_plan_event(op, plan, store)
            register_json_artifact(store, plan)
            binding, report = self._evaluate_binding(op, identifier, plan, store, readonly=False)
            report_path = directory / 'mechanism_report.json'
            if report:
                report_hash = register_json_artifact(store, report)
                gate = {'candidate_id': plan['candidate_id'], **{key: 'not_run' for key in
                    ('static_review', 'build', 'accuracy', 'runtime', 'semantic', 'scope', 'portability')},
                    'artifacts': {'mechanism_report': report_hash}}
                if mechanism_alignment_from_artifacts(gate, store) is not True:
                    raise StoreError('strict mechanism report failed runtime raw-CSV replay')
                write(report_path, report)
            elif report_path.exists():
                raise StoreError('new evidence cannot silently revoke or replace an existing admitted mechanism report')
            digest = register_json_artifact(store, binding)
            write(directory / 'mechanism_bindings' / (digest.removeprefix('sha256:') + '.json'), binding)
            write(directory / 'mechanism_binding.json', binding, immutable=False)
            return binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'bind'))
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--candidate', help='Comma-separated directory IDs; default is the complete operator roster.')
    parser.add_argument('--cases', help='Comma-separated planned sentinel profile cases; prepare only.')
    parser.add_argument('--spec', type=Path, help='Reviewed specifications keyed by candidate directory ID; prepare only.')
    args = parser.parse_args()
    binder = MechanismBinder(args.run)
    if args.action == 'bind' and (args.cases or args.spec):
        parser.error('--cases and --spec are only valid for prepare')
    identifiers = binder.identifiers(args.operator, args.candidate.split(',') if args.candidate else None)
    specs = read(args.spec) if args.spec else {}
    cases = [int(value) for value in args.cases.split(',')] if args.cases else binder.campaign.manifest['sentinel_case_ids']
    results = [binder.prepare(args.operator, identifier, cases, specs.get(identifier)) if args.action == 'prepare'
               else binder.bind(args.operator, identifier) for identifier in identifiers]
    print(json.dumps(results, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
