#!/usr/bin/env python3
"""CPU-only shared_context_paired_v1 analysis; never invokes hardware or a gate."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics as st

from jsonschema import Draft202012Validator

PROTOCOL = 'shared_context_paired_v1'
ANALYSIS = 'shared_context_analysis_v1'
ROOT = Path(__file__).resolve().parents[1]
T_TWO = 2.570581835636305
T_ONE = 2.0150483733330233
TOL = math.log(1.005)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def strict_load(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate JSON key: ' + key)
            out[key] = value
        return out
    def reject(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=reject)


def finite(value, path='root'):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite number at ' + path)
    if isinstance(value, dict):
        for key, item in value.items():
            finite(item, path + '.' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite(item, path + '[' + str(index) + ']')


def validate_schema(value, filename):
    finite(value)
    schema = strict_load(ROOT / 'schemas' / filename)
    Draft202012Validator(schema).validate(value)


def effect(logs):
    if len(logs) != 6:
        raise ValueError('effect requires exactly six independent process/block effects')
    mean = st.mean(logs)
    sd = st.stdev(logs)
    se = sd / math.sqrt(6)
    lo, hi = mean - T_TWO * se, mean + T_TWO * se
    speeds = [math.exp(x) for x in logs]
    return dict(n=6, df=5, log_effects=list(logs), process_speedups=speeds,
                mean_log=mean, log_sd=sd, log_ci95=[lo, hi],
                speedup=math.exp(mean), ci95=[math.exp(lo), math.exp(hi)],
                lcb95=math.exp(mean - T_ONE * se),
                latency_change=math.expm1(-mean),
                latency_change_ci95=[math.expm1(-hi), math.expm1(-lo)],
                direction_counts={'faster': sum(x > 0 for x in logs),
                                  'equal': sum(x == 0 for x in logs),
                                  'slower': sum(x < 0 for x in logs)},
                speedup_range=[min(speeds), max(speeds)],
                reproducibility_status=('mixed_process_directions' if any(x>0 for x in logs) and any(x<0 for x in logs) else 'requires_independence_and_condition_review'))


def equivalence(summary):
    lo, hi = summary['log_ci95']
    if lo >= -TOL and hi <= TOL:
        return 'equivalent'
    if lo > TOL or hi < -TOL:
        return 'observed_bias'
    return 'precision_insufficient'


def series_summary(values):
    mean = st.mean(values)
    return dict(mean=mean, median=st.median(values), cv=st.stdev(values)/mean,
                minimum=min(values), maximum=max(values))


def slope(values):
    center = (len(values)-1)/2
    return sum((i-center)*x for i,x in enumerate(values))/sum((i-center)**2 for i in range(len(values)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_plan(manifest):
    """Validate the complete frozen design before any hardware process starts."""
    validate_schema(manifest, 'shared-context-manifest.schema.json')
    cases = {c['case_id']: c for c in manifest['cases']}
    require(cases and len(cases) == len(manifest['cases']), 'empty/duplicate case declaration')
    stages = manifest['stages']
    require(stages and len(set(stages)) == len(stages), 'empty/duplicate stages')
    require(manifest['control_identities']['A']['source_hash'] == manifest['control_identities']['B']['source_hash'] == manifest['identities']['A']['source_hash'], 'A/A control source identity mismatch')
    plans = manifest['session_plan']
    plan_by_id = {p['session_id']: p for p in plans}
    require(len(plan_by_id) == len(plans), 'duplicate planned session ID')
    require(set(p['phase'] for p in plans) == set(stages), 'unexpected/missing stage')
    for p in plans:
        require(len(p['case_order']) == len(cases) and set(p['case_order']) == set(cases), 'case order incomplete or duplicated')
    for phase in stages:
        rows = [p for p in plans if p['phase'] == phase]
        if phase == 'qualification':
            require(len(rows) == 12, 'qualification requires 12 sessions')
            require({(p['block_id'],p['load_order']) for p in rows} == {(b,l) for b in range(1,7) for l in ('AB','BA')}, 'qualification block/load coverage')
            for p in rows:
                require(p['replicate_id'] == p['block_id'], 'qualification replicate/block mismatch')
                require(set(p['buffer_configs']) == {'normal','swapped'} and len(p['buffer_configs']) == 2, 'qualification buffer coverage')
            for b in range(1,7):
                block = [p for p in rows if p['block_id'] == b]
                require(block[0]['load_order'] == ('AB' if b%2 else 'BA'), 'qualification load sequence unbalanced')
            for load in ('AB','BA'):
                column = [p for p in rows if p['load_order'] == load]
                require(sum(p['buffer_configs'][0] == 'normal' for p in column) == 3, 'qualification buffer order unbalanced')
                require(sum(p['first_order'] == 'AB' for p in column) == 3, 'qualification pair direction unbalanced')
        else:
            require(len(rows) == 6 and {p['replicate_id'] for p in rows} == set(range(1,7)), phase + ' requires six replicates')
            require(all(p['block_id'] is None and len(p['buffer_configs']) == 1 for p in rows), 'routine phase unexpected configuration')
            require(sum(p['first_order'] == 'AB' for p in rows) == 3, 'routine first pair direction unbalanced')
            expected = 'swapped' if phase == 'reverse' else 'normal'
            require(all(p['buffer_configs'] == [expected] for p in rows), 'routine buffer configuration mismatch')
    return cases, plan_by_id


def validate_inputs(manifest, sessions):
    cases, plan_by_id = validate_plan(manifest)
    plans = manifest['session_plan']
    validate_schema(sessions, 'shared-context-sessions.schema.json')
    require(len(sessions) == len(plans) and {s['session_id'] for s in sessions} == set(plan_by_id), 'missing/duplicate/unexpected session')
    require(len({s['session_id'] for s in sessions}) == len(sessions), 'duplicate session ID')
    sample_ids = set()
    process_ids = set()
    last_time = 0
    # Array order is execution order, and must match the frozen plan.
    require([s['session_id'] for s in sessions] == [p['session_id'] for p in plans], 'session execution order differs from plan')
    for session in sessions:
        sid = session['session_id']; p = plan_by_id[sid]
        require(session['started_at'] > last_time, 'native process starts not strictly ordered')
        require(session['ended_at'] >= session['started_at'], 'session end precedes start')
        last_time = session['ended_at']
        identity = (session['host'], session['pid'], session['started_at'])
        require(identity not in process_ids, 'duplicate native process identity'); process_ids.add(identity)
        require(session['host'] == manifest['hardware']['host'], 'host identity mismatch')
        require(session['exit_code'] == 0, 'failed session retained: ' + sid)
        expected_ids = manifest['identities'] if p['phase'] == 'ab' else manifest['control_identities']
        require(session['identities'] == expected_ids, 'implementation identity mismatch')
        lifecycle = session['lifecycle_events']
        require(all(e['session_id'] == sid for e in lifecycle), 'lifecycle session identity mismatch')
        starts = [e for e in lifecycle if e['type']=='session_start']
        ends = [e for e in lifecycle if e['type']=='session_end']
        require(len(starts)==1 and len(ends)==1, 'missing/duplicate lifecycle start/end')
        start,end = starts[0],ends[0]
        require(lifecycle[0] == start and lifecycle[-1] == end, 'lifecycle ordering mismatch')
        require(all(start[k]==session[k] for k in ('pid','host','started_at','context_id','stream_id')), 'lifecycle creation identity mismatch')
        require(start['load_order']==p['load_order'] and start['first_order']==p['first_order'] and start['device']==manifest['hardware']['logical_device'], 'lifecycle configuration mismatch')
        require(end['exit_code']==0 and end['ended_at']==session['ended_at'], 'lifecycle destruction mismatch')
        expected_lifecycle = [(kind,c,u) for c in p['case_order'] for u in p['buffer_configs'] for kind in ('case_start','warmup_complete','outputs_verified')]
        actual_lifecycle = [(e['type'],e['case_id'],e['buffer_config']) for e in lifecycle[1:-1]]
        require(actual_lifecycle==expected_lifecycle, 'case warmup/output lifecycle incomplete or out of order')
        require(all(e['case_index']==p['case_order'].index(e['case_id']) for e in lifecycle if e['type']=='case_start'), 'case index mismatch')
        resources = session['resource_events']
        resource_keys = [(e['case_id'],e['buffer_config'],e['role']) for e in resources]
        require(len(resource_keys)==len(set(resource_keys)) and set(resource_keys)=={(c,u,r) for c in cases for u in p['buffer_configs'] for r in 'AB'}, 'resource identities incomplete')
        for e in resources:
            buffers=e['buffers']
            require(buffers and [b['index'] for b in buffers]==list(range(len(buffers))), 'resource buffers missing/duplicate indices')
            require({'input','output'} <= {b['kind'] for b in buffers}, 'resource input/output identities missing')
        for c in cases:
            for u in p['buffer_configs']:
                role_buffers = {r:next(e['buffers'] for e in resources if e['case_id']==c and e['buffer_config']==u and e['role']==r) for r in 'AB'}
                addresses = {r:{b['address'] for b in role_buffers[r]} for r in 'AB'}
                require(not addresses['A'].intersection(addresses['B']), 'separate role resources alias')
        expected_keys = [(c,u,j,r) for c in p['case_order'] for u in p['buffer_configs'] for j in range(30) for r in (p['first_order'] if j%2 == 0 else p['first_order'][::-1])]
        actual_keys = [(v['case_id'],v['buffer_config'],v['pair_id'],v['role']) for v in session['samples']]
        require(actual_keys == expected_keys, 'missing/duplicate sample or unexpected case/configuration/order')
        previous_end = session['started_at']
        for v in session['samples']:
            require(previous_end <= v['started_at'] <= v['ended_at'] <= session['ended_at'], 'sample times overlap or leave session')
            previous_end = v['ended_at']
            require(v['sample_id'] not in sample_ids, 'duplicate sample ID'); sample_ids.add(v['sample_id'])
            require(v['session_id'] == sid and v['context_id'] == session['context_id'] and v['stream_id'] == session['stream_id'], 'sample session/context/stream mismatch')
            order = p['first_order'] if v['pair_id']%2 == 0 else p['first_order'][::-1]
            require(v['order'] == order and order[v['position']] == v['role'], 'pair AB/BA order mismatch')
            require(v['to_ns'] == {'ms':1e6,'us':1e3,'ns':1}[v['raw_unit']], 'unit conversion mismatch')
            require(math.isclose(v['ns_per_call'], v['raw_duration']*v['to_ns']/100, rel_tol=1e-10), 'raw timing conversion mismatch')
            role = v['role'] if p['phase'] == 'ab' else 'A'
            require(v['launches_per_call'] == cases[v['case_id']]['launches_per_call'][role], 'incomplete operator launch count')
        outputs = session['outputs']
        expected_outputs = {(c,u,r) for c in cases for u in p['buffer_configs'] for r in 'AB'}
        require(len(outputs) == len(expected_outputs) and {(v['case_id'],v['buffer_config'],v['role']) for v in outputs} == expected_outputs, 'prepared output validation incomplete')
        require(all(v['passed'] for v in outputs), 'prepared output validation failed')
    return cases, plan_by_id


def analyze(manifest, sessions):
    cases, plans = validate_inputs(manifest, sessions)
    cells = []
    for session in sessions:
        p = plans[session['session_id']]
        for c in p['case_order']:
            for u in p['buffer_configs']:
                samples = [v for v in session['samples'] if v['case_id'] == c and v['buffer_config'] == u]
                a = [v['ns_per_call'] for v in samples if v['role'] == 'A']
                b = [v['ns_per_call'] for v in samples if v['role'] == 'B']
                logs = [math.log(x)-math.log(y) for x,y in zip(a,b)]
                orders = [v['order'] for v in samples if v['role'] == 'A']
                strata = {o:st.mean(x for x,k in zip(logs,orders) if k == o) for o in ('AB','BA')}
                cells.append(dict(session_id=session['session_id'],phase=p['phase'],replicate_id=p['replicate_id'],block_id=p['block_id'],case_id=c,buffer_config=u,load_order=p['load_order'],first_order=p['first_order'],started_at=session['started_at'],A=series_summary(a),B=series_summary(b),pair_logs=logs,mean_log=st.mean(logs),speedup=math.exp(st.mean(logs)),pair_log_sd=st.stdev(logs),pair_log_slope=slope(logs),order_log_means=strata,order_log_contrast=strata['AB']-strata['BA']))
    phase_reports = {}
    for phase in manifest['stages']:
        if phase == 'qualification':
            continue
        selected = [v for v in cells if v['phase'] == phase]
        per_case = {c:effect([next(v['mean_log'] for v in selected if v['case_id']==c and v['replicate_id']==r) for r in range(1,7)]) for c in cases}
        suite = effect([st.mean(v['mean_log'] for v in selected if v['replicate_id']==r) for r in range(1,7)])
        order = {c:effect([next(v['order_log_contrast'] for v in selected if v['case_id']==c and v['replicate_id']==r) for r in range(1,7)]) for c in cases}
        strata = {c:{o:effect([next(v['order_log_means'][o] for v in selected if v['case_id']==c and v['replicate_id']==r) for r in range(1,7)]) for o in ('AB','BA')} for c in cases}
        phase_reports[phase] = dict(suite=suite,cases=per_case,order_contrasts=order,order_conditions=strata)
    qualification = {}
    if 'qualification' in manifest['stages']:
        selected = [v for v in cells if v['phase'] == 'qualification']
        for c in cases:
            def q(block,load,buffer,order):
                return next(v['order_log_means'][order] for v in selected if v['case_id']==c and v['block_id']==block and v['load_order']==load and v['buffer_config']==buffer)
            conditions = {l+'/'+u+'/'+o:effect([q(b,l,u,o) for b in range(1,7)]) for l in ('AB','BA') for u in ('normal','swapped') for o in ('AB','BA')}
            contrasts = dict(load=effect([st.mean(q(b,'AB',u,o)-q(b,'BA',u,o) for u in ('normal','swapped') for o in ('AB','BA')) for b in range(1,7)]),buffer=effect([st.mean(q(b,l,'normal',o)-q(b,l,'swapped',o) for l in ('AB','BA') for o in ('AB','BA')) for b in range(1,7)]),order=effect([st.mean(q(b,l,u,'AB')-q(b,l,u,'BA') for l in ('AB','BA') for u in ('normal','swapped')) for b in range(1,7)]))
            qualification[c] = dict(conditions=conditions,contrasts=contrasts)
    failures = []
    for v in cells:
        for role in 'AB':
            if v[role]['cv'] > .05:
                failures.append(dict(check='within_process_cv',location='/'.join([v['session_id'],v['case_id'],v['buffer_config'],role]),status='exceeds_0.05'))
    for phase,data in phase_reports.items():
        if phase == 'ab':
            continue
        summaries = [(c,x) for c,x in data['cases'].items()] + [('order/'+c,x) for c,x in data['order_contrasts'].items()] + [('condition/'+c+'/'+o,x) for c,items in data['order_conditions'].items() for o,x in items.items()]
        for loc,x in summaries:
            if equivalence(x) != 'equivalent':
                failures.append(dict(check='aa_equivalence',location=phase+'/'+loc,status=equivalence(x)))
    for c,data in qualification.items():
        for kind,items in data.items():
            for key,x in items.items():
                if equivalence(x) != 'equivalent':
                    failures.append(dict(check='aa_equivalence',location='qualification/'+c+'/'+kind+'/'+key,status=equivalence(x)))
    drift = {}
    for c in cases:
        drift[c] = {}
        for phase in manifest['stages']:
            selected = [v for v in cells if v['case_id']==c and v['phase']==phase]
            medians = {r:[v[r]['median'] for v in selected] for r in 'AB'}
            aa,bb = medians['A'],medians['B']
            covariance = sum((x-st.mean(aa))*(y-st.mean(bb)) for x,y in zip(aa,bb))/(len(aa)-1)
            drift[c][phase] = dict(session_ids=[v['session_id'] for v in selected],buffer_configs=[v['buffer_config'] for v in selected],started_at=[v['started_at'] for v in selected],A_medians=aa,B_medians=bb,A_relative_range=max(aa)/min(aa)-1,B_relative_range=max(bb)/min(bb)-1,covariance=covariance,diagnostic_only=True)
    ab = phase_reports.get('ab')
    max_regression = max((x['latency_change'] for x in ab['cases'].values()), default=0) if ab else None
    complete_controls = all(p in manifest['stages'] for p in ('before','reverse','after'))
    report = dict(protocol_version=PROTOCOL,analysis_version=ANALYSIS,manifest_hash=digest(manifest),sessions_hash=digest(sessions),case_attributes={c:cases[c]['attributes'] for c in cases},measurement_quality=dict(structurally_complete=True,observed_checks_pass=not failures,failures=failures,method_qualification='evaluated_here' if qualification else 'external_scope_required',routine_controls_complete=complete_controls),cells=cells,phases=phase_reports,qualification=qualification,absolute_drift=drift,research_screen=dict(evaluated=bool(ab),suite_lcb_at_least_1_03=ab['suite']['lcb95'] >= 1.03 if ab else None,max_case_point_regression=max_regression,max_case_point_regression_at_most_0_03=max_regression <= .03 if ab else None,quality_checks_pass=not failures and complete_controls),formal_admission='not_evaluated',limitations=['Six independent process/block log effects; Student t assumptions are not proven by new PIDs.','Absolute drift is diagnostic and has no blanket 2% rejection rule.','Per-case intervals are marginal, not simultaneous guarantees.','Method qualification coverage and mechanism evidence require separate review.','Research screening is not a runtime gate verdict.'])
    finite(report)
    validate_schema(report, 'shared-context-report.schema.json')
    return report


def verify_report(manifest, sessions, report):
    """Read-only verification against all frozen raw inputs and deterministic analysis."""
    validate_schema(report, 'shared-context-report.schema.json')
    expected = analyze(manifest, sessions)
    require(canonical(report) == canonical(expected), 'report does not match frozen raw data/recomputed analysis')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('analyze','verify'))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--sessions', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    manifest, sessions = strict_load(args.manifest), strict_load(args.sessions)
    if args.command == 'verify':
        verify_report(manifest, sessions, strict_load(args.report))
        print('verified (read-only; formal admission not evaluated)')
    else:
        report = analyze(manifest, sessions)
        with Path(args.report).open('xb') as output:
            output.write(canonical(report))
        print(args.report)


if __name__ == '__main__':
    main()
