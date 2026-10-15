"""CPU policy/wiring checks only; mocked component success is not qualification."""
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))
import task_rule_promotion as promotion
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import ContractError
from timing_admission import read
from test_task_rule_campaign import make_campaign

WIKI_ID = 'exp-tile8192'
TARGET = promotion.SCOPES[WIKI_ID]['target_skill']
SOURCE_KEYS = promotion.SCOPES[WIKI_ID]['source_keys']


def pointer(store, path):
    return {'path': str(path), 'sha256': store.register_artifact(path)}


def test_single_skill_revision_rejects_extra_edit_and_changed_original(tmp_path):
    local = LocalEvidence(tmp_path / 'records'); release = tmp_path / 'release'
    first = release / TARGET; first.parent.mkdir(parents=True); first.write_text('before')
    other = release / 'skills/other/SKILL.md'; other.parent.mkdir(); other.write_text('unchanged')
    after = tmp_path / 'proposed-skill.md'; after.write_text('after')
    before = {TARGET: local.register_artifact(first), 'skills/other/SKILL.md': local.register_artifact(other)}
    before_ref = local.register_json(before)
    changed = dict(before, **{TARGET: local.register_artifact(after)})
    receipt = dict(wiki_id=WIKI_ID, skill_inventory_before_ref=before_ref, skill_inventory_after_ref=local.register_json(changed),
                   skill_before=pointer(local, first), skill_after=pointer(local, after))
    result = promotion._skills(local, receipt, release, before_ref)
    assert not result['applied'] and result['target_skill'] == TARGET
    extra = dict(changed, **{'skills/other/SKILL.md': changed[TARGET]})
    with pytest.raises(ValueError, match='exactly the one'):
        promotion._skills(local, dict(receipt, skill_inventory_after_ref=local.register_json(extra)), release, before_ref)
    with pytest.raises(ValueError, match='trusted previous'):
        promotion._skills(local, receipt, release, receipt['skill_inventory_after_ref'])
    after.write_text('forged')
    with pytest.raises(Exception):
        promotion._skills(local, receipt, release, before_ref)


@pytest.fixture(params=list(promotion.SCOPES))
def source_fixture(tmp_path, request):
    wiki_id = request.param; scope = promotion.SCOPES[wiki_id]; operator = scope['operator']
    local = LocalEvidence(tmp_path / 'records'); repo = tmp_path / 'repo'
    release = repo / 'skill-libs/graph-base/1.0.0'
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))
        return pointer(local, path)
    for split, names in [('train', ['exp', 'sigmoid']), ('validation', ['gelu']), ('test', ['relu'])]:
        base = repo / 'scaffolding/benchmarks/cannbench' / split
        save(base / 'manifest.json', {'active_operators': names})
        (base / 'operators.txt').write_text('\n'.join(names) + '\n')
    trace = save(tmp_path / 'optimization-traces/index.json', {'CPU_fixture': True})
    split = save(repo / 'scaffolding/benchmarks/cannbench/split_index.json', {'CPU_fixture': True})
    records, refs = {}, []
    for i, key in enumerate(scope['source_keys']):
        lesson = {'id': key[3:], 'record_hash': 'sha256:' + str(i) * 64,
                  'body': {'operator': operator, 'split': 'train'}}
        line = json.dumps(lesson).encode(); path = tmp_path / f'optimization-traces/lesson-{i}.jsonl'
        path.write_bytes(line + b'\n')
        source = dict(path=path.relative_to(tmp_path).as_posix(), sha256=promotion.digest(line),
                      record_hash=lesson['record_hash'])
        records[key] = dict(level=1, operator=operator, split='train', decision='include',
                            wiki_ids=[wiki_id], sources=[source])
        refs.append({'key': key, 'sha256': [source['sha256']]})
    campaign = dict(trace_index_sha256=trace['sha256'], split_index_sha256=split['sha256'])
    audit = dict(**campaign, records=records)
    entry = dict(source_keys=scope['source_keys'], page=wiki_id+'.md', skill_refs=[], status='draft',
                 graph_nodes=scope['graph_nodes'], source_refs=refs)
    wiki = dict(trace_index_sha256=trace['sha256'], entries={wiki_id: entry})
    receipt = dict(wiki_id=wiki_id, trace_index_ref=trace, split_index_ref=split,
        source_audit_ref=save(repo / 'scaffolding/curation/graph-base-1.0.0.json', audit),
        wiki_index_ref=save(release / 'wiki/index.json', wiki), wiki_page_ref=save(release / 'wiki' / (wiki_id+'.md'), {}))
    return local, receipt, campaign, repo, release


def test_source_split_replays_original_lesson_bytes(source_fixture):
    local, receipt, campaign, repo, release = source_fixture
    assert promotion._sources(local, receipt, campaign, repo, release)['source_split'] == 'train'
    path = repo.parent / 'optimization-traces/lesson-0.jsonl'
    value = json.loads(path.read_text()); value['body']['operator'] = 'another-operator'; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='original lesson'):
        promotion._sources(local, receipt, campaign, repo, release)


def test_no_split_relabeling(source_fixture):
    local, receipt, campaign, repo, release = source_fixture
    base = repo / 'scaffolding/benchmarks/cannbench'
    (base / 'train/operators.txt').write_text('')
    (base / 'train/manifest.json').write_text(json.dumps({'active_operators': []}))
    with pytest.raises(ValueError, match='validation/test'):
        promotion._sources(local, receipt, campaign, repo, release)


def test_immutable_wiki_snapshot_survives_status_application(source_fixture):
    local, receipt, campaign, repo, release = source_fixture
    path = release / 'wiki/index.json'; snapshot = repo.parent / 'wiki-before.json'
    snapshot.write_bytes(path.read_bytes())
    # A post-task reader indexes the retained snapshot first. Original task
    # LocalEvidence intentionally retains its first path for a duplicate digest.
    retained = LocalEvidence(repo.parent / 'retained-records')
    receipt['wiki_index_ref'] = pointer(retained, snapshot)
    retained.register_artifacts(list(local._paths.values()))
    value = json.loads(path.read_text()); entry = value['entries'][receipt['wiki_id']]
    entry.update(status='validated',skill_refs=[promotion.SCOPES[receipt['wiki_id']]['target_skill']])
    path.write_text(json.dumps(value))
    assert promotion._sources(retained,receipt,campaign,repo,release)['wiki_id'] == receipt['wiki_id']


@pytest.fixture(params=list(promotion.SCOPES))
def runtime_fixture(tmp_path, monkeypatch, request):
    wiki_id = request.param; operator = promotion.SCOPES[wiki_id]['operator']
    local = LocalEvidence(tmp_path / 'records'); save = local.register_json
    import retained_source_review
    expected = dict(operator=operator,run_id='CPU-new-'+operator,candidate_id='CPU-candidate',session_id='CPU-session',
        source_hashes={r:save({'source':r}) for r in ('baseline','candidate')}, measurement_report_ref=save({'report':True}))
    campaign_ref = save({'CPU_campaign':True})
    hardware_ref = save({'soc':'Ascend910_9392','cann_version':{'version':'9.0.0'},'CPU_fixture':True})
    workspace = tmp_path / 'worker/root/work'; workspace.mkdir(parents=True)
    review_path = workspace / 'candidate_review.json'; review_path.write_text(json.dumps({'CPU_review':True}))
    review_pointer = pointer(local, review_path)
    review = dict(accepted=True, source_review={}, source_review_ref=review_pointer)
    retained_refs = {'archive_inventory_ref':save({'archive':True}), 'producer_snapshot_ref':save({'producers':True})}
    review_calls = []
    def retained_replay(reader, **kwargs):
        review_calls.append(kwargs)
        assert kwargs == dict(anchor_ref=anchor_ref, source_review_ref=review_pointer['sha256'], **retained_refs)
        return review
    monkeypatch.setattr(retained_source_review, 'replay_retained_source_review', retained_replay)
    anchor_ref = save({'controller_plan_ref': save({'directory': str(tmp_path)})})
    attempt_path = tmp_path / 'build-attempt.json'
    attempt_path.write_text(json.dumps({'route':{'mode':'exploration','anchor_ref':anchor_ref},
                                      'independent_review':review_pointer}))
    correctness = save({'build_receipt_ref':save({'attempt_ref':pointer(local, attempt_path)})})
    report = {'correctness_report_ref':correctness, 'boundary_report_ref':save({'boundary':True}),
              'measurement_admission_ref':save({'NOT_A_REAL_PROOF':True}), 'mechanism_report_ref':save({'pmu':True})}
    registration = save({'reg':True})
    artifacts = dict(accuracy_report=correctness, boundary_report=report['boundary_report_ref'],
        measurement_admission=report['measurement_admission_ref'], mechanism_report=report['mechanism_report_ref'],
        measurement_report=expected['measurement_report_ref'], qualification_campaign=campaign_ref,
        qualification_registration=registration, hardware_report=hardware_ref, source_review=review_pointer['sha256'])
    identity = {k: expected[k] for k in ('operator','run_id','candidate_id','session_id')}
    identity.update(task_id=operator,split='train',source_parent_hash=expected['source_hashes']['baseline'])
    candidate = dict(candidate_id=expected['candidate_id'],source_hashes=expected['source_hashes'])
    request = dict(candidates=[candidate], evidence=[dict(candidate_id=candidate['candidate_id'],artifacts=artifacts)],
        config={}, frozen_manifest_hash=save({k: identity[k] for k in ('run_id','task_id','split')}))
    outcome = dict(request_hash=save(request),verdict='production_safe_gain')
    trace = dict(identity=identity,routing={'mode':'exploration'}, result=dict(exploration_outcome_ref=save(outcome),
        verdict='production_safe_gain'), workload=dict(case_ids=list(range(1,21)),hardware_fingerprint=hardware_ref),
        validation=dict(case_count=20,passed_count=20,timing_case_ids=list(range(1,21))))
    child = dict(trace_ref=save(trace),exploration_request_ref=outcome['request_hash'],
        exploration_outcome_ref=trace['result']['exploration_outcome_ref'],formal_outcome='production_safe_gain')
    components = dict(report_ref=save(report), measurement_expected=expected,qualification_registration_ref=registration,
        roster={'stage_evidence':{'online_admission':[child[k] for k in
            ('trace_ref','exploration_request_ref','exploration_outcome_ref')]}},
        checks={'task_and_profile':{'capture_manifests':{r:save({'hardware_hash':hardware_ref}) for r in ('baseline','candidate')}}})
    selected = dict(controller_result_ref=save(child),anchor_ref=anchor_ref,components=components)
    receipt = dict(wiki_id=wiki_id, trace_ref=child['trace_ref'],hardware_report_ref=hardware_ref)
    return local, receipt, selected, campaign_ref, review, retained_refs, review_calls


def test_runtime_does_not_accept_component_passed_summary(runtime_fixture):
    local, receipt, selected, campaign_ref, _, retained_refs, review_calls = runtime_fixture
    with pytest.raises(ContractError):
        promotion._runtime(local, receipt, selected, campaign_ref, promotion.selected_runtime(),
                           retained_review_refs=retained_refs)


def test_runtime_wiring_calls_real_gate_api_once_without_writes(runtime_fixture, monkeypatch):
    local, receipt, selected, campaign_ref, _, retained_refs, review_calls = runtime_fixture
    from aprof_runtime import traces
    calls = []; before = dict(local._paths)
    def spy(trace, reader):
        calls.append(trace)
        path = local.verify_artifact(receipt['trace_ref'])
        assert reader.register_artifact(path) == receipt['trace_ref']
    monkeypatch.setattr(traces, 'validate_optimization_trace', spy)
    result = promotion._runtime(local, receipt, selected, campaign_ref, promotion.selected_runtime(),
                           retained_review_refs=retained_refs)
    assert len(calls) == 1 and local._paths == before
    assert result['retained_source_review_replay_complete']
    assert result['retained_review_refs'] == retained_refs and len(review_calls) == 1


@pytest.mark.parametrize('defect', ['changed_review', 'wrong_hardware', 'different_trace'])
def test_runtime_joins_reject_substituted_evidence(runtime_fixture, defect):
    local, receipt, selected, campaign_ref, review, retained_refs, review_calls = runtime_fixture
    if defect == 'changed_review':
        review['source_review_ref'] = {'path':str(local.directory/'other-review.json'), 'sha256':local.register_json({'other':True})}
    elif defect == 'wrong_hardware':
        receipt['hardware_report_ref'] = local.register_json({'soc':'Ascend910_9392','cann_version':'other'})
    else:
        receipt['trace_ref'] = local.register_json({'summary':'passed'})
    with pytest.raises(ValueError):
        promotion._runtime(local, receipt, selected, campaign_ref, promotion.selected_runtime(),
                           retained_review_refs=retained_refs)


@pytest.mark.parametrize('version', [{}, {'version':'8.0.0'}])
def test_hardware_scope_requires_exact_cann_version(runtime_fixture, monkeypatch, version):
    local, receipt, selected, campaign_ref, _, retained_refs, review_calls = runtime_fixture
    original = promotion.read
    def changed(reader, ref):
        value = original(reader, ref)
        return dict(value,cann_version=version) if ref == receipt['hardware_report_ref'] else value
    # Isolate the version policy from separately tested immutable hash joins.
    monkeypatch.setattr(promotion, 'read', changed)
    with pytest.raises(ValueError, match='CANN 9.0.0'):
        promotion._runtime(local,receipt,selected,campaign_ref,promotion.selected_runtime(),
                           retained_review_refs=retained_refs)


@pytest.mark.parametrize('defect', ['mixed_wiki', 'mixed_sources', 'second_skill'])
def test_mixed_rule_promotion_rejects_before_component_replay(tmp_path, defect):
    local = LocalEvidence(tmp_path / 'records')
    receipt = dict.fromkeys(promotion.KEYS, None)
    receipt.update(schema_version=1,kind='teacher_task_rule_promotion',proposal_id='CPU',
        wiki_id=WIKI_ID,target_skill=TARGET,source_keys=SOURCE_KEYS,campaign_ref='CPU')
    if defect == 'mixed_wiki':receipt['wiki_id']='tile-amortization'
    elif defect == 'mixed_sources':receipt['source_keys']=[*SOURCE_KEYS, 'l1:sigmoid']
    else:receipt['target_skill']='skills/other/SKILL.md'
    with pytest.raises(ValueError, match='mixed-rule'):
        promotion.verify_task_rule_promotion(local,local.register_json(receipt),campaign_ref='CPU',trials={},
            trusted_before_inventory_ref='CPU',repo=REPO,release=promotion.selected_runtime())


@pytest.mark.parametrize('wiki_id', list(promotion.SCOPES))
def test_real_failed_trial_cannot_be_promoted(make_campaign, monkeypatch, wiki_id):
    fixture = make_campaign(('prebuild', 'prebuild'))
    local = fixture['top']
    receipt = dict.fromkeys(promotion.KEYS, None)
    receipt.update(schema_version=1,kind='teacher_task_rule_promotion',proposal_id='CPU',
        wiki_id=wiki_id,target_skill=promotion.SCOPES[wiki_id]['target_skill'],source_keys=promotion.SCOPES[wiki_id]['source_keys'],
        campaign_ref=fixture['ref'],selected_run_id='CPU-'+promotion.SCOPES[wiki_id]['operator'])
    # Isolate this join from the separately tested source/revision checks. The
    # finite campaign and both real dispatcher exits are verified without mocks.
    monkeypatch.setattr(promotion, '_skills', lambda *args: {})
    monkeypatch.setattr(promotion, '_sources', lambda *args: {})
    def forbidden(*args):
        raise AssertionError('failed attempt reached promotion runtime replay')
    monkeypatch.setattr(promotion, '_runtime', forbidden)
    with pytest.raises(ValueError, match='failed/not-run operator'):
        promotion.verify_task_rule_promotion(local,local.register_json(receipt),campaign_ref=fixture['ref'],
            trials=fixture['trials'],trusted_before_inventory_ref='CPU',repo=REPO,release=promotion.selected_runtime())


def test_promotion_requires_explicit_trusted_archive_refs(runtime_fixture):
    local, receipt, selected, campaign_ref, _, _, review_calls = runtime_fixture
    with pytest.raises(ValueError, match='trusted post-task'):
        promotion._runtime(local, receipt, selected, campaign_ref, promotion.selected_runtime(),
                           retained_review_refs=None)
    assert review_calls == []
