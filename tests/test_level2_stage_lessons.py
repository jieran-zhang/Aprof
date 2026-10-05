"""Stage-aware fresh lessons retain actual v2 memory hashes; legacy replay stays intact."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import msprof_exploration_archive as archive
import trace_v2_dataset as v2
from test_msprof_exploration_archive import run, fresh_planning_run, stage, save, source, read_memory


def fresh(run, monkeypatch, stages=('execution',)):
    fresh_planning_run(run,monkeypatch)
    proposal=archive.load(run['candidate']/'proposal.json')
    proposal['optimization_stage']=stages[0]
    proposal['dispatch_selections'][0]['case_id']=1
    save(run['candidate']/'proposal.json',proposal)
    stage(run,name='first-build')
    if len(stages)>1:
        candidate=run['candidate'].with_name('exp002');candidate.mkdir()
        current=source(candidate/'source.tar',candidate/'op','second original candidate variant')
        write=candidate/'optimization.patch';write.write_text('second synthetic patch')
        item=deepcopy(run['item']);item.update(candidate_id='exp002',source_hash=current,
             patch_hash=archive.sha(write),stable_id='new-run/train/exp002')
        artifacts=item['artifacts']
        for kind in ('architecture_profile','parallel_plan','dispatch_plan'):
            value=archive.load(artifacts[kind]['path'])
            if kind=='parallel_plan':
                value['plan_id']+='-second'
            if kind=='dispatch_plan':
                value['source_hash']=value['implementation_source_hash']=current
                value['parallel_plan_ref']=second['parallel_plan_ref']
                value['entries'][0]['tiling_key']=2;value['entries'][0]['kernel_entry']='second_entry'
            path=save(candidate/'plans'/(kind+'.json'),value)
            artifacts[kind]={'path':str(path),'sha256':archive.sha(path)}
            if kind=='architecture_profile':second=deepcopy(proposal)
            second[kind+'_ref']=archive.content_hash(value)
        second.update(optimization_stage=stages[1],implementation_source_hash=current)
        second['dispatch_selections'][0].update(tiling_key=2,kernel_entry='second_entry',case_id=2)
        save(candidate/'proposal.json',second)
        run['state']['candidates']['exp002']=item
        stage({**run,'candidate':candidate,'candidate_id':'exp002'},name='second-build')
    return run


def lesson(run, **values):
    body=dict(id='stage-lesson',kind='operator_optimization',operator='maximum',title='Bound stage experience',
        source_attempt_ids=list(run['state']['candidates']),intervention={'statement':'Compare recorded interventions.','basis':'source'},
        evidence=[{'path':str(run['candidate']/'proposal.json')}])
    body.update(values)
    save(run['task']/'analysis/lessons.json',[body])
    return body


@pytest.mark.parametrize('optimization_stage',['algorithm_parallel','execution'])
def test_actual_stage_plan_and_key_context_is_inferred_from_real_memories(run,monkeypatch,optimization_stage):
    fresh(run,monkeypatch,(optimization_stage,optimization_stage));lesson(run)
    archive.archive_split(run['root'],'train')
    memories,base=read_memory(run['root']);body=v2.load_rows(base/'train/lessons.jsonl')[0]['body']
    attrs=body['intervention']['attributes']
    assert attrs['optimization_stage']==optimization_stage and len(attrs['planning_contexts'])==2
    assert {c['parallel_plan_ref'] for c in attrs['planning_contexts']}=={r['body']['intervention']['attributes']['parallel_plan_ref'] for r in memories}
    assert len({c['parallel_plan_ref'] for c in attrs['planning_contexts']})==2
    for context,memory in zip(attrs['planning_contexts'],memories):
        assert context['memory_id']==memory['id'] and context['memory_record_hash']==memory['record_hash']
        assert context['dispatch_selections']==memory['body']['intervention']['attributes']['dispatch_selections']
    assert {c['dispatch_selections'][0]['tiling_key'] for c in attrs['planning_contexts']}=={1,2}
    assert all(m['body']['machine_results'][0]['episode_ref'] is None for m in memories)
    assert archive.load(base/'metadata.json')['lesson_planning_contract']==v2.LESSON_PLANNING_CONTRACT
    assert archive.verify_split(run['root'],'train')['valid']


def test_mixed_algorithm_and_execution_memories_cannot_be_one_operator_lesson(run,monkeypatch):
    fresh(run,monkeypatch,('algorithm_parallel','execution'));lesson(run)
    with pytest.raises(ValueError,match='mixes algorithm_parallel and execution'):
        archive.archive_split(run['root'],'train')
    assert not (run['root']/'archive/train/v2/current.json').exists()


@pytest.mark.parametrize('location',['top','intervention','condition'])
def test_author_stage_claim_cannot_override_actual_memory(run,monkeypatch,location):
    fresh(run,monkeypatch)
    extra=({'optimization_stage':'algorithm_parallel'} if location=='top' else
           {'intervention':{'statement':'Wrong stage','optimization_stage':'algorithm_parallel'}} if location=='intervention' else
           {'effective_conditions':[{'statement':'Wrong condition stage','optimization_stage':'algorithm_parallel'}]})
    lesson(run,**extra)
    with pytest.raises(ValueError,match='stage|contradicts'):
        archive.archive_split(run['root'],'train')


@pytest.mark.parametrize('condition',[
    {'tiling_key':99}, {'tiling_key':1,'kernel_entry':'second_entry'},
    {'tiling_key':1,'case_ids':[2]}, {'parallel_plan_ref':'sha256:'+'f'*64},
    {'architecture_profile_ref':'sha256:'+'e'*64}, {'group_id':'not-declared'},
])
def test_plan_and_key_conditions_must_exist_together_in_genuine_memories(run,monkeypatch,condition):
    fresh(run,monkeypatch,('execution','execution'))
    lesson(run,effective_conditions=[{'statement':'Scoped observed condition',**condition}])
    with pytest.raises(ValueError,match='absent from its memories'):
        archive.archive_split(run['root'],'train')


def test_distinct_same_stage_plan_conditions_are_preserved(run,monkeypatch):
    fresh(run,monkeypatch,('execution','execution'))
    lesson(run,effective_conditions=[{'statement':'First observed group','tiling_key':1,'kernel_entry':'small_entry','case_ids':[1]}],
        ineffective_conditions=[{'statement':'Second observed group','tiling_key':2,'kernel_entry':'second_entry','case_ids':[2]}])
    assert archive.archive_split(run['root'],'train')['verification']['valid']


def test_cross_stage_transformation_association_is_rejected(run,monkeypatch):
    fresh(run,monkeypatch)
    lesson(run,graph_links=[{'graph_version':'v0002','node_id':'transformation.select_parallel_algorithm','basis':'Retrospective'}])
    with pytest.raises(ValueError,match='different optimization stage'):
        archive.archive_split(run['root'],'train')


def test_generic_verifier_rechecks_derived_bindings_after_resealing(run,monkeypatch):
    fresh(run,monkeypatch);lesson(run)
    archive.archive_split(run['root'],'train')
    memories,base=read_memory(run['root']);dataset=base.parent.parent
    body=v2.load_rows(base/'train/lessons.jsonl')[0]['body']
    body['intervention']['attributes']['optimization_stage']='algorithm_parallel'
    evidence=v2.Evidence();evidence.entries=archive.load(base/'evidence_index.json');evidence.contexts=archive.load(base/'contexts.json')
    before=(dataset/'current.json').read_bytes()
    with pytest.raises(ValueError,match='differ from real memories'):
        v2.publish(dataset,{m['id']:m['body'] for m in memories},lambda _: {'stage-lesson':body},evidence,archive.load(base/'metadata.json'))
    assert (dataset/'current.json').read_bytes()==before


def test_new_stage_binding_survives_portable_offline_replay(run,monkeypatch,tmp_path):
    import trace_v2_portable as portable
    fresh(run,monkeypatch);lesson(run)
    archive.archive_split(run['root'],'train')
    destination=tmp_path/'portable'
    portable.export(run['root']/'archive/train/v2',destination)
    run['root'].rename(tmp_path/'original-location-unavailable')
    assert portable.verify(destination)['valid']


def test_fresh_stage_mapping_cannot_bypass_scoping_via_legacy_graph_link(run,monkeypatch):
    fresh(run,monkeypatch)
    lesson(run,graph_links=[{'graph_version':'v0001','node_id':'transformation.decompose_tasks_dynamically','basis':'Retrospective'}])
    with pytest.raises(ValueError,match='requires bound v0002'):
        archive.archive_split(run['root'],'train')


@pytest.mark.parametrize('scoped_fields',[
    {'source_split':'validation'},
    {'dispatch_selections':[{'case_id':1,'tiling_key':999,'kernel_entry':'not-real','group_id':'generic'}]},
    {'planning_contexts':[{'memory_id':'fake','source_split':'validation'}]},
])
def test_direct_planning_fields_cannot_claim_fabricated_memory_scope(run,monkeypatch,scoped_fields):
    fresh(run,monkeypatch)
    lesson(run,effective_conditions=[{'statement':'False direct scope',**scoped_fields}])
    with pytest.raises(ValueError,match='absent from its memories'):
        archive.archive_split(run['root'],'train')


@pytest.mark.parametrize('scope',[
    {'case_ids':['999']}, {'case_ids':'999'}, {'cases':[True]}, {'case_ids':[1.0]},
    {'cases':None}, {'case_ids':[-1]}, {'case_ids':[1],'cases':[2]},
])
def test_malformed_direct_case_scope_is_never_erased_to_unscoped(run,monkeypatch,scope):
    fresh(run,monkeypatch)
    lesson(run,effective_conditions=[{'statement':'Must not become unscoped',**scope}])
    with pytest.raises(ValueError,match='case scope|scopes contradict'):
        archive.archive_split(run['root'],'train')


def test_full_context_subset_and_dispatch_rows_require_one_actual_memory(tmp_path):
    from test_trace_v2_dataset import fixture_data
    evidence,base=fixture_data(tmp_path)
    def memory(identifier,key):
        body=deepcopy(base);body['identity']['candidate_id']=identifier
        body['intervention']['attributes']={'optimization_stage':'execution',
            **{field:'sha256:'+str(key)*64 for field in v2.LESSON_PLANNING_FIELDS
               if field not in ('dispatch_selections','source_split','implementation_source_hash')},
            'implementation_source_hash':body['sources']['candidate'],'source_split':'test',
            'dispatch_selections':[{'case_id':key,'tiling_key':key,'kernel_entry':'entry'+str(key),'group_id':'generic'}]}
        return v2.seal('optimization_memory',identifier,body)
    memories={r['id']:r for r in (memory('one',1),memory('two',2))}
    item={'kind':'operator_optimization','operator':'op','split':'train',
          'memory_refs':[{'id':r['id'],'record_hash':r['record_hash']} for r in memories.values()]}
    binding=v2.lesson_planning_bindings(item,memories)
    body={**item,'intervention':v2.fact('i',{'statement':'Compare actual memory scope',**binding}),
          'diagnosis':{'symptoms':[],'hypotheses':[]},'effective_conditions':[],
          'ineffective_conditions':[],'counterexamples':[],'claims':[]}
    context=binding['planning_contexts'][0]
    scoped={'statement':'First actual context subset','source_split':'test','planning_contexts':[context],
            'dispatch_selections':context['dispatch_selections'],'tiling_key':1,'case_ids':[1]}
    body['effective_conditions']=[v2.fact('condition',scoped)]
    v2.verify_lesson_planning(body,memories)
    body['effective_conditions'][0]['attributes']['dispatch_selections']=binding['planning_contexts'][1]['dispatch_selections']
    with pytest.raises(ValueError,match='absent from its memories'):
        v2.verify_lesson_planning(body,memories)


def test_false_numeric_alias_cannot_forge_canonical_planning_context(tmp_path):
    from test_trace_v2_dataset import fixture_data
    evidence,memory=fixture_data(tmp_path)
    memory['intervention']['attributes']={'optimization_stage':'execution',
        **{key:'sha256:'+'a'*64 for key in v2.LESSON_PLANNING_FIELDS if key not in ('dispatch_selections','source_split','implementation_source_hash')},
        'implementation_source_hash':memory['sources']['candidate'],'source_split':'test',
        'dispatch_selections':[{'case_id':1,'tiling_key':1,'kernel_entry':'one','group_id':'g'},
                               {'case_id':2,'tiling_key':2,'kernel_entry':'two','group_id':'g'}]}
    sealed=v2.seal('optimization_memory','one',memory);memories={'one':sealed}
    body={'kind':'operator_optimization','operator':'op','split':'train',
          'memory_refs':[{'id':'one','record_hash':sealed['record_hash']}],
          'diagnosis':{'symptoms':[],'hypotheses':[]},'effective_conditions':[],
          'ineffective_conditions':[],'counterexamples':[],'claims':[]}
    binding=v2.lesson_planning_bindings(body,memories)
    body['intervention']=v2.fact('i',{'statement':'Actual',**binding})
    altered=deepcopy(body);altered['intervention']['attributes']['planning_contexts'][0]['dispatch_selections'][0]['tiling_key']=True
    with pytest.raises(ValueError,match='differ from real memories'):
        v2.verify_lesson_planning(altered,memories)
    first=binding['planning_contexts'][0]['dispatch_selections'][0]
    scoped={'statement':'Contradictory selected row','dispatch_selections':[first],'tiling_key':2}
    body['effective_conditions']=[v2.fact('c',scoped)]
    with pytest.raises(ValueError,match='key/entry/case is absent'):
        v2.verify_lesson_planning(body,memories)
    scoped['tiling_key']=1;scoped['dispatch_selections'][0]['case_id']=True
    body['effective_conditions']=[v2.fact('c',scoped)]
    with pytest.raises(ValueError,match='absent from its memories'):
        v2.verify_lesson_planning(body,memories)
