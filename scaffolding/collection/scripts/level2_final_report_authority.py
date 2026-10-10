"""Data-only admission of a separately committed retrospective final-report audit.

This module does not replay native analysis, import archived Python, execute a
campaign transition, publish anything, or claim capture-time report authority.
All I/O is supplied by a trusted logical-byte reader. The returned storage_catalog
must accompany portable authority; its tar objects must be streamed, not loaded
through the metadata callback. Existing v1 attestations are deliberately excluded.
"""
from pathlib import Path
import hashlib
import json
import re

VERSION = 'level2_final_report_consistency_attestation_v2'
KIND = 'retrospective_final_report_authority_v1'
EVENT = 'final_report_consistency_attested'
TIMING = 'retrospective_audit_now_not_original_measurement'
CLAIM = 'Retained evidence and saved final reports were consistent at this retrospective audit; no earlier report authority is asserted.'
# Explicit review boundary. A later writer needs its own reviewed immutable row.
APPROVED_WRITERS = {
    'sha256:ad40092950da21cefbe9a35bd9f27e7dff690caee904e0a923cda9611283de1e': VERSION,
    'sha256:de18e5fed791d14dcc3a4db979a274b40c7ad8da79cf1da023fc244f6ca3d832': VERSION,
    'sha256:9deebeb3d3246d778aa58476792198ba2079f25b21133bee175c64121cc86227': VERSION,
}
APPROVED_PROFILE_HASHES = {
    'sha256:ad40092950da21cefbe9a35bd9f27e7dff690caee904e0a923cda9611283de1e': 'sha256:35683c778eb0f97b9633ec64855bd905e8a3ac42d1a7010193eb1a1e00a24d99',
    'sha256:de18e5fed791d14dcc3a4db979a274b40c7ad8da79cf1da023fc244f6ca3d832': 'sha256:e3d04146c58a4002ba709b29afffe87ca334739a499efcf94c12d244e8719928',
    'sha256:9deebeb3d3246d778aa58476792198ba2079f25b21133bee175c64121cc86227': 'sha256:0e4aaea5fc12539c241cf0a3a63486195fef8485e03db5297226a52c13be69bd',
}
# Repository layout migration writer
# Historical writer/profile rows remain unchanged; this row binds the relocated code.
APPROVED_WRITERS['sha256:f6c018611301273dd2ee402c8a4d95b548a1e4c4c99b586a5be12023e275e426'] = VERSION
APPROVED_PROFILE_HASHES['sha256:f6c018611301273dd2ee402c8a4d95b548a1e4c4c99b586a5be12023e275e426'] = 'sha256:3afb503006cfa399dae8c3c2b31f4fa1e6364d94cfa00d507b4019d773300b9e'
# Gather search recovery uses the reviewed v5 raw reader and its own frozen
# engineering profile. Historical writer/profile rows above remain unchanged.
APPROVED_WRITERS['sha256:83d94118c0979e70bb050a0ef25d26f24d07e6b701e23a0a3a0cfb3bd5394289'] = VERSION
APPROVED_PROFILE_HASHES['sha256:83d94118c0979e70bb050a0ef25d26f24d07e6b701e23a0a3a0cfb3bd5394289'] = 'sha256:de6a9e2641b8ac1bc75a2f553d8733c341fedcc46132b618cdb29efda7c514e3'
# End layout migration
ALL_CASES = list(range(1, 21))
MAX_METADATA = 32 * 1024 * 1024


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def path(value):
    require(isinstance(value, (str, Path)), 'invalid logical path')
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts and str(p) == str(value), 'noncanonical logical path')
    return p


def pointer(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'invalid exact pointer')
    path(value['path'])
    require(isinstance(value['sha256'], str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value['sha256']), 'invalid pointer digest')
    return value


def decode(data):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


class Reader:
    def __init__(self, read_bytes):
        self.read_bytes = read_bytes
        self.protected = {}

    def raw(self, value, expected=None, *, protect=True):
        p = path(value)
        data = self.read_bytes(p)
        require(isinstance(data, bytes) and len(data) <= MAX_METADATA, 'authority metadata exceeds bound')
        ref = {'path': str(p), 'sha256': digest(data)}
        require(expected is None or ref == pointer(expected), 'bound authority bytes differ: ' + str(p))
        if protect:
            require(str(p) not in self.protected or self.protected[str(p)] == ref, 'authority changed during read')
            self.protected[str(p)] = ref
        return data

    def document(self, value, expected=None):
        return decode(self.raw(value, expected))

    def checked(self, ref):
        return self.document(pointer(ref)['path'], ref)

    def proof_refs(self, value):
        if isinstance(value, dict):
            if {'path', 'sha256'} <= value.keys():
                self.raw(value['path'], {k: value[k] for k in ('path', 'sha256')})
            for key, item in value.items():
                if key != 'origin': self.proof_refs(item)
        elif isinstance(value, list):
            for item in value: self.proof_refs(item)

    def ref(self, value):
        self.raw(value)
        return self.protected[str(value)]


def public_events(data):
    require(not data or data.endswith(b'\n'), 'incomplete public event tail')
    result = []; previous = None
    for n, line in enumerate(data.splitlines()):
        row = decode(line)
        require(set(row) == {'sequence', 'recorded_at', 'kind', 'previous_hash', 'value', 'hash'}
                and type(row['sequence']) is int and row['sequence'] == n
                and row['previous_hash'] == previous
                and row['hash'] == digest(canonical({k: v for k, v in row.items() if k != 'hash'})),
                'public event chain differs')
        previous = row['hash']; result.append(row)
    return result


def ledger_events(data, config_hash):
    require(data and data.endswith(b'\n'), 'incomplete ledger prefix')
    rows = []; previous = 'sha256:' + '0' * 64; ids = set()
    for n, line in enumerate(data.splitlines()):
        row = decode(line)
        require(set(row) == {'sequence', 'event_id', 'operation', 'arguments', 'recorded_at', 'previous_hash', 'config_hash', 'hash'}
                and packed(row) == line and type(row['sequence']) is int and row['sequence'] == n
                and row['previous_hash'] == previous and row['config_hash'] == config_hash
                and row['hash'] == digest(packed({k: v for k, v in row.items() if k != 'hash'}))
                and isinstance(row['event_id'], str) and row['event_id'] and row['event_id'] not in ids
                and isinstance(row['arguments'], dict), 'ledger hash/identity chain differs')
        if n == 0:
            require(row['operation'] == 'prepare' and row['event_id'] == 'genesis' and row['arguments'] == {}, 'ledger genesis differs')
        previous = row['hash']; ids.add(row['event_id']); rows.append(row)
    return rows


def projection(rows, operator):
    """Only the immutable source/stage/observation/freeze identities, no executor."""
    registered = {}; starts = {}; finishes = {}; counts = {}; observed = {}; freeze = None
    open_stages = set(); seen_counts = {}; frozen_candidates = None; qualified_recoveries = set()
    for position,row in enumerate(rows[1:],1):
        a = row['arguments']; op = row['operation']
        if a.get('workload') != operator:
            continue
        if op == 'register':
            cid = a['candidate_id']
            require(freeze is None and cid not in registered, 'duplicate or post-freeze registration')
            registered[cid] = a
        elif op == 'start':
            sid = a['stage_id']
            require(sid not in open_stages, 'stage starts while still active')
            if sid in starts:
                if sid in qualified_recoveries:
                    from level2_stage_recovery import project_stage
                    projected=project_stage(rows[:position+1],operator,sid)
                    require(starts[sid]==a and counts[sid]==1 and len(projected['attempts'])==2
                            and projected.get('prestart_recovery') is not None,'unsupported qualified final retry')
                else:
                    require(starts[sid] == a and finishes[sid].get('outcome') == 'prestart_failure'
                            and finishes[sid].get('native_started') is False and counts[sid] == 1,
                            'unsupported stage identity/retry')
            starts[sid] = a; finishes.pop(sid, None); counts[sid] = counts.get(sid, 0) + 1; open_stages.add(sid)
        elif op == 'qualify_prestart':
            sid=a['stage_id']
            require(sid in starts and sid in finishes and sid not in open_stages
                    and sid not in qualified_recoveries and counts[sid]==1
                    and starts[sid]['kind']=='timing'
                    and ((freeze is None and starts[sid]['plan'].get('purpose')=='search'
                          and starts[sid]['candidate_id'] in registered)
                         or (freeze is not None and starts[sid]['plan'].get('purpose')=='final'
                             and starts[sid]['candidate_id'] in freeze['candidate_ids'])),
                    'prestart qualification is outside an eligible search or frozen final stage')
            from level2_stage_recovery import project_stage
            projected=project_stage(rows[:position+1],operator,sid)
            require(projected.get('prestart_recovery')==a,'qualified recovery projection differs')
            qualified_recoveries.add(sid)
        elif op == 'finish':
            sid = a['stage_id']; require(sid in open_stages, 'finish without active original stage')
            finishes[sid] = a; open_stages.remove(sid)
        elif op == 'observe':
            cid = a['candidate_id']; require(cid in registered, 'observation source is unregistered')
            ids = a.get('stage_ids', [])
            require(isinstance(ids, list) and ids and len(ids) == len(set(ids))
                    and all(s in finishes and starts[s]['candidate_id'] == cid for s in ids), 'observation stage identity differs')
            seen = seen_counts.setdefault(cid, {})
            if a.get('close_feedback') is True:
                require(not any(starts[s]['candidate_id'] == cid for s in open_stages)
                        and all(s in ids or seen.get(s) == counts[s] for s in starts if starts[s]['candidate_id'] == cid),
                        'closed source observation omits an attempt')
            for sid in ids: seen[sid] = counts[sid]
            observed[cid] = a
        elif op == 'freeze':
            require(freeze is None and not open_stages and len(registered) == 3
                    and all(observed.get(c, {}).get('close_feedback') is True for c in registered),
                    'freeze lacks three genuinely closed attempts')
            freeze = a; frozen_candidates = list(registered)
        else:
            require(op in ('checkpoint', 'resume'), 'unknown task ledger operation')
    require(freeze is not None and not open_stages and list(registered) == frozen_candidates, 'final ledger prefix is not closed/frozen')
    return registered, starts, finishes, observed, freeze


def ledger_costs(rows, config):
    used={op:dict(task['inherited_used']) for op,task in config['tasks'].items()}
    seen=set()
    for row in rows[1:]:
        a=row['arguments']; op=a.get('workload')
        if row['operation']=='register':
            require(op in used,'unknown charged workload');used[op]['source']+=1
        elif row['operation']=='start':
            require(op in used,'unknown started workload')
            key=(op,a['stage_id']);kind=a['kind'];cost={'build':'build','timing':'timing_groups','profile':'profile_groups'}.get(kind)
            if a['candidate_id'] is not None and cost and (kind=='build' or key not in seen):used[op][cost]+=1
            seen.add(key)
    return used


def storage_catalog(value, evidence):
    require(isinstance(value, dict) and set(value) == {'version', 'origins', 'archives', 'closed_evidence'}
            and value['version'] == 'level2_attestation_storage_closure_v1', 'unknown attestation storage catalog')
    require(all(isinstance(value[k], dict) for k in ('origins', 'archives', 'closed_evidence')), 'invalid storage catalogs')
    for origin, row in value['origins'].items():
        require(set(row) == {'sha256', 'seal'} and evidence.get(origin) == row['sha256']
                and row['seal'] in value['archives'], 'storage origin is outside attested exact evidence')
        pointer({'path': origin, 'sha256': row['sha256']})
    require(set(value['archives']) == {v['seal'] for v in value['origins'].values()}, 'orphan/dropped storage archive')
    for sha, row in value['archives'].items():
        require(set(row) == {'version', 'seal', 'archive', 'producer', 'closed_evidence_ref'}
                and row['version'] in ('level2_closed_verification_storage_v1', 'level2_closed_verification_storage_v2',
                                       'level2_closed_verification_storage_v3', 'level2_closed_native_outputs_v1',
                                       'level2_closed_raw_storage_v1', 'level2_closed_raw_storage_v2', 'level2_closed_raw_storage_v3', 'level2_closed_raw_storage_v4')
                and pointer(row['seal'])['sha256'] == sha and row['closed_evidence_ref'] in value['closed_evidence'], 'invalid compact archive')
        pointer(row['archive']); pointer(row['producer'])
    require(set(value['closed_evidence']) == {v['closed_evidence_ref'] for v in value['archives'].values()}, 'orphan/dropped nested proof')
    for sha, row in value['closed_evidence'].items():
        require(digest(canonical(row)) == sha, 'nested storage proof differs')
    return value


def report_replay(reader, proof, expected, evidence):
    require(set(proof) == {'report', 'plan', 'completion', 'source_hashes', 'saved_digest', 'replayed_digest',
                           'comparison', 'observation_producers', 'session_directories'}, 'report replay shape differs')
    for key in ('report', 'plan', 'completion', 'source_hashes'):
        require(proof[key] == expected[key], 'replay comparison source/slot differs: ' + key)
    directory = path(proof['report']['path']).parent
    report = reader.checked(proof['report']); plan = reader.checked(proof['plan']); completion = reader.checked(proof['completion'])
    names = [r['name'] for r in plan['schedule']]
    require(len(names) == len(set(names)) == 6 and all(isinstance(n, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', n)
            and n not in ('.', '..') for n in names), 'invalid six-process schedule')
    sessions = [str(directory / n) for n in names]
    require(proof['session_directories'] == sessions == completion['completed_sessions'] == [v['directory'] for v in report['sessions']]
            and completion['status'] == 'passed' and completion.get('error') is None, 'six-process closure differs')
    require(report['case_ids'] == list(map(str, ALL_CASES)) and plan['case_ids'] == ALL_CASES
            and report['evidence_status'] == 'verified_complete' and report['source_hashes'] == proof['source_hashes']
            and report['comparison_kind'] == plan['comparison_kind'] == expected['comparison_kind'], 'full report coverage/source differs')
    cells = [(v['case_id'], v['buffer_config']) for v in report['results']]
    require(len(cells) == 40 and set(cells) == {(str(c), b) for c in ALL_CASES for b in ('normal', 'swapped')}, 'report result roster differs')
    require(proof['saved_digest'] == digest(canonical(report)), 'saved report digest differs')
    matched = proof['comparison']['comparison']
    require(matched.get('matched') is True and matched.get('comparison') in ('exact', 'all_observation_fields_equal_with_attested_analyzer_update'),
            'audit did not establish observation equality')
    if matched['comparison'] == 'exact':
        require(proof['replayed_digest'] == proof['saved_digest'], 'exact audit replay digest differs')
    else:
        require(proof['comparison'].get('historical_producers')
                and matched.get('saved_analysis_producer_hash') == report.get('analysis_producer_hash')
                and re.fullmatch(r'sha256:[0-9a-f]{64}', matched.get('reanalysis_producer_hash', '')), 'unproven analyzer-only exception')
        adjusted = dict(report, analysis_producer_hash=matched['reanalysis_producer_hash'])
        require(proof['replayed_digest'] == digest(canonical(adjusted)), 'observation changed beyond analyzer identity')
    reader.proof_refs(proof['comparison'].get('historical_producers', []))
    reader.proof_refs(proof['observation_producers'])
    historical = {p.get('origin', {}).get('path'): p for p in proof['observation_producers']}
    for session in report['sessions']:
        require(isinstance(session['artifacts'], dict), 'missing report artifact identities')
        for logical, sha in session['artifacts'].items():
            pointer({'path': logical, 'sha256': sha})
            if evidence.get(logical) != sha:
                h = historical.get(logical, {})
                require(h.get('origin') == {'path': logical, 'sha256': sha}
                        and h.get('snapshot', {}).get('sha256') == sha
                        and evidence.get(h.get('snapshot', {}).get('path')) == sha, 'report artifact omitted from attested evidence')
    return report


def authority(session, read_bytes):
    """Return an independently committed *current audit* report binding.

    Protected refs are only bounded metadata read by this validator. The compact
    storage_catalog is a separate mandatory portable closure: retaining this JSON
    alone never proves that its archived payload objects were exported.
    """
    session = path(session); cohort = session.parent
    require(cohort.name in ('direct_parent', 'original_baseline') and cohort.parent.name == 'final'
            and cohort.parent.parent.name == 'stages' and cohort.parents[3].name == 'candidates', 'not a canonical final comparison')
    candidate = cohort.parents[2].name; task = cohort.parents[4]; operator = task.name
    require(task.parent.name == 'tasks' and task.parents[1].name in ('train', 'validation'), 'unknown final task path')
    run = task.parents[2]; ledger = task.parents[1] / 'ledger'; reader = Reader(read_bytes)
    manifest = reader.document(task / 'manifest.json')
    require(manifest.get('version') == 'msprof_task_time_exploration_v2' and manifest.get('operator') == operator
            and manifest.get('task_dir') == str(task), 'foreign/nonfresh task')
    event_path = task / 'events.jsonl'; event_data = reader.raw(event_path, protect=False)
    events = public_events(event_data); target = reader.ref(cohort / 'report.json')
    found = []
    for row in events:
        if row['kind'] != EVENT: continue
        v = row['value']
        require(isinstance(v, dict), 'invalid attestation event')
        if v.get('operator') != operator: continue
        pointer(v.get('attestation'))
        att = reader.checked(v['attestation'])
        if att.get('version') != VERSION: continue  # old protocol conveys no new authority
        if any(p.get('candidate_id') == candidate and p.get('relation') == cohort.name
               and p.get('report') == target for p in att.get('comparisons', [])):
            found.append((row, att))
    require(len(found) == 1, 'no unique separately committed current final-report audit')
    event, att = found[0]; ev = event['value']; directory = path(ev['attestation_directory'])
    require(set(ev) == {'operator', 'attestation_id', 'attestation_directory', 'finalization_request', 'attestation', 'authority_timing'}
            and directory.parent == task / 'finalization' and ev['attestation']['path'] == str(directory / 'attestation.json')
            and ev['authority_timing'] == TIMING, 'foreign attestation event slot')
    require(set(att) == {'version', 'status', 'kind', 'operator', 'attestation_id', 'audited_at', 'request', 'comparisons',
                        'historical_report_authority', 'native_executed', 'costs_unchanged_during_audit', 'formal_admission',
                        'graph_policy_eligible', 'episode_ref', 'selected_candidate_id', 'claim'}
            and att['status'] == 'passed' and att['kind'] == 'retrospective_full_report_replay' and att['operator'] == operator
            and att['historical_report_authority'] is False and att['native_executed'] is False
            and att['costs_unchanged_during_audit'] is True and att['formal_admission'] == 'not_evaluated'
            and att['graph_policy_eligible'] is False and att['episode_ref'] is None and att['selected_candidate_id'] is None
            and att['claim'] == CLAIM and att['request']['path'] == str(directory / 'request.json'), 'invalid or overclaimed audit')
    request = reader.checked(att['request']); scope = request['scope']
    require(set(scope)=={'version','operator','campaign_config_hash','storage_profile','finalization_request',
                        'finalization_completion','sources','jobs','engineering','historical_request_producers',
                        'producers','evidence'},'unknown audit scope fields')
    require(set(request) == {'version', 'scope', 'ledger_prefix', 'costs_before', 'attestation_id', 'storage_bindings'}
            and request['version'] == VERSION and scope['version'] == VERSION and scope['operator'] == operator, 'unknown audit protocol')
    identity = digest(canonical({'request': scope['finalization_request']['sha256'], 'engineering': scope['engineering']['sha256'], 'protocol': VERSION}))
    require(identity == request['attestation_id'] == att['attestation_id'] == ev['attestation_id']
            and directory.name == 'report-attestation-' + identity[7:23]
            and ev['finalization_request'] == scope['finalization_request'], 'audit identity differs')
    evidence = {}
    for ref in scope['evidence']:
        pointer(ref); require(ref['path'] not in evidence, 'duplicate attested evidence path'); evidence[ref['path']] = ref['sha256']
    catalog = storage_catalog(request['storage_bindings'], evidence)
    config = reader.document(ledger / 'config.json'); config_hash = digest(packed(config))
    require(config.get('schema_version') == 'msprof_exploration_campaign_v2' and config['tasks'][operator]['split'] == task.parents[1].name
            and reader.document(ledger / 'config.sha256.json') == {'sha256': config_hash}
            and scope['campaign_config_hash'] == config_hash, 'campaign config identity differs')
    prefix = reader.raw(directory / 'ledger-prefix.jsonl'); rows = ledger_events(prefix, config_hash)
    require(request['ledger_prefix'] == {'event_count': len(rows), 'head_hash': rows[-1]['hash'], 'sha256': digest(prefix)}, 'ledger prefix binding differs')
    require(request['costs_before']==ledger_costs(rows,config),'original audited cost snapshot differs')
    current = reader.raw(ledger / 'events.jsonl', protect=False); ledger_events(current, config_hash)
    require(current.startswith(prefix), 'original ledger prefix changed')
    regs, starts, finishes, observed, freeze = projection(rows, operator)
    original = reader.checked(scope['finalization_request']); completion = reader.checked(scope['finalization_completion'])
    require(scope['finalization_request']['path'] == str(task / 'finalization/request.json')
            and scope['finalization_completion']['path'] == str(task / 'finalization/completion.json')
            and original['version'] == 'level2_final_evaluation_v1' and original['operator'] == operator
            and original['case_ids'] == ALL_CASES and original['campaign_config_hash'] == config_hash
            and freeze['reason'] == 'All safe candidates; no winner selected; finalization request ' + scope['finalization_request']['sha256'], 'original final request is not ledger-frozen')
    require(original['selection_policy'] == 'all_correctness_runtime_boundary_qualified_candidates_without_timing_filter'
            and original['formal_admission'] == 'not_evaluated' and original['selected_candidate_id'] is None
            and original['episode_ref'] is None and original['graph_policy_eligible'] is False, 'final request overclaims selection')
    require([r['candidate_id'] for r in original['source_attempts']] == list(regs)
            and original['evaluation_candidate_ids'] == freeze['candidate_ids']
            and set(original['final_plans']) == set(freeze['final_plans']) == set(freeze['candidate_ids']), 'source/final roster differs')
    baseline = config['tasks'][operator]['baseline_source_hash']
    require(set(scope['sources']) == {'baseline', *regs}, 'audit source roster differs')
    for cid, source in scope['sources'].items():
        expected = task / 'baseline-source.tar' if cid == 'baseline' else task / 'candidates' / cid / 'source.tar'
        require(source['archive'] == {'path': str(expected), 'sha256': baseline if cid == 'baseline' else regs[cid]['source_hash']}, 'original source archive identity differs')
        reader.raw(expected, source['archive'])
    for attempt in original['source_attempts']:
        cid = attempt['candidate_id']; obs = observed[cid]; feedback = reader.checked(attempt['feedback'])
        require(obs.get('close_feedback') is True and obs['feedback'] == feedback and obs['report_ref'] == attempt['feedback']['sha256']
                and feedback['source_hash'] == regs[cid]['source_hash'] == attempt['source_hash']
                and feedback['source_parent'] == regs[cid]['source_parent'] and feedback['status'] == attempt['status']
                and feedback['status'] in ('measured', 'source_attempt_failed') and not feedback.get('measurement_error')
                and not obs.get('quality', {}).get('infrastructure_blocked'), 'source observation not genuinely closed')
        if feedback['status'] == 'source_attempt_failed':
            require(feedback.get('failure_classification', {}).get('status') == 'source_attempt_failed', 'failed source lacks positive recorded attribution')
        source_stages = {sid: s for sid, s in starts.items() if s['candidate_id'] == cid and not (s['kind'] == 'timing' and s['plan'].get('purpose') == 'final')}
        require(set(attempt['stages']) == set(source_stages), 'closed source stage roster differs')
        for sid, ref in attempt['stages'].items():
            require(finishes[sid].get('evidence', {}).get('result') == ref, 'closed source result differs'); reader.checked(ref)
        require(type(attempt['qualified']) is bool and attempt['qualified'] == (cid in freeze['candidate_ids']), 'safe final roster differs')
        if attempt['qualified']:
            require(feedback['status'] == 'measured' and reader.checked(attempt['semantic_guards'])['status'] == 'passed', 'qualified source has no passing guard')
    require(completion['request'] == scope['finalization_request'] and completion['operator'] == operator
            and completion['version'] == original['version'] and completion['source_attempt_count'] == 3
            and completion['final_measurements_complete'] is True and completion['selected_candidate_id'] is None
            and completion['evaluation_candidate_ids'] == freeze['candidate_ids']
            and completion['status'] == 'final_evaluations_completed'
            and [r['candidate_id'] for r in completion['comparisons']] == freeze['candidate_ids'], 'final completion not closed')
    jobs = []; comparisons = []; calibrations = {}; recovery_events=[]
    for cid, completed in zip(freeze['candidate_ids'], completion['comparisons']):
        parent = task / 'candidates' / cid
        plan = reader.checked(original['final_plans'][cid]); sid = cid + '-final'
        require(plan == freeze['final_plans'][cid] == starts[sid]['plan'] == reader.document(parent / 'stages/final/stage-plan.json')
                and starts[sid]['candidate_id'] == cid and starts[sid]['kind'] == 'timing'
                and plan['purpose'] == 'final' and plan['case_ids'] == ALL_CASES and plan['processes'] == 6, 'final plan identity differs')
        stage_directory=parent/'stages/final'
        result = reader.ref(stage_directory/'result.json'); result_value = reader.checked(result)
        if result_value.get('status')!='passed':
            from level2_stage_recovery import project_stage,resolve_result
            resolved=resolve_result(stage_directory,project_stage(rows,operator,sid),
                                    lambda p:reader.raw(p,protect=False),require_success=True)
            require(resolved['original_failed_result']==result and resolved['qualification'] is not None,
                    'final recovery omitted original failed result')
            for fixed in resolved['protected']:reader.raw(fixed['path'],fixed)
            result=resolved['current_result'];result_value=reader.checked(result)
            for binding in resolved['event_bindings']:
                if binding not in recovery_events:recovery_events.append(binding)
        require(finishes[sid]['outcome'] == 'success' and finishes[sid]['native_started'] is True
                and finishes[sid]['evidence']['result'] == result == completed['result']
                and result_value['status'] == 'passed' and result_value.get('error') is None, 'final stage not successfully closed')
        controls = {'direct_parent': regs[cid]['source_parent']['candidate_id'] or 'baseline'}
        if regs[cid]['source_parent']['source_hash'] != baseline: controls['original_baseline'] = 'baseline'
        require(len(plan['cohorts']) == len(controls) and {r['relation'] for r in plan['cohorts']} == set(controls)
                and [r['relation'] for r in completed['comparisons']] == [r['relation'] for r in plan['cohorts']], 'final relation coverage differs')
        comparison_manifest = path(original['final_plans'][cid]['path']).parent / 'comparisons.json'
        require(reader.ref(comparison_manifest)['sha256'] == plan['manifest_ref']
                and reader.document(comparison_manifest) == {'candidate_id': cid, 'cohorts': plan['cohorts'], 'case_ids': ALL_CASES}, 'original comparison manifest differs')
        for entry, done in zip(plan['cohorts'], completed['comparisons']):
            relation = entry['relation']; control = controls[relation]; d = parent / 'stages/final' / relation
            require(entry['control_candidate_id'] == done['control_candidate_id'] == control
                    and done['report']['path'] == str(d / 'report.json') and done['completion']['path'] == str(d / 'group-completion.json'), 'foreign report/completion relation slot')
            frozen = reader.checked(entry['plan']); build = reader.checked(frozen['identity_bindings']['role_build'])
            hashes = {'A': scope['sources'][control]['native_tree_hash'], 'B': scope['sources'][cid]['native_tree_hash']}
            require(frozen == reader.document(d / 'plan.json') and build['operator'] == operator
                    and {r: build['roles'][r]['source_sha256'] for r in 'AB'} == hashes, 'source-role build mismatch')
            cal = entry.get('calibration_report', plan['calibration_report'])
            job = {'candidate_id': cid, 'relation': relation, 'control_candidate_id': control, 'directory': str(d), 'plan': entry['plan'],
                   'report': done['report'], 'completion': done['completion'], 'stage_result': result, 'calibration': cal, 'source_hashes': hashes}
            jobs.append(job)
    require(scope['jobs'] == jobs and len(att['comparisons']) == len(jobs), 'audit omitted/added final comparison')
    for job, proof in zip(jobs, att['comparisons']):
        require({k: proof[k] for k in ('candidate_id', 'relation', 'control_candidate_id')} == {k: job[k] for k in ('candidate_id', 'relation', 'control_candidate_id')}, 'audit comparison foreign slot')
        main = {k: v for k, v in proof.items() if k not in ('candidate_id', 'relation', 'control_candidate_id', 'calibration_replay')}
        report_replay(reader, main, {**job, 'comparison_kind': 'ab'}, evidence)
        cal = proof['calibration_replay']; ref = job['calibration']; key = (ref['path'], ref['sha256'])
        require(cal['report'] == ref, 'audit calibration differs from frozen plan')
        if key in calibrations: require(calibrations[key] == cal, 'inconsistent unique calibration replay')
        else:
            report = reader.checked(ref); require(report['comparison_kind'] == 'aa' and report['source_hashes']['A'] == report['source_hashes']['B'], 'calibration not fixed-source AA')
            report_replay(reader, cal, {'report': ref, 'plan': reader.ref(path(ref['path']).parent / 'plan.json'),
                          'completion': reader.ref(path(ref['path']).parent / 'group-completion.json'),
                          'source_hashes': report['source_hashes'], 'comparison_kind': 'aa'}, evidence)
            calibrations[key] = cal
        comparisons.append((job['candidate_id'], job['relation'], job['report']))
    require((candidate, cohort.name, target) in comparisons, 'target not in complete audited roster')
    engpath = path(scope['engineering']['path'])
    require(engpath.parent == run / 'bootstrap' and re.fullmatch(r'frozen-engineering(?:-[a-zA-Z0-9_-]+)?\.json', engpath.name), 'noncanonical engineering manifest')
    eng = reader.checked(scope['engineering'])
    require(eng['version'] == 'level2_frozen_engineering_v1' and eng['campaign_manifest'] == reader.ref(run / 'campaign-manifest.json')
            and reader.ref(task / 'manifest.json') in eng['task_manifests'], 'engineering campaign/task identity differs')
    files = {r['path']: r for r in eng['files']}; require(len(files) == len(eng['files']), 'duplicate engineering producer')
    writers = []; producer_origins = {}
    for producer in scope['producers']:
        require(set(producer) == {'origin', 'snapshot'}, 'invalid audit producer proof')
        origin, snapshot = pointer(producer['origin']), pointer(producer['snapshot'])
        require(origin['path'] not in producer_origins, 'duplicate audited producer')
        producer_origins[origin['path']] = origin['sha256']
        require(files.get(origin['path']) == {**origin, 'snapshot': snapshot['path']}
                and snapshot == {'path': str(run / 'bootstrap/source-cas' / origin['sha256'][7:]), 'sha256': origin['sha256']}, 'producer engineering/CAS binding differs')
        reader.raw(snapshot['path'], snapshot)
        if path(origin['path']).name == 'level2_final_report_attestation.py': writers.append(origin['sha256'])
    require(len(writers) == 1 and APPROVED_WRITERS.get(writers[0]) == VERSION, 'unreviewed attestation writer protocol')
    require(digest(canonical(scope['storage_profile'])) == APPROVED_PROFILE_HASHES.get(writers[0]), 'writer storage profile differs from reviewed version')
    for name, sha in scope['storage_profile']['expected_producer_sha256'].items():
        require(len([origin for origin, value in producer_origins.items() if path(origin).name == name and value == sha]) == 1, 'storage producer is missing from audited engineering')
    old_proofs = {p.get('origin', {}).get('path'): p for p in scope['historical_request_producers']}
    for old in original['producers']:
        pointer(old)
        if producer_origins.get(old['path']) != old['sha256']:
            historical = old_proofs.get(old['path'], {})
            if historical:
                require(historical.get('origin') == old and historical.get('snapshot', {}).get('sha256') == old['sha256'], 'original finalizer producer proof missing')
            else:
                require(evidence.get(old['path']) == old['sha256'], 'original finalizer producer omitted from audit')
                # The original request pins these exact bytes. CAS is inert data;
                # later current-source drift cannot invalidate old proof.
                snapshot={'path':str(run/'bootstrap/source-cas'/old['sha256'][7:]),'sha256':old['sha256']}
                reader.raw(snapshot['path'],snapshot)
    reader.proof_refs(scope['historical_request_producers'])
    for ref in reader.protected.values():
        # New attestation files and ledger/config are independently bound above;
        # original audited objects must also be in its immutable evidence list.
        if ref['path'] in evidence: require(evidence[ref['path']] == ref['sha256'], 'audit evidence index differs')
    report_slot = next(i for i, v in enumerate(att['comparisons']) if (v['candidate_id'], v['relation'], v['report']) == (candidate, cohort.name, target))
    return {'kind': KIND, 'slot': 'attestation.comparisons[' + str(report_slot) + '].report', 'report': target,
            'authority_timing': TIMING, 'historical_report_authority': False,
            'event_bindings': [{'path': str(event_path), 'sequence': event['sequence'], 'hash': event['hash']},
                               {'path': str(ledger / 'events.jsonl'), 'sequence': len(rows)-1, 'hash': rows[-1]['hash']},
                               *recovery_events],
            'protected': [reader.protected[k] for k in sorted(reader.protected)],
            'storage_catalog': catalog}


def catalog_bindings(authority_value):
    """One full nested storage proof per seal, plus every exact logical origin.

    This is an export plan, not evidence verification. Callers must copy each full
    archive with streaming hashes and independently run the trusted storage-kind
    validator offline. Inert producer bytes must never be imported. No origin is
    dropped even when only one file led a final seal to this authority.
    """
    require(authority_value.get('kind') == KIND and authority_value.get('historical_report_authority') is False,
            'not the reviewed retrospective authority')
    value = authority_value['storage_catalog']
    storage_catalog(value, {p: row['sha256'] for p, row in value['origins'].items()})
    for key in sorted(value['archives']):
        entry = value['archives'][key]
        origins = [{'path': p, 'sha256': row['sha256']} for p, row in sorted(value['origins'].items()) if row['seal'] == key]
        yield {'binding': {**{k: entry[k] for k in ('version', 'seal', 'archive', 'producer')},
                           'origin': origins[0], 'closed_evidence': value['closed_evidence'][entry['closed_evidence_ref']]},
               'origins': origins}


def reconstruct_catalog(authority_value):
    """Pure export interface: one full binding per seal and the full origin map."""
    rows = list(catalog_bindings(authority_value))
    return {'archives': {row['binding']['seal']['sha256']: row['binding'] for row in rows},
            'origins': {origin['path']: {'sha256': origin['sha256'], 'seal': row['binding']['seal']['sha256']}
                        for row in rows for origin in row['origins']}}
