"""Planning output is required at admission, while initial routing stays open."""
from aprof_layout import skill_lib
from copy import deepcopy
from pathlib import Path
import json

import pytest

from aprof_runtime.contracts import Context, GateRequest, CandidateEpisode
from aprof_runtime.episodes import finalize_episodes
from profile_evidence_fixture import finalize_with_profile_fixture
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.gates import CandidateGate
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import canonical_json, content_hash, to_primitive
from aprof_runtime.planning import validate_planning_context, verify_profile_probe
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact
from test_planning import context_example, rebind, HASH
from test_runtime import request_dict, noop_request_dict

ROOT = Path(__file__).resolve().parents[2]
GRAPH, _ = load_snapshot(skill_lib() / 'skillgraph/versions/v0002')
CANDIDATE = 'sha256:' + 'b' * 64
OTHER = 'sha256:' + 'c' * 64


def complete_context(stage='execution', implementation=CANDIDATE):
    value = context_example()
    value['evidence']['optimization_stage'] = stage
    if stage == 'algorithm_parallel':
        value['evidence']['predicate_states'] = {'predicate.source.algorithm_parallel_plan_required': True}
    value['workload'].update(plan_basis_source_hash=HASH, implementation_source_hash=implementation)
    value['evidence']['dispatch_plan'].update(source_hash=implementation,
        plan_basis_source_hash=HASH, implementation_source_hash=implementation)
    rebind(value)
    return value


def request_for(value, candidate_hash=CANDIDATE, graph=GRAPH, noop=False):
    context = Context.from_dict(value)
    route = route_graph(graph, context)
    selected = next(x for x in route.candidates if x.edge_id == route.selected_edge_id)
    request = noop_request_dict('audit') if noop else request_dict('audit')
    draft = request['candidates'][0]
    draft.update(route=to_primitive(route), transformation_id=selected.target_id)
    draft['source_hashes'] = dict(baseline=value['workload'].get('source_hash', HASH), candidate=candidate_hash)
    if selected.target_id == 'transformation.select_parallel_algorithm':
        draft['parameters'] = {'plan_id': 'test-plan', 'group_id': 'generic'}
    return context, GateRequest.from_dict(request)


def unchecked_episode(value, candidate_hash=CANDIDATE, graph=GRAPH):
    """A correctly self-hashed old producer payload: no admission helper call."""
    context, request = request_for(value, candidate_hash, graph)
    outcome = CandidateGate().evaluate(request)[0]
    payload = to_primitive(dict(schema_version='1.0.0', episode_id='episode-audit', context=context,
        graph_snapshot=graph, graph_hash=content_hash(graph), behavior_policy_checkpoint=None,
        policy_checkpoint_hash=None, gate_request=request, draft=request.candidates[0],
        evidence=request.evidence[0], outcome=outcome, finalized_at='2026-10-06T00:00:00Z',
        runtime_build='synthetic-audit'))
    payload['episode_hash'] = content_hash(payload)
    return payload


@pytest.mark.parametrize('missing', ['parallel_plan', 'dispatch_plan', 'parallel_plan_ref', 'dispatch_plan_ref'])
def test_algorithm_initial_route_allows_planning_but_admission_requires_output(missing):
    value = complete_context('algorithm_parallel'); value['evidence'].pop(missing)
    context, request = request_for(value)
    assert request.candidates[0].transformation_id == 'transformation.select_parallel_algorithm'
    with pytest.raises(ContractError): finalize_episodes(context, request, graph=GRAPH)
    with pytest.raises(ContractError): CandidateEpisode.from_dict(unchecked_episode(value))


@pytest.mark.parametrize('stage', ['algorithm_parallel', 'execution'])
def test_explicit_dispatch_implementation_must_be_actual_candidate(stage):
    value = complete_context(stage)
    context, request = request_for(value, OTHER)
    with pytest.raises(ContractError, match='actual candidate source'): finalize_episodes(context, request, graph=GRAPH)
    with pytest.raises(ContractError, match='actual candidate source'): CandidateEpisode.from_dict(unchecked_episode(value, OTHER))


@pytest.mark.parametrize('stage', ['algorithm_parallel', 'execution'])
def test_complete_matching_bundle_finalizes_and_replays(stage):
    context, request = request_for(complete_context(stage))
    episode = finalize_with_profile_fixture(context, request, graph=GRAPH)[0]
    assert episode.outcome.eligible and episode.outcome.policy_update_eligible
    assert CandidateEpisode.from_dict(to_primitive(episode)) == episode


def test_initial_algorithm_route_survives_attachment_of_its_valid_output():
    completed = complete_context('algorithm_parallel')
    initial = deepcopy(completed)
    for name in ('parallel_plan', 'dispatch_plan', 'parallel_plan_ref', 'dispatch_plan_ref'):
        initial['evidence'].pop(name)
    _, request = request_for(initial)
    episode = finalize_episodes(Context.from_dict(completed), request, graph=GRAPH)[0]
    assert episode.draft.route == request.candidates[0].route
    assert CandidateEpisode.from_dict(to_primitive(episode)) == episode


@pytest.mark.parametrize('change', ['profile_ref', 'plan_hash', 'dispatch_hash', 'memory_unknown', 'memory_exceeded', 'capability_unknown', 'cross_architecture', 'operator', 'group'])
def test_algorithm_result_plan_checks_are_as_strict_as_execution(change):
    value = complete_context('algorithm_parallel'); evidence=value['evidence']
    if change=='profile_ref': evidence['parallel_plan']['architecture_profile_ref']=OTHER; evidence['parallel_plan_ref']=content_hash(evidence['parallel_plan']); evidence['dispatch_plan']['parallel_plan_ref']=evidence['parallel_plan_ref']; evidence['dispatch_plan_ref']=content_hash(evidence['dispatch_plan'])
    elif change=='plan_hash': evidence['parallel_plan']['plan_id']='tampered'
    elif change=='dispatch_hash': evidence['dispatch_plan']['dispatch_id']='tampered'
    elif change=='memory_unknown': evidence['architecture_profile']['memory_bytes']['UB']=None; rebind(value)
    elif change=='memory_exceeded': evidence['parallel_plan']['groups'][0]['memory_requirements']['UB']=999999; rebind(value)
    elif change=='capability_unknown': evidence['architecture_profile']['capabilities']['vector']['status']='unknown'; rebind(value)
    elif change=='cross_architecture': evidence['parallel_plan']['groups'][0]['required_capabilities']=['simt']; rebind(value)
    elif change=='operator': evidence['parallel_plan']['operator']='another'; rebind(value)
    elif change=='group': evidence['dispatch_plan']['entries'][0]['group_id']='absent'; rebind(value)
    context, request=request_for(value)
    # The algorithm may be reviewed but its invalid completed output is inadmissible.
    assert request.candidates[0].transformation_id=='transformation.select_parallel_algorithm'
    with pytest.raises(ContractError): finalize_episodes(context,request,graph=GRAPH)
    with pytest.raises(ContractError): CandidateEpisode.from_dict(unchecked_episode(value))


@pytest.mark.parametrize('bad', [True,False,1.0,-1,2**64,'1',None])
def test_context_key_requires_exact_uint64(bad):
    value=complete_context();value['workload']['tiling_key']=bad
    with pytest.raises(ContractError,match='uint64'): validate_planning_context(Context.from_dict(value),execution=True)
    route=route_graph(GRAPH,Context.from_dict(value))
    assert next(x for x in route.candidates if x.edge_id==route.selected_edge_id).target_id=='transformation.noop'


def test_legacy_v1_finalization_and_episode_replay_are_unchanged():
    graph,_=load_snapshot(skill_lib() / 'skillgraph/versions/v0001')
    value=context_example();value['evidence']={'predicate_states':{'predicate.profile.vector_granularity_low':True},'optimization_stage':'invalid'}
    value['workload']['tiling_key']=True
    context,request=request_for(value,OTHER,graph)
    episode=finalize_with_profile_fixture(context,request,graph=graph)[0]
    assert episode.outcome.eligible
    assert CandidateEpisode.from_dict(to_primitive(episode))==episode


def test_v2_noop_does_not_require_output_plan_or_architecture():
    value=context_example();value['evidence']={}
    context,request=request_for(value,HASH,noop=True)
    episode=finalize_episodes(context,request,graph=GRAPH)[0]
    assert episode.outcome.verdict.value=='verified_noop'
    assert CandidateEpisode.from_dict(to_primitive(episode))==episode


def cas_context(store,tmp_path,stage):
    """Complete synthetic CAS including a consistent raw probe (not real hardware)."""
    evidence=tmp_path/'synthetic-evidence';evidence.write_bytes(b'synthetic not actual source or measurement')
    digest=store.register_artifact(evidence)
    candidate=tmp_path/'candidate';candidate.write_bytes(b'synthetic candidate')
    candidate_hash=store.register_artifact(candidate)
    value=complete_context(stage,candidate_hash)
    # Substitute all old synthetic placeholder references with an existing object.
    value=json.loads(json.dumps(value).replace(HASH,digest))
    profile=value['evidence']['architecture_profile']
    raw=dict(probe_kind=profile['probe_kind'],device_id=profile['device_id'],soc_name=profile['soc_name'],
        platform={k:profile[k] for k in ('npu_arch','core_counts','memory_bytes')})
    profile['provenance']['raw_probe_ref']=register_json_artifact(store,raw)
    rebind(value)
    for name in ['architecture_profile','parallel_plan','dispatch_plan']:
        assert register_json_artifact(store,value['evidence'][name])==value['evidence'][name+'_ref']
    context,request=request_for(value,candidate_hash)
    body=to_primitive(request)
    for d in body['candidates']:
        d['producer_hashes']={'model':'unknown','prompt':digest,'agent':digest};d['patch_artifact_hash']=digest
    for e in body['evidence']:e['artifacts']={k:digest for k in e['artifacts']}
    return value,context,GateRequest.from_dict(body),digest,candidate_hash


@pytest.mark.parametrize('stage',['algorithm_parallel','execution'])
def test_matching_bundle_cas_admission_and_integrity(tmp_path,stage):
    with EpisodeStore(tmp_path/'episodes.sqlite') as store:
        value,context,request,_,_=cas_context(store,tmp_path,stage)
        episode=finalize_episodes(context,request,graph=GRAPH)[0]
        assert store.append(episode)==1
        store.verify_integrity()
        assert len(list(store.iter_payloads()))==1


def test_rehashed_profile_cannot_claim_capacity_absent_from_bound_raw_probe(tmp_path):
    with EpisodeStore(tmp_path/'episodes.sqlite') as store:
        value,_,request,_,_=cas_context(store,tmp_path,'execution')
        value['evidence']['architecture_profile']['memory_bytes']['UB']+=1;rebind(value)
        for name in ['architecture_profile','parallel_plan','dispatch_plan']:register_json_artifact(store,value['evidence'][name])
        context=Context.from_dict(value)
        body=to_primitive(request);route=route_graph(GRAPH,context)
        for d in body['candidates']:d['route']=to_primitive(route)
        episode=finalize_episodes(context,GateRequest.from_dict(body),graph=GRAPH)[0]
        with pytest.raises(StoreError,match='architecture probe verification'):store.append(episode)

@pytest.mark.parametrize('field,bad',[('plan_id','absent'),('group_id','absent'),('plan_id',None),('group_id',None)])
def test_algorithm_selection_parameters_name_the_admitted_output(field,bad):
    value=complete_context('algorithm_parallel');context,request=request_for(value)
    body=to_primitive(request)
    if bad is None:body['candidates'][0]['parameters'].pop(field)
    else:body['candidates'][0]['parameters'][field]=bad
    with pytest.raises(ContractError,match='output plan/group'):
        finalize_episodes(context,GateRequest.from_dict(body),graph=GRAPH)

@pytest.mark.parametrize('stage',['algorithm_parallel','execution'])
def test_every_transformation_in_the_other_phase_is_hard_masked(stage):
    value=complete_context(stage)
    value['evidence']['predicate_states']={p['id']:True for p in GRAPH['predicates']}
    route=route_graph(GRAPH,Context.from_dict(value));transforms={t['id']:t for t in GRAPH['transformations']}
    checked=0
    for candidate in route.candidates:
        t=transforms[candidate.target_id]
        if t['id']!='transformation.noop' and t['optimization_stage']!=stage:
            assert not candidate.allowed and candidate.probability==0
            assert 'optimization_stage_mismatch' in candidate.mask_reasons
            checked+=1
    assert checked

@pytest.mark.parametrize('family,soc,arch',[('910b','Ascend910B2',2201),('910c','Ascend910_9392',2201),('950','Ascend950PR_9599',3510)])
def test_reviewed_families_admit_vector_plan_only_with_bound_identity(family,soc,arch):
    value=complete_context();p=value['evidence']['architecture_profile']
    p.update(architecture_id=family,soc_name=soc,npu_arch=arch);rebind(value)
    context,request=request_for(value);episode=finalize_with_profile_fixture(context,request,graph=GRAPH)[0]
    assert episode.outcome.eligible
    assert CandidateEpisode.from_dict(to_primitive(episode))==episode

@pytest.mark.parametrize('family,soc,arch',[('910b','Ascend910B2',2201),('910c','Ascend910_9392',2201)])
def test_950_specialization_cannot_be_enabled_on_2201_even_with_evidence(family,soc,arch):
    value=complete_context();p=value['evidence']['architecture_profile']
    p.update(architecture_id=family,soc_name=soc,npu_arch=arch)
    p['capabilities']['simt']={'status':'supported','basis':'synthetic claim','evidence_refs':[HASH]}
    p['compiler']={'status':'verified','path':'/synthetic/compiler','version':'synthetic','evidence_refs':[HASH]}
    value['evidence']['parallel_plan']['groups'][0]['required_capabilities'].append('simt');rebind(value)
    route=route_graph(GRAPH,Context.from_dict(value))
    assert next(x for x in route.candidates if x.edge_id==route.selected_edge_id).target_id=='transformation.noop'
    with pytest.raises(ContractError,match='confirmed 950'):validate_planning_context(Context.from_dict(value),execution=True)

@pytest.mark.parametrize('status',['unknown','unsupported','missing'])
def test_unconfirmed_required_capability_is_not_a_specialization_permission(status):
    value=complete_context();profile=value['evidence']['architecture_profile']
    if status=='missing':profile['capabilities'].pop('vector')
    else:profile['capabilities']['vector']['status']=status
    rebind(value);route=route_graph(GRAPH,Context.from_dict(value))
    assert next(x for x in route.candidates if x.edge_id==route.selected_edge_id).target_id=='transformation.noop'
