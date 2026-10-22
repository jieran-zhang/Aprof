#!/usr/bin/env python3
"""CPU-only LIVE manifest -> strict v2 projection; no runtime/hardware imports.

Usage: python scaffolding/collection/scripts/feedback_trace_export.py --input LIVE/recording.json
       [--output LIVE/dataset/v2]

Input contract (JSON, paths relative to the input file):
  {"run_id": str, "task_id": str, "attempts": [], "lessons": [],
   "task_checkpoints": [], "artifact_index": []}
Each attempt has id, operator, task_id (defaults to collection task_id), split (default train), sources (original_baseline,
 direct_parent, candidate, patch: evidence pointers; parent_attempt_id: str|null),
 context: object, diagnosis: {symptoms: facts, hypotheses: facts,
 missing_evidence: strings, retrospective: bool}, intervention: fact,
 evaluations: [], timeline: [], actual_reads: [], next_decision: object.
A fact is {statement, basis, case_ids?, evidence?: [pointer], ...attributes}.
Basis must explicitly distinguish prospective_agent_observation from
retrospective_curator (or a more specific truthful attribution).
Evidence pointer: {path, selector?: JSON pointer or 'line:N /pointer', sha256?}.
Sources must point to complete frozen source/patch files or source inventories,
not selectors. Their byte hashes bind the comparison, not a reconstructed tree.
Evaluation: {id, session_id, baseline: original_baseline|direct_parent,
 relation: original_attempt|measurement_continuation, stages: [{name, record:
 pointer}], measurement_quality, observations?: pointer, machine_result?: pointer}.
Stage record selects an execution/completion object with status and optional
error/reason. Observations select {summary?: object, cases?: [object]}.
Machine result selects an actual runtime result object containing verdict,
first_failed_stage, graph_policy_eligible, episode_ref, metrics. Omit if absent:
not_recorded is an absence sentinel, never a generated gate verdict.
Timeline: [{record: pointer}] selects an actually recorded object with timestamp,
 event_type and summary, or a TraceWriter payload. Payload summaries use only
 recorded reason/hypothesis/action/operator/stage fields or bounded canonical
 payload text; no curator text is promoted into prospective history.
Actual reads: [{record: pointer}] selects {purpose, ...}; only a recorded access
 belongs here. Parsed machine measurements are not knowledge reads.
Next decision is {action, reason, evidence?: [pointer]}; missing -> not_recorded.
Lessons use trace_v2_dataset.normalize_lessons' input contract (id, kind, title,
 intervention, evidence, optional diagnosis/conditions/claims/source_attempt_ids).
Lessons are always retrospective. Optional graph_links are explicit objects
{graph_version, node_id, basis}; existing v2 verification checks version and node
existence. These are knowledge associations, never routes or probabilities.
Task checkpoints hold calibration blockers separately from source attempts.
Artifact index is [pointer]; all content is snapshotted, indexed externally.
Repeated evaluations with the same id/content are deduplicated; conflicting ids
or reusing a physical stage set under another id are rejected, not recounted.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import trace_v2_dataset as v2


class Recorder:
    def __init__(self, manifest, output):
        self.manifest = Path(manifest).resolve()
        self.output = Path(output).resolve()
        self.evidence = v2.Evidence()
        self.origins = {}

    def freeze_physical(self, path, expected=None):
        """Freeze physical evidence without holding its payload in memory.

        Existing content identities and CAS layout are unchanged. Publish the
        fully hashed temporary inode without replacing an existing object.
        """
        root = self.output / 'external_evidence'
        root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.freeze-', dir=root, delete=False) as stream:
                temporary = Path(stream.name)
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
                        stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            h = 'sha256:' + digest.hexdigest()
            if expected is not None and h != expected:
                raise ValueError('evidence hash mismatch: ' + str(path))
            frozen = v2.object_path(root, h)
            frozen.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(temporary, frozen)
            except FileExistsError:
                if v2.evidence_fingerprint(frozen, external=False)['sha256'] != h:
                    raise ValueError('CAS collision or corruption')
            fd = os.open(frozen.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return frozen, h
        finally:
            if temporary is not None:
                temporary.unlink()

    def pointer(self, pointer, split='train', purpose='LIVE evidence'):
        if not isinstance(pointer, dict) or not isinstance(pointer.get('path'), str):
            raise ValueError('evidence requires a path')
        path = (self.manifest.parent / pointer['path']).resolve()
        purpose = pointer.get('purpose', purpose) + ' [' + path.name + ']'
        try:
            import level2_evidence_storage as storage
        except ModuleNotFoundError as error:
            if error.name != 'level2_evidence_storage':
                raise
            binding = None
        else:
            binding = storage.evidence_binding(path, pointer.get('sha256'))
        if binding is not None:
            # The current trusted reader verifies the complete archive and its
            # original authority. Retain its logical member; the existing
            # portable exporter carries the tar/proof closure once per seal.
            origin = binding['origin']
            if origin['path'] != str(path):
                raise ValueError('archive evidence origin differs')
            frozen, h = path, origin['sha256']
        else:
            frozen, h = self.freeze_physical(path, pointer.get('sha256'))
        selector = pointer.get('selector', '')
        v2.validate_selector(selector, frozen)
        ref = self.evidence.file(frozen, split=split, selector=selector,
                                 purpose=purpose, expected=h)
        self.origins.setdefault(ref, set()).add(str(path))
        return ref

    def selected(self, pointer, split='train', purpose='recorded observation'):
        ref = self.pointer(pointer, split, purpose)
        entry = self.evidence.entries[ref]
        data = v2.external_evidence_bytes(entry['path'])
        selector = entry['selector']
        line = re.fullmatch(r'line[: ](\d+)(?: (/.+))?', selector)
        if line:
            value = v2.strict_loads(data.splitlines()[int(line[1])-1])
            selector = line[2] or ''
        else:
            value = v2.strict_loads(data)
        for part in selector.split('/')[1:] if selector else []:
            part = part.replace('~1', '/').replace('~0', '~')
            value = value[int(part)] if isinstance(value, list) else value[part]
        return ref, value

    def refs(self, pointers, split):
        return [self.pointer(p, split) for p in pointers]

    def fact(self, identifier, value, split, fallback):
        if not isinstance(value, dict) or not value.get('basis') or not value.get('statement'):
            raise ValueError('facts require explicit statement and basis')
        return v2.fact(identifier, value, self.refs(value.get('evidence', []), split) or [fallback])

    def memory(self, attempt, number, config):
        a = copy.deepcopy(attempt)
        split = a.get('split', 'train')
        root_ref = self.pointer({'path': str(self.manifest), 'selector': '/attempts/'+str(number)}, split,
                                'curator manifest; not proof of prospective knowledge')
        sources = {}; source_refs = []
        for key in ('original_baseline', 'direct_parent', 'candidate', 'patch'):
            pointer = a['sources'][key]
            if pointer.get('selector'): raise ValueError('source must bind complete bytes')
            ref = self.pointer(pointer, split, 'frozen '+key)
            sources[key] = self.evidence.entries[ref]['sha256']; source_refs.append(ref)
        sources.update(parent_attempt_id=a['sources'].get('parent_attempt_id'), evidence_ids=source_refs)
        if sources['candidate'] == sources['direct_parent']:
            raise ValueError('unchanged source is a calibration/checkpoint, not an attempt')
        diagnosis = a.get('diagnosis', {})
        diag = {key: [self.fact(a['id']+'/'+key+'/'+str(i), f, split, root_ref)
                      for i, f in enumerate(diagnosis.get(key, []))] for key in ('symptoms', 'hypotheses')}
        diag.update(missing_evidence=diagnosis.get('missing_evidence', []),
                    retrospective=diagnosis.get('retrospective', True), evidence_ids=[root_ref])
        evaluations = []; machines = []; seen = {}; physical = set(); missing = {}
        for ev in a.get('evaluations', []):
            if ev['id'] in seen:
                if seen[ev['id']] != ev: raise ValueError('conflicting evaluation id')
                continue
            seen[ev['id']] = ev
            if ev['baseline'] not in ('original_baseline', 'direct_parent'):
                raise ValueError('evaluation baseline must identify source role')
            if ev['relation'] not in ('original_attempt', 'measurement_continuation'):
                raise ValueError('unknown evaluation relation')
            stages = []; refs = []
            for stage in ev['stages']:
                ref, record = self.selected(stage['record'], split, 'machine stage completion')
                if not isinstance(record, dict) or not isinstance(record.get('status'), str):
                    raise ValueError('stage evidence must select an object with status')
                stages.append(dict(name=stage['name'], status=record['status'],
                                   reason=record.get('reason', record.get('error')), evidence_ids=[ref]))
                refs.append(ref)
            if not refs: raise ValueError('evaluation requires actual stage evidence')
            key = tuple(sorted(refs))
            if key in physical: raise ValueError('physical execution reused as another evaluation')
            physical.add(key)
            obs = {}
            if ev.get('observations'):
                ref, obs = self.selected(ev['observations'], split, 'machine measurements; not knowledge access')
                refs.append(ref)
            evaluations.append(dict(id=ev['id'], run_id=config['run_id'], session_id=ev['session_id'],
                relation=ev['relation'], comparison={'baseline': sources[ev['baseline']], 'candidate': sources['candidate']},
                stages=stages, measurement_quality=ev['measurement_quality'], summary=obs.get('summary', {}),
                cases=obs.get('cases', []), evidence_ids=refs))
            if ev.get('machine_result'):
                ref, result = self.selected(ev['machine_result'], split, 'recorded runtime machine result')
                machine = {k: result[k] for k in ('verdict', 'first_failed_stage', 'graph_policy_eligible', 'episode_ref', 'metrics')}
                machine.update(evaluation_id=ev['id'], evidence_ids=[ref])
            else:
                machine = dict(evaluation_id=ev['id'], verdict='not_recorded', first_failed_stage=None,
                               graph_policy_eligible=False, episode_ref=None, metrics={}, evidence_ids=[])
                missing['machine_results.'+ev['id']] = ('No runtime verdict, gate stage, graph eligibility or episode was recorded. '
                    'not_recorded/null/false encode absence only; stage process outcomes above remain independent.')
            machines.append(machine)
        timeline = []
        for event in a.get('timeline', []):
            ref, row = self.selected(event['record'], split, 'recorded prospective event')
            if 'summary' in row:
                summary = row['summary']
                if not isinstance(summary, str): raise ValueError('recorded event summary must be a string')
            else:
                payload = row['payload']
                fields = {key: payload[key] for key in ('reason', 'hypothesis', 'action', 'operator', 'stage')
                          if isinstance(payload, dict) and key in payload}
                summary = v2.canonical(fields or payload).decode().rstrip('\n')
                if len(summary) > 320: summary = summary[:319] + '…'
            timeline.append({**{k: row[k] for k in ('timestamp', 'event_type')},
                             'summary': summary, 'evidence_id': ref})
        reads = []
        for read in a.get('actual_reads', []):
            ref, row = self.selected(read['record'], split, 'recorded knowledge access, not machine artifact parsing')
            reads.append({'evidence_id': ref, 'purpose': row['purpose']})
        decision = a.get('next_decision')
        if decision:
            decision = dict(action=decision['action'], reason=decision['reason'], evidence_ids=self.refs(decision.get('evidence', []), split) or [root_ref])
        else:
            decision = dict(action='not_recorded', reason='No agent next decision recorded.', evidence_ids=[])
        return dict(identity=dict(run_id=config['run_id'], task_id=a.get('task_id', config['task_id']), candidate_id=a['id'], operator=a['operator'], split=split),
            sources=sources, context_ref=self.evidence.context(a.get('context', {})),
            knowledge=dict(catalog_ref=self.evidence.context(a.get('knowledge_catalog', {})), actual_reads=reads,
                           classification_note='Only explicit recorded accesses are knowledge reads; machine evidence and retrospective curator facts are separate.'),
            diagnosis=diag, intervention=self.fact(a['id']+'/intervention', a['intervention'], split, root_ref),
            evaluations=evaluations, machine_results=machines, timeline=sorted(timeline, key=lambda e: e['timestamp']),
            next_decision=decision, provenance=dict(retrospective=True, source_record_refs=[root_ref],
                importer_hash=v2.digest_bytes(Path(__file__).read_bytes()), knowledge_state='recorded_accesses_only' if reads else 'not_recorded',
                null_reasons=missing))

    def export(self):
        config = v2.strict_loads(self.manifest.read_bytes())
        memories = {}; source_attempts = set()
        for n, attempt in enumerate(config.get('attempts', [])):
            identifier = config['run_id']+'/'+attempt.get('split', 'train')+'/'+attempt['id']
            if identifier in memories: raise ValueError('duplicate source attempt')
            body = self.memory(attempt, n, config)
            source_key = (body['identity']['split'], body['identity']['operator'], body['sources']['candidate'])
            if source_key in source_attempts:
                raise ValueError('same candidate source must be one attempt with multiple evaluations')
            source_attempts.add(source_key)
            memories[identifier] = body
        # Freeze all explicit lesson evidence, including nested case conditions.
        def freeze(value, split):
            if isinstance(value, list): return [freeze(v, split) for v in value]
            if isinstance(value, dict):
                out = {}
                for key, item in value.items():
                    if key == 'evidence':
                        out[key] = [dict(path=self.evidence.entries[r]['path'], selector=self.evidence.entries[r]['selector']) for r in self.refs(item, split)]
                    else: out[key] = freeze(item, split)
                return out
            return value
        lessons = []
        lesson_ids = set()
        for i, item in enumerate(config.get('lessons', [])):
            for link in item.get('graph_links', []):
                if (not isinstance(link, dict)
                        or set(link) != {'graph_version', 'node_id', 'basis'}
                        or any(not isinstance(link[k], str) or not link[k].strip() for k in link)):
                    raise ValueError('graph association requires explicit graph_version, node_id and basis only')
            if item['id'] in lesson_ids: raise ValueError('duplicate lesson')
            lesson_ids.add(item['id'])
            item = copy.deepcopy(item)
            item.setdefault('evidence', []).append({'path': str(self.manifest), 'selector': '/lessons/'+str(i)})
            lessons.append(freeze(item, item.get('split', 'train')))
        checkpoint_refs = []
        for i, checkpoint in enumerate(config.get('task_checkpoints', [])):
            split = checkpoint.get('split', 'train')
            checkpoint_refs.append(self.pointer({'path': str(self.manifest), 'selector': '/task_checkpoints/'+str(i)}, split, 'task checkpoint; not a source attempt'))
            freeze(checkpoint, split)
        for pointer in config.get('artifact_index', []):
            self.pointer(pointer, pointer.get('split', 'train'), 'external full artifact index')
        metadata = dict(schema_version=v2.VERSION, run_id=config['run_id'], task_id=config['task_id'],
            exporter_hardware_executed=False, legacy_gate_and_episode_semantics='unchanged',
            new_source_attempts=len(memories), task_checkpoint_refs=checkpoint_refs,
            original_evidence_locations={k: sorted(v) for k,v in self.origins.items()},
            producer_hash=v2.digest_bytes(Path(__file__).read_bytes()))
        # All source selectors have already been deeply checked before commit.
        result = v2.publish(self.output, memories, lambda rows: v2.normalize_lessons(lessons, rows, self.evidence), self.evidence, metadata)
        result['verification'] = v2.verify(self.output, deep=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.input.parent/'dataset/v2'
    print(json.dumps(Recorder(args.input, output).export(), sort_keys=True))


if __name__ == '__main__':
    main()
