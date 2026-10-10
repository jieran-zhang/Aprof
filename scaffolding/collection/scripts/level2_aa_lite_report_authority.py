"""Data-only reader for the reviewed retrospective Gather lite A/A audit."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

VERSION = 'level2_aa_lite_report_consistency_attestation_v1'
KIND = 'retrospective_lite_aa_report_authority_v1'
EVENT = 'aa_lite_report_consistency_attested'
TIMING = 'retrospective_audit_now_not_original_measurement'
CLAIM = 'Retained evidence and the saved lite A/A report were consistent at this retrospective audit; no earlier report authority is asserted.'
APPROVED_WRITER_SHA = 'sha256:a095e6e8c39f08996c008d3b81b094e2502fe1e6aad588fbd5cba7a4cc88d974'
HASH = re.compile(r'sha256:[0-9a-f]{64}\Z')
MAX_METADATA = 32 * 1024 * 1024


def require(ok, why):
    if not ok: raise ValueError(why)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def decode(data):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate A/A audit key'); out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite A/A audit JSON')))


def path(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts and str(p) == str(value), 'noncanonical A/A audit path')
    return p


def pointer(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}
            and isinstance(value['sha256'], str) and HASH.fullmatch(value['sha256']), 'invalid A/A audit pointer')
    path(value['path']); return value


def authority(session, read_bytes):
    session = path(session)
    cohort = session.parent; stage = cohort.parent; task = stage.parent.parent
    require(task.name == 'gather' and stage == task / 'stages/aa-search-lite-031'
            and cohort == stage / 'cohort'
            and session.name in {'aa-search-lite-031-p01', 'aa-search-lite-031-p02'},
            'A/A audit is restricted to the closed Gather lite control')
    run = task.parents[2]
    protected = {}
    def raw(value, expected=None):
        p = path(value); data = read_bytes(p)
        require(isinstance(data, bytes) and len(data) <= MAX_METADATA, 'A/A audit metadata exceeds bound')
        ref = {'path': str(p), 'sha256': digest(data)}
        require(expected is None or ref == pointer(expected), 'A/A audit reference differs')
        require(str(p) not in protected or protected[str(p)] == ref, 'A/A audit metadata changed')
        protected[str(p)] = ref
        return data
    def document(value, expected=None): return decode(raw(value, expected))

    report_path = cohort / 'report.json'; report_ref = {'path': str(report_path), 'sha256': digest(read_bytes(report_path))}
    report = document(report_path, report_ref)
    require(report.get('protocol') == 'msprof_task_time_search_lite_v1'
            and report.get('comparison_kind') == 'aa'
            and report.get('case_ids') == ['1', '8', '14', '20']
            and report.get('evidence_status') == 'verified_complete', 'A/A audit report scope differs')
    require(len(report.get('sessions', [])) == 2 and len(report.get('results', [])) == 8
            and {(row['case_id'],row['buffer_config']) for row in report['results']}
                == {(str(case),mode) for case in (1,8,14,20) for mode in ('normal','swapped')},
            'A/A audit report coverage differs')
    event_path = task / 'events.jsonl'; data = raw(event_path)
    require(data.endswith(b'\n'), 'A/A task event tail incomplete')
    rows = []; previous = None
    for number, line in enumerate(data.splitlines()):
        row = decode(line)
        require(set(row) == {'sequence','recorded_at','kind','previous_hash','value','hash'}
                and row['sequence'] == number and row['previous_hash'] == previous
                and row['hash'] == digest(canonical({k:v for k,v in row.items() if k != 'hash'})),
                'A/A public event chain differs')
        previous = row['hash']; rows.append(row)
    found = [row for row in rows if row['kind'] == EVENT]
    require(len(found) == 1, 'missing or duplicate A/A audit event')
    event = found[0]; value = event['value']
    require(set(value) == {'operator','stage_id','report','attestation','authority_timing'}
            and value['operator'] == 'gather' and value['stage_id'] == 'baseline-aa-search-lite-031'
            and value['report'] == report_ref and value['authority_timing'] == TIMING,
            'A/A event scope differs')
    attestation_ref = pointer(value['attestation']); attestation_path = path(attestation_ref['path'])
    require(attestation_path.parent.parent == stage and attestation_path.name == 'attestation.json'
            and re.fullmatch(r'report-attestation-[0-9a-f]{16}', attestation_path.parent.name),
            'A/A attestation outside fixed stage namespace')
    attestation = document(attestation_path, attestation_ref)
    require(set(attestation) == {'version','status','kind','attestation_id','audited_at','request',
                                 'comparison','native_executed','formal_admission','graph_policy_eligible','claim'}
            and attestation['version'] == VERSION and attestation['status'] == 'passed'
            and attestation['kind'] == 'retrospective_lite_aa_report_replay'
            and attestation['comparison'].get('matched') is True
            and attestation['native_executed'] is False
            and attestation['formal_admission'] == 'not_evaluated'
            and attestation['graph_policy_eligible'] is False
            and attestation['claim'] == CLAIM, 'A/A attestation overclaims or differs')
    request_ref = pointer(attestation['request']); request_path = path(request_ref['path'])
    require(request_path == attestation_path.parent / 'request.json', 'A/A request path differs')
    request = document(request_path, request_ref)
    require(set(request) == {'version','attestation_id','scope'} and request['version'] == VERSION
            and request['attestation_id'] == attestation['attestation_id']
            and request['attestation_id'][7:23] == attestation_path.parent.name.removeprefix('report-attestation-'),
            'A/A request identity differs')
    scope = request['scope']
    require(scope['version'] == VERSION and scope['task'] == str(task) and scope['stage'] == str(stage)
            and scope['report'] == report_ref
            and scope['stage_result'] == {'path':str(stage/'result.json'),'sha256':digest(read_bytes(stage/'result.json'))}
            and scope['stage_plan'] == {'path':str(stage/'stage-plan.json'),'sha256':digest(read_bytes(stage/'stage-plan.json'))}
            and scope['completion'] == {'path':str(cohort/'group-completion.json'),'sha256':digest(read_bytes(cohort/'group-completion.json'))}
            and scope['comparison'] == attestation['comparison']
            and HASH.fullmatch(scope['replayed_report_sha256']), 'A/A audited scope differs')
    for ref in (scope['stage_result'],scope['stage_plan'],scope['completion']): raw(ref['path'],ref)
    refs = {row['path']:pointer(row) for row in scope['evidence']}
    require(len(refs) == len(scope['evidence']) and refs.get(str(report_path)) == report_ref,
            'A/A audit evidence roster differs')
    for row in report['sessions']:
        for logical, sha in row['artifacts'].items():
            if refs.get(logical) == {'path':logical,'sha256':sha}: continue
            matches = [proof for proof in scope['historical_producers']
                       if proof.get('origin') == {'path':logical,'sha256':sha}]
            require(matches and all(proof.get('snapshot',{}).get('sha256') == sha for proof in matches),
                    'A/A audited artifact lacks original or frozen producer')
            for proof in matches: raw(proof['snapshot']['path'],proof['snapshot'])
    engineering_ref = pointer(scope['engineering']); engineering_path = path(engineering_ref['path'])
    require(engineering_path.parent == run / 'bootstrap', 'A/A audit engineering outside run')
    frozen = document(engineering_path, engineering_ref)
    writer = run.parents[3] / 'aprof-restructured/scaffolding/collection/scripts/level2_aa_lite_report_attestation.py'
    writer = path(writer)
    require(HASH.fullmatch(APPROVED_WRITER_SHA), 'A/A writer has not been approved')
    matches = [row for row in frozen['files'] if row['path'] == str(writer)
               and row['sha256'] == APPROVED_WRITER_SHA]
    require(len(matches) == 1, 'reviewed A/A writer not in frozen engineering')
    snapshot = path(matches[0]['snapshot'])
    require(snapshot == run / 'bootstrap/source-cas' / APPROVED_WRITER_SHA[7:]
            and digest(read_bytes(snapshot)) == APPROVED_WRITER_SHA,
            'reviewed A/A writer snapshot differs')
    require(any(row.get('origin') == {'path':str(writer),'sha256':APPROVED_WRITER_SHA}
                and row.get('snapshot') == {'path':str(snapshot),'sha256':APPROVED_WRITER_SHA}
                for row in scope['producers']), 'A/A audit did not bind its reviewed writer')
    prefix_path = attestation_path.parent / 'ledger-prefix.jsonl'
    prefix = raw(prefix_path); recorded = scope['ledger_prefix']
    require(digest(prefix) == recorded['sha256'] and len(prefix.splitlines()) == recorded['event_count']
            and decode(prefix.splitlines()[-1])['hash'] == recorded['head_hash']
            and read_bytes(run/'train/ledger/events.jsonl').startswith(prefix), 'A/A ledger prefix differs')
    return {'kind':KIND,'report':report_ref,'historical_report_authority':False,
            'attestation':attestation_ref,
            'event_bindings':[{'path':str(event_path),'sequence':event['sequence'],'hash':event['hash']}],
            'protected':[protected[k] for k in sorted(protected) if k != str(event_path)]}
