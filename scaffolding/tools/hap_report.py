#!/usr/bin/env python3
"""HAP_sow reporting over frozen runtime replay results; never issue an engineering verdict."""
import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import os
HERE = Path(__file__).resolve().parent
SKILL = Path(os.environ.get('APROF_SKILL_LIB', str(HERE.parents[1]/'skill-libs/graph-base/1.2.0')))
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL / 'runtime/src'))
from aprof_runtime import unified_timing as timing
from aprof_runtime.execution_policy import local_path
ANCHOR = None
PROMPT = Path(__file__)
CASE_IDS = list(range(1, 21))
FORMULA_VERSION = 'HAP_sow.v1'
THRESHOLD = Fraction(7, 20)


def file_ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': timing.file_hash(path)}


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def hap_values(B, H, C):
    """Use exact decimal spellings of unrounded inputs for the 7/20 comparison."""
    result = {'B_us': B, 'H_us': H, 'C_us': None, 'C_target_us': None,
              'HAP_sow': None, 'threshold_met': None, 'anchor_valid': False,
              'at_or_below_H': None, 'exact_score_fraction': None, 'exact_target_fraction': None}
    if not positive(B) or not positive(H) or B <= H:
        return result
    b, h = Fraction(str(B)), Fraction(str(H))
    target = h + Fraction(13, 7) * (b-h)
    result.update(anchor_valid=True, C_target_us=float(target), exact_target_fraction=str(target))
    if not positive(C):
        return result
    c = Fraction(str(C)); score = Fraction(1) if c <= h else (b-h)/((c-h)+(b-h))
    result.update(C_us=C, HAP_sow=float(score), threshold_met=score >= THRESHOLD,
                  at_or_below_H=c <= h, exact_score_fraction=str(score))
    return result


def anchor_cases(anchor, operator):
    hits = [(level, data[operator]) for level, data in anchor.items()
            if level != '_metadata' and isinstance(data, dict) and operator in data]
    if len(hits) != 1:
        raise ValueError('operator anchor missing or ambiguous: ' + operator)
    return hits[0]


def normalize_replay(replay, capture_path, *, evaluated_at=None):
    """Input must be the actual return value of frozen timing.replay_capture in this process."""
    capture = replay['capture']; path = Path(capture_path).resolve()
    if timing.file_hash(path) != replay['capture_ref']:
        raise ValueError('capture changed after runtime replay')
    decl = timing.declaration(path.parent, capture['artifacts']['declaration'])
    hardware = timing.read_json(timing.reference(path.parent, capture['artifacts']['hardware']))
    when = evaluated_at or datetime.now(timezone.utc).isoformat()
    age = timing.timestamp(when) - timing.timestamp(capture['captured_at'])
    stats = replay.get('sample_statistics')
    reasons = []
    if stats is None or stats.get('policy') != 'bounded_outlier_v1':
        reasons.append('missing_current_stability_policy')
    if len(replay['values_us']) != 20:
        reasons.append('complete_call_count_not_20')
    if stats and stats.get('exclusion_limit_exceeded'):
        reasons.append('outlier_limit_exceeded')
    if not math.isfinite(replay['within_process_cv']) or replay['within_process_cv'] > .05:
        reasons.append('within_process_cv_over_limit')
    if age < 0 or age > decl['reuse_policy']['max_age_seconds']:
        reasons.append('outside_declared_capture_age')
    receipt = timing.read_json(timing.reference(path.parent, capture['artifacts']['oracle_receipt']))
    assumed = receipt.get('status') == 'assumed'
    return {'case_id': capture['case_id'], 'operator': capture['operator'],
            'capture': {'path': str(path), 'sha256': replay['capture_ref']},
            'identity': dict(capture['identity']), 'hardware': hardware, 'declaration_ref': capture['declaration_ref'],
            'captured_at': capture['captured_at'], 'evaluated_at': when,
            'capture_age_seconds': age, 'correctness_valid': None if assumed else True,
            'correctness_status': 'assumed' if assumed else 'verified',
            'correctness_basis': 'user_provided_baseline' if assumed else 'actual_oracle_or_authenticated_content_reuse',
            'timing_valid': not reasons, 'validation_reasons': reasons,
            'observed_median_us': replay['median_us'], 'sample_statistics': stats,
            'raw_values_us': list(replay['values_us']),
            'raw_median_us': stats['raw_median_us'] if stats else None,
            'retained_median_us': stats['median_us'] if stats else None,
            'raw_cv': stats['raw_cv'] if stats else None,
            'retained_cv': stats['cv'] if stats else replay['within_process_cv'],
            'outlier_indices': stats['outlier_indices'] if stats else None,
            'excluded_indices': stats['excluded_indices'] if stats else None,
            'retained_count': stats['retained_count'] if stats else None,
            'outlier_threshold_us': stats['outlier_threshold_us'] if stats else None,
            'exclusion_limit_exceeded': stats['exclusion_limit_exceeded'] if stats else None}


def score_rows(anchor, operator, rows, *, global_errors=None):
    """Pure reporting layer; caller supplies normalized actual-runtime evidence, not new verdicts."""
    level, anchors = anchor_cases(anchor, operator)
    by_case = {}
    for row in rows:
        cid = row['case_id']
        if type(cid) is not int or cid not in CASE_IDS or cid in by_case:
            raise ValueError('unexpected or duplicate case; selecting one would hide evidence')
        if row.get('operator') != operator:
            raise ValueError('mixed operators')
        by_case[cid] = row
    errors = list(global_errors or [])
    complete_identities = [row.get('identity') for row in rows if row.get('identity')]
    for key in ['source_sha256', 'binary_sha256', 'toolchain_ref', 'collector_ref']:
        if len({identity.get(key) for identity in complete_identities}) > 1:
            errors.append('mixed_' + key)
    if len({row.get('declaration_ref') for row in rows if row.get('declaration_ref')}) > 1:
        errors.append('mixed_declaration_ref')
    if len({row['hardware'].get('physical_device') for row in rows if row.get('hardware')}) > 1:
        errors.append('mixed_physical_device')
    result = []
    for cid in CASE_IDS:
        entry = anchors.get(str(cid)); row = by_case.get(cid)
        B = entry.get('baseline_perf_us') if isinstance(entry, dict) else None
        H = entry.get('t_hw_us') if isinstance(entry, dict) else None
        evidence_valid = bool(row and (row.get('correctness_valid') is True or row.get('correctness_status') == 'assumed') and row.get('timing_valid') is True)
        C = row.get('observed_median_us') if evidence_valid else None
        numbers = hap_values(B, H, C)
        reasons = list(row.get('validation_reasons', [])) if row else ['missing_case']
        if not numbers['anchor_valid']:
            reasons.append('invalid_or_missing_anchor_B_must_exceed_H_positive')
        if row and not evidence_valid and not reasons:
            reasons.append('correctness_or_timing_not_valid')
        if evidence_valid and not positive(C):
            reasons.append('invalid_C')
        qualified = evidence_valid and numbers['anchor_valid'] and numbers['threshold_met'] is True
        row_fields = ['correctness_status', 'correctness_basis', 'correctness_valid', 'timing_valid', 'raw_median_us', 'retained_median_us', 'raw_cv', 'retained_cv',
                      'outlier_indices', 'excluded_indices', 'retained_count', 'outlier_threshold_us', 'exclusion_limit_exceeded',
                      'raw_values_us', 'capture', 'identity', 'hardware', 'captured_at', 'evaluated_at', 'sample_statistics']
        result.append({'case_id': cid, **numbers, **{key: row.get(key) if row else None for key in row_fields},
                       'observed_median_us': row.get('observed_median_us') if row else None,
                       'case_qualified': bool(qualified), 'validation_reasons': reasons,
                       'anchor_entry': entry, 'anchor_entry_pointer': '/' + level + '/' + operator + '/' + str(cid),
                       'anchor_case_source_classification': 'unknown; frozen entry has no per-case measured/capped/proxy tag',
                       'requires_below_anchor_timing_review': numbers['at_or_below_H'] is True})
    missing = [cid for cid in CASE_IDS if cid not in by_case]
    valid = [row['case_id'] for row in result if (row['correctness_valid'] is True or row.get('correctness_status') == 'assumed') and row['timing_valid'] is True and row['anchor_valid'] and positive(row['C_us'])]
    qualified_ids = [row['case_id'] for row in result if row['case_qualified']]
    return {'schema_version': 1, 'kind': 'hap_sow_report', 'operator': operator, 'case_ids': CASE_IDS,
            'formula_version': FORMULA_VERSION, 'threshold': .35, 'threshold_exact_fraction': '7/20',
            'comparison': 'exact rational arithmetic over original unrounded decimal input representations; no rounding before >= 7/20',
            'formula': 'B>H>0; C<=H:1; C>H:(B-H)/((C-H)+(B-H)); C_target=H+(13/7)*(B-H)',
            'anchor_level': level, 'anchor_metadata': anchor.get('_metadata'),
            'anchor_provenance': 'B is the frozen published baseline_perf_us, possibly capped measured value or t_hw-derived proxy; H is frozen t_hw_us. No per-case source tags are present; no provenance is inferred from numerical equality.',
            'reference_disclosure': '执行设备以实际capture硬件证据为准；HAP参考锚点为冻结版本的cannBench 910B2发布数据。跨平台参考评分不代表平台性能等效。',
            'cases': result, 'missing_case_ids': missing,
            'invalid_case_ids': [cid for cid in CASE_IDS if cid not in valid and cid not in missing],
            'below_threshold_case_ids': [row['case_id'] for row in result if row['threshold_met'] is False],
            'valid_case_count': len(valid), 'qualified_case_count': len(qualified_ids),
            'complete_20_valid_cases': len(valid) == 20 and not errors,
            'operator_hap_qualified': len(qualified_ids) == 20 and not errors and all(r.get('correctness_status') != 'assumed' for r in result),
            'operator_hap_qualified_under_assumption': len(qualified_ids) == 20 and not errors,
            'baseline_correctness_assumed': any(r.get('correctness_status') == 'assumed' for r in result),
            'global_errors': errors, 'runtime_verdict': None,
            'runtime_verdict_authority': 'Only aprofctl timing finalize may produce accepted/rejected/inconclusive; this helper produces none.',
            'limits': 'HAP qualification is independent of speedup versus local seed and engineering verdict. No R0 self-comparison verdict is invented.'}


def summarize_replays(operator, replays, anchor_path=ANCHOR, *, evaluated_at=None):
    """Same-process fast path: [(capture_path, actual replay_capture return value), ...]."""
    started = time.monotonic()
    rows = [normalize_replay(value, path, evaluated_at=evaluated_at) for path, value in replays]
    anchor = timing.read_json(anchor_path)
    result = score_rows(anchor, operator, rows)
    result['evidence'] = {'anchor': file_ref(anchor_path), 'formula_source': file_ref(PROMPT),
                          'helper': file_ref(__file__), 'runtime': file_ref(timing.__file__)}
    result['reporting_costs'] = {'elapsed_seconds': time.monotonic()-started,
                               'oracle_replay_cost': 'caller must separately retain the costs of the supplied real runtime replays',
                               'capture_timestamps_modified': False}
    return result


def summarize_collection(collection_path, operator, anchor_path=ANCHOR, *, verified=None, timeout_seconds=600):
    """verified may only be an in-memory set populated by genuine frozen-runtime oracle execution."""
    if not positive(timeout_seconds):
        raise ValueError('timeout_seconds must be positive and finite')
    started = time.monotonic(); deadline = started + timeout_seconds
    path = Path(collection_path).resolve(); collection = timing.read_json(path)
    if collection.get('protocol') != timing.PROTOCOL or not isinstance(collection.get('captures'), list):
        raise ValueError('expected actual single_role_task.py collection.json')
    rows = []; errors = []; replay_costs = []
    verified = set() if verified is None else verified
    for ref in collection['captures']:
        began = time.monotonic(); capture_path = None; case_id = None
        try:
            capture_path = timing.reference(path.parent, ref)
            record = timing.read_json(capture_path); case_id = record.get('case_id')
            replay = timing.replay_capture(capture_path, deadline=deadline, verified=verified)
            row = normalize_replay(replay, capture_path)
        except Exception as error:
            reason = getattr(error, 'reason', type(error).__name__)
            if type(case_id) is int and case_id in CASE_IDS:
                row = {'case_id': case_id, 'operator': operator, 'correctness_valid': False if reason == 'numerical_mismatch' else None,
                       'timing_valid': False, 'validation_reasons': [reason + ': ' + str(error)],
                       'capture': file_ref(capture_path) if capture_path and capture_path.is_file() else None}
            else:
                errors.append({'capture_reference': ref, 'reason': reason, 'message': str(error)})
                row = None
        if row is not None:
            rows.append(row)
        replay_costs.append({'case_id': case_id, 'elapsed_seconds': time.monotonic()-began})
    result = score_rows(timing.read_json(anchor_path), operator, rows, global_errors=errors)
    result['evidence'] = {'collection': file_ref(path), 'anchor': file_ref(anchor_path), 'formula_source': file_ref(PROMPT),
                          'helper': file_ref(__file__), 'runtime': file_ref(timing.__file__)}
    result['reporting_costs'] = {'elapsed_seconds': time.monotonic()-started, 'case_replays': replay_costs,
                               'kind': 'CPU evidence/oracle replay and reporting; no NPU execution',
                               'capture_timestamps_modified': False,
                               'target_seconds': timeout_seconds, 'budget_warnings': ['target_exceeded'] if time.monotonic()>deadline else [],
                               'cache_policy': 'task-local authenticated content cache; explicit audit bypasses reuse'}
    return result


def write_report(result, output):
    root = local_path(output); root.mkdir(parents=True, exist_ok=False)
    (root / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    columns = ['case_id', 'B_us', 'H_us', 'C_us', 'C_target_us', 'HAP_sow', 'correctness_valid', 'timing_valid',
               'case_qualified', 'raw_median_us', 'retained_median_us', 'raw_cv', 'retained_cv', 'retained_count',
               'outlier_indices', 'excluded_indices', 'exclusion_limit_exceeded', 'validation_reasons']
    with (root / 'cases.tsv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, columns, delimiter='\t'); writer.writeheader()
        for row in result['cases']:
            writer.writerow({key: 'null' if row.get(key) is None else json.dumps(row[key]) if isinstance(row[key], (list, dict, bool)) else row[key] for key in columns})
    return root / 'summary.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--anchor', required=True)
    parser.add_argument('--output', required=True, help='new output directory; existing directories are refused')
    parser.add_argument('--timeout-seconds', type=float, default=600)
    args = parser.parse_args()
    summary = summarize_collection(args.collection, args.operator, args.anchor, timeout_seconds=args.timeout_seconds)
    print(write_report(summary, args.output))
