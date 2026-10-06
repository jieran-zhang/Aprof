#!/usr/bin/env python3
"""External, CPU-only optimization memory projections. Never imports runtime gates.

Published revisions are immutable. current.json is the sole atomic commit point.
Operator-specific attributes are extensible JSON values; record/fact structure is
closed. Old source archives remain read-only and are addressed by content hash.
"""
from __future__ import annotations
import argparse
import copy
import contextlib
import fcntl
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from urllib.parse import urlparse, unquote

from jsonschema import Draft202012Validator

VERSION = '2.0.0'
ROOT = Path(__file__).resolve().parents[1]
HASH_RE = re.compile(r'^sha256:[0-9a-f]{64}$')


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest_bytes(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def digest(value):
    return digest_bytes(canonical(value))


def strict_loads(data):
    def reject(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('duplicate JSON key: ' + key)
            out[key] = value
        return out
    return json.loads(data, parse_constant=reject, object_pairs_hook=pairs)


def finite_tags(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'special_value': 'NaN' if math.isnan(value) else '+Inf' if value > 0 else '-Inf'}
    if isinstance(value, dict): return {k: finite_tags(v) for k, v in value.items()}
    if isinstance(value, list): return [finite_tags(v) for v in value]
    return value


def obj(fields, required=None):
    return {'type': 'object', 'properties': fields, 'required': list(fields) if required is None else required,
            'additionalProperties': False}


def arr(item): return {'type': 'array', 'items': item}
S = {'type': 'string'}
B = {'type': 'boolean'}
I = {'type': 'integer', 'minimum': 0}
H = {'type': 'string', 'pattern': HASH_RE.pattern}
N = {'type': ['string', 'null']}
REFS = arr(S)
ATTRS = {'type': 'object', 'additionalProperties': {'$ref': '#/$defs/value'}}
FACT = obj({'id': S, 'statement': S, 'basis': S, 'case_ids': arr(I), 'attributes': ATTRS,
            'evidence_ids': REFS, 'limitations': REFS, 'claim_ids': REFS})
CLAIM = obj({**FACT['properties'], 'status': {'enum': ['supported', 'refuted', 'inconclusive']}})
DIAGNOSIS = obj({'symptoms': arr(FACT), 'hypotheses': arr(FACT), 'missing_evidence': REFS,
                 'retrospective': B, 'evidence_ids': REFS})
EVALUATION = obj({'id': S, 'run_id': S, 'session_id': S, 'relation': S, 'comparison': obj({'baseline': H, 'candidate': H}),
                  'stages': arr(obj({'name': S, 'status': S, 'reason': N, 'evidence_ids': REFS})),
                  'measurement_quality': S, 'summary': ATTRS, 'cases': arr(ATTRS), 'evidence_ids': REFS})
MEMORY_BODY = obj({
    'identity': obj({'run_id': S, 'task_id': S, 'candidate_id': S, 'operator': S, 'split': {'enum': ['train', 'validation']}}),
    'sources': obj({'original_baseline': H, 'direct_parent': H, 'candidate': H, 'patch': H,
                    'parent_attempt_id': N, 'evidence_ids': REFS}),
    'context_ref': H, 'knowledge': obj({'catalog_ref': H, 'actual_reads': arr(obj({'evidence_id': S, 'purpose': S})),
                                       'classification_note': S}),
    'diagnosis': DIAGNOSIS, 'intervention': FACT, 'evaluations': arr(EVALUATION),
    'machine_results': arr(obj({'evaluation_id': S, 'verdict': S, 'first_failed_stage': N,
                               'graph_policy_eligible': B, 'episode_ref': N, 'evidence_ids': REFS,
                               'metrics': ATTRS})),
    'timeline': arr(obj({'timestamp': S, 'event_type': S, 'summary': S, 'evidence_id': S})),
    'next_decision': obj({'action': S, 'reason': S, 'evidence_ids': REFS}),
    'provenance': obj({'retrospective': B, 'source_record_refs': REFS, 'importer_hash': H,
                       'knowledge_state': S, 'null_reasons': ATTRS})})
LESSON_BODY = obj({'kind': {'enum': ['operator_optimization', 'measurement_method', 'infrastructure']},
                   'operator': N, 'split': {'enum': ['train', 'validation']}, 'title': S,
                   'diagnosis': DIAGNOSIS, 'intervention': FACT,
                   'effective_conditions': arr(FACT), 'ineffective_conditions': arr(FACT),
                   'counterexamples': arr(FACT), 'claims': arr(CLAIM), 'limitations': REFS,
                   'next_questions': REFS, 'graph_links': arr(obj({'graph_version': S, 'node_id': S, 'basis': S})),
                   'memory_refs': arr(obj({'id': S, 'record_hash': H})), 'evidence_ids': REFS,
                   'retrospective': B})


def schema(kind):
    body = MEMORY_BODY if kind == 'optimization_memory' else LESSON_BODY
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$id': 'https://aprof.local/schemas/' + kind + '-v2.schema.json',
            '$defs': {'value': {'anyOf': [{'type': ['null', 'boolean', 'number', 'string']},
                                        arr({'$ref': '#/$defs/value'}), ATTRS]}},
            **obj({'schema_version': {'const': VERSION}, 'record_kind': {'const': kind}, 'id': S,
                   'revision': {'type': 'integer', 'minimum': 1}, 'previous_ref': {'type': ['string', 'null'], 'pattern': HASH_RE.pattern},
                   'record_hash': H, 'body': body})}


def seal(kind, identifier, body, previous=None):
    if previous:
        validate_record(previous)
        if previous['id'] != identifier or previous['record_kind'] != kind:
            raise ValueError('previous identity mismatch')
    if previous and previous['body'] == body: return previous
    value = {'schema_version': VERSION, 'record_kind': kind, 'id': identifier,
             'revision': previous['revision'] + 1 if previous else 1,
             'previous_ref': previous['record_hash'] if previous else None, 'body': body}
    value['record_hash'] = digest(value)
    validate_record(value)
    return value


def validate_record(value):
    canonical(value)
    if value.get('record_kind') not in ('optimization_memory', 'lesson'): raise ValueError('unknown record kind')
    Draft202012Validator(schema(value['record_kind'])).validate(value)
    if value['record_hash'] != digest({k: v for k, v in value.items() if k != 'record_hash'}):
        raise ValueError('record hash mismatch')


@contextlib.contextmanager
def external_evidence_session():
    try:
        import level2_verification_storage as storage
    except ModuleNotFoundError as error:
        if error.name != 'level2_verification_storage':
            raise
        yield
    else:
        with storage.reader_session():
            yield


def external_evidence_reader(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        if kwargs.get('evidence_paths') is not None:
            # Portable maps are complete and must not import an original-store resolver.
            return function(*args, **kwargs)
        with external_evidence_session():
            return function(*args, **kwargs)
    return run


def external_evidence_bytes(path):
    """Read exact historical logical bytes; explicit portable maps bypass this resolver."""
    try:
        import level2_verification_storage as storage
    except ModuleNotFoundError as error:
        if error.name != 'level2_verification_storage':
            raise
        return Path(path).read_bytes()
    return storage.read_bytes(path)


def evidence_fingerprint(path, *, external=True):
    if external:
        try:
            import level2_verification_storage as storage
        except ModuleNotFoundError as error:
            if error.name != 'level2_verification_storage':raise
        else:return storage.fingerprint(path)
    h=hashlib.sha256();size=0
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024):h.update(block);size+=len(block)
    return {'sha256':'sha256:'+h.hexdigest(),'size_bytes':size}


class Evidence:
    """Read-only legacy catalog plus content-deduplicated evidence selectors."""
    def __init__(self, runs=()):
        self.entries = {}; self.locations = {}; self.bytes_cache = {}; self.contexts = {}
        for run in runs:
            for split in ('train', 'validation'):
                db = Path(run) / split / 'episodes.sqlite'
                if not db.is_file(): continue
                with sqlite3.connect(db.resolve().as_uri() + '?mode=ro&immutable=1', uri=True) as conn:
                    for h, uri, size in conn.execute('SELECT content_hash, uri, size_bytes FROM artifact_locations'):
                        if urlparse(uri).scheme == 'file':
                            path = unquote(urlparse(uri).path)
                            self.locations.setdefault((split, h), []).append((path, size))

    def read(self, path):
        path = str(Path(path).resolve())
        if path not in self.bytes_cache: self.bytes_cache[path] = external_evidence_bytes(path)
        return self.bytes_cache[path]

    def file(self, path, *, split='train', selector='', purpose='source evidence', expected=None):
        path = str(Path(path).resolve()); fp=evidence_fingerprint(path);h=fp['sha256']
        if expected and expected != h: raise ValueError('evidence hash mismatch: ' + path)
        return self._entry(h, path, fp['size_bytes'], split, selector, purpose)

    def hash(self, h, split, purpose='legacy artifact'):
        locations = self.locations.get((split, h), [])
        # Prefer immutable CAS over live working files, avoid reading every blob at import.
        locations = sorted(locations, key=lambda p: ('.objects/sha256/' not in p[0], p[0]))
        if not locations: raise ValueError('unresolved ' + split + ' artifact ' + h)
        path, size = locations[0]
        return self._entry(h, path, size, split, '', purpose)

    def _entry(self, h, path, size, split, selector, purpose):
        key = 'e-' + digest([split, h, selector]).split(':')[1][:24]
        if key not in self.entries:
            self.entries[key] = {'sha256': h, 'path': path, 'size_bytes': size, 'split': split,
                                 'selector': selector, 'purposes': []}
        if purpose not in self.entries[key]['purposes']: self.entries[key]['purposes'].append(purpose)
        return key

    def context(self, value):
        h = digest(value); self.contexts[h] = value; return h


def decode_json_strings(value):
    if isinstance(value, list): return [decode_json_strings(v) for v in value]
    if isinstance(value, dict): return {k: decode_json_strings(v) for k, v in value.items()}
    if isinstance(value, str) and value.startswith(('{', '[')):
        try: return finite_tags(json.loads(value))
        except ValueError: pass
    return value


def fact(identifier, value, evidence_ids=(), basis='retrospective_extraction'):
    if isinstance(value, str): value = {'statement': value}
    value = copy.deepcopy(value)
    fact_basis = str(value.get('basis', basis))
    statement = next((value[k] for k in ('statement', 'description', 'summary', 'condition', 'symptom', 'title', 'intent', 'text')
                      if isinstance(value.get(k), str)), identifier)
    case_ids = value.get('case_ids', value.get('cases', []))
    if not isinstance(case_ids, list) or any(type(v) is not int for v in case_ids): case_ids = []
    claim_ids = value.get('claim_ids', [])
    for key in ('target_claim_id', 'claim_id', 'refutes_claim_id'):
        if isinstance(value.get(key), str) and value[key] not in claim_ids: claim_ids = [*claim_ids, value[key]]
    limitations = value.get('limitations', [])
    if isinstance(limitations, str): limitations = [limitations]
    limitations = [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in limitations]
    for key in ('id', 'statement', 'basis', 'case_ids', 'status', 'evidence', 'evidence_ids', 'limitations', 'claim_ids'):
        value.pop(key, None)
    return {'id': identifier, 'statement': statement, 'basis': fact_basis,
            'case_ids': case_ids, 'attributes': finite_tags(value), 'evidence_ids': list(dict.fromkeys(evidence_ids)),
            'limitations': limitations, 'claim_ids': claim_ids}


def artifact_hashes(value):
    if isinstance(value, str) and HASH_RE.match(value): yield value
    elif isinstance(value, dict):
        for v in value.values(): yield from artifact_hashes(v)
    elif isinstance(value, list):
        for v in value: yield from artifact_hashes(v)


def load_rows(path):
    return [strict_loads(line) for line in Path(path).read_bytes().splitlines() if line.strip()]


def import_memories(parent, serial, evidence):
    memories = {}; original_rows = {}; source_rows = {}
    knowledge_cache = {}
    for run in (parent, serial):
        for split in ('train', 'validation'):
            path = run / split / 'optimization_traces.jsonl'
            if not path.is_file(): continue
            for number, row in enumerate(load_rows(path), 1):
                ident = row['identity']; cid = ident['candidate_id']; identifier = parent.name + '/' + split + '/' + cid
                line_ref = evidence.file(path, split=split, selector='line:' + str(number), purpose='immutable legacy attempt summary')
                p = row['provenance']
                if identifier not in memories:
                    if run != parent: raise ValueError('continuation without original attempt: ' + cid)
                    original_rows[identifier] = row
                    # Full catalogs are facts about historical bookkeeping, not proof of reading.
                    knowledge_key = (split, ident['operator'])
                    if knowledge_key not in knowledge_cache:
                        ledger = parent/'tasks'/ident['operator']/'worker_knowledge_reads.jsonl'
                        classified = []; actual_reads = []
                        if ledger.is_file():
                            for li, entry in enumerate(load_rows(ledger), 1):
                                purpose = entry.get('purpose', ''); access_path = entry.get('path', '')
                                category = ('integrity_check' if 'hash-only' in purpose.lower() else
                                            'knowledge_read' if '/skills/' in access_path else
                                            'parsed_measurement' if access_path.endswith('.csv') else 'other_recorded_access')
                                classified.append({**entry, 'category': category})
                                if category == 'knowledge_read':
                                    ref = evidence.file(ledger, split=split, selector='line:'+str(li), purpose='Recorded knowledge access; not proof of decision use')
                                    actual_reads.append({'evidence_id': ref, 'purpose': purpose})
                        catalog = evidence.context({'legacy_loaded_catalog': row['knowledge'], 'classified_access_log': classified,
                                                    'decision_use': [], 'interpretation': 'Recorded reading is distinct from decision use; no decision use is inferred from file access.'})
                        knowledge_cache[knowledge_key] = (catalog, actual_reads)
                    catalog, actual_reads = knowledge_cache[knowledge_key]
                    context = evidence.context({'workload': row['workload'], 'dependencies': p['dependencies'],
                                                'graph_hash': p['graph_hash'], 'skill_manifest_hash': p['skill_manifest_hash'],
                                                'harness_hash': p['harness_hash']})
                    sources = {name: p[key] for name, key in [('original_baseline', 'baseline_source_hash'),
                                                              ('candidate', 'candidate_source_hash'), ('patch', 'patch_hash')]}
                    sources['direct_parent'] = ident['source_parent_hash']; sources['parent_attempt_id'] = ident['parent_attempt_id']
                    sources['evidence_ids'] = [evidence.hash(h, split, 'source or parent-relative patch') for h in dict.fromkeys(sources[k] for k in ('original_baseline', 'direct_parent', 'candidate', 'patch'))]
                    dr = row['diagnosis']; refs = [evidence.hash(h, split, 'original diagnostic evidence') for h in dict.fromkeys(dr['supporting_evidence'] + dr['contradicting_evidence'])]
                    diagnosis = {'symptoms': [fact(cid + '/symptom/' + str(i), v, [line_ref], 'original_record') for i, v in enumerate(dr['symptoms'])],
                                 'hypotheses': [fact(cid + '/hypothesis/' + str(i), {'statement': v, 'source_anchors': decode_json_strings(dr['source_anchors']), 'assessment_basis': dr['assessment_basis']}, refs, 'original_record') for i, v in enumerate(dr['mechanisms'])],
                                 'missing_evidence': list(dr['missing_evidence']) + ([] if dr['symptoms'] else ['Original diagnostic summary contains no structured symptoms; do not infer measurements from handler names.']),
                                 'retrospective': True, 'evidence_ids': [line_ref]}
                    body = {'identity': {k: ident[k] for k in ('run_id', 'task_id', 'candidate_id', 'operator', 'split')},
                            'sources': sources, 'context_ref': context,
                            'knowledge': {'catalog_ref': catalog, 'actual_reads': actual_reads, 'classification_note': 'Task-scoped recorded skill reads; candidate-specific use is unproven. Parsed measurements and hash checks are classified separately in the shared catalog.'},
                            'diagnosis': diagnosis, 'intervention': fact(cid + '/intervention', decode_json_strings(row['intervention']), [line_ref], 'original_record'),
                            'evaluations': [], 'machine_results': [], 'timeline': [],
                            'next_decision': {'action': 'paused_pending_serial_measurement', 'reason': 'Historical candidate remains frozen; no source search or serial completion is inferred.', 'evidence_ids': []},
                            'provenance': {'retrospective': True, 'source_record_refs': [], 'importer_hash': digest_bytes(Path(__file__).read_bytes()),
                                           'knowledge_state': 'historical_measurement_unstable', 'null_reasons': {'sources.parent_attempt_id': 'Independent original-baseline attempt' if sources['parent_attempt_id'] is None else 'not null'}}}
                    patch_ref = evidence.hash(p['patch_hash'], split, 'Exact parent-relative patch')
                    patch_data = evidence.read(evidence.entries[patch_ref]['path'])
                    if digest_bytes(patch_data) != p['patch_hash']: raise ValueError('patch bytes changed')
                    patch_lines = patch_data.decode('utf-8').splitlines(keepends=True)
                    body['intervention']['attributes']['patch_excerpt'] = ''.join(patch_lines[:80])
                    body['intervention']['attributes']['patch_excerpt_truncated'] = len(patch_lines) > 80
                    body['intervention']['evidence_ids'].append(patch_ref)
                    memories[identifier] = body
                body = memories[identifier]
                if (p['candidate_source_hash'] != body['sources']['candidate'] or p['baseline_source_hash'] != body['sources']['original_baseline'] or p['patch_hash'] != body['sources']['patch']):
                    raise ValueError('continuation source identity changed: ' + cid)
                body['provenance']['source_record_refs'].append(line_ref)
                eid = run.name + '/' + cid
                stages = []
                for name in ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile'):
                    stage = row['validation'][name]
                    refs = [evidence.hash(h, split, name + ' artifact') for h in dict.fromkeys(stage['artifact_refs'])]
                    # The artifact group is indexed once, not repeated in the visible evaluation.
                    group = evidence.context({'stage': name, 'evidence_ids': refs})
                    stages.append({'name': name, 'status': stage['status'], 'reason': stage['reason'], 'evidence_ids': [line_ref]})
                    source_rows.setdefault('stage_groups', {})[eid + '/' + name] = group
                ev = {'id': eid, 'run_id': run.name, 'session_id': ident['session_id'],
                      'relation': 'original_attempt' if run == parent else 'measurement_continuation',
                      'comparison': {'baseline': p['baseline_source_hash'], 'candidate': p['candidate_source_hash']},
                      'stages': stages, 'measurement_quality': 'unresolved', 'summary': {}, 'cases': [], 'evidence_ids': [line_ref]}
                if run == serial:
                    op = ident['operator']; suffix = cid.rsplit('-', 1)[-1]
                    obs = run / 'tasks' / op / 'serial_analysis' / ('measurement_observations_' + suffix + '.json')
                    if obs.is_file():
                        observation = json.loads(evidence.read(obs))
                        ev['summary'] = finite_tags(observation['summary'])
                        if 'speedup_lcb_95' in ev['summary']:
                            ev['summary']['descriptive_speedup_lcb_95'] = ev['summary'].pop('speedup_lcb_95')
                        ev['summary']['formal_gate_speedup_lcb'] = row['result']['speedup_lcb']
                        ev['summary']['confidence_method_note'] = 'Descriptive and formal gate bootstrap seeds differ; formal gate LCB is authoritative for machine admission.'
                        fields = ('case_id', 'pair_count', 'baseline_median_ns', 'candidate_median_ns', 'baseline_cv', 'candidate_cv', 'speedup', 'regression', 'dtype', 'scalar', 'mode', 'lengths', 'list_length', 'branch', 'baseline_blocks', 'candidate_blocks', 'tiling_unchanged')
                        ev['cases'] = [{k: finite_tags(v) for k, v in case.items() if k in fields} for case in observation['cases']]
                        ev['evidence_ids'].append(evidence.file(obs, split=split, purpose='serial per-case observations; preliminary status superseded by sealed outcome'))
                        ev['summary']['preliminary_status_superseded_by'] = eid
                    ev['measurement_quality'] = 'admitted' if row['result']['speedup'] is not None else 'not_admitted'
                    body['provenance']['knowledge_state'] = 'serial_measurement_completed'
                    body['next_decision'] = {'action': 'paused_after_serial_measurement', 'reason': 'No new source attempt follows the frozen serial batch. Retrospective next questions live in lessons, not fabricated original decisions.', 'evidence_ids': [line_ref]}
                else:
                    ev['measurement_quality'] = 'not_admitted' if row['result']['verdict'] == 'measurement_unstable' else 'see_machine_result'
                body['evaluations'].append(ev)
                result = row['result']; refs = [line_ref]
                for h in dict.fromkeys(result[k] for k in ('machine_outcome_ref', 'exploration_outcome_ref', 'episode_ref') if result[k]):
                    refs.append(evidence.hash(h, split, 'unchanged formal machine outcome'))
                body['machine_results'].append({'evaluation_id': eid, 'verdict': result['verdict'], 'first_failed_stage': result['first_failed_stage'],
                                                 'graph_policy_eligible': result['graph_policy_eligible'], 'episode_ref': result['episode_ref'], 'evidence_ids': refs,
                                                 'metrics': {**{k: result[k] for k in ('speedup', 'speedup_lcb', 'max_regression')},
                                                             'null_reasons': {k: 'Not available/admitted in original outcome: '+result['verdict'] for k in ('speedup', 'speedup_lcb', 'max_regression') if result[k] is None}}})
    # Preserve actual event chronology and log/command closure outside training prose.
    for run in (parent, serial):
        for split in ('train', 'validation'):
            path = run / split / 'trace_events.jsonl'
            if not path.is_file(): continue
            for i, event in enumerate(load_rows(path), 1):
                identifier = parent.name + '/' + split + '/' + str(event.get('candidate_id'))
                if identifier not in memories: continue
                ref = evidence.file(path, split=split, selector='line:' + str(i), purpose='actual event with original execution command, times and logs')
                payload = event['payload']; summary = payload.get('reason') or payload.get('stage') or payload.get('verdict') or event['event_type']
                memories[identifier]['timeline'].append({'timestamp': event['timestamp'], 'event_type': event['event_type'], 'summary': str(summary), 'evidence_id': ref})
    for body in memories.values(): body['timeline'].sort(key=lambda x: x['timestamp'])
    evidence.context({'stage_artifact_groups': source_rows.get('stage_groups', {})})
    return memories


LESSON_PLANNING_CONTRACT = 'fresh_lesson_stage_bindings_v1'
LESSON_PLANNING_FIELDS = ('architecture_profile_ref', 'parallel_plan_ref', 'dispatch_plan_ref',
    'graph_hash', 'plan_basis_source_hash', 'implementation_source_hash', 'dispatch_selections', 'source_split')


def lesson_planning_bindings(body, memories):
    """Derive stage and per-memory plan/key context from actual sealed memories.

    Different plans, architectures and keys may be compared within one stage.
    A cross-stage comparison must be written as separate operator lessons; method
    and infrastructure lessons retain their historical representation.
    """
    if body.get('kind') != 'operator_optimization':
        return None
    refs = body.get('memory_refs', [])
    if not refs or len({r['id'] for r in refs}) != len(refs):
        raise ValueError('stage-scoped operator lesson needs distinct real memory references')
    contexts, stages = [], set()
    for ref in refs:
        memory = memories.get(ref['id'])
        if (memory is None or memory['record_kind'] != 'optimization_memory'
                or memory['record_hash'] != ref['record_hash']):
            raise ValueError('lesson planning memory identity differs')
        identity = memory['body']['identity']
        if identity['operator'] != body.get('operator') or identity['split'] != body['split']:
            raise ValueError('lesson planning operator/split differs from memory')
        attrs = memory['body']['intervention']['attributes']
        stage = attrs.get('optimization_stage')
        if stage not in ('algorithm_parallel', 'execution'):
            raise ValueError('lesson memory has no explicit optimization stage')
        if any(key not in attrs for key in LESSON_PLANNING_FIELDS):
            raise ValueError('lesson memory lacks planning context')
        if attrs['implementation_source_hash'] != memory['body']['sources']['candidate']:
            raise ValueError('lesson memory implementation differs from actual source')
        stages.add(stage)
        contexts.append({'memory_id': ref['id'], 'memory_record_hash': ref['record_hash'],
            'source_attempt_id': identity['candidate_id'],
            **{key: copy.deepcopy(attrs[key]) for key in LESSON_PLANNING_FIELDS}})
    if len(stages) != 1:
        raise ValueError('operator lesson mixes algorithm_parallel and execution memories')
    return {'optimization_stage': stages.pop(), 'planning_contexts': contexts}


def verify_lesson_planning(body, memories):
    binding = lesson_planning_bindings(body, memories)
    if binding is None:
        return
    attrs = body['intervention']['attributes']
    if any(canonical(attrs.get(key)) != canonical(value) for key, value in binding.items()):
        raise ValueError('lesson stage or planning contexts differ from real memories')
    facts = [body['intervention'], *body['diagnosis']['symptoms'], *body['diagnosis']['hypotheses'],
             *body['effective_conditions'], *body['ineffective_conditions'], *body['counterexamples'], *body['claims']]
    for fact in facts:
        scoped = fact['attributes']
        if 'optimization_stage' in scoped and scoped['optimization_stage'] != binding['optimization_stage']:
            raise ValueError('lesson fact optimization stage contradicts its memories')
        contexts = binding['planning_contexts']
        if 'cases' in scoped and (not isinstance(scoped['cases'], list)
                or any(type(cid) is not int or cid < 0 for cid in scoped['cases'])
                or scoped['cases'] != fact['case_ids']):
            raise ValueError('lesson direct cases scope differs from canonical case_ids')
        if 'planning_contexts' in scoped and fact is not body['intervention']:
            declared = scoped['planning_contexts']
            if (not isinstance(declared, list) or not declared
                    or any(not isinstance(ctx, dict) or not any(canonical(ctx) == canonical(real) for real in contexts) for ctx in declared)
                    or len({ctx['memory_id'] for ctx in declared}) != len(declared)):
                raise ValueError('lesson condition planning_contexts are absent from its memories')
            contexts = declared
        for key in LESSON_PLANNING_FIELDS:
            if key in scoped and key != 'dispatch_selections':
                contexts = [c for c in contexts if c[key] == scoped[key]]
        if 'dispatch_selections' in scoped:
            declared = scoped['dispatch_selections']
            if not isinstance(declared, list) or not declared or any(not isinstance(row, dict) for row in declared):
                raise ValueError('lesson condition dispatch_selections must be actual selected rows')
            contexts = [ctx for ctx in contexts if all(any(canonical(row) == canonical(real)
                        for real in ctx['dispatch_selections']) for row in declared)]
        if not contexts:
            raise ValueError('lesson condition plan/architecture/source/dispatch is absent from its memories')
        selection_keys = ('tiling_key', 'kernel_entry', 'group_id')
        conditions = {key: scoped[key] for key in selection_keys if key in scoped}
        if conditions or fact['case_ids']:
            selections = [row for ctx in contexts for row in ctx['dispatch_selections']
                          if all(type(row.get(key)) is type(value) and row.get(key) == value for key, value in conditions.items())
                          and ('dispatch_selections' not in scoped or any(canonical(row) == canonical(real)
                               for real in scoped['dispatch_selections']))]
            if not selections or any(cid not in {r.get('case_id') for r in selections} for cid in fact['case_ids']):
                raise ValueError('lesson condition key/entry/case is absent from its memories')


def normalize_lessons(items, memories, evidence):
    out = {}
    for item in items:
        split = item.get('split', 'train'); refs = []
        def index_entries(entries):
            result = []
            for entry in entries:
                if isinstance(entry, dict) and entry.get('path'):
                    result.append(evidence.file(entry['path'], split=split, selector=str(entry.get('selector', '')), purpose=str(entry.get('purpose', 'lesson evidence'))))
            return result
        refs = index_entries(item.get('evidence', []))
        def convert(key, values, claims=False):
            result = []
            for i, value in enumerate(values):
                value = {'statement': value} if isinstance(value, str) else value
                local = index_entries(value.get('evidence', []))
                def clean_nested(node):
                    if isinstance(node, list): return [clean_nested(v) for v in node]
                    if isinstance(node, dict):
                        result = {k: clean_nested(v) for k, v in node.items() if k != 'evidence'}
                        if 'evidence' in node: result['evidence_ids'] = index_entries(node['evidence'])
                        return result
                    return node
                value = clean_nested(value)
                f = fact(str(value.get('id', item['id'] + '/' + key + '/' + str(i))), value, local or refs)
                if claims: f['status'] = value['status']
                result.append(f)
            return result
        diagnosis = item.get('diagnosis', {})
        links = []
        for link in item.get('graph_links', []):
            if isinstance(link, str): link = {'node_id': link}
            links.append({'graph_version': link.get('graph_version', 'v0001'), 'node_id': link.get('node_id', link.get('graph_id', '')), 'basis': str(link.get('basis', 'Retrospective knowledge association; not a route'))})
        memory_refs = []
        for cid in item.get('source_attempt_ids', []):
            found = [r for r in memories if r['body']['identity']['candidate_id'] == cid and r['body']['identity']['split'] == split]
            if len(found) != 1: raise ValueError('ambiguous lesson candidate: ' + cid)
            memory_refs.append({'id': found[0]['id'], 'record_hash': found[0]['record_hash']})
        body = {'kind': item['kind'], 'operator': item.get('operator'), 'split': split, 'title': item['title'],
                'diagnosis': {'symptoms': convert('symptom', diagnosis.get('symptoms', [])), 'hypotheses': convert('hypothesis', diagnosis.get('hypotheses', [])),
                              'missing_evidence': diagnosis.get('missing_evidence', []), 'retrospective': True, 'evidence_ids': refs},
                'intervention': convert('intervention', [item['intervention']])[0],
                'effective_conditions': convert('effective', item.get('effective_conditions', [])),
                'ineffective_conditions': convert('ineffective', item.get('ineffective_conditions', [])),
                'counterexamples': convert('counterexample', item.get('counterexamples', [])),
                'claims': convert('claim', item.get('claims', []), True), 'limitations': item.get('limitations', []),
                'next_questions': item.get('next_questions', []), 'graph_links': links, 'memory_refs': memory_refs,
                'evidence_ids': refs, 'retrospective': True}
        out[item['id']] = body
    return out


def object_path(root, h):
    if not HASH_RE.match(h): raise ValueError('invalid content hash')
    return Path(root) / 'cas' / 'sha256' / h[7:9] / h[9:]


def store_bytes(root, data):
    h = digest_bytes(data); p = object_path(root, h); p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        if p.read_bytes() != data: raise ValueError('CAS collision or corruption')
    else:
        with p.open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
    return h


def previous_records(root):
    pointer = Path(root) / 'current.json'
    if not pointer.exists(): return {}
    verify(root)
    current = strict_loads(pointer.read_bytes()); base = Path(root) / 'revisions' / current['revision']
    records = {}
    for split in ('train', 'validation'):
        for name in ('optimization_traces.jsonl', 'lessons.jsonl'):
            for row in load_rows(base / split / name): records[row['id']] = row
    return records


def write_synced(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())


def publish(root, memory_bodies, lesson_builder, evidence, metadata):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    with (root / '.publish.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = previous_records(root)
        memories = [seal('optimization_memory', k, v, previous.get(k)) for k, v in sorted(memory_bodies.items())]
        lesson_bodies = lesson_builder(memories)
        lessons = [seal('lesson', k, v, previous.get(k)) for k, v in sorted(lesson_bodies.items())]
        files = {}
        for split in ('train', 'validation'):
            files[split + '/optimization_traces.jsonl'] = b''.join(canonical(r) for r in memories if r['body']['identity']['split'] == split)
            files[split + '/lessons.jsonl'] = b''.join(canonical(r) for r in lessons if r['body']['split'] == split)
        for kind in ('optimization_memory', 'lesson'): files['schemas/' + kind + '.schema.json'] = canonical(schema(kind))
        files['evidence_index.json'] = canonical(evidence.entries)
        files['contexts.json'] = canonical(evidence.contexts)
        files['metadata.json'] = canonical(metadata)
        # Archive each record under its canonical byte hash; semantic hash omits record_hash.
        record_objects = {r['record_hash']: store_bytes(root, canonical(r)) for r in [*memories, *lessons]}
        if previous:
            for r in previous.values(): record_objects[r['record_hash']] = store_bytes(root, canonical(r))
        for h, value in evidence.contexts.items():
            if store_bytes(root, canonical(value)) != h: raise AssertionError('context hash')
        oldmap = {}
        if (root/'current.json').exists():
            cur = strict_loads((root/'current.json').read_bytes())
            oldmap = strict_loads((root/'revisions'/cur['revision']/'record_objects.json').read_bytes())
        files['record_objects.json'] = canonical({**oldmap, **record_objects})
        manifest = {'schema_version': VERSION, 'files': {k: digest_bytes(v) for k, v in sorted(files.items())},
                    'counts': {'optimization_attempts': len(memories), 'lessons': len(lessons),
                               'measurement_continuations': sum(e['relation'] == 'measurement_continuation' for r in memories for e in r['body']['evaluations'])}}
        revision = digest(manifest)[7:]; files['manifest.json'] = canonical(manifest)
        target = root / 'revisions' / revision
        if target.exists():
            for name, data in files.items():
                if (target/name).read_bytes() != data: raise ValueError('immutable revision conflict')
        else:
            (root/'revisions').mkdir(exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=root/'revisions'))
            try:
                for name, data in files.items(): write_synced(temporary/name, data)
                temporary.rename(target)
                fd = os.open(root/'revisions', os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
            except BaseException:
                # Staging is deliberately retained for forensic recovery; never current.
                raise
        pointer = {'revision': revision, 'manifest_hash': digest(manifest)}
        verify(root, prospective_pointer=pointer)
        tmp = root / '.current.tmp'; write_synced(tmp, canonical(pointer)); os.replace(tmp, root/'current.json')
        fd = os.open(root, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return {'root': str(root.resolve()), 'revision': revision, **manifest['counts']}


@external_evidence_reader
def verify(root, deep=False, prospective_pointer=None, *, evidence_paths=None, graph_root=None):
    """Pure reader: no store constructors, gate replay, registrations or writes."""
    root = Path(root); pointer = prospective_pointer or strict_loads((root/'current.json').read_bytes())
    if not re.fullmatch('[0-9a-f]{64}', pointer['revision']): raise ValueError('invalid revision')
    base = root/'revisions'/pointer['revision']; manifest = strict_loads((base/'manifest.json').read_bytes())
    expected_files = {'evidence_index.json', 'contexts.json', 'metadata.json', 'record_objects.json',
                      'schemas/optimization_memory.schema.json', 'schemas/lesson.schema.json',
                      *[s+'/'+n for s in ('train', 'validation') for n in ('optimization_traces.jsonl', 'lessons.jsonl')]}
    if set(manifest['files']) != expected_files: raise ValueError('manifest file set')
    if digest(manifest) != pointer['manifest_hash'] or digest(manifest)[7:] != pointer['revision']: raise ValueError('manifest hash')
    for name, expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe manifest path')
        if digest_bytes((base/name).read_bytes()) != expected: raise ValueError('file hash: ' + name)
    index = strict_loads((base/'evidence_index.json').read_bytes()); contexts = strict_loads((base/'contexts.json').read_bytes())
    metadata = strict_loads((base/'metadata.json').read_bytes())
    # Portable bundles preserve signed records and the original evidence index.
    # An explicit, complete map changes only where immutable bytes are read.
    # Never silently fall back to a historical checkout when a map is supplied.
    if evidence_paths is not None:
        if not isinstance(evidence_paths, dict) or set(evidence_paths) != {v['path'] for v in index.values()}:
            raise ValueError('portable evidence map must cover exactly the evidence index')
        if any(not isinstance(v, (str, Path)) for v in evidence_paths.values()):
            raise ValueError('invalid portable evidence location')
    def evidence_path(original):
        return Path(original if evidence_paths is None else evidence_paths[original])
    def evidence_bytes(original):
        return external_evidence_bytes(original) if evidence_paths is None else evidence_path(original).read_bytes()
    entry_schema = obj({'sha256': H, 'path': S, 'size_bytes': I, 'split': {'enum': ['train', 'validation']},
                        'selector': S, 'purposes': REFS})
    for key, entry in index.items():
        Draft202012Validator(entry_schema).validate(entry)
        if key != 'e-' + digest([entry['split'], entry['sha256'], entry['selector']])[7:31]:
            raise ValueError('evidence identifier mismatch')
    for kind in ('optimization_memory', 'lesson'):
        if strict_loads((base/'schemas'/(kind+'.schema.json')).read_bytes()) != schema(kind):
            raise ValueError('schema changed without version change')
    objects = strict_loads((base/'record_objects.json').read_bytes()); memories = {}; lessons = []; all_records = {}
    for split in ('train', 'validation'):
        for filename in ('optimization_traces.jsonl', 'lessons.jsonl'):
            for row in load_rows(base/split/filename):
                validate_record(row)
                expected_kind = 'optimization_memory' if filename == 'optimization_traces.jsonl' else 'lesson'
                if row['record_kind'] != expected_kind: raise ValueError('record kind/file mismatch')
                if row['id'] in all_records: raise ValueError('duplicate record id')
                all_records[row['id']] = row
                actual_split = row['body']['identity']['split'] if row['record_kind'] == 'optimization_memory' else row['body']['split']
                if actual_split != split: raise ValueError('cross-split record')
                if row['record_kind'] == 'optimization_memory': memories[row['id']] = row
                else: lessons.append(row)
    def check_refs(value, split):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('evidence_ids', 'source_record_refs'):
                    for ref in v:
                        if ref not in index or index[ref]['split'] != split: raise ValueError('missing or cross-split evidence: ' + ref)
                if k == 'evidence_id' and (v not in index or index[v]['split'] != split): raise ValueError('evidence identity')
                check_refs(v, split)
        elif isinstance(value, list):
            for v in value: check_refs(v, split)
    for row in all_records.values():
        split = row['body'].get('split', row['body'].get('identity', {}).get('split'))
        check_refs(row['body'], split)
        h = row['record_hash']; data = object_path(root, objects[h]).read_bytes()
        if digest_bytes(data) != objects[h] or strict_loads(data) != row: raise ValueError('record CAS')
        previous = row['previous_ref']; seen = {h}; expected_revision = row['revision'] - 1
        while previous:
            if previous in seen or previous not in objects: raise ValueError('revision chain')
            seen.add(previous); data = object_path(root, objects[previous]).read_bytes()
            if digest_bytes(data) != objects[previous]: raise ValueError('historical CAS hash')
            prior = strict_loads(data); validate_record(prior)
            prior_split = prior['body'].get('split', prior['body'].get('identity', {}).get('split'))
            if (prior['id'] != row['id'] or prior['record_hash'] != previous or prior['revision'] != expected_revision
                    or prior['record_kind'] != row['record_kind'] or prior_split != split):
                raise ValueError('revision identity')
            expected_revision -= 1
            previous = prior['previous_ref']
        if expected_revision != 0: raise ValueError('incomplete revision chain')
    for h, value in contexts.items():
        if digest(value) != h or digest_bytes(object_path(root, h).read_bytes()) != h: raise ValueError('context CAS')
        def check_context_refs(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    if k == 'evidence_ids' and not all(e in index for e in x): raise ValueError('context evidence missing')
                    check_context_refs(x)
            elif isinstance(v, list):
                for x in v: check_context_refs(x)
        check_context_refs(value)
    for row in memories.values():
        body = row['body']
        if body['context_ref'] not in contexts or body['knowledge']['catalog_ref'] not in contexts: raise ValueError('missing context')
        seen_evals = set()
        bound_sources = {index[e]['sha256'] for e in body['sources']['evidence_ids']}
        if not all(body['sources'][k] in bound_sources for k in ('original_baseline', 'direct_parent', 'candidate', 'patch')):
            raise ValueError('source/patch evidence binding')
        parent_id = body['sources']['parent_attempt_id']
        if parent_id is None:
            if body['sources']['direct_parent'] != body['sources']['original_baseline']: raise ValueError('original parent binding')
        else:
            parents = [m for m in memories.values() if m['body']['identity']['candidate_id'] == parent_id
                       and m['body']['identity']['split'] == body['identity']['split']]
            if len(parents) != 1 or parents[0]['body']['sources']['candidate'] != body['sources']['direct_parent']:
                raise ValueError('parent attempt binding')
        for ev in body['evaluations']:
            if ev['id'] in seen_evals: raise ValueError('duplicate evaluation')
            seen_evals.add(ev['id'])
            if ev['comparison']['candidate'] != body['sources']['candidate']: raise ValueError('candidate source mismatch')
            if ev['comparison']['baseline'] not in (body['sources']['direct_parent'], body['sources']['original_baseline']):
                raise ValueError('baseline source mismatch')
        if len(body['machine_results']) != len(seen_evals) or {m['evaluation_id'] for m in body['machine_results']} != seen_evals:
            raise ValueError('machine evaluation binding')
    lesson_contract = metadata.get('lesson_planning_contract')
    if lesson_contract not in (None, LESSON_PLANNING_CONTRACT):
        raise ValueError('unknown lesson planning contract')
    for row in lessons:
        body = row['body']; claim_ids = [c['id'] for c in body['claims']]
        if lesson_contract == LESSON_PLANNING_CONTRACT:
            verify_lesson_planning(body, memories)
        if len(claim_ids) != len(set(claim_ids)): raise ValueError('duplicate claims')
        for group in ('effective_conditions', 'ineffective_conditions', 'counterexamples'):
            for condition in body[group]:
                if not set(condition['claim_ids']).issubset(claim_ids): raise ValueError('unknown condition claim')
        for ref in body['memory_refs']:
            memory = memories.get(ref['id'])
            if not memory or memory['record_hash'] != ref['record_hash'] or memory['body']['identity']['split'] != body['split']: raise ValueError('lesson memory binding')
        for link in body['graph_links']:
            if (lesson_contract == LESSON_PLANNING_CONTRACT and body['kind'] == 'operator_optimization'
                    and link['graph_version'] != 'v0002'):
                raise ValueError('stage-scoped operator lesson requires bound v0002 graph associations')
            def collect_ids(v):
                if isinstance(v, dict):
                    if isinstance(v.get('id'), str): yield v['id']
                    for x in v.values(): yield from collect_ids(x)
                elif isinstance(v, list):
                    for x in v: yield from collect_ids(x)
            nodes = set()
            if link['graph_version'] == 'v0001':
                authority = ROOT/'skillgraph/versions' if graph_root is None else Path(graph_root)
                for p in (authority/'v0001').glob('*.json'): nodes.update(collect_ids(strict_loads(p.read_bytes())))
            elif link['graph_version'] == 'v0002':
                declarations = metadata.get('graph_snapshots', {}).get('v0002', [])
                if not declarations: raise ValueError('unknown graph version: missing frozen snapshot')
                for declaration in declarations:
                    entry = index.get(declaration.get('evidence_id'))
                    if not entry or entry['split'] != body['split'] or entry['selector']:
                        raise ValueError('graph snapshot evidence binding')
                    raw = evidence_bytes(entry['path'])
                    if digest_bytes(raw) != entry['sha256']: raise ValueError('graph snapshot changed')
                    graph = strict_loads(raw)
                    if graph.get('graph_version') != 'v0002' or digest_bytes(canonical(graph)[:-1]) != declaration.get('content_hash'):
                        raise ValueError('graph snapshot canonical identity')
                    if lesson_contract == LESSON_PLANNING_CONTRACT and body['kind'] == 'operator_optimization':
                        contexts = body['intervention']['attributes']['planning_contexts']
                        if declaration['content_hash'] not in {ctx['graph_hash'] for ctx in contexts}:
                            continue
                        for transformation in graph.get('transformations', []):
                            if (transformation['id'] == link['node_id'] and transformation.get('optimization_stage')
                                    not in (body['intervention']['attributes']['optimization_stage'], 'any')):
                                raise ValueError('lesson graph transformation belongs to a different optimization stage')
                    nodes.update(collect_ids(graph))
            else:
                raise ValueError('unknown graph version')
            if link['node_id'] not in nodes: raise ValueError('unknown graph node')
    actual_counts = {'optimization_attempts': len(memories), 'lessons': len(lessons),
                     'measurement_continuations': sum(e['relation'] == 'measurement_continuation' for m in memories.values() for e in m['body']['evaluations'])}
    if manifest['counts'] != actual_counts: raise ValueError('manifest counts')
    verified = 0; cache = {}; contents = {}; selector_cache = {}
    selector_paths = {v['path'] for v in index.values() if v['selector']}
    if deep:
        for entry in index.values():
            path = entry['path']; expected = entry['sha256']
            if path not in cache:
                fp=evidence_fingerprint(evidence_path(path),external=evidence_paths is None)
                cache[path]=(fp['sha256'],fp['size_bytes'])
                if path in selector_paths:contents[path]=evidence_bytes(path)
            if cache[path] != (expected, entry['size_bytes']): raise ValueError('external evidence changed: ' + path)
            validate_selector(entry['selector'], evidence_path(path), contents.get(path), selector_cache)
            verified += 1
    return {'valid': True, 'revision': pointer['revision'], **manifest['counts'], 'evidence_entries': len(index),
            'deep_evidence_entries_verified': verified, 'unique_external_files_read': len(cache), 'hardware_executed': False}


def validate_selector(selector, path, data=None, cache=None):
    if not selector: return
    line = re.fullmatch(r'line[: ](\d+)(?: (/.+))?', selector)
    lines = re.fullmatch(r'lines (\d+)-(end|\d+)', selector)
    if data is None: data = external_evidence_bytes(path)
    if cache is None: cache = {}
    if lines:
        count = len(data.splitlines()); start = int(lines[1]); end = count if lines[2] == 'end' else int(lines[2])
        if not 1 <= start <= end <= count: raise ValueError('line selector out of range')
        return
    if line:
        rows = data.splitlines(); n = int(line[1])
        if not 1 <= n <= len(rows): raise ValueError('JSONL line selector out of range')
        key = (str(path), n)
        if key not in cache: cache[key] = json.loads(rows[n-1])
        value = cache[key]; selector = line[2] or ''
    else:
        key = (str(path), None)
        if key not in cache: cache[key] = json.loads(data)
        value = cache[key]
    if selector and not selector.startswith('/'): raise ValueError('unsupported evidence selector: '+selector)
    for part in selector.split('/')[1:] if selector else []:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]


def export(parent, serial, output):
    parent, serial = Path(parent).resolve(), Path(serial).resolve(); evidence = Evidence((parent, serial))
    memories = import_memories(parent, serial, evidence)
    from trace_v2_lessons import build_lessons
    items = build_lessons(parent, serial)
    metadata = {'schema_version': VERSION, 'parent_run': str(parent), 'serial_run': str(serial),
                'scope': 'known_workload_conditional_learning', 'hardware_executed': False, 'automatic_restart': False,
                'resume_requires_explicit_start': True,
                'frozen_pending_source_candidates': sum(not any(e['relation'] == 'measurement_continuation' for e in m['evaluations']) for m in memories.values()),
                'producer_hashes': {name: digest_bytes((ROOT/'scripts'/name).read_bytes()) for name in ('trace_v2_dataset.py', 'trace_v2_lessons.py', 'trace_v2_campaign.py')},
                'legacy_gate_and_episode_semantics': 'unchanged', 'new_source_attempts': 0}
    return publish(output, memories, lambda rows: normalize_lessons(items, rows, evidence), evidence, metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export'); exp.add_argument('--parent', required=True, type=Path); exp.add_argument('--serial', required=True, type=Path); exp.add_argument('--output', required=True, type=Path)
    ver = sub.add_parser('verify'); ver.add_argument('--output', required=True, type=Path); ver.add_argument('--deep', action='store_true')
    args = parser.parse_args()
    result = export(args.parent, args.serial, args.output) if args.command == 'export' else verify(args.output, args.deep)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))

if __name__ == '__main__': main()
