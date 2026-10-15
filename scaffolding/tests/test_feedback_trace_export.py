"""CPU-only recorder contract tests; no runtime, build, timing, or gate calls."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import feedback_trace_export as live
import trace_v2_dataset as v2


def save(path, value):
    path.write_text(json.dumps(value))
    return {'path': str(path)}


def fixture(tmp_path):
    baseline = tmp_path/'baseline.txt'; baseline.write_text('baseline')
    candidate = tmp_path/'candidate.txt'; candidate.write_text('candidate')
    patch = tmp_path/'patch.diff'; patch.write_text('-baseline\n+candidate\n')
    execution = save(tmp_path/'execution.json', {'status': 'failed', 'error': 'compiler error'})
    event = save(tmp_path/'event.json', {'timestamp': '2026-09-08T12:00:00Z', 'event_type': 'hypothesis', 'summary': 'Test fewer launches'})
    evaluation = dict(id='eval-1', session_id='session-1', baseline='original_baseline', relation='original_attempt',
                      stages=[{'name': 'build', 'record': execution}], measurement_quality='not_measured')
    attempt = dict(id='c1', operator='op', sources=dict(original_baseline={'path':str(baseline)}, direct_parent={'path':str(baseline)},
                   candidate={'path':str(candidate)}, patch={'path':str(patch)}, parent_attempt_id=None),
                   diagnosis={'symptoms':[{'statement':'Launch overhead suspected', 'basis':'prospective_agent_observation', 'evidence':[event]}],
                              'missing_evidence':['Timing not reached'], 'retrospective':False},
                   intervention={'statement':'Reduce launch count', 'basis':'prospective_agent_observation'},
                   evaluations=[evaluation], timeline=[{'record':event}])
    manifest = tmp_path/'recording.json'
    config = dict(run_id='live', task_id='op', attempts=[attempt], lessons=[], task_checkpoints=[])
    save(manifest, config)
    return manifest, config


def export(manifest, config):
    save(manifest, config)
    output = manifest.parent/'dataset/v2'
    return output, live.Recorder(manifest, output).export()


def test_failed_stage_is_not_runtime_verdict_and_snapshots_are_immutable(tmp_path):
    manifest, config = fixture(tmp_path)
    output, result = export(manifest, config)
    assert result['verification']['valid'] and not result['verification']['hardware_executed']
    body = v2.previous_records(output)['live/train/c1']['body']
    assert body['evaluations'][0]['stages'][0]['status'] == 'failed'
    assert body['machine_results'][0]['verdict'] == 'not_recorded'
    assert body['machine_results'][0]['first_failed_stage'] is None
    assert 'machine_results.eval-1' in body['provenance']['null_reasons']
    assert body['knowledge']['actual_reads'] == []
    assert body['diagnosis']['symptoms'][0]['basis'] == 'prospective_agent_observation'
    assert body['timeline'][0]['event_type'] == 'hypothesis'
    (tmp_path/'execution.json').write_text('changed working file')
    assert v2.verify(output, deep=True)['valid']


def test_idempotence_and_remeasurement_not_extra_attempt(tmp_path):
    manifest, config = fixture(tmp_path)
    first = copy.deepcopy(config['attempts'][0]['evaluations'][0])
    config['attempts'][0]['evaluations'].append(first)
    second = copy.deepcopy(first)
    second.update(id='eval-2', relation='measurement_continuation')
    second['stages'][0]['record'] = save(tmp_path/'rerun.json', {'status':'passed', 'error':None})
    config['attempts'][0]['evaluations'].append(second)
    output, result = export(manifest, config)
    assert result['optimization_attempts'] == 1
    assert result['measurement_continuations'] == 1
    before = (output/'current.json').read_bytes()
    assert export(manifest, config)[1] == result
    assert (output/'current.json').read_bytes() == before


@pytest.mark.parametrize('fault', ['selector', 'status', 'hash', 'reuse', 'same_source'])
def test_bad_input_cannot_replace_current(tmp_path, fault):
    manifest, config = fixture(tmp_path)
    output, _ = export(manifest, config)
    before = (output/'current.json').read_bytes()
    a = config['attempts'][0]; stage = a['evaluations'][0]['stages'][0]
    if fault == 'selector': stage['record']['selector'] = '/missing'
    if fault == 'status': stage['record']['selector'] = '/status'
    if fault == 'hash': stage['record']['sha256'] = 'sha256:'+'0'*64
    if fault == 'reuse':
        duplicate = copy.deepcopy(a['evaluations'][0]); duplicate['id']='renamed'
        a['evaluations'].append(duplicate)
    if fault == 'same_source': a['sources']['candidate'] = a['sources']['direct_parent']
    with pytest.raises((ValueError, KeyError)):
        export(manifest, config)
    assert (output/'current.json').read_bytes() == before


def test_zero_attempt_calibration_checkpoint_and_method_lesson(tmp_path):
    manifest, config = fixture(tmp_path)
    config['attempts'] = []
    evidence = {'path':str(tmp_path/'execution.json'), 'selector':'/status'}
    config['task_checkpoints'] = [{'status':'blocked', 'reason':'Calibration failed', 'evidence':[evidence]}]
    config['lessons'] = [dict(id='method', kind='measurement_method', title='Calibration needs a successful control',
                             intervention={'statement':'Hold candidate creation', 'basis':'retrospective_curator'}, evidence=[evidence],
                             diagnosis={'symptoms':[{'statement':'Execution failed'}], 'missing_evidence':['Valid baseline timing']})]
    output, result = export(manifest, config)
    assert result['optimization_attempts'] == 0 and result['lessons'] == 1
    rows = v2.previous_records(output)
    assert rows['method']['body']['memory_refs'] == []
    assert rows['method']['body']['retrospective'] is True
    current = v2.strict_loads((output/'current.json').read_bytes())
    meta = v2.strict_loads((output/'revisions'/current['revision']/'metadata.json').read_bytes())
    assert len(meta['task_checkpoint_refs']) == 1
    assert meta['exporter_hardware_executed'] is False
    assert 'hardware_executed' not in meta


def test_parent_and_original_baseline_comparisons_and_actual_machine_result(tmp_path):
    manifest, config = fixture(tmp_path)
    a = config['attempts'][0]
    b = copy.deepcopy(a); b['id']='c2'
    child = tmp_path/'child.txt'; child.write_text('child')
    b['sources'].update(direct_parent=a['sources']['candidate'], candidate={'path':str(child)}, parent_attempt_id='c1')
    b['evaluations'] = []
    for i, role in enumerate(('direct_parent', 'original_baseline')):
        ev = copy.deepcopy(a['evaluations'][0]); ev.update(id='child-'+role, baseline=role)
        ev['stages'][0]['record'] = save(tmp_path/(role+'.json'), {'status':'passed', 'error':None, 'request':i})
        ev['machine_result'] = save(tmp_path/(role+'-result.json'), dict(verdict='correctness_failed', first_failed_stage='correctness',
                                 graph_policy_eligible=False, episode_ref=None, metrics={'failed_cases':[2]}))
        b['evaluations'].append(ev)
    config['attempts'].append(b)
    output, result = export(manifest, config)
    assert result['optimization_attempts'] == 2
    body = v2.previous_records(output)['live/train/c2']['body']
    assert {e['comparison']['baseline'] for e in body['evaluations']} == {body['sources']['original_baseline'], body['sources']['direct_parent']}
    assert body['machine_results'][0]['verdict'] == 'correctness_failed'


def test_same_source_cannot_be_renamed_into_another_attempt(tmp_path):
    manifest, config = fixture(tmp_path)
    duplicate = copy.deepcopy(config['attempts'][0]); duplicate['id'] = 'renamed'
    config['attempts'].append(duplicate)
    with pytest.raises(ValueError, match='same candidate source'):
        export(manifest, config)


def test_true_graph_association_preserves_basis_without_route(tmp_path):
    manifest, config = fixture(tmp_path)
    basis = 'Retrospective association: the recorded launch overhead hypothesis concerns task parallelism; no route was executed.'
    config['lessons'] = [dict(id='association', kind='operator_optimization', title='Launch overhead hypothesis',
        intervention={'statement':'Reduce launch count', 'basis':'retrospective_curator'},
        source_attempt_ids=['c1'],
        graph_links=[dict(graph_version='v0001', node_id='anchor.ai_core_utilization', basis=basis)])]
    output, result = export(manifest, config)
    assert result['verification']['valid']
    body = v2.previous_records(output)['association']['body']
    assert body['graph_links'] == config['lessons'][0]['graph_links']
    assert body['retrospective'] is True
    before = (output/'current.json').read_bytes()
    for link in (
        dict(graph_version='v0001', node_id='nonexistent.feedback.node', basis=basis),
        dict(graph_version='v9999', node_id='anchor.ai_core_utilization', basis=basis),
        dict(graph_version='v0001', basis=basis),
        dict(graph_version='v0001', node_id='anchor.ai_core_utilization'),
        dict(graph_version='v0001', node_id='anchor.ai_core_utilization', basis=basis, probability=0.9),
    ):
        config['lessons'][0]['graph_links'] = [link]
        with pytest.raises(ValueError):
            export(manifest, config)
        assert (output/'current.json').read_bytes() == before


def test_tracewriter_payload_timeline_keeps_recorded_content_and_line_refs(tmp_path):
    manifest, config = fixture(tmp_path)
    events = [
        {'timestamp':'2026-09-08T12:00:00.123Z', 'event_type':'diagnosis',
         'payload':{'reason':'Too many launches', 'hypothesis':'Fuse reductions', 'operator':'norm',
                    'unrelated':'must not enter the concise field summary'}},
        {'timestamp':'2026-09-08T12:01:00Z', 'event_type':'observation', 'payload':{'details':'x'*500}},
    ]
    path = tmp_path/'trace_events.jsonl'
    path.write_bytes(b''.join(v2.canonical(e) for e in events))
    config['attempts'][0]['timeline'] = [{'record':{'path':str(path), 'selector':'line:'+str(i+1)}} for i in range(2)]
    output, _ = export(manifest, config)
    body = v2.previous_records(output)['live/train/c1']['body']
    timeline = body['timeline']
    for expected, actual in zip(events, timeline):
        assert actual['timestamp'] == expected['timestamp']
        assert actual['event_type'] == expected['event_type']
    assert v2.strict_loads(timeline[0]['summary']) == {k:events[0]['payload'][k] for k in ('reason','hypothesis','operator')}
    assert len(timeline[1]['summary']) == 320 and timeline[1]['summary'].endswith('…')
    current = v2.strict_loads((output/'current.json').read_bytes())
    index = v2.strict_loads((output/'revisions'/current['revision']/'evidence_index.json').read_bytes())
    assert [index[e['evidence_id']]['selector'] for e in timeline] == ['line:1','line:2']
    assert all(index[e['evidence_id']]['sha256'] == v2.digest_bytes(path.read_bytes()) for e in timeline)


def test_per_attempt_task_identity_separates_operators_and_keeps_default(tmp_path):
    manifest, config = fixture(tmp_path)
    config['task_id'] = 'campaign-default'
    first = config['attempts'][0]
    first.update(operator='norm', task_id='task-norm')
    second = copy.deepcopy(first)
    second.update(id='c2', operator='activation', task_id='task-activation')
    config['attempts'].append(second)
    output, _ = export(manifest, config)
    records = v2.previous_records(output)
    assert records['live/train/c1']['body']['identity']['task_id'] == 'task-norm'
    assert records['live/train/c2']['body']['identity']['task_id'] == 'task-activation'
    del second['task_id']
    output, _ = export(manifest, config)
    assert v2.previous_records(output)['live/train/c2']['body']['identity']['task_id'] == 'campaign-default'
