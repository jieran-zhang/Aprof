#!/usr/bin/env python3
"""Split-isolated CPU archive for new msprof observations; legacy gates are untouched.

archive_split writes a new v2 revision. verify_split is a pure reader. The
recorder binds complete source tar bytes; native source hashes are checked
separately against op_host/op_kernel members, never substituted for tar hashes.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tempfile
from types import SimpleNamespace

import feedback_trace_export
import msprof_exploration_campaign as campaign
import msprof_exploration_report as analysis
from shared_context_archive import FrozenRecorder, _safe_path
import trace_v2_dataset as v2

VERSION = 'msprof_exploration_archive_v1'
POLICY = dict(formal_admission='not_evaluated', graph_policy_eligible=False, episode_ref=None)
ENGINEERING_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINEERING_SCRIPTS.parent / 'src'))
from aprof_runtime.jsonio import content_hash
from aprof_runtime.planning import validate_planning_contract, validate_planning_context, verify_profile_probe, select_dispatch
from aprof_runtime.graph import validate_graph


def require(condition, message):
    if not condition:
        raise ValueError(message)


def map_lesson_evidence(node, transform):
    """Map structural evidence; fact attributes are opaque extensible JSON.

    An attributes payload may itself contain an ordinary key named evidence.
    Its provenance is the enclosing lesson/fact evidence, not a pointer list.
    """
    if isinstance(node, list):
        return [map_lesson_evidence(value, transform) for value in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key == 'attributes':
            result[key] = deepcopy(value)
        elif key == 'evidence':
            require(isinstance(value, list) and all(isinstance(ref, dict) and
                    isinstance(ref.get('path'), str) and ref['path'] for ref in value),
                    'structural lesson evidence must be a pointer list')
            result[key] = [transform(ref) for ref in value]
        else:
            result[key] = map_lesson_evidence(value, transform)
    return result


def normalize_exploration_lessons(items, memories, evidence, *, stage_scoped=False):
    """Use unchanged v2 lesson/link semantics with opaque-aware fact conversion.

    The legacy converter consumes every nested evidence key. Its structural
    lesson conversion receives empty facts; this adapter fills those facts via
    v2.fact after mapping structural evidence while preserving attributes JSON.
    No marker or temporary encoding can leak through legacy stringification.
    """
    skeletons = deepcopy(items)
    fields = ('effective_conditions', 'ineffective_conditions', 'counterexamples', 'claims')
    for item in skeletons:
        item['intervention'] = {}
        for field in fields:
            item[field] = []
        if 'diagnosis' in item:
            item['diagnosis']['symptoms'] = []
            item['diagnosis']['hypotheses'] = []
    result = v2.normalize_lessons(skeletons, memories, evidence)
    for item in items:
        split = item.get('split', 'train')
        body = result[item['id']]
        def index_entries(entries):
            require(isinstance(entries, list) and all(isinstance(ref, dict) and
                    isinstance(ref.get('path'), str) and ref['path'] for ref in entries),
                    'structural lesson evidence must be a pointer list')
            return [evidence.file(ref['path'], split=split, selector=str(ref.get('selector', '')),
                                  purpose=str(ref.get('purpose', 'lesson evidence'))) for ref in entries]
        def clean(node):
            if isinstance(node, list):
                return [clean(value) for value in node]
            if not isinstance(node, dict):
                return node
            out = {}
            for key, value in node.items():
                if key == 'attributes':
                    out[key] = deepcopy(value)
                elif key != 'evidence':
                    out[key] = clean(value)
            if 'evidence' in node:
                out['evidence_ids'] = index_entries(node['evidence'])
            return out
        def convert(key, values, claims=False):
            facts = []
            for i, value in enumerate(values):
                value = {'statement': value} if isinstance(value, str) else value
                if stage_scoped and body['kind'] == 'operator_optimization':
                    for scope_key in ('case_ids', 'cases'):
                        if scope_key in value:
                            require(isinstance(value[scope_key], list)
                                    and all(type(cid) is int and cid >= 0 for cid in value[scope_key]),
                                    'fresh lesson case scope must be a list of nonnegative integer IDs')
                    require(not {'case_ids', 'cases'} <= value.keys() or value['case_ids'] == value['cases'],
                            'fresh lesson case_ids and cases scopes contradict each other')
                local = index_entries(value.get('evidence', []))
                fact = v2.fact(str(value.get('id', item['id'] + '/' + key + '/' + str(i))),
                               clean(value), local or body['evidence_ids'])
                if claims:
                    fact['status'] = value['status']
                facts.append(fact)
            return facts
        diagnosis = item.get('diagnosis', {})
        body['diagnosis']['symptoms'] = convert('symptom', diagnosis.get('symptoms', []))
        body['diagnosis']['hypotheses'] = convert('hypothesis', diagnosis.get('hypotheses', []))
        body['intervention'] = convert('intervention', [item['intervention']])[0]
        for field, key in zip(fields, ('effective', 'ineffective', 'counterexample', 'claim')):
            body[field] = convert(key, item.get(field, []), claims=field == 'claims')
        if stage_scoped and body['kind'] == 'operator_optimization':
            memory_index = {row['id']: row for row in memories}
            binding = v2.lesson_planning_bindings(body, memory_index)
            require(item.get('optimization_stage', binding['optimization_stage']) == binding['optimization_stage'],
                    'declared lesson optimization stage differs from its memories')
            attrs = body['intervention']['attributes']
            require(all(key not in attrs or v2.canonical(attrs[key]) == v2.canonical(value) for key, value in binding.items()),
                    'declared lesson stage/planning context contradicts its memories')
            attrs.update(binding)
            v2.verify_lesson_planning(body, memory_index)
    return result

def load(path):
    return v2.strict_loads(Path(path).read_bytes())


def sha(path):
    return analysis.verification_storage.fingerprint(path)['sha256']


def native_tar_files(path):
    files = {}
    with tarfile.open(path) as archive:
        names = set()
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            require(not name.is_absolute() and '..' not in name.parts, 'unsafe source archive member')
            require(member.name not in names, 'duplicate source archive member')
            names.add(member.name)
            require(member.isfile() or member.isdir(), 'source archive links/special members are forbidden')
            parts = name.parts[1:] if name.parts and name.parts[0] == 'source' else name.parts
            if member.isfile() and parts and parts[0] in ('op_host', 'op_kernel'):
                relative = '/'.join(parts)
                require(relative not in files, 'duplicate normalized native archive member')
                files[relative] = archive.extractfile(member).read()
    require(files, 'source archive lacks native optimization source')
    return files


def native_tar_hash(path, source_dir=None):
    files = native_tar_files(path)
    if source_dir is not None:
        root = Path(source_dir)
        require(not root.is_symlink(), 'native source symlink is forbidden')
        actual = {}
        for folder in ('op_host', 'op_kernel'):
            require(not (root / folder).is_symlink(), 'native source symlink is forbidden')
            for path in (root / folder).rglob('*'):
                require(not path.is_symlink(), 'native source symlink is forbidden')
                if path.is_file():
                    actual[path.relative_to(root).as_posix()] = path.read_bytes()
        require(actual == files, 'source tar native members differ from role source_dir')
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b'\0' + data + b'\0')
    return digest.hexdigest()


def references(value):
    """Evidence IDs referenced by a v2 memory, including historical bodies."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('evidence_ids', 'source_record_refs'):
                yield from item
            elif key == 'evidence_id':
                yield item
            else:
                yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


class Archive:
    def __init__(self, run, split):
        require(split in ('train', 'validation'), 'invalid split')
        self.run, self.split = Path(run).resolve(), split
        self.task_root = self.run / split / 'tasks'
        self.ledger = campaign.Campaign(self.run / split / 'ledger')
        self.ledger.verify()
        self.fresh = self.ledger.config.get('schema_version') == campaign.FRESH_SCHEMA
        require(all(task['split'] == split for task in self.ledger.state['tasks'].values()), 'cross-split ledger')
        require(all((self.ledger.config['tasks'][name]['split'] if self.fresh else campaign._split(name)) == split
                    for name in self.ledger.state['tasks']), 'cross-split task declaration')
        self.root = self.run / 'archive' / split
        self.output = self.root / 'v2'
        self.artifacts = {}
        self.pointer_cache = {}
        self.engineering_bindings = {}
        self.observation_producer_bindings = {}
        self.pointer_hash_normalizations = {}
        self.preparation_relocations = {}
        self.history = {}
        self.prior_records = {}
        self.prior_contexts = {}
        self.prior_entries = {}
        self.prior_chains = {}
        self.planning_graphs = {}

    def safe(self, path, owner=None):
        path = Path(path)
        path = path if path.is_absolute() else self.run / path
        require('swi_glu' not in path.parts, 'sealed test source is forbidden')
        if self.fresh:
            return self.safe_fresh(path, owner)
        resolved = _safe_path(path, self.split, owner=owner)
        for parts in (path.absolute().parts, resolved.parts):
            for i, part in enumerate(parts[:-1]):
                if part == 'operators' and parts[i + 1] in (*campaign.WORKLOADS, 'foreach_norm'):
                    op = parts[i + 1]
                    require(campaign._split(op) == self.split, 'cross-split operator source')
                    require(owner is None or op == owner, 'cross-task operator source')
                require(not (part == 'cannbench' and parts[i + 1] == 'test'), 'sealed test evidence')
        return resolved

    def safe_fresh(self, path, owner=None):
        """Manifest-driven split ownership without importing historical rosters."""
        original, resolved = Path(path).absolute(), Path(path).resolve()
        opposite = 'validation' if self.split == 'train' else 'train'
        declarations = self.ledger.config['tasks']
        for current in (original, resolved):
            parts = current.parts
            require('aprof-feat-aprofgraph' not in parts, 'fresh archive cannot depend on the historical feature checkout')
            anchors = [(i, parts[i + 1]) for i, p in enumerate(parts[:-1]) if p == 'tasks']
            for _, task in anchors:
                require(task in declarations and declarations[task]['split'] == self.split, 'cross-split or undeclared task evidence')
                require(owner is None or task == owner, 'cross-task evidence owner mismatch')
            prefix = parts[:anchors[0][0]] if anchors else parts
            require(opposite not in prefix, 'cross-split evidence directory before owner')
            if anchors:
                require(len({task for _, task in anchors}) == 1, 'cross-task nested evidence')
                for i in range(anchors[0][0] + 2, len(parts)):
                    if parts[i] == opposite and (parts[i - 1] in {'archive', 'dataset', 'datasets', 'export', 'exports', 'v2'}
                            or i >= 2 and parts[i - 2] == 'revisions'):
                        raise ValueError('cross-split nested dataset root')
            for i, part in enumerate(parts[:-1]):
                if part == 'operators':
                    op = parts[i + 1]
                    require(op in declarations and (owner is None or op == owner), 'undeclared or cross-task operator source')
            require('ledger' not in parts, 'global ledger bytes must be projected before archive')
            require(current.name not in {'run-manifest.json', 'config.sha256.json'}, 'global manifest must be projected before archive')
        return resolved

    def candidate_guard(self, owner, candidate, proposal):
        """Close every frozen guard input and execution for portable replay."""
        artifacts = candidate.get('artifacts', {})
        guard_ref = artifacts.get('semantic_guard_contract')
        if guard_ref is not None:
            from level2_guard_contract import checked_contract
            require(proposal.get('artifacts', {}).get('semantic_guard_contract') == guard_ref,
                    'candidate guard proposal/ledger identity differs')
            guard = checked_contract(guard_ref, source_hash=candidate['source_hash'],
                                     dispatch_plan=artifacts.get('dispatch_plan'))
            require(guard['task'] == str(self.task_root / owner) and guard['candidate_id'] == candidate['candidate_id'],
                    'candidate guard archive owner differs')
            self.audit_paths(guard, owner)
            self.files(Path(guard_ref['path']).parent, owner)
            validation = Path(guard_ref['path']).parent.parent / 'boundary-validation'
            self.files(validation, owner)
            for evidence in sorted(validation.rglob('*.json')):
                self.audit_paths(load(evidence), owner, evidence_path=evidence)

    def planning(self, owner, candidate, declaration, proposal):
        """Bind predeclared plans and actual implementation lineage for fresh runs."""
        artifacts = candidate.get('artifacts', {})
        self.audit_paths(artifacts, owner)
        documents, pointers = {}, []
        self.candidate_guard(owner, candidate, proposal)
        for kind in ('architecture_profile', 'parallel_plan', 'dispatch_plan'):
            pointer = artifacts.get(kind)
            require(isinstance(pointer, dict) and {'path', 'sha256'} <= pointer.keys(), f'fresh candidate lacks bound {kind}')
            bound = self.pointer(pointer['path'], owner, expected=pointer['sha256'])
            value = validate_planning_contract(kind, load(bound['path']))
            require(proposal.get(kind + '_ref') == content_hash(value), f'{kind} canonical reference differs')
            documents[kind] = value; pointers.append(bound)
        profile, plan, dispatch = (documents[k] for k in ('architecture_profile', 'parallel_plan', 'dispatch_plan'))
        require(proposal.get('optimization_stage') in ('algorithm_parallel', 'execution'), 'fresh proposal requires explicit optimization stage')
        basis, implementation = proposal.get('plan_basis_source_hash'), proposal.get('implementation_source_hash')
        require(basis in {declaration['baseline_source_hash'], candidate['source_parent']['source_hash']}, 'plan basis is not original baseline or direct parent')
        require(implementation == candidate['source_hash'], 'implementation source identity differs from registered candidate')
        require(plan['source_hash'] == basis and dispatch['source_hash'] == implementation
                and dispatch.get('plan_basis_source_hash') == basis and dispatch.get('implementation_source_hash') == implementation,
                'planning basis/implementation bindings differ')
        require(plan['operator'] == dispatch['operator'] == owner, 'planning operator differs')
        require(plan['architecture_profile_ref'] == dispatch['architecture_profile_ref'] == proposal['architecture_profile_ref']
                and dispatch['parallel_plan_ref'] == proposal['parallel_plan_ref'], 'cross-plan architecture identity differs')
        groups = {g['group_id'] for g in plan['groups']}
        require(all(e['group_id'] in groups for e in [*dispatch['entries'], dispatch['fallback']]), 'dispatch group is absent from parallel plan')
        selections = proposal.get('dispatch_selections')
        require(isinstance(selections, list) and selections, 'fresh proposal requires concrete metadata dispatch selections')
        for selection in selections:
            require(isinstance(selection, dict) and {'metadata', 'tiling_key', 'kernel_entry', 'group_id'} <= selection.keys(), 'incomplete dispatch selection')
            selected = select_dispatch(dispatch, selection['metadata'])
            require(all(selected[k] == selection[k] for k in ('tiling_key', 'kernel_entry', 'group_id')), 'recorded dispatch selection differs from metadata rules')
            # Replay the same capability/capacity/source checks as routing. A
            # well-formed plan must not become admissible by archive alone.
            evidence = {**documents, **{kind + '_ref': proposal[kind + '_ref'] for kind in documents}}
            validate_planning_context(SimpleNamespace(evidence=evidence, operator=owner,
                hardware_fingerprint=profile['hardware_fingerprint'], workload={
                    'source_hash': basis, 'plan_basis_source_hash': basis, 'implementation_source_hash': implementation,
                    'metadata': selection['metadata'], 'tiling_key': selected['tiling_key'], 'workload_group': selected['group_id']}), execution=True)
        # Explicit pointers may carry snapshots anywhere in the new run. The
        # default preflight probe directory is also included without old checkout
        # dependencies; raw facts are recomputed, not trusted because of hashes.
        self.files(self.run / 'preflight', None)
        for pointer in artifacts.get('planning_evidence', []):
            self.pointer(pointer['path'], owner, expected=pointer['sha256'])
        by_hash = {p['sha256']: p for p in self.artifacts.values()}
        refs = [ref for ref in profile['provenance'].values() if ref]
        refs += [ref for c in profile['capabilities'].values() for ref in c['evidence_refs']]
        refs += profile.get('compiler', {}).get('evidence_refs', [])
        refs += [ref for group in plan['groups'] for ref in group['selection_evidence']]
        require(all(ref in by_hash for ref in refs), 'planning evidence closure lacks raw probe, producer, header or selection evidence')
        pointers.extend(by_hash[ref] for ref in refs)
        verify_profile_probe(profile, load(by_hash[profile['provenance']['raw_probe_ref']]['path']))
        graph_pointer = artifacts.get('graph_snapshot')
        require(isinstance(graph_pointer, dict) and {'path', 'sha256'} <= graph_pointer.keys(), 'fresh candidate requires graph snapshot pointer')
        graph_pointer = self.pointer(graph_pointer['path'], owner, expected=graph_pointer['sha256'])
        graph = validate_graph(load(graph_pointer['path']))
        require(graph['graph_version'] == 'v0002' and proposal.get('graph_hash') == content_hash(graph), 'proposal graph identity differs')
        self.planning_graphs[content_hash(graph)] = graph_pointer
        graph_root = Path(graph_pointer['path']).parent
        require(graph_root.resolve() == (self.run / 'graph/v0002').resolve(), 'fresh graph is outside the frozen run bundle')
        declared_bundle = artifacts.get('graph_bundle')
        require(isinstance(declared_bundle, list) and declared_bundle, 'fresh registration lacks graph bundle hash bindings')
        bound_bundle = {}
        for ref in declared_bundle:
            require(isinstance(ref, dict) and {'path', 'sha256'} <= ref.keys(), 'invalid graph bundle binding')
            resolved = Path(ref['path']).resolve()
            require(resolved.is_relative_to(graph_root.resolve()) and resolved not in bound_bundle, 'graph bundle path differs or repeats')
            bound_bundle[resolved] = self.pointer(ref['path'], owner, expected=ref['sha256'])
        require(all((graph_root / name).resolve() in bound_bundle for name in ('graph.json', 'manifest.json', 'checksums.json', 'lineage.json')),
                'fresh registration omits graph bundle members')
        bundle = {name: bound_bundle[(graph_root / name).resolve()] for name in ('manifest.json', 'checksums.json', 'lineage.json')}
        manifest, checksums = load(bundle['manifest.json']['path']), load(bundle['checksums.json']['path'])
        require(manifest.get('immutable') is True and manifest.get('graph_version') == 'v0002', 'graph bundle is not an immutable v0002 snapshot')
        require(manifest['graph_sha256'].removeprefix('sha256:') == graph_pointer['sha256'][7:], 'graph manifest hash differs')
        for name, pointer in {**bundle, 'graph.json': graph_pointer}.items():
            if name != 'checksums.json':
                require(checksums['files'][name].removeprefix('sha256:') == pointer['sha256'][7:], 'graph bundle checksum differs')
        pointers.extend(bound_bundle.values())
        attributes = {key: deepcopy(proposal[key]) for key in ('optimization_stage', 'architecture_profile_ref', 'parallel_plan_ref',
            'dispatch_plan_ref', 'graph_hash', 'plan_basis_source_hash', 'implementation_source_hash', 'dispatch_selections')}
        attributes['source_split'] = declaration['source_split']
        return attributes, pointers

    def frozen_engineering(self, origin, expected, live_hash, owner):
        """An explicit frozen script declaration can bind old producer bytes.

        Inputs, native sources and arbitrary Python files are never substituted.
        The original document keeps its path/hash; this is a separate index edge.
        """
        if not origin.is_relative_to(ENGINEERING_SCRIPTS.resolve()) or origin.suffix not in ('.py', '.sh'):
            return None
        manifests, snapshots = [], set()
        for manifest in sorted((self.run / 'bootstrap').glob('frozen-engineering*.json')):
            value = load(self.safe(manifest, owner))
            require(isinstance(value.get('files'), list), 'invalid frozen engineering manifest')
            matching = [item for item in value['files'] if isinstance(item, dict)
                        and item.get('path') == str(origin) and item.get('sha256') == expected]
            if not matching:
                continue
            manifests.append(self.pointer(manifest, owner))
            for item in matching:
                declared = Path(item['snapshot'])
                require(not declared.is_symlink(), 'frozen engineering snapshot is a symlink')
                snapshot = self.safe(declared, owner)
                target = self.run / 'bootstrap/source-cas' / expected.removeprefix('sha256:')
                require(snapshot == target.resolve(), 'frozen engineering snapshot is outside its declared CAS identity')
                require(snapshot.is_file() and sha(snapshot) == expected, 'frozen engineering snapshot hash differs')
                snapshots.add(snapshot)
        if not manifests:
            return None
        require(len(snapshots) == 1, 'ambiguous frozen engineering snapshots')
        snapshot = self.pointer(next(iter(snapshots)), owner, expected=expected)
        binding = dict(origin=dict(path=str(origin), sha256=expected), snapshot=snapshot,
                       frozen_manifests=manifests, observed_live_sha256=live_hash,
                       binding_mode='frozen_engineering_snapshot', live_path_contains_expected_bytes=False)
        self.engineering_bindings[v2.digest(binding)] = binding
        return snapshot

    def relocated_preparation(self, origin, expected, owner):
        """Resolve an event-attested preparation relocation, never an input/source."""
        if not self.fresh or owner not in self.ledger.config['tasks']:
            return None
        task = self.task_root / owner
        allowed = {'started.json', 'execution.json', 'generate_all.py', 'stdout.log', 'stderr.log'}
        if origin.parent != task / 'input-generation' or origin.name not in allowed:
            return None
        events = task / 'events.jsonl'
        if not events.is_file():
            return None
        def pointer_refs(value):
            if isinstance(value, dict):
                if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                    yield value
                for item in value.values():
                    yield from pointer_refs(item)
            elif isinstance(value, list):
                for item in value:
                    yield from pointer_refs(item)
        previous, observed, matches = None, set(), []
        for i, event in enumerate(v2.load_rows(self.safe(events, owner))):
            payload = {key: value for key, value in event.items() if key != 'hash'}
            digest = v2.digest_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode())
            require(event['sequence'] == i and event['previous_hash'] == previous and event['hash'] == digest,
                    'preparation relocation event chain differs')
            previous = event['hash']
            if event['kind'] == 'preparation_evidence_relocated':
                pointer = event['value'].get('manifest', {})
                declared = Path(pointer.get('path', ''))
                require(declared.is_absolute() and declared.parent == task and
                        re.fullmatch(r'evidence-relocations(?:-v[0-9]+)?\.json', declared.name) and
                        not declared.is_symlink() and v2.HASH_RE.fullmatch(pointer.get('sha256', '')),
                        'preparation relocation manifest location differs')
                manifest = self.pointer(declared, owner, expected=pointer.get('sha256'))
                value = load(manifest['path'])
                # Older opaque relocation notes remain evidence, not authority.
                if value.get('version') != 'fresh_preparation_relocations_v1':
                    continue
                require(value.get('operator') == owner, 'preparation relocation task differs')
                task_pointer = value.get('task_manifest', {})
                require(task_pointer.get('path') == str(task / 'manifest.json') and
                        task_pointer.get('sha256') == sha(task / 'manifest.json'),
                        'preparation relocation task manifest binding differs')
                require(isinstance(value.get('entries'), list), 'preparation relocation entries missing')
                for entry in value['entries']:
                    old, new = entry.get('origin', {}), entry.get('snapshot', {})
                    old_path, new_path = Path(old.get('path', '')), Path(new.get('path', ''))
                    require(old_path.is_absolute() and old_path.parent == task / 'input-generation' and
                            old_path.name in allowed and new_path.is_absolute() and
                            new_path.parent.parent == task and re.fullmatch(r'input-generation-failed-[0-9]+', new_path.parent.name) and
                            new_path.name == old_path.name, 'preparation relocation exceeds allowed scope')
                    require((str(old_path), old.get('sha256')) in observed and
                            old.get('sha256') == new.get('sha256') and v2.HASH_RE.fullmatch(old.get('sha256', '')),
                            'preparation relocation lacks prior exact event identity')
                    if old_path == origin and old['sha256'] == expected:
                        require(not new_path.is_symlink(), 'preparation relocation snapshot is a symlink')
                        snapshot = self.pointer(new_path, owner, expected=expected)
                        if origin.name in {'started.json', 'execution.json'}:
                            require(load(new_path).get('hardware_executed') is False, 'preparation relocation is not CPU-only')
                        matches.append((snapshot, manifest, self.pointer(events, owner, selector=f'line:{i + 1}'),
                                        self.pointer(task / 'manifest.json', owner)))
            for ref in pointer_refs(event['value']):
                if isinstance(ref.get('path'), str):
                    observed.add((ref['path'], ref.get('sha256')))
        if not matches:
            return None
        require(len({(row[0]['path'], row[0]['sha256']) for row in matches}) == 1, 'ambiguous preparation relocation')
        snapshot, manifest, event, task_manifest = matches[-1]
        binding = dict(origin=dict(path=str(origin), sha256=expected), snapshot=snapshot,
                       manifest=manifest, event=event, task_manifest=task_manifest, binding_mode='fresh_preparation_relocation')
        self.preparation_relocations[v2.digest(binding)] = binding
        return snapshot

    def bind_closed_observation_producers(self, session, owner):
        """Register attested code snapshots before auditing original binding paths."""
        from msprof_exploration_provenance import frozen_producer
        for origin, expected in load(session / 'bindings.json').items():
            path = self.safe(origin, owner)
            if sha(path) == expected:
                continue
            binding = frozen_producer(path, expected, evidence_path=session / 'completion.json',
                                      semantic_path=('observation_binding',))
            # Unknown/data identities still fail in the ordinary strict pointer audit.
            if binding is None:
                continue
            for ref in [binding['snapshot'], binding['frozen_manifest'], *binding['closed_observation'].values()]:
                self.pointer(ref['path'], owner, expected=ref['sha256'])
            key = (str(path), expected)
            self.observation_producer_bindings[key] = binding
            self.document({'closed_observation_producer_binding': binding})

    def verification_snapshot(self, path, owner, expected):
        import level2_verification_storage as storage
        binding = storage.evidence_binding(path, expected)
        if binding is None:
            return None
        binding.pop('bytes',None)
        result = dict(binding['origin'])
        # Explicitly retain every archive/seal/producer and closed-state dependency.
        for key in ('seal', 'archive', 'producer'):
            ref = binding[key]
            self.pointer(ref['path'], owner, expected=ref['sha256'])
        for ref in binding['closed_evidence']['protected']:
            self.pointer(ref['path'], owner, expected=ref['sha256'])
        for event in storage.event_bindings(binding['closed_evidence']):
            self.pointer(event['path'], owner, selector='line:'+str(event['sequence']+1))
        self.document({'version': binding.get('version',storage.VERSION), 'archive_mapping': {key:value for key,value in binding.items() if key!='origin'}})
        return result

    def pointer(self, path, owner=None, expected=None, selector=''):
        path = self.safe(path, owner)
        key = str(path), expected, selector
        if key in self.pointer_cache:
            result = self.pointer_cache[key]
            require(expected is None or result['sha256'] == expected, 'evidence hash differs: ' + str(path))
            return result
        snapshot = self.verification_snapshot(path, owner, expected)
        if snapshot is not None:
            result = {**snapshot}
            if selector:
                v2.validate_selector(selector, Path(result['path']), analysis.verification_storage.read_bytes(result['path']))
                result['selector'] = selector
            self.artifacts[v2.digest(result)] = result
            self.pointer_cache[key] = result
            return result
        require(path.is_file(), 'missing archive evidence: ' + str(path))
        result = dict(path=str(path), sha256=sha(path))
        if expected is not None and result['sha256'] != expected:
            binding = getattr(self, 'observation_producer_bindings', {}).get((str(path), expected))
            snapshot = binding['snapshot'] if binding else self.frozen_engineering(path, expected, result['sha256'], owner)
            if snapshot is None:
                snapshot = self.relocated_preparation(path, expected, owner)
            if snapshot is not None:
                result = {**snapshot}
                path = Path(snapshot['path'])
        require(expected is None or result['sha256'] == expected, 'evidence hash differs: ' + str(path))
        if selector:
            v2.validate_selector(selector, path)
            result['selector'] = selector
        self.artifacts[v2.digest(result)] = result
        self.pointer_cache[key] = result
        return result

    def document(self, value):
        data = v2.canonical(value)
        path = self.root / 'documents' / (v2.digest_bytes(data)[7:] + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            require(path.read_bytes() == data, 'immutable archive document changed')
        else:
            with path.open('xb') as stream:
                stream.write(data)
        return self.pointer(path)

    def files(self, directory, owner):
        directory = self.safe(directory, owner)
        if not directory.exists():
            return
        for path in sorted(directory.rglob('*')):
            self.safe(path, owner)
            require(not path.is_symlink(), 'symlink inside artifact closure')
            if path.is_file():
                self.pointer(path, owner)
        import level2_verification_storage as storage
        for path in storage.logical_files(directory):
            self.pointer(path, owner)

    def audit_paths(self, value, owner, *, evidence_path=None):
        """Check referenced absolute paths before the report reader can open them."""
        if isinstance(value, dict):
            # The original shared-context producer spells only this pointer's
            # SHA-256 as bare hex. Normalize its representation, not its bytes
            # or the immutable source document; generic v2 pointers stay strict.
            runner = value.get('runner')
            if (value.get('version') == 'shared_context_build_v1' and isinstance(runner, dict)
                    and isinstance(runner.get('path'), str) and isinstance(runner.get('sha256'), str)
                    and len(runner['sha256']) == 64):
                expected = 'sha256:' + runner['sha256']
                require(v2.HASH_RE.fullmatch(expected), 'invalid legacy runner pointer hash')
                verified = self.pointer(runner['path'], owner, expected=expected, selector=runner.get('selector', ''))
                binding = dict(binding_mode='shared_context_build_v1_runner_raw_sha256',
                               field='/runner/sha256', source_object_sha256=v2.digest(value),
                               original_pointer=deepcopy(runner), normalized_pointer=verified)
                if evidence_path is not None:
                    binding['source_document'] = self.pointer(evidence_path, owner)
                self.pointer_hash_normalizations[v2.digest(binding)] = binding
                value = {**value, 'runner': {**runner, 'sha256': expected}}
            bound = isinstance(value.get('path'), str) and 'sha256' in value
            if bound:
                require(isinstance(value['sha256'], str) and v2.HASH_RE.fullmatch(value['sha256']), 'invalid evidence pointer hash')
                self.pointer(value['path'], owner, expected=value['sha256'], selector=value.get('selector', ''))
            for key, item in value.items():
                if bound and key in ('path', 'sha256', 'selector'):
                    continue
                if isinstance(key, str) and key.startswith('/'):
                    self.pointer(key, owner, expected=item if isinstance(item, str) and item.startswith('sha256:') else None)
                self.audit_paths(item, owner, evidence_path=evidence_path)
        elif isinstance(value, list):
            for item in value:
                self.audit_paths(item, owner, evidence_path=evidence_path)
        elif isinstance(value, str) and value.startswith('/'):
            path = self.safe(value, owner)
            if path.is_file():
                self.pointer(path, owner)

    def prior(self, taskdir, candidate):
        stable = candidate['stable_id']
        if stable in self.prior_records:
            return self.prior_records[stable]
        context = taskdir / 'inheritance-context.json'
        info = load(self.safe(context)) if context.exists() else load(self.safe(taskdir / 'manifest.json'))
        declared = info.get('prior_dataset')
        require(isinstance(declared, dict) and info.get('inherited_attempt_id') == stable, 'inherited source lacks pinned prior dataset/attempt')
        root = self.safe(declared['path'])
        current_ref = declared['current']
        pointer_path = self.safe(current_ref['path'])
        require(pointer_path == root / 'current.json', 'prior current pointer location differs')
        self.pointer(pointer_path, expected=current_ref['sha256'])
        pointer = load(pointer_path)
        base = root / 'revisions' / pointer['revision']
        # This is a split-specific prior view. Refuse nonempty opposite views
        # before allowing v2.verify to traverse its files.
        manifest = load(base / 'manifest.json')
        empty_hash = v2.digest_bytes(b'')
        opposite = 'validation' if self.split == 'train' else 'train'
        require(all(manifest['files'][opposite + '/' + n] == empty_hash for n in ('optimization_traces.jsonl', 'lessons.jsonl')),
                'prior dataset contains opposite-split outcomes')
        index = load(base / 'evidence_index.json')
        require(all(row['split'] == self.split for row in index.values()), 'prior evidence index crosses split')
        v2.verify(root, deep=False)
        rows = v2.load_rows(base / self.split / 'optimization_traces.jsonl')
        found = [row for row in rows if row['id'] == stable]
        require(len(found) == 1, 'inherited stable attempt missing or ambiguous')
        record = found[0]
        self.prior_records[stable] = record
        contexts, objects = load(base / 'contexts.json'), load(base / 'record_objects.json')
        chain = [record]
        while chain[-1]['previous_ref']:
            chain.append(load(v2.object_path(root, objects[chain[-1]['previous_ref']])))
        for old in chain:
            self.prior_chains[old['record_hash']] = old
        needed = set(references(record['body']))
        for field in (record['body']['context_ref'], record['body']['knowledge']['catalog_ref']):
            self.prior_contexts[field] = contexts[field]
            needed.update(references(contexts[field]))
        for ref in needed:
            require(ref in index and index[ref]['split'] == self.split, 'historical evidence closure is incomplete')
            entry = index[ref]
            path = self.safe(entry['path'])
            require(sha(path) == entry['sha256'], 'historical evidence changed')
            self.prior_entries[ref] = entry
        return record

    def control_source_tar(self, owner, source_hash):
        """Resolve a frozen control's full source identity within its own task."""
        task = self.ledger.state['tasks'][owner]
        declaration = self.ledger.config['tasks'][owner]
        if source_hash == declaration['baseline_source_hash']:
            path = self.task_root / owner / 'baseline-source.tar'
        else:
            matches = [cid for cid, row in task['candidates'].items() if row['source_hash'] == source_hash]
            require(matches, 'fixed control source is not registered for this task')
            path = self.task_root / owner / 'candidates' / sorted(matches)[0] / 'source.tar'
        self.pointer(path, owner, expected=source_hash)
        return path

    @analysis.verification_storage.reader_session()
    def cohort(self, directory, owner, control_tar, candidate_tar, calibration_ref=None):
        directory = self.safe(directory, owner)
        completion = load(self.safe(directory / 'group-completion.json', owner))
        require(completion.get('status') in ('passed', 'failed'), 'cohort completion status missing')
        self.files(directory, owner)
        if completion['status'] != 'passed':
            return None
        plan = load(directory / 'plan.json')
        paths = [self.safe(path, owner) for path in completion['completed_sessions']]
        require(len(paths) == len(set(paths)) == 6 and all(path.parent == directory for path in paths), 'cohort session boundary differs')
        for item in completion.get('sessions', []):
            require(self.safe(item['directory'], owner) in paths, 'session pointer outside cohort')
            for key in ('completion', 'samples', 'journal'):
                ref = item[key]
                self.pointer(ref['path'], owner, expected=ref['sha256'])
        self.audit_paths(plan, owner)
        for entry, path in zip(plan['schedule'], paths):
            request = entry['request']
            for field in ('role_build', 'runner_build'):
                ref = self.safe(request[field], owner)
                self.audit_paths(load(ref), owner, evidence_path=ref)
                self.files(ref.parent, owner)
            self.bind_closed_observation_producers(path, owner)
            self.audit_paths(load(path / 'bindings.json'), owner)
            build = load(self.safe(request['role_build'], owner))
            for role, source_tar in (('A', control_tar), ('B', candidate_tar)):
                source = self.safe(build['roles'][role]['source_dir'], owner)
                require(native_tar_hash(source_tar, source) == build['roles'][role]['source_sha256'], 'native source identity differs from source tar')
        saved = load(directory / 'report.json')
        if calibration_ref is not None:
            require(isinstance(calibration_ref, dict) and 'path' in calibration_ref and 'sha256' in calibration_ref,
                    'frozen cohort calibration pointer is required')
            self.pointer(calibration_ref['path'], owner, expected=calibration_ref['sha256'])
            declared_calibration = load(self.safe(calibration_ref['path'], owner))
            require(analysis.digest(declared_calibration) == saved.get('calibration_report_hash'),
                    'cohort calibration differs from frozen stage plan')
        calibration = None
        if saved.get('calibration_report_hash'):
            matches = {}
            for sid, stage in self.ledger.state['tasks'][owner]['stages'].items():
                if stage['kind'] != 'control' or stage.get('plan', {}).get('control_type') != 'aa':
                    continue
                for attempt in stage['attempts']:
                    result_ref = attempt.get('evidence', {}).get('result')
                    if attempt.get('outcome') != 'success' or not isinstance(result_ref, dict):
                        continue
                    result_path = self.safe(result_ref['path'], owner)
                    self.pointer(result_path, owner, expected=result_ref['sha256'])
                    result = load(result_path)
                    require(result.get('stage_id') == sid and result.get('kind') == 'control'
                            and result.get('candidate_id') is None and result.get('status') == 'passed',
                            'calibration stage result differs from ledger')
                    p = result_path.parent / 'cohort' / 'report.json'
                    if p.is_file():
                        value = load(self.safe(p, owner))
                        if analysis.digest(value) == saved['calibration_report_hash']:
                            matches[str(p)] = value
            require(matches, 'bound calibration report is unavailable')
            require(len(matches) == 1, 'bound calibration report is ambiguous')
            p, calibration = next(iter(matches.items()))
            if calibration_ref is not None:
                require(self.safe(p, owner) == self.safe(calibration_ref['path'], owner),
                        'frozen calibration path is not the registered A/A report')
            self.pointer(p, owner)
        actual = analysis.analyze_task_cohort(paths, plan, calibration=calibration)
        analysis_bindings = []
        comparison = analysis.compare_saved_report(saved, actual, evidence_path=directory / 'report.json',
                                                    provenance_out=analysis_bindings)
        for binding in analysis_bindings:
            for key in ('snapshot', 'frozen_manifest'):
                self.pointer(binding[key]['path'], owner, expected=binding[key]['sha256'])
        if analysis_bindings:
            self.document(dict(report=self.pointer(directory / 'report.json', owner), comparison=comparison,
                               analysis_producer_bindings=analysis_bindings))
        require(all(actual.get(key) == value for key, value in POLICY.items()), 'new report cannot enter graph policy/gate')
        require(actual['operator'] == owner, 'report operator differs')
        require(actual['source_hashes'] == {'A': native_tar_hash(control_tar), 'B': native_tar_hash(candidate_tar)}, 'report/source archive mismatch')
        for path, expected in actual.get('calibration_scope_artifacts', {}).items():
            self.pointer(path, owner, expected=expected)
        for session in actual['sessions']:
            for field in ('artifacts', 'bound_artifacts'):
                for path, expected in session.get(field, {}).items():
                    self.pointer(path, owner, expected=expected)
        # The v2 adapter admits summary/cases; retain every result without
        # inserting old event timing arrays or a synthetic machine verdict.
        summary = {key: value for key, value in saved.items() if key not in ('sessions', 'results')}
        summary['native_process_count'] = len(actual['sessions'])
        return self.document(dict(summary=summary, cases=saved['results']))

    def single_process_method(self, directory, owner, plan, result):
        """Replay the explicit local-raw method without synthesizing a cohort."""
        require(plan.get('control_type') == 'method' and plan.get('declared_native_processes') == 1
                and plan.get('calibration_eligible') is False, 'method qualification scope differs')
        if result['status'] != 'passed':
            return None  # stage() already preserves every partial raw/output byte.
        require(result.get('control_type') == 'method' and result.get('calibration_eligible') is False,
                'method result claims an incompatible control type')
        template = analysis.validate_plan(plan['cohort_template'])
        require(plan.get('selected_schedule_index') == 0 and template['comparison_kind'] == 'aa'
                and plan['request'] == template['schedule'][0]['request']
                and plan['case_ids'] == template['case_ids'] and len(plan['case_ids']) == 1,
                'method frozen request differs from selected template')
        request = load(directory / 'request.json')
        require(request == plan['request'], 'method executed request differs')
        proof_path = directory / 'method-qualification.json'
        proof = load(proof_path)
        require(proof.get('version') == plan['version'] and proof.get('status') == 'passed'
                and proof.get('native_processes') == 1 and proof.get('case_ids') == plan['case_ids']
                and proof.get('calibration_eligible') is False and proof.get('six_process_cohort_report_emitted') is False,
                'method proof is not a one-process qualification')
        for field, name in (('request', 'request.json'), ('observation', 'observation.json')):
            require(proof.get(field) == {'path': str(directory / name), 'sha256': sha(directory / name)},
                    'method proof pointer differs')
        source_tar = self.control_source_tar(owner, plan['source_hash'])
        build = load(self.safe(request['role_build'], owner))
        for role in 'AB':
            source = self.safe(build['roles'][role]['source_dir'], owner)
            require(native_tar_hash(source_tar, source) == build['roles'][role]['source_sha256'],
                    'method role source differs from fixed control source')
        actual = analysis.verify_observation(directory / 'evidence', expected_request=request)
        require(load(directory / 'observation.json') == actual and actual['operator'] == owner
                and actual['source_hashes'] == dict.fromkeys('AB', native_tar_hash(source_tar)),
                'method observation differs from raw/source replay')
        for field in ('artifacts', 'bound_artifacts'):
            for path, expected in actual.get(field, {}).items():
                self.pointer(path, owner, expected=expected)
        return self.document(dict(method_qualification=self.pointer(proof_path, owner),
            observation=self.pointer(directory / 'observation.json', owner), native_process_count=1,
            calibration_eligible=False, attribution='verified_single_process_method_only', **POLICY))

    def stage(self, path, task, cid, owner):
        value = load(self.safe(path, owner))
        sid = value['stage_id']
        require(sid in task['stages'] and task['stages'][sid]['candidate_id'] == cid, 'stage result is not registered for this source')
        stage = task['stages'][sid]
        self.audit_paths(stage.get('plan', {}), owner)
        require(value.get('status') in ('passed', 'failed', 'interrupted', 'incomplete', 'prestart_failure'), 'unknown execution status')
        # Bind this result to a completed ledger attempt, rather than directory names.
        target_hash = sha(path)
        def hashes(node):
            if isinstance(node, dict):
                return any(hashes(v) for v in node.values())
            if isinstance(node, list):
                return any(hashes(v) for v in node)
            return node == target_hash
        require(any(attempt.get('outcome') is not None and hashes(attempt.get('evidence', {})) for attempt in stage['attempts']), 'stage result hash lacks ledger completion binding')
        require(all(value.get(key) == val for key, val in POLICY.items()), 'stage formal admission differs')
        raw = self.pointer(path, owner)
        reason = value.get('reason', value.get('error'))
        if reason is not None and not isinstance(reason, str):
            reason = v2.canonical(reason).decode().strip()
        record = self.document(dict(status=value['status'], reason=reason, source_record=raw,
                                    attribution='recorded_execution_status_projection', **POLICY))
        self.files(path.parent, owner)
        return value, dict(name=value.get('kind', stage['kind']), record=record)

    def manual_static_stages(self, task, cid, owner, projected, represented):
        """Project actual ledger outcomes without manufacturing execution files."""
        for sid, stage in task['stages'].items():
            if sid in represented or stage['kind'] != 'static' or stage['candidate_id'] != cid:
                continue
            for number, attempt in enumerate(stage['attempts']):
                outcome = attempt.get('outcome')
                if outcome is None:
                    continue
                require(outcome in campaign.OUTCOMES, 'unknown manual static stage outcome')
                review = attempt.get('evidence', {}).get('review')
                if review is not None:
                    require(isinstance(review, dict) and 'path' in review and 'sha256' in review,
                            'manual static review requires a bound evidence pointer')
                    self.pointer(review['path'], owner, expected=review['sha256'])
                    self.audit_paths(load(self.safe(review['path'], owner)), owner)
                status = 'passed' if outcome == 'success' else outcome
                value = dict(stage_id=sid, candidate_id=cid, kind='static', status=status)
                record = self.document(dict(**value, reason=attempt.get('reason'),
                    attribution='recorded_ledger_static_stage_projection', source_record=projected,
                    ledger_outcome=outcome, ledger_attempt_index=number,
                    ledger_plan=stage.get('plan', {}), ledger_attempt=attempt, **POLICY))
                yield value, dict(name='static', record=record)

    def attempt(self, owner, cid, candidate, task, declaration, projected):
        taskdir = self.task_root / owner
        directory = taskdir / 'candidates' / cid
        baseline = taskdir / 'baseline-source.tar'
        parent_id = candidate['source_parent']['candidate_id']
        parent = baseline if parent_id is None else directory.parent / parent_id / 'source.tar'
        sources = {'original_baseline': self.pointer(baseline, owner, declaration['baseline_source_hash']),
                   'direct_parent': self.pointer(parent, owner, candidate['source_parent']['source_hash']),
                   'candidate': self.pointer(directory / 'source.tar', owner, candidate['source_hash']),
                   'patch': self.pointer(directory / 'optimization.patch', owner, candidate['patch_hash']),
                   'parent_attempt_id': parent_id}
        inherited = candidate.get('inherited', False)
        if inherited:
            self.prior(taskdir, candidate)
        proposal_path = directory / 'proposal.json'
        proposal_binding = candidate.get('artifacts', {}).get('proposal')
        if not proposal_path.exists() and isinstance(proposal_binding, dict):
            proposal_path = self.safe(proposal_binding['path'], owner)
        proposal = load(self.safe(proposal_path, owner)) if proposal_path.exists() else {}
        require(inherited or proposal, 'new source attempt requires actual optimizer proposal')
        proposal_ref = self.pointer(proposal_path, owner, expected=proposal_binding.get('sha256') if proposal_binding else None) if proposal else projected
        planning_attributes, planning_evidence = self.planning(owner, candidate, declaration, proposal) if self.fresh else ({}, [])
        statement = next((proposal[key] for key in ('statement', 'intent', 'hypothesis', 'rationale', 'public_rationale', 'summary', 'description') if isinstance(proposal.get(key), str)), None)
        intervention_basis = 'recorded_optimizer_proposal' if statement else 'retrospective_source_registration'
        statement = statement or 'Registered optimization source differs from its frozen direct parent; consult the bound patch and proposal.'
        for folder in ('build', 'plans'):
            self.files(directory / folder, owner)
        for filename in ('source-binding.json', 'registration.json', 'inheritance.json'):
            if (directory / filename).is_file():
                self.pointer(directory / filename, owner)
        stages, comparisons, represented = [], [], set()
        for path in sorted((directory / 'stages').glob('*/result.json')):
            raw, record = self.stage(path, task, cid, owner)
            represented.add(raw['stage_id'])
            stages.append(record)
            for label, source_tar in (('direct_parent', parent), ('original_baseline', baseline)):
                cohort = path.parent / label
                if (cohort / 'group-completion.json').is_file():
                    stage_plan = task['stages'][raw['stage_id']].get('plan', {})
                    plans = [row for row in stage_plan.get('cohorts', []) if row.get('relation') == label]
                    require(len(plans) <= 1, 'duplicate frozen comparison relation')
                    calibration_ref = (plans[0].get('calibration_report') if plans else None) or stage_plan.get('calibration_report')
                    observations = self.cohort(cohort, owner, source_tar, directory / 'source.tar', calibration_ref)
                    completion = self.pointer(cohort / 'group-completion.json', owner)
                    # Error objects need a string/null stage reason under v2.
                    value = load(completion['path'])
                    reason = value.get('error')
                    completion = self.document(dict(status=value['status'], reason=v2.canonical(reason).decode().strip() if reason else None,
                                                     source_record=completion))
                    comparisons.append(dict(id=f'{self.run.name}/{owner}/{cid}/{raw["stage_id"]}/{label}',
                        session_id=str(cohort), baseline=label, relation='measurement_continuation' if inherited else 'original_attempt',
                        stages=[dict(name='msprof_complete_operator_comparison', record=completion)],
                        measurement_quality='complete_with_caution' if observations else 'execution_failed',
                        **({'observations': observations} if observations else {})))
        stages.extend(record for _, record in self.manual_static_stages(task, cid, owner, projected, represented))
        if comparisons:
            for comparison in comparisons:
                comparison['stages'] = [*stages, *comparison['stages']]
        elif stages:
            comparisons = [dict(id=f'{self.run.name}/{owner}/{cid}/execution', session_id=str(directory), baseline='direct_parent',
                relation='measurement_continuation' if inherited else 'original_attempt', stages=stages,
                measurement_quality='no_complete_timing_comparison')]
        reads, timeline = [], []
        for path in sorted((taskdir / 'knowledge-reads').glob('*.json')):
            row = load(self.safe(path, owner))
            origin = self.pointer(path, owner)
            self.safe(row['path'], owner)
            require(row.get('purpose') and row.get('sha256') and row.get('snapshot'), 'actual read lacks purpose or frozen bytes')
            self.pointer(row['snapshot'], owner, expected=row['sha256'])
            if row.get('classification') == 'knowledge_read':
                reads.append(dict(record=origin))
            elif row.get('classification') != 'source_or_feedback_read':
                raise ValueError('unrecognized actual read classification')
        events_path = taskdir / 'events.jsonl'
        if events_path.is_file():
            data = events_path.read_bytes()
            require(not data or data.endswith(b'\n'), 'incomplete public-work event log')
            previous_hash = None
            for i, event in enumerate(v2.load_rows(self.safe(events_path, owner))):
                payload = {key: val for key, val in event.items() if key != 'hash'}
                digest = v2.digest_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode())
                require(event['sequence'] == i and event['previous_hash'] == previous_hash and event['hash'] == digest, 'public-work event hash chain differs')
                previous_hash = event['hash']
                value = event['value']
                origin = self.pointer(events_path, owner, selector=f'line:{i + 1}')
                if self.fresh and event['kind'] in {'input_generation_started', 'input_generation_finished'}:
                    # Close preparation failures as task provenance without
                    # relabeling them as candidate evaluations or episodes.
                    self.audit_paths(value, owner)
                    for key in ('request', 'execution'):
                        ref = value.get(key)
                        if isinstance(ref, dict) and {'path', 'sha256'} <= ref.keys():
                            bound = self.pointer(ref['path'], owner, expected=ref['sha256'])
                            self.audit_paths(load(bound['path']), owner)
                if value.get('candidate_id') == cid or event['kind'] == 'actual_read':
                    timeline.append(dict(record=self.document(dict(timestamp=event['recorded_at'], event_type=event['kind'],
                        summary=v2.canonical(value).decode().strip(), source_record=origin))))
        for name in ('knowledge-read.jsonl', 'knowledge-reads.jsonl', 'knowledge_reads.jsonl'):
            path = taskdir / name
            if path.is_file():
                for i, row in enumerate(v2.load_rows(self.safe(path, owner))):
                    purpose = row.get('purpose', row.get('used_for'))
                    require(isinstance(purpose, str) and purpose, 'knowledge read needs a recorded purpose')
                    origin = self.pointer(path, owner, selector=f'line:{i + 1}')
                    self.audit_paths(row, owner)
                    reads.append(dict(record=self.document({**row, 'purpose': purpose, 'source_record': origin})))
        # Ledger events are projected per task, retaining their actual timestamps.
        for event in self.ledger.events:
            args = event['arguments']
            if args.get('workload') == owner and (args.get('candidate_id') == cid or args.get('stage_id') in {sid for sid, s in task['stages'].items() if s['candidate_id'] == cid}):
                row = dict(timestamp=event['recorded_at'], event_type=event['operation'],
                           summary=v2.canonical(args).decode().strip(), ledger_event=event)
                timeline.append(dict(record=self.document(row)))
        observation_ids = candidate.get('observation_ids', [])
        decision = None
        # A retrospective quality observation is not a new search decision.
        # Preserve the latest actual decision while retaining all observations
        # in the ledger timeline and evidence closure above.
        for observation_id in reversed(observation_ids):
            last = task['observations'][observation_id]
            feedback = last['feedback']
            action = feedback.get('action', feedback.get('decision'))
            reason = feedback.get('reason')
            if action == 'quality_update':
                continue
            if isinstance(action, str) and isinstance(reason, str):
                decision = dict(action=action, reason=reason, evidence=[self.document(last)])
                break
        manifest = load(taskdir / 'manifest.json')
        catalog_path = taskdir / 'knowledge-catalog.json'
        catalog = load(self.safe(catalog_path, owner)) if catalog_path.exists() else {}
        self.pointer(taskdir / 'manifest.json', owner)
        if catalog_path.exists():
            self.pointer(catalog_path, owner)
        context = {**manifest, **({'planning': planning_attributes, 'source_split': declaration['source_split']} if self.fresh else {})}
        return dict(id=cid, operator=owner, task_id=owner, split=self.split, sources=sources,
                    stable_id=candidate['stable_id'], inherited=inherited, context=context, knowledge_catalog=catalog,
                    diagnosis=dict(symptoms=[], hypotheses=[], missing_evidence=[], retrospective=True),
                    intervention=dict(statement=statement, basis=intervention_basis,
                        **planning_attributes, **({'parameters': deepcopy(proposal['parameters'])} if 'parameters' in proposal else {}),
                        evidence=[proposal_ref, sources['patch'], *planning_evidence]),
                    evaluations=comparisons, timeline=timeline, actual_reads=reads, next_decision=decision)

    @analysis.verification_storage.reader_session()
    def prepare(self, lessons_paths=None):
        attempts, checkpoints, lessons = [], [], []
        paths = [] if lessons_paths is None else list(lessons_paths)
        for owner, task in sorted(self.ledger.state['tasks'].items()):
            directory = self.task_root / owner
            manifest = load(self.safe(directory / 'manifest.json', owner))
            require(manifest.get('operator', owner) == owner and manifest.get('split', self.split) == self.split,
                    'task manifest identity differs')
            declaration = self.ledger.config['tasks'][owner]
            for stage in task['stages'].values():
                self.audit_paths(stage.get('plan', {}), owner)
                for attempt in stage['attempts']:
                    self.audit_paths(attempt.get('evidence', {}), owner)
            for observation in task.get('observations', {}).values():
                self.audit_paths(observation.get('feedback', {}), owner)
                self.audit_paths(observation.get('quality', {}), owner)
            projected = self.document(dict(schema_version=VERSION, operator=owner, split=self.split,
                declaration=declaration, task=task, source_ledger_head=self.ledger.events[-1]['hash'],
                source_config_hash=self.ledger.config_hash, attribution='verified_same_split_ledger_projection', **POLICY))
            evidence = [projected]
            for filename in ('manifest.json', 'input-bindings.json', 'knowledge-catalog.json', 'baseline-source.tar', 'inheritance-context.json',
                             'input-origin.json', 'task-parity.json', 'split.json'):
                path = directory / filename
                if path.is_file():
                    evidence.append(self.pointer(path, owner))
            self.files(directory / 'agent', owner)
            self.files(directory / 'build', owner)
            methods, represented = [], set()
            for path in sorted((directory / 'stages').glob('*/result.json')):
                value, record = self.stage(path, task, None, owner)
                represented.add(value['stage_id'])
                method = dict(stage_id=value['stage_id'], status=value['status'], record=record['record'])
                stage_plan = task['stages'][value['stage_id']].get('plan', {})
                if stage_plan.get('version') == 'level2_local_raw_method_qualification_v1':
                    method['single_process_qualification'] = self.single_process_method(path.parent, owner, stage_plan, value)
                cohort = path.parent / 'cohort'
                if (cohort / 'group-completion.json').is_file():
                    source = self.control_source_tar(owner, stage_plan.get('source_hash'))
                    method['observations'] = self.cohort(cohort, owner, source, source)
                methods.append(method)
            for value, record in self.manual_static_stages(task, None, owner, projected, represented):
                methods.append(dict(stage_id=value['stage_id'], status=value['status'], record=record['record']))
            checkpoints.append(dict(operator=owner, split=self.split, status='checkpoint',
                source_attempt_count=len(task['candidates']), used=task['used'],
                remaining={k: campaign.BUDGETS[k] - task['used'][k] for k in campaign.BUDGETS},
                new_rounds_started=task['new_rounds_started'], methods=methods, evidence=evidence, **POLICY))
            for cid, candidate in sorted(task['candidates'].items()):
                attempts.append(self.attempt(owner, cid, candidate, task, declaration, projected))
            if lessons_paths is None:
                path = directory / 'analysis' / 'lessons.json'
                if path.is_file():
                    paths.append(path)
        seen = set()
        for path in paths:
            path = self.safe(path)
            value = load(path)
            items = value.get('lessons', []) if isinstance(value, dict) else value
            require(isinstance(items, list), 'lesson input must be a list or {lessons: list}')
            for item in items:
                item = deepcopy(item)
                owner = item.get('operator')
                require(owner in self.ledger.state['tasks'], 'lesson requires same-split task owner')
                self.safe(path, owner)
                require(item.get('split', self.split) == self.split, 'cross-split lesson')
                require(item['id'] not in seen, 'duplicate lesson identity')
                if self.fresh and item.get('kind') == 'operator_optimization':
                    ids = item.get('source_attempt_ids')
                    require(isinstance(ids, list) and ids and len(ids) == len(set(ids)),
                            'fresh operator lesson requires explicit source_attempt_ids')
                    require(all(cid in self.ledger.state['tasks'][owner]['candidates'] for cid in ids),
                            'lesson source attempt belongs to a different task or is absent')
                seen.add(item['id'])
                item['split'] = self.split
                item = map_lesson_evidence(item, lambda ref: self.pointer(
                    Path(ref['path']) if Path(ref['path']).is_absolute() else path.parent / ref['path'],
                    owner, expected=ref.get('sha256'), selector=ref.get('selector', '')))
                item.setdefault('evidence', []).append(self.pointer(path, owner))
                lessons.append(item)
        return dict(run_id=self.run.name, task_id='msprof-exploration-' + self.split, split=self.split,
                    attempts=attempts, task_checkpoints=checkpoints, lessons=lessons,
                    artifact_index=list(self.artifacts.values()), engineering_snapshot_bindings=list(self.engineering_bindings.values()),
                    pointer_hash_normalizations=list(self.pointer_hash_normalizations.values()),
                    preparation_relocations=list(self.preparation_relocations.values()),
                    archive_version=VERSION, **POLICY)

    def import_history(self, recorder):
        for key, value in self.prior_contexts.items():
            require(v2.digest(value) == key, 'historical context hash differs')
            recorder.evidence.contexts[key] = value
        for ref, entry in self.prior_entries.items():
            actual = recorder.pointer(dict(path=entry['path'], sha256=entry['sha256'], selector=entry['selector']),
                                      self.split, 'unchanged historical evidence')
            require(actual == ref, 'historical evidence ID changed')

    def seed_history(self, recorder, output):
        """Preserve original record revisions before v2.publish appends a revision.

        Only the selected inherited records and their chains are seeded; prior
        method lessons and other task bodies never enter this new dataset.
        """
        if not self.prior_records or (output / 'current.json').exists():
            return
        rows = list(self.prior_records.values())
        files = {}
        for split in ('train', 'validation'):
            files[split + '/optimization_traces.jsonl'] = b''.join(v2.canonical(row) for row in rows if row['body']['identity']['split'] == split)
            files[split + '/lessons.jsonl'] = b''
        for kind in ('optimization_memory', 'lesson'):
            files['schemas/' + kind + '.schema.json'] = v2.canonical(v2.schema(kind))
        files['evidence_index.json'] = v2.canonical(recorder.evidence.entries)
        files['contexts.json'] = v2.canonical(recorder.evidence.contexts)
        files['metadata.json'] = v2.canonical(dict(version=VERSION, split=self.split, historical_identity_seed=True, **POLICY))
        objects = {key: v2.store_bytes(output, v2.canonical(row)) for key, row in self.prior_chains.items()}
        files['record_objects.json'] = v2.canonical(objects)
        for value in recorder.evidence.contexts.values():
            v2.store_bytes(output, v2.canonical(value))
        manifest = dict(schema_version=v2.VERSION, files={k: v2.digest_bytes(v) for k, v in sorted(files.items())},
                        counts=dict(optimization_attempts=len(rows), lessons=0,
                            measurement_continuations=sum(e['relation'] == 'measurement_continuation' for r in rows for e in r['body']['evaluations'])))
        revision = v2.digest(manifest)[7:]
        files['manifest.json'] = v2.canonical(manifest)
        for name, data in files.items():
            path = output / 'revisions' / revision / name
            if path.exists():
                require(path.read_bytes() == data, 'historical seed revision conflict')
            else:
                v2.write_synced(path, data)
        pointer = dict(revision=revision, manifest_hash=v2.digest(manifest))
        v2.verify(output, deep=True, prospective_pointer=pointer)
        v2.write_synced(output / 'current.json', v2.canonical(pointer))

    @analysis.verification_storage.reader_session()
    def publish(self, config):
        manifest = Path(self.document(config)['path'])
        recorder = FrozenRecorder(manifest, self.output)
        self.import_history(recorder)
        memories = {}
        for number, attempt in enumerate(config['attempts']):
            stable = attempt['stable_id']
            origin = stable.rsplit('/', 2)[0]
            body = recorder.memory(attempt, number, {**config, 'run_id': origin})
            for evaluation in body['evaluations']:
                evaluation['run_id'] = self.run.name
            if attempt['inherited']:
                previous = self.prior_records[stable]
                inherited = deepcopy(previous['body'])
                require(inherited['identity']['candidate_id'] == attempt['id'], 'historical candidate identity differs')
                for key in ('original_baseline', 'direct_parent', 'candidate', 'patch', 'parent_attempt_id'):
                    require(inherited['sources'][key] == body['sources'][key], 'historical full source/patch identity differs')
                for key in ('evaluations', 'machine_results'):
                    id_key = 'id' if key == 'evaluations' else 'evaluation_id'
                    existing = {row[id_key]: row for row in inherited[key]}
                    for row in body[key]:
                        require(row[id_key] not in existing or existing[row[id_key]] == row, 'historical evaluation ID conflict')
                        if row[id_key] not in existing:
                            inherited[key].append(row)
                inherited['timeline'] = sorted(inherited['timeline'] + [row for row in body['timeline'] if row not in inherited['timeline']], key=lambda row: row['timestamp'])
                inherited['sources']['evidence_ids'] = list(dict.fromkeys(inherited['sources']['evidence_ids'] + body['sources']['evidence_ids']))
                inherited['knowledge']['actual_reads'] += [row for row in body['knowledge']['actual_reads'] if row not in inherited['knowledge']['actual_reads']]
                inherited['provenance']['source_record_refs'] = list(dict.fromkeys(inherited['provenance']['source_record_refs'] + body['provenance']['source_record_refs']))
                inherited['provenance']['null_reasons'].update(body['provenance']['null_reasons'])
                if body['next_decision']['action'] != 'not_recorded':
                    inherited['next_decision'] = body['next_decision']
                body = inherited
            require(stable not in memories, 'duplicate source attempt identity')
            memories[stable] = body
        checkpoints = [recorder.pointer(dict(path=str(manifest), selector='/task_checkpoints/' + str(i)), self.split,
                         'method/task checkpoint, not a source attempt') for i in range(len(config['task_checkpoints']))]
        for pointer in config['artifact_index']:
            recorder.pointer(pointer, self.split, 'same-split frozen evidence closure')
        for binding in config.get('engineering_snapshot_bindings', []):
            ref = recorder.pointer(binding['snapshot'], self.split, 'frozen bytes of the recorded engineering producer')
            recorder.origins.setdefault(ref, set()).add(binding['origin']['path'])
        for binding in config.get('preparation_relocations', []):
            ref = recorder.pointer(binding['snapshot'], self.split, 'event-attested failed preparation bytes')
            recorder.origins.setdefault(ref, set()).add(binding['origin']['path'])
        def freeze_pointer(pointer):
            ref = recorder.pointer(pointer, self.split, 'independent analysis lesson evidence')
            entry = recorder.evidence.entries[ref]
            return dict(path=entry['path'], selector=entry['selector'])
        lessons = map_lesson_evidence(config['lessons'], freeze_pointer)
        producer = recorder.pointer(dict(path=str(Path(__file__).resolve())), self.split, 'archive adapter source')
        for module in (campaign, analysis, analysis.engineering_provenance, feedback_trace_export, v2):
            recorder.pointer(dict(path=str(Path(module.__file__).resolve())), self.split, 'archive dependency source')
        metadata = dict(schema_version=v2.VERSION, archive_version=VERSION, run_id=self.run.name,
            split=self.split, exporter_hardware_executed=False, legacy_gate_and_episode_semantics='unchanged',
            new_source_attempts=sum(not a['inherited'] for a in config['attempts']),
            inherited_source_attempts=sum(a['inherited'] for a in config['attempts']),
            task_checkpoint_refs=checkpoints, producer_source_ref=producer,
            engineering_snapshot_bindings=config.get('engineering_snapshot_bindings', []),
            pointer_hash_normalizations=config.get('pointer_hash_normalizations', []),
            preparation_relocations=config.get('preparation_relocations', []),
            original_evidence_locations={key: sorted(value) for key, value in recorder.origins.items()},
            evaluation_granularity='one evaluation per actual comparison; shared execution stages retain original evidence', **POLICY)
        if self.fresh:
            metadata['campaign_schema'] = campaign.FRESH_SCHEMA
            metadata['lesson_planning_contract'] = v2.LESSON_PLANNING_CONTRACT
            metadata['source_splits'] = {owner: declaration['source_split'] for owner, declaration in self.ledger.config['tasks'].items()}
            metadata['graph_snapshots'] = {'v0002': [dict(content_hash=digest,
                evidence_id=recorder.pointer(pointer, self.split, 'frozen v0002 graph association authority'))
                for digest, pointer in sorted(self.planning_graphs.items())]}
        self.output.mkdir(parents=True, exist_ok=True)
        with (self.output / '.publish.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # Only this unpublished workspace sees the historical seed pointer.
            # Shared immutable stores avoid relocating any absolute evidence path.
            # Failed workspaces remain available for forensic inspection.
            staging = Path(tempfile.mkdtemp(prefix='.publish-staging-', dir=self.root))
            for name in ('cas', 'revisions'):
                target = self.output / name
                target.mkdir(exist_ok=True)
                (staging / name).symlink_to(target, target_is_directory=True)
            current = self.output / 'current.json'
            if current.exists():
                v2.write_synced(staging / 'current.json', current.read_bytes())
            self.seed_history(recorder, staging)
            result = v2.publish(staging, memories,
                lambda rows: normalize_exploration_lessons(lessons, rows, recorder.evidence, stage_scoped=self.fresh), recorder.evidence, metadata)
            pointer = load(staging / 'current.json')
            result['verification'] = verify_dataset(self.output, self.split, deep=True, pointer=pointer)
            result.update(root=str(self.output), new_source_attempts=metadata['new_source_attempts'],
                          inherited_source_attempts=metadata['inherited_source_attempts'],
                          task_checkpoints=len(checkpoints), hardware_executed=False)
            # All publication/validation work finishes before the sole public commit.
            analysis.verification_storage.reverify_cached()
            os.replace(staging / 'current.json', current)
            return result


def archive_split(run, split, lessons_paths=None):
    archive = Archive(run, split)
    return archive.publish(archive.prepare(lessons_paths))


def verify_split(run, split, deep=True):
    """Pure reader. It never constructs a writable store, recorder or gate."""
    require(split in ('train', 'validation'), 'invalid split')
    root = Path(run).resolve() / 'archive' / split / 'v2'
    return verify_dataset(root, split, deep=deep)


def verify_dataset(root, split, deep=True, pointer=None):
    """Verify either a public revision or a prospective one without publishing."""
    pointer = pointer or load(root / 'current.json')
    base = root / 'revisions' / pointer['revision']
    manifest = load(base / 'manifest.json')
    opposite = 'validation' if split == 'train' else 'train'
    require(all(manifest['files'][opposite + '/' + name] == v2.digest_bytes(b'') for name in ('optimization_traces.jsonl', 'lessons.jsonl')),
            'archive contains opposite-split outcomes')
    index = load(base / 'evidence_index.json')
    require(all(row['split'] == split for row in index.values()), 'archive evidence crosses split')
    metadata = load(base / 'metadata.json')
    require(metadata['split'] == split and all(metadata.get(k) == v for k, v in POLICY.items()), 'archive policy metadata differs')
    if metadata.get('campaign_schema') == campaign.FRESH_SCHEMA:
        require(all('aprof-feat-aprofgraph' not in Path(row['path']).parts for row in index.values()),
                'fresh evidence index references historical checkout')
        memories = v2.load_rows(base / split / 'optimization_traces.jsonl')
        for record in memories:
            attributes = record['body']['intervention']['attributes']
            require(attributes.get('optimization_stage') in ('algorithm_parallel', 'execution'), 'missing archived optimization stage')
            require(attributes.get('implementation_source_hash') == record['body']['sources']['candidate'], 'archived implementation source differs')
        for record in v2.load_rows(base / split / 'lessons.jsonl'):
            if record['body']['kind'] == 'operator_optimization':
                require(record['body']['memory_refs'], 'fresh operator lesson lost its memory references')
    return v2.verify(root, deep=deep, prospective_pointer=pointer)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('archive', 'verify'))
    parser.add_argument('--run', required=True)
    parser.add_argument('--split', required=True, choices=('train', 'validation'))
    parser.add_argument('--lessons', action='append')
    args = parser.parse_args(argv)
    result = archive_split(args.run, args.split, args.lessons) if args.command == 'archive' else verify_split(args.run, args.split)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
