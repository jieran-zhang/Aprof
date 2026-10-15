"""Read-only individual Teacher rule admission; never writes a skill or publishes.

The caller supplies the trusted finite campaign and previous complete skill
inventory. Both registered attempts are replayed, including failures. Only the
operator-specific page may use its independently passing trial. Independent review
is replayed from caller-trusted post-task archives, without the original workspace.
"""
import json
from pathlib import Path
import sys

from shared_validation_adapter import selected_runtime
from task_rule_campaign import _pointer, replay_task_rule_campaign
from timing_admission import checked_path, digest, file_hash, read, require


SCOPES = {
    'exp-tile8192': {
        'operator': 'exp', 'target_skill': 'skills/ascendc-aprof-optimization/SKILL.md',
        'source_keys': [
            'l1:level1-feedback-shared-context-20260910T142313Z/train/operator/exp/exp001/case03-tile-setup',
            'l1:train/exp/exp001/tile-coalescing-search-retrospective'],
        'graph_nodes': ['transformation.coalesce_contiguous_transfers'],
    },
    'sigmoid-pipeline': {
        'operator': 'sigmoid', 'target_skill': 'skills/ascendc-aprof-optimization/SKILL.md',
        'source_keys': ['l1:sigmoid001-pipeline-final-v1'],
        'graph_nodes': ['mechanism.pipeline_serialization', 'transformation.software_pipeline_stages'],
    },
}
KEYS = {'schema_version', 'kind', 'proposal_id', 'wiki_id', 'target_skill', 'source_keys',
    'source_audit_ref', 'wiki_index_ref', 'wiki_page_ref', 'trace_index_ref', 'split_index_ref',
    'skill_before', 'skill_after', 'skill_inventory_before_ref', 'skill_inventory_after_ref',
    'campaign_ref', 'selected_run_id', 'trace_ref', 'hardware_report_ref'}


def _skills(reader, receipt, release, expected_before):
    target = SCOPES[receipt['wiki_id']]['target_skill']
    require(receipt['skill_inventory_before_ref'] == expected_before,
            'promotion changed the trusted previous skill revision')
    before, after = (read(reader, receipt['skill_inventory_' + name + '_ref']) for name in ('before', 'after'))
    require(isinstance(before, dict) and before and set(before) == set(after),
            'promotion added or removed a canonical skill')
    for name in before:
        path = Path(name)
        require(len(path.parts) == 3 and path.parts[0] == 'skills' and path.name == 'SKILL.md'
                and path.as_posix() == name and '..' not in path.parts,
                'invalid canonical skill inventory')
        for ref in (before[name], after[name]):
            reader.verify_artifact(ref)
    require([name for name in before if before[name] != after[name]] == [target]
            and receipt['skill_before']['sha256'] == before[target]
            and receipt['skill_after']['sha256'] == after[target],
            'promotion must change exactly the one named canonical skill')
    for name in ('skill_before', 'skill_after'):
        pointer = receipt[name]
        require(set(pointer) == {'path', 'sha256'} and Path(pointer['path']).is_absolute(),
                'skill revision needs its original absolute path and hash')
        # The one canonical target intentionally changes on application. Its
        # archived revision bytes and the complete live inventory are both checked.
        if pointer['path'] == str(release / target):
            reader.verify_artifact(pointer['sha256'])
        else:
            checked_path(reader, pointer['path'], pointer['sha256'])
    paths = sorted((release / 'skills').glob('*/SKILL.md'))
    require(all(not any(p.is_symlink() for p in (path, *path.parents)) for path in paths),
            'canonical skill path is a symlink')
    live = {path.relative_to(release).as_posix(): file_hash(path) for path in paths}
    require(live in (before, after), 'live skills differ from both complete proposed revisions')
    return {'target_skill': target, 'before': before[target], 'after': after[target],
            'before_inventory_ref': expected_before, 'after_inventory_ref': receipt['skill_inventory_after_ref'],
            'applied': live == after}


def _sources(reader, receipt, campaign, repo, release):
    """Read original lesson records, not a passed source-audit summary."""
    wiki_id = receipt['wiki_id']; scope = SCOPES[wiki_id]; operator = scope['operator']
    expected_paths = {
        'source_audit_ref': repo / 'scaffolding/curation/graph-base-1.0.0.json',
        'trace_index_ref': repo.parent / 'optimization-traces/index.json',
        'split_index_ref': repo / 'scaffolding/benchmarks/cannbench/split_index.json',
    }
    for key, path in expected_paths.items():
        require(receipt[key]['path'] == str(path), 'promotion changed the canonical source/index location')
        checked_path(reader, path, receipt[key]['sha256'])
    # Wiki entry status changes during application; preserve immutable index/page
    # snapshots and compare their source scope with the current canonical entry.
    for key in ('wiki_index_ref', 'wiki_page_ref'):
        pointer = receipt[key]
        require(set(pointer) == {'path', 'sha256'} and Path(pointer['path']).is_absolute(),
                'Wiki snapshot requires its original path and hash')
        checked_path(reader, pointer['path'], pointer['sha256'])
    require(receipt['trace_index_ref']['sha256'] == campaign['trace_index_sha256']
            and receipt['split_index_ref']['sha256'] == campaign['split_index_sha256'],
            'promotion changed the preregistered source split')
    audit, wiki = (read(reader, receipt[key]['sha256']) for key in ('source_audit_ref', 'wiki_index_ref'))
    require(audit['trace_index_sha256'] == campaign['trace_index_sha256']
            and audit['split_index_sha256'] == campaign['split_index_sha256']
            and wiki['trace_index_sha256'] == campaign['trace_index_sha256'], 'curation source indices differ')
    entry = wiki['entries'][wiki_id]
    current = json.loads((release / 'wiki/index.json').read_text())['entries'][wiki_id]
    for item in (entry, current):
        require(item['source_keys'] == scope['source_keys'] and item['page'] == wiki_id + '.md'
                and (item['status'], item['skill_refs']) in (('draft', []), ('validated', [scope['target_skill']]))
                and item['graph_nodes'] == scope['graph_nodes'] and item['source_refs'] == entry['source_refs'],
                'mixed or different Wiki rule cannot inherit this operator qualification')
    sys.path.insert(0, str(repo / 'scaffolding/tools'))
    from verify_teacher_wiki import split_members
    require(split_members(repo).get(operator) == 'train', 'validation/test evidence cannot promote a skill')
    source_refs = []
    for key in scope['source_keys']:
        row = audit['records'][key]
        require(row['level'] == 1 and row['operator'] == operator and row['split'] == 'train'
                and row['decision'] in ('include', 'merge') and wiki_id in row['wiki_ids']
                and row['sources'], 'promotion contains an uncurated or different-operator source')
        for source in row['sources']:
            relative = Path(source['path'])
            require(not relative.is_absolute() and '..' not in relative.parts
                    and relative.parts[0] == 'optimization-traces', 'lesson source escaped trace inventory')
            path = repo.parent / relative
            # The established source audit hashes each JSONL record, not its entire file.
            lines = [line for line in path.read_bytes().splitlines() if digest(line) == source['sha256']]
            require(len(lines) == 1, 'original lesson record is absent or duplicated')
            lesson = json.loads(lines[0])
            require('l1:' + lesson['id'] == key and lesson['record_hash'] == source['record_hash']
                    and lesson['body']['operator'] == operator and lesson['body']['split'] == 'train',
                    'lesson identity/split differs from the curated record')
        source_refs.append({'key': key, 'sha256': [s['sha256'] for s in row['sources']]})
    require(entry['source_refs'] == source_refs, 'Wiki source hashes differ from original lesson records')
    return {'wiki_id': wiki_id, 'source_keys': scope['source_keys'], 'source_refs': source_refs,
            'source_split': 'train', 'source_audit_ref': receipt['source_audit_ref']}


class _ReadOnlyRuntime:
    """Existing exploration replay may re-register canonical JSON; only verify it."""
    def __init__(self, reader):
        self.reader = reader

    def verify_artifact(self, reference):
        return self.reader.verify_artifact(reference)

    def object_path(self, reference):
        return self.verify_artifact(reference)

    def register_artifact(self, path, **_kwargs):
        reference = file_hash(Path(path))
        self.verify_artifact(reference)
        return reference


def _runtime(reader, receipt, selected, campaign_ref, release, *, retained_review_refs):
    from aprof_runtime.planning import architecture_id
    from aprof_runtime.traces import validate_optimization_trace
    from retained_source_review import replay_retained_source_review

    operator = SCOPES[receipt['wiki_id']]['operator']
    components = selected['components']
    child = read(reader, selected['controller_result_ref'])
    report = read(reader, components['report_ref'])
    trace_ref, request_ref, outcome_ref = (child[k] for k in
        ('trace_ref', 'exploration_request_ref', 'exploration_outcome_ref'))
    require(receipt['trace_ref'] == trace_ref
            and set(components['roster']['stage_evidence']['online_admission']) == {trace_ref, request_ref, outcome_ref},
            'promotion selected a trace outside the actual online gate stage')
    trace, request, outcome = (read(reader, ref) for ref in (trace_ref, request_ref, outcome_ref))
    expected = components['measurement_expected']; identity = trace['identity']
    require(trace['routing']['mode'] == 'exploration'
            and trace['result']['exploration_outcome_ref'] == outcome_ref
            and outcome['request_hash'] == request_ref
            and trace['result']['verdict'] == child['formal_outcome'] == 'production_safe_gain'
            and all(identity[key] == expected[key] for key in ('operator', 'run_id', 'candidate_id', 'session_id'))
            and identity['operator'] == identity['task_id'] == operator and identity['split'] == 'train'
            and identity['source_parent_hash'] == expected['source_hashes']['baseline'],
            'promotion requires the selected operator independent production-safe outcome')
    require(len(request['candidates']) == len(request['evidence']) == 1 and request['config'] == {},
            'promotion changed the single candidate or default machine gate')
    candidate, evidence = request['candidates'][0], request['evidence'][0]
    require(candidate['candidate_id'] == evidence['candidate_id'] == expected['candidate_id']
            and candidate['source_hashes'] == expected['source_hashes'], 'machine candidate/source identity differs')
    manifest = read(reader, request['frozen_manifest_hash'])
    require(all(manifest[k] == identity[k] for k in ('run_id', 'task_id', 'split')),
            'machine manifest changed the independent run/source split')
    artifacts = evidence['artifacts']
    bindings = {'accuracy_report': report['correctness_report_ref'], 'boundary_report': report['boundary_report_ref'],
        'measurement_admission': report['measurement_admission_ref'], 'mechanism_report': report['mechanism_report_ref'],
        'measurement_report': expected['measurement_report_ref'], 'qualification_campaign': campaign_ref,
        'qualification_registration': components['qualification_registration_ref'], 'hardware_report': receipt['hardware_report_ref']}
    require(all(artifacts.get(k) == ref for k, ref in bindings.items()), 'runtime gate changed a replayed outer component')
    require(trace['workload']['case_ids'] == list(range(1, 21))
            and trace['validation']['case_count'] == trace['validation']['passed_count'] == 20
            and trace['validation']['timing_case_ids'] == list(range(1, 21))
            and trace['workload']['hardware_fingerprint'] == receipt['hardware_report_ref'],
            'promotion trace changed complete-case coverage or hardware')
    hardware = read(reader, receipt['hardware_report_ref'])
    require(architecture_id(hardware.get('soc', '')) == '910c'
            and isinstance(hardware.get('cann_version'), dict) and hardware['cann_version'].get('version') == '9.0.0',
            'hardware is not verified 910C/A3 with CANN 9.0.0')
    for ref in components['checks']['task_and_profile']['capture_manifests'].values():
        require(read(reader, ref)['hardware_hash'] == receipt['hardware_report_ref'], 'PMU capture hardware differs')
    correctness = read(reader, report['correctness_report_ref'])
    build = read(reader, correctness['build_receipt_ref'])
    attempt = _pointer(reader, build['attempt_ref'])
    require(attempt['route'] == {'mode': 'exploration', 'anchor_ref': selected['anchor_ref']},
            'build did not use the registered exploration authority')
    require(isinstance(retained_review_refs, dict)
            and set(retained_review_refs) == {'archive_inventory_ref', 'producer_snapshot_ref'},
            'promotion requires trusted post-task review archive and producer snapshot refs')
    review = replay_retained_source_review(reader, anchor_ref=selected['anchor_ref'],
        source_review_ref=attempt['independent_review']['sha256'], **retained_review_refs)
    require(review['accepted'] is True and review['source_review_ref'] == attempt['independent_review']
            and review['source_review_ref']['sha256'] == artifacts['source_review'],
            'actual independent review differs from the single build or runtime gate')
    _pointer(reader, review['source_review_ref'])
    # Reuse the full machine implementation, including raw Task/profile replay.
    # This is separate from the campaign's one outer replay; no summary substitutes it.
    validate_optimization_trace(trace, _ReadOnlyRuntime(reader))
    return {'trace_ref': trace_ref, 'request_ref': request_ref, 'outcome_ref': outcome_ref,
            'hardware_report_ref': receipt['hardware_report_ref'], 'source_review_ref': review['source_review_ref'],
            'verdict': outcome['verdict'], 'retained_source_review_replay_complete': True,
            'retained_review_refs': dict(retained_review_refs)}


def verify_task_rule_promotion(reader, promotion_ref, *, campaign_ref, trials,
                               trusted_before_inventory_ref, repo, release,
                               trusted_review_archives=None):
    """Validate one proposed edit; caller still owns applying it and release sealing."""
    repo, release = Path(repo).resolve(), Path(release).resolve()
    require(selected_runtime() == release and release == repo / 'skill-libs/graph-base/1.0.0',
            'promotion must use the explicitly selected 1.0.0 runtime')
    receipt = read(reader, promotion_ref)
    require(set(receipt) == KEYS and receipt['schema_version'] == 1
            and receipt['kind'] == 'teacher_task_rule_promotion' and receipt['proposal_id']
            and receipt['wiki_id'] in SCOPES
            and receipt['target_skill'] == SCOPES[receipt['wiki_id']]['target_skill']
            and receipt['source_keys'] == SCOPES[receipt['wiki_id']]['source_keys']
            and receipt['campaign_ref'] == campaign_ref,
            'unsupported, mixed-rule or unbound Task Teacher promotion')
    campaign = read(reader, campaign_ref)
    edit = _skills(reader, receipt, release, trusted_before_inventory_ref)
    sources = _sources(reader, receipt, campaign, repo, release)
    replay = replay_task_rule_campaign(reader, campaign_ref, trials=trials)
    operator = SCOPES[receipt['wiki_id']]['operator']
    selected = next(row for row in replay['trials'] if row['operator'] == operator)
    require(selected['run_id'] == receipt['selected_run_id'] and selected['status'] == 'completed_child'
            and selected['components'] is not None, 'failed/not-run operator cannot promote its Wiki rule')
    machine = _runtime(trials[operator]['reader'], receipt, selected, campaign_ref, release,
        retained_review_refs=(trusted_review_archives or {}).get(operator))
    return {'valid': True, 'scope': 'one_operator_teacher_edit', 'operator': operator, 'promotion_ref': promotion_ref,
            'campaign_ref': campaign_ref, 'campaign': replay, 'edit': edit, 'sources': sources, 'machine': machine,
            'eligible_for_teacher_edit': True, 'eligible_for_publication': False, 'graph_policy_eligible': False,
            'remaining_publication_requirements': [
                'apply the single accepted edit and run the complete release/publication verifier']}
