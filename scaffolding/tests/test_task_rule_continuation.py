"""Continuation control on CPU: capture/normalization doubles, real oracle exits."""
import json
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
from timing_admission import read
import local_controller_bridge as bridge
import task_rule_continuation as continuation
import task_rule_continuation_admission as admission


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def make(*, oracle_code=0, stdout='normal', capture_error=False, capture_expires=False, gate='pass'):
        output=tmp_path/'continuation';output.mkdir()
        parent=tmp_path/'parent';parent.mkdir();old=parent/'retained-output.bin';old.write_bytes(b'old evidence')
        local=LocalEvidence(parent/'records')
        def put(value):return local.register_json(value)
        binary=parent/'exp';binary.write_text('CPU binary placeholder')
        binary_ref=local.register_artifact(binary)
        sources={role:put({'CPU_source':role}) for role in ('baseline','candidate')}
        script=('import argparse,json,sys; from pathlib import Path; '
            'p=argparse.ArgumentParser();p.add_argument("--output");p.add_argument("--result");a=p.parse_args();'
            'assert Path(a.output).read_bytes()==b"candidate output";'
            'v={"case_id":3,"passed":True};Path(a.result).write_text(json.dumps(v));'
            'print(json.dumps(v)' + ('' if stdout=='normal' else '+"\\n{}"') + ');'
            'print("CPU oracle diagnostic",file=sys.stderr);sys.exit('+str(oracle_code)+')')
        case=dict(case_id=3,command=['CPU-capture-only','--baseline-output','{cycle_dir}/baseline.bin',
            '--candidate-output','{cycle_dir}/candidate.bin'],
            output_files={role:['{cycle_dir}/'+role+'.bin'] for role in ('baseline','candidate')},
            verify_commands={'candidate':[str(Path(sys.executable).resolve()),'-c',script,
                '--output','{cycle_dir}/candidate.bin','--result','{cycle_dir}/oracle-result.json']})
        task_config_ref=put({'cases':[case]})
        original=dict(role='candidate',warmups=10,repeats=5,case_id=3,cwd=str(parent),binary=str(binary))
        original_ref=put(original)
        protocol_ref=put({'profile_configs':{'candidate':original_ref}})
        registration_ref=put({'identity':{'build':{'binary_ref':binary_ref}}})
        prefix=dict(valid=True,parent_status='failed',eligible_for_publication=False,
            checks={'task':{'config_ref':task_config_ref,'registration_ref':registration_ref}},
            protocol_ref=protocol_ref,measurement_expected={'source_hashes':sources})
        prefix_ref=put(prefix)
        expand=lambda values:[x.replace('{cycle_dir}',str(output)) for x in values]
        config=dict(original,command=expand(case['command'])+['--aprof-mechanism-role','candidate'])
        frozen={str(path):ref for ref,path in local._paths.items()}
        clock=SimpleNamespace(now=100.0)
        monkeypatch.setattr(continuation,'time',SimpleNamespace(time=lambda:1000+clock.now,
                                                              monotonic=lambda:clock.now))
        plan=dict(kind='exp_pmu_continuation_v1',directory=str(output),new_roles=['candidate'],
            actual_new_builds=0,new_formal_timing_pairs=0,runner_ref=file_hash(Path(continuation.__file__)),
            created_at=1080,parent_duration_seconds=100,total_budget_seconds=5400,
            additional_budget_seconds=5300,object_roots=[],frozen_files=frozen,prefix_replay_ref=prefix_ref,
            parent_anchor_ref=put({'CPU':'original anchor'}),
            trusted_review_refs={key:put({'CPU':key}) for key in ('archive_inventory_ref','producer_snapshot_ref')},
            candidate_profile_config=config,source_hashes=sources,binary_ref=binary_ref,
            output_files=expand(case['output_files']['candidate']),
            oracle_command=expand(case['verify_commands']['candidate']),specs={})
        plan_path=output/'plan.json'
        def freeze():
            plan_path.write_text(json.dumps(plan))
            (output/'launch.json').write_text(json.dumps(dict(plan_ref=file_hash(plan_path),started_at=1090,
                started_monotonic=90,deadline_monotonic=5390)))
        freeze();calls=[]
        def capture(config,destination):
            calls.append(('capture',config,str(destination)))
            destination.mkdir();captured=LocalEvidence(destination/'records')
            raw=destination/'raw.txt';raw.write_text('CPU capture double, not PMU evidence')
            captured.register_artifact(raw)
            Path(plan['output_files'][0]).write_bytes(b'candidate output')
            manifest_ref=captured.register_json(dict(collector_hash=continuation.ORIGINAL_COLLECTOR,
                binary_hash=binary_ref,source_hash=sources['candidate']))
            index=captured.write_index(destination/'local-index.json')
            clock.now=5391 if capture_expires else clock.now+1
            if capture_error:raise RuntimeError('CPU capture failed with retained partial')
            return dict(local_index=str(index),manifest_hash=manifest_ref)
        def run_oracle(*args,**kwargs):
            calls.append(('oracle',args[0]));clock.now+=1
            return bridge.profile_capture.run(*args,**kwargs)
        monkeypatch.setattr(continuation,'original_collector',lambda reader:SimpleNamespace(capture=capture,run=run_oracle))
        monkeypatch.setattr(continuation,'load_capture_manifest',read)
        monkeypatch.setattr(continuation,'expand_specs',lambda manifest,specs:specs)
        monkeypatch.setattr(continuation,'normalize_profile',lambda *args:{'CPU_normalization_double':True})
        def finalize(reader,registered,old_prefix,profile):
            calls.append(('gate',registered['plan_ref']))
            assert registered['plan_ref']==file_hash(plan_path) and old_prefix==prefix
            assert profile=={'CPU_normalization_double':True}
            if gate=='throw':raise ValueError('CPU gate rejection')
            if gate=='late':clock.now=5391
            return {'formal_outcome':'no_gain' if gate=='no_gain' else 'production_safe_gain'}
        monkeypatch.setattr(continuation,'finalize_gate',finalize)
        monkeypatch.setattr(admission,'retained_producer_scope',lambda *args,**kwargs:nullcontext())
        return SimpleNamespace(**locals())
    return make


def test_real_oracle_stdout_excludes_stderr_and_cost_keeps_parent_separate(setup):
    f=setup();result=continuation.run(f.plan_path)
    assert result['status']=='passed' and result['parent_status']=='failed'
    assert result['actual_new_builds']==result['new_formal_timing_pairs']==0 and not result['archive_performed']
    assert result['duration_seconds']==2 and result['cumulative_online_seconds']==112
    assert f.old.read_bytes()==b'old evidence'
    local=LocalEvidence.from_index(f.output/'local-index.json')
    oracle=read(local,result['candidate_oracle_ref'])
    assert oracle['exit_code']==0
    assert local.verify_artifact(oracle['stderr_hash']).read_text()=='CPU oracle diagnostic\n'
    assert json.loads(local.verify_artifact(oracle['stdout_hash']).read_text())=={'case_id':3,'passed':True}


@pytest.mark.parametrize('field,value',[
    ('runner_ref','sha256:'+'0'*64),('new_roles',['baseline','candidate']),
    ('actual_new_builds',1),('new_formal_timing_pairs',30),
    ('parent_duration_seconds',5400),('parent_duration_seconds',float('nan')),
])
def test_bad_registered_runner_scope_or_budget_never_captures(setup,field,value):
    f=setup();f.plan[field]=value;f.freeze()
    with pytest.raises(ValueError):continuation.run(f.plan_path)
    assert not f.calls and f.old.read_bytes()==b'old evidence'


@pytest.mark.parametrize('defect',['source','binary','command','oracle_path','output_path',
                                  'existing_output','existing_baseline','existing_oracle'])
def test_original_identity_and_fresh_output_routing_are_checked_before_capture(setup,defect):
    f=setup()
    if defect=='source':f.plan['source_hashes']=dict(f.sources,candidate='sha256:'+'0'*64)
    elif defect=='binary':f.plan['binary_ref']='sha256:'+'0'*64
    elif defect=='command':f.plan['candidate_profile_config']['command'][0]='another-program'
    elif defect=='oracle_path':f.plan['oracle_command'][-1]=str(f.old)
    elif defect=='output_path':f.plan['output_files']=[str(f.old)]
    elif defect=='existing_baseline':(f.output/'baseline.bin').write_bytes(b'existing baseline')
    elif defect=='existing_oracle':Path(f.plan['oracle_command'][-1]).write_bytes(b'existing oracle')
    else:Path(f.plan['output_files'][0]).write_bytes(b'existing output')
    f.freeze();result=continuation.run(f.plan_path)
    assert result['status']=='failed' and result['error'] and not f.calls
    assert f.old.read_bytes()==b'old evidence'


def test_noncanonical_plan_directory_cannot_write_a_terminal(setup):
    f=setup();f.plan['directory']=str(f.parent);f.freeze()
    with pytest.raises(ValueError,match='fresh canonical'):continuation.run(f.plan_path)
    assert not f.calls and not (f.parent/'result.json').exists()


@pytest.mark.parametrize('options',[dict(oracle_code=2),dict(stdout='extra'),dict(capture_error=True)])
def test_actual_oracle_failure_or_partial_capture_stays_failed(setup,options):
    f=setup(**options);result=continuation.run(f.plan_path)
    assert result['status']=='failed' and result['parent_status']=='failed' and result['error']
    assert 'candidate_profile_ref' not in result and (f.output/'local-index.json').is_file()
    assert f.old.read_bytes()==b'old evidence'
    if options.get('oracle_code'):
        oracle=json.loads((f.output/'candidate-oracle.execution.json').read_text())
        assert oracle['exit_code']==2
    if options.get('capture_error'):
        index=json.loads((f.output/'local-index.json').read_text())
        assert str(f.output/'candidate/raw.txt') in index['artifacts'].values()


@pytest.mark.parametrize('phase',['before_capture','before_oracle'])
def test_exhausted_absolute_budget_starts_no_new_work(setup,phase):
    f=setup(capture_expires=phase=='before_oracle')
    if phase=='before_capture':f.clock.now=5391
    result=continuation.run(f.plan_path)
    assert result['status']=='failed'
    assert [call[0] for call in f.calls]==([] if phase=='before_capture' else ['capture'])


@pytest.mark.parametrize('gate',['throw','no_gain','late'])
def test_final_gate_rejection_or_overrun_cannot_become_passed(setup,gate):
    f=setup(gate=gate);result=continuation.run(f.plan_path)
    assert result['status']=='failed' and result['parent_status']=='failed' and result['error']
    assert [call[0] for call in f.calls]==['capture','oracle','gate']
    assert (f.output/'local-index.json').is_file() and f.old.read_bytes()==b'old evidence'


def test_only_the_exact_old_collector_digest_can_be_loaded(tmp_path):
    assert continuation.ORIGINAL_COLLECTOR=='sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc'
    objects=tmp_path/'objects';digest=continuation.ORIGINAL_COLLECTOR[7:]
    path=objects/digest[:2]/digest[2:];path.parent.mkdir(parents=True)
    marker=tmp_path/'must-not-execute'
    path.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
    reader=continuation.Evidence(LocalEvidence(tmp_path/'records'),[objects])
    with pytest.raises(ValueError,match='retained evidence changed'):continuation.original_collector(reader)
    assert not marker.exists()
