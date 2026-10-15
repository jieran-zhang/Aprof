"""CPU join tests with tiny evidence; heavy leaf doubles confer no qualification."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aprof_runtime import profile_evidence, traces
from aprof_runtime.local_evidence import LocalEvidence
import task_rule_continuation_admission as admission
import task_rule_promotion as promotion


@pytest.fixture
def continued(tmp_path, monkeypatch):
    def make(defect=None):
        local = LocalEvidence(tmp_path/'records')
        put = local.register_json
        root, old_root = tmp_path/'new-exp', tmp_path/'failed-exp'
        release = admission.selected_runtime(); repo = release.parents[2]
        def artifact(name, data):
            path = tmp_path/name
            path.write_bytes(data)
            return local.register_artifact(path)
        def pointer(ref):
            return dict(path=str(local.verify_artifact(ref)), sha256=ref)
        def timestamp(value):
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        stdout_ref = artifact('stdout.txt', b'{}\n')
        stderr_ref = artifact('stderr.txt', b'CPU-only diagnostic\n')
        sources = {role: put({'CPU source': role}) for role in admission.ROLES}
        binary_ref = artifact('original-binary.txt', b'CPU fixture: never executable\n')
        expected = dict(operator='exp', run_id='original-exp', candidate_id='candidate',
                        session_id='session', source_hashes=sources,
                        measurement_report_ref=put({'CPU': 'original measurement report'}))
        candidate = dict(candidate_id='candidate', source_hashes=sources)
        frozen_ref = put(dict(candidate=candidate, frozen_manifest_hash=put({'CPU': 'frozen manifest'})))
        campaign_ref = put({'CPU': 'failed original campaign'})
        amendment_ref = put(dict(schema_version=1, kind='teacher_exp_only_scope_amendment',
            authorization='user_requested_exp_only_release_on_success', release_id='graph-base/1.0.0',
            target=dict(device='910C', architecture='A3', cann_version='9.0.0'), operators=['exp'],
            validation_45='not_run', postseal_full_tests='not_run', other_rules='draft', created_at=900))
        choice = dict(case_id=3, metric='vector_busy', expected_direction='decrease')
        specs = {'vector_busy': {'unit': 'percent'}}
        choice_ref = put(dict(choice=choice, specs=specs))
        old_plan_ref = put({'directory': str(old_root)})
        anchor_ref = put(dict(controller_plan_ref=old_plan_ref, profile_plan_ref=choice_ref))
        archive_ref = put({'files': {str(old_root/'frozen-candidate.json'): {'sha256': frozen_ref}}})
        trusted = dict(archive_inventory_ref=archive_ref, producer_snapshot_ref=put({'CPU': 'snapshot'}))
        case = dict(case_id=3, command=['original-binary', '--output', '{cycle_dir}'],
            verify_commands={role: ['original-oracle', '--role', role, '--output', '{cycle_dir}/'+role+'.bin']
                             for role in admission.ROLES},
            output_files={role: ['{cycle_dir}/'+role+'.bin'] for role in admission.ROLES},
            workload=dict(case_id=3, numel=1, dtype='float16'))
        config_ref = put(dict(cases=[case], build=dict(source_dir=str(old_root/'source'), binary='original-binary')))
        registration_ref = put({'identity': {'build': {'binary_ref': binary_ref}}})
        original_configs = {role: dict(role=role, case_id=3, command=['old', role]) for role in admission.ROLES}
        profile_config_refs = {role: put(value) for role, value in original_configs.items()}
        protocol_ref = put({'profile_configs': profile_config_refs})
        original_report = {key: put({'CPU': key}) for key in
                           ('correctness_report_ref', 'boundary_report_ref', 'measurement_admission_ref')}
        original_report_ref = put(original_report)
        prefix = dict(parent_status='failed', anchor_ref=anchor_ref, original_duration_seconds=100,
            original_profile_window=[10, 90], checks={'task': {'config_ref': config_ref, 'registration_ref': registration_ref}},
            measurement_expected=expected, protocol_ref=protocol_ref, report_ref=original_report_ref,
            source_review_ref=pointer(put({'CPU': 'accepted original review'})),
            build_receipt_ref=put({'CPU': 'single original build'}),
            qualification_registration_ref=put({'CPU': 'original registration'}))
        hardware_ref = put(dict(soc='Ascend910C', cann_version={'version': '9.0.0'}))
        manifests, profiles, oracle_refs, output_hashes = {}, {}, {}, {}
        for role, lower in [('baseline', 10), ('candidate', 1002)]:
            def execution(start, argv):
                return dict(argv=argv, exit_code=0, error=None, started_at=start, ended_at=start+0.1,
                            stdout_hash=stdout_ref, stderr_hash=stderr_ref)
            warmups = []
            for i in range(10):
                start = lower+i+1
                if defect == role+'_capture_window' and i == 0:
                    start = 1003 if role == 'baseline' else 11
                record = execution(start, ['warmup', role])
                warmups.append(dict(argv=record['argv'], exit_code=0, log_hash=put(record)))
            captures = []
            for i in range(5):
                capture = execution(lower+20+i, ['capture', role])
                imported = execution(lower+20+i+0.2, ['import', role])
                receipt = {name: dict(value, log_hash=put(value)) for name, value in
                           [('capture', capture), ('import', imported)]}
                captures.append(dict(capture_id=f'capture-{i:03d}', argv=capture['argv'],
                                     exit_code=0, log_hash=put(receipt)))
            if defect == role+'_extra_pmu': captures.append(copy.deepcopy(captures[-1]))
            manifest = dict(role=role, collector_hash=
                'sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc',
                hardware_hash=hardware_ref, policy=dict(warmups=10, repeats=5),
                warmup_runs=warmups, captures=captures)
            manifests[role] = put(manifest)
            profiles[role] = put(dict(capture_manifest_hash=manifests[role],
                metrics={'vector_busy': {'value': 80 if role == 'baseline' else 60}}))
            result = dict(passed=not (defect == role+'_oracle_failed'), case_id=3)
            result_ref = put(result)
            stdout = json.dumps(result)+'\n'
            if defect == role+'_oracle_stdout': stdout = '{"passed": false, "case_id": 3}\n'
            if defect == role+'_oracle_extra_stdout': stdout += 'diagnostic on stdout\n'
            oracle_stdout = artifact(role+'-oracle-stdout.txt', stdout.encode())
            directory = old_root/'mechanism' if role == 'baseline' else root
            command = [value.replace('{cycle_dir}', str(directory)) for value in case['verify_commands'][role]]
            oracle = dict(argv=command, cwd=str(old_root/'source'), environment={}, exit_code=0,
                error=None, started_at=lower+30, ended_at=lower+31, timeout_seconds=10,
                stdout_hash=oracle_stdout, stderr_hash=stderr_ref)
            if defect == role+'_oracle_window': oracle.update(started_at=lower+90, ended_at=lower+91)
            oracle_refs[role] = (put(oracle), result_ref)
            output_ref = artifact(role+'-output.bin', b'\x00' if defect == role+'_output_short' else b'\x00\x00')
            output_hashes[role] = {str(directory/(role+'.bin')): output_ref}
        old_artifacts = {ref: str(local.verify_artifact(ref)) for ref in
                         (manifests['baseline'], *oracle_refs['baseline'], *output_hashes['baseline'].values())}
        trials = {'exp': {'index_ref': put({'artifacts': old_artifacts})},
                  'sigmoid': {'not_run_ref': put({'CPU': 'sigmoid not run'})}}
        candidate_config = dict(original_configs['candidate'], command=
            [value.replace('{cycle_dir}', str(root)) for value in case['command']]+['--aprof-mechanism-role', 'candidate'])
        runner = repo/'scaffolding/collection/scripts/task_rule_continuation.py'
        runner_ref = local.register_artifact(runner)
        plan = dict(kind='exp_pmu_continuation_v1', created_at=950, campaign_ref=campaign_ref,
            amendment_ref=amendment_ref, trusted_review_refs=trusted, new_roles=['candidate'],
            actual_new_builds=0, new_formal_timing_pairs=0, parent_anchor_ref=anchor_ref,
            prefix_replay_ref=put(prefix), directory=str(root), parent_duration_seconds=100,
            total_budget_seconds=5400, additional_budget_seconds=5300,
            frozen_files={str(runner): runner_ref}, runner_ref=runner_ref,
            frozen_candidate_ref=frozen_ref, choice=copy.deepcopy(choice), specs=specs,
            source_hashes=sources, binary_ref=binary_ref, candidate_profile_config=copy.deepcopy(candidate_config),
            baseline_manifest_ref=manifests['baseline'], baseline_oracle_ref=oracle_refs['baseline'][0],
            baseline_oracle_result_ref=oracle_refs['baseline'][1], baseline_output_hashes=output_hashes['baseline'])
        if defect == 'plan_new_build': plan['actual_new_builds'] = 1
        if defect == 'plan_extra_role': plan['new_roles'].append('baseline')
        if defect == 'budget_total': plan['total_budget_seconds'] = 5401
        if defect == 'budget_renewed': plan['additional_budget_seconds'] = 5400
        if defect == 'changed_choice': plan['choice']['case_id'] = 4
        if defect == 'changed_config': plan['candidate_profile_config']['command'][0] = 'other-binary'
        if defect == 'plan_source': plan['source_hashes'] = dict(sources, candidate=stdout_ref)
        if defect == 'plan_binary': plan['binary_ref'] = stdout_ref
        plan_ref = put(plan)
        launch = dict(schema_version=1, plan_ref=plan_ref, started_at=1000,
                      started_monotonic=200, deadline_monotonic=5500)
        if defect == 'launch_deadline': launch['deadline_monotonic'] += 1
        launch_ref = put(launch)
        job = dict(argv=['python', str(runner), '--plan', str(root/'plan.json')], cwd=str(repo),
            output_dir=str(root/'job'), physical_device=0, timeout_seconds=5300,
            deadline_monotonic=launch['deadline_monotonic'], environment=dict(APROF_SKILL_LIB=str(release),
                ASCEND_RT_VISIBLE_DEVICES='0', PYTHONDONTWRITEBYTECODE='1'))
        job_ref = put(job)
        execution_record = dict(kind='aprof_execution_report', schema_version='1.0.0', job=job,
            status='passed', exit_code=0, error=None, started_at=timestamp(1001), finished_at=timestamp(1100),
            duration_seconds=99, stdout=pointer(stdout_ref), stderr=pointer(stderr_ref))
        if defect == 'execution_failed': execution_record.update(status='failed', exit_code=2)
        if defect == 'execution_late': execution_record['finished_at'] = timestamp(6301)
        execution_ref = put(execution_record)
        mechanism_ref = put(dict(schema_version='1.0.0', candidate_id='candidate', hypothesis_basis='heuristic',
            metrics=[dict(name='vector_busy', unit='percent', expected_direction='decrease', baseline=80,
                candidate=60, baseline_profile_hash=profiles['baseline'], candidate_profile_hash=profiles['candidate'])]))
        bindings = dict(source_review=prefix['source_review_ref']['sha256'], build_log=prefix['build_receipt_ref'],
            accuracy_report=original_report['correctness_report_ref'], boundary_report=original_report['boundary_report_ref'],
            measurement_admission=original_report['measurement_admission_ref'], measurement_report=expected['measurement_report_ref'],
            mechanism_report=mechanism_ref, hardware_report=hardware_ref, qualification_campaign=campaign_ref,
            qualification_registration=prefix['qualification_registration_ref'], continuation_plan=plan_ref,
            continuation_amendment=amendment_ref)
        if defect == 'machine_binding': bindings['build_log'] = stdout_ref
        gate_candidate = copy.deepcopy(candidate)
        if defect == 'machine_source': gate_candidate['source_hashes']['candidate'] = stdout_ref
        request = dict(candidates=[gate_candidate], evidence=[dict(candidate_id='candidate', artifacts=bindings)],
                       config={}, frozen_manifest_hash=admission.read(local, frozen_ref)['frozen_manifest_hash'])
        if defect == 'machine_second_candidate': request['candidates'].append(candidate)
        request_ref = put(request)
        outcome_ref = put(dict(request_hash=request_ref, verdict='production_safe_gain'))
        trace = dict(result=dict(verdict='production_safe_gain', exploration_outcome_ref=outcome_ref),
            routing={'mode': 'exploration'}, identity=dict(operator='exp', run_id='original-exp', candidate_id='candidate',
                session_id='session', split='train', task_id='exp', source_parent_hash=sources['baseline']),
            workload=dict(case_ids=list(range(1, 21)), hardware_fingerprint=hardware_ref),
            validation=dict(timing_case_ids=list(range(1, 21)), case_count=20, passed_count=20))
        if defect == 'machine_coverage': trace['validation']['passed_count'] = 19
        trace_ref = put(trace)
        child = dict(schema_version=1, kind='exp_pmu_continuation_result_v1', plan_ref=plan_ref,
            status='passed', error=None, parent_status='failed', actual_new_builds=0, new_formal_timing_pairs=0,
            archive_performed=False, storage_mode='local_profile_only', started_at=1002, profile_finished_at=1080,
            gate_started_at=1081, gate_finished_at=1098, finished_at=1099, duration_seconds=97,
            cumulative_online_seconds=200, profile_configs=dict(baseline=profile_config_refs['baseline'],
                candidate=admission.content_hash(candidate_config)), measurement_expected=expected,
            baseline_profile_ref=profiles['baseline'], candidate_profile_ref=profiles['candidate'],
            candidate_manifest_ref=manifests['candidate'], mechanism_report_ref=mechanism_ref,
            candidate_oracle_ref=oracle_refs['candidate'][0], candidate_oracle_result_ref=oracle_refs['candidate'][1],
            candidate_output_hashes=output_hashes['candidate'], hardware_report_ref=hardware_ref,
            exploration_request_ref=request_ref, exploration_outcome_ref=outcome_ref, trace_ref=trace_ref,
            formal_outcome='production_safe_gain')
        if defect == 'child_new_build': child['actual_new_builds'] = 1
        if defect == 'child_upgraded_parent': child['parent_status'] = 'passed'
        if defect == 'child_stage_order': child['gate_started_at'] = 1079
        if defect == 'child_cumulative': child['cumulative_online_seconds'] = 5401
        if defect == 'child_underreported': child['cumulative_online_seconds'] = 196
        if defect == 'child_no_gain': child['formal_outcome'] = 'no_gain'
        child_ref = put(child)
        terminal = dict(schema_version=1, kind='exp_pmu_continuation_dispatcher_v1', plan_ref=plan_ref,
            child_result_ref=child_ref, execution_ref=execution_ref, status='passed', archive_performed=False,
            admission_authority=False, finished_at=1101, launch_ref=launch_ref, job_ref=job_ref)
        if defect == 'terminal_failed': terminal['status'] = 'failed'
        terminal_ref = put(terminal)
        calls = []
        def prefix_leaf(reader, **kwargs):
            calls.append(('prefix', kwargs))
            return copy.deepcopy(prefix)
        def load_leaf(reader, reference):
            calls.append(('load', reference))
            return admission.read(reader, reference)
        def compare_leaf(reader, baseline, candidate, metric, **kwargs):
            calls.append(('compare', baseline, candidate, metric, kwargs))
            return True
        @contextmanager
        def scope_leaf(reader, **kwargs):
            calls.append(('scope_enter', kwargs))
            try: yield
            finally: calls.append(('scope_exit',))
        def profile_leaf(reader, reference, **kwargs):
            calls.append(('profile', reference, kwargs))
            if defect == 'profile_leaf_reject': raise ValueError('full Task profile leaf rejected')
            return {'CPU_test_only_wiring': True}
        def gate_leaf(value, runtime):
            calls.append(('gate', value, runtime))
            if defect == 'gate_leaf_reject': raise ValueError('full gate leaf rejected')
        monkeypatch.setattr(admission, 'replay_reused_prefix', prefix_leaf)
        monkeypatch.setattr(admission, 'retained_producer_scope', scope_leaf)
        monkeypatch.setattr(admission, 'verify_task_profile_window', profile_leaf)
        monkeypatch.setattr(profile_evidence, 'load_capture_manifest', load_leaf)
        monkeypatch.setattr(profile_evidence, 'compare_profiles', compare_leaf)
        monkeypatch.setattr(traces, 'validate_optimization_trace', gate_leaf)
        def replay():
            return admission.verify_continuation(local, terminal_ref, campaign_ref=campaign_ref,
                trials=trials, amendment_ref=amendment_ref, trusted_review_refs=trusted)
        return SimpleNamespace(**locals())
    return make


def test_final_join_keeps_failed_parent_and_calls_heavy_leaves_with_original_bindings(continued):
    f = continued(); before = copy.deepcopy(f.prefix)
    result = f.replay()
    assert result['valid'] and result['eligible_for_rule'] and not result['eligible_for_publication']
    assert result['parent_status'] == 'failed' and f.prefix == before
    assert result['cumulative_online_seconds'] == 200
    assert [row[0] for row in f.calls] == ['prefix', 'load', 'load', 'compare', 'scope_enter', 'profile', 'gate', 'scope_exit']
    assert f.calls[0][1]['campaign_ref'] == f.campaign_ref
    assert f.calls[0][1]['trusted_review_refs'] == f.trusted
    assert {op: {k: v for k, v in row.items() if k != 'reader'} for op, row in
            f.calls[0][1]['trials'].items()} == f.trials
    assert [row[1] for row in f.calls[1:3]] == [f.manifests[role] for role in admission.ROLES]
    assert f.calls[3][1:] == (admission.read(f.local, f.profiles['baseline']),
        admission.read(f.local, f.profiles['candidate']), 'vector_busy', {'source_hashes': f.sources})
    assert f.calls[4][1] == dict(anchor_ref=f.anchor_ref, trusted_review_refs=f.trusted)
    assert f.calls[5][1:] == (f.mechanism_ref, dict(window=[10, 1080],
        measurement_admission_ref=f.original_report['measurement_admission_ref'],
        expected=f.expected, profile_configs=f.child['profile_configs']))
    assert f.calls[6][1] == f.trace
    assert f.calls[6][2].verify_artifact(f.trace_ref) == f.local.verify_artifact(f.trace_ref)


@pytest.mark.parametrize('defect,reason', [
    ('terminal_failed', 'real successful dispatcher exit'),
    ('plan_new_build', 'registered scope'), ('plan_extra_role', 'registered scope'),
    ('budget_total', 'cumulative budget'), ('budget_renewed', 'cumulative budget'),
    ('launch_deadline', 'cumulative budget'), ('execution_failed', 'actual continuation process'),
    ('execution_late', 'actual continuation process'),
    ('child_new_build', 'actual cumulative allowance'), ('child_upgraded_parent', 'actual cumulative allowance'),
    ('child_stage_order', 'actual cumulative allowance'), ('child_cumulative', 'actual cumulative allowance'),
    ('child_underreported', 'actual cumulative allowance'),
    ('changed_choice', 'mechanism choice'), ('changed_config', 'frozen profile command'),
    ('plan_source', 'source or binary'), ('plan_binary', 'source or binary'),
    ('baseline_capture_window', 'outside its registered stage'), ('candidate_capture_window', 'outside its registered stage'),
    ('baseline_extra_pmu', 'capture inventory'), ('candidate_extra_pmu', 'capture inventory'),
    ('baseline_oracle_window', 'oracle execution'), ('candidate_oracle_window', 'oracle execution'),
    ('baseline_oracle_stdout', 'stdout/result'), ('candidate_oracle_stdout', 'stdout/result'),
    ('candidate_oracle_failed', 'stdout/result'), ('candidate_oracle_extra_stdout', 'Extra data'),
    ('baseline_output_short', 'output is incomplete'), ('candidate_output_short', 'output is incomplete'),
    ('machine_binding', 'substituted reused evidence'), ('machine_source', 'single candidate'),
    ('machine_second_candidate', 'final gate changed'), ('machine_coverage', 'full-case coverage'),
    ('child_no_gain', 'final gate changed'), ('profile_leaf_reject', 'profile leaf rejected'),
    ('gate_leaf_reject', 'gate leaf rejected'),
])
def test_final_join_rejects_changed_evidence_and_failed_leaves(continued, defect, reason):
    f = continued(defect)
    with pytest.raises(ValueError, match=reason): f.replay()
    if any(row[0] == 'scope_enter' for row in f.calls):
        assert f.calls[-1] == ('scope_exit',)


@pytest.fixture
def proposed(tmp_path, monkeypatch):
    """Real promotion helpers over a tiny repo; continuation is an explicit leaf double."""
    def make(defect=None):
        local = LocalEvidence(tmp_path/'promotion-records'); put = local.register_json
        real_repo = admission.selected_runtime().parents[2]
        monkeypatch.syspath_prepend(str(real_repo/'scaffolding/tools'))
        repo = tmp_path/'repo'; release = repo/'skill-libs/graph-base/1.0.0'
        monkeypatch.setattr(admission, 'selected_runtime', lambda: release)
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value, sort_keys=True))
            reference = local.register_artifact(path)
            return dict(path=str(path), sha256=reference)
        target = promotion.SCOPES['exp-tile8192']['target_skill']
        other = 'skills/ascendc-aprof-profiling/SKILL.md'
        before = {name: write(release/name, 'original '+name+'\n')['sha256'] for name in (target, other)}
        after = dict(before)
        skill_after = write(tmp_path/'after.md', 'Exp only proposed edit\n'); after[target] = skill_after['sha256']
        if defect == 'second_skill': after[other] = write(tmp_path/'other-after.md', 'another edit\n')['sha256']
        before_ref, after_ref = put(before), put(after)
        split_root = repo/'scaffolding/benchmarks/cannbench'
        for split in ('train', 'validation', 'test'):
            members = ['exp'] if split == ('validation' if defect == 'validation_source' else 'train') else []
            write(split_root/split/'operators.txt', ''.join(name+'\n' for name in members))
            write(split_root/split/'manifest.json', {'active_operators': members})
        split_pointer = write(split_root/'split_index.json', {'CPU': 'tiny source split'})
        trace_pointer = write(repo.parent/'optimization-traces/index.json', {'CPU': 'tiny trace index'})
        campaign = dict(trace_index_sha256=trace_pointer['sha256'], split_index_sha256=split_pointer['sha256'])
        campaign_ref = put(campaign)
        scope = promotion.SCOPES['exp-tile8192']; rows, source_refs = {}, []
        for index, key in enumerate(scope['source_keys']):
            record_hash = 'sha256:'+str(index)*64
            lesson = dict(id=key.removeprefix('l1:'), record_hash=record_hash,
                          body=dict(operator='exp', split='train'))
            line = json.dumps(lesson, sort_keys=True).encode()
            relative = f'optimization-traces/tiny-{index}.jsonl'
            write(repo.parent/relative, line.decode()+'\n')
            line_ref = promotion.digest(line)
            rows[key] = dict(level=1, operator='exp', split='train', decision='include',
                wiki_ids=['exp-tile8192'], sources=[dict(path=relative, sha256=line_ref, record_hash=record_hash)])
            source_refs.append(dict(key=key, sha256=[line_ref]))
        if defect == 'source_operator': rows[scope['source_keys'][0]]['operator'] = 'sigmoid'
        audit = dict(**campaign, records=rows)
        audit_pointer = write(repo/'scaffolding/curation/graph-base-1.0.0.json', audit)
        entry = dict(source_keys=scope['source_keys'], page='exp-tile8192.md', status='draft', skill_refs=[],
                     graph_nodes=scope['graph_nodes'], source_refs=source_refs)
        wiki_pointer = write(release/'wiki/index.json', dict(trace_index_sha256=trace_pointer['sha256'],
                                                           entries={'exp-tile8192': entry}))
        page_pointer = write(release/'wiki/exp-tile8192.md', '# Exp CPU fixture\n')
        amendment_ref = put({'CPU': 'amendment binding supplied to continuation leaf'})
        continuation_ref = put({'CPU': 'continuation binding supplied to continuation leaf'})
        trace_ref, hardware_ref = put({'CPU': 'trace'}), put({'CPU': 'hardware'})
        machine = dict(trace_ref=trace_ref, hardware_report_ref=hardware_ref)
        continued_result = dict(parent_status='failed', machine=machine,
            prefix={'measurement_expected': {'run_id': 'original-exp'}}, eligible_for_publication=False)
        trusted, trials = {'CPU': 'trusted archive bindings'}, {'exp': {'CPU': 'original index'}}
        receipt = dict(schema_version=1, kind='teacher_exp_continuation_promotion', proposal_id='one-exp-edit',
            wiki_id='exp-tile8192', target_skill=target, source_keys=scope['source_keys'],
            source_audit_ref=audit_pointer, wiki_index_ref=wiki_pointer, wiki_page_ref=page_pointer,
            trace_index_ref=trace_pointer, split_index_ref=split_pointer,
            skill_before=dict(path=str(release/target), sha256=before[target]), skill_after=skill_after,
            skill_inventory_before_ref=before_ref, skill_inventory_after_ref=after_ref,
            campaign_ref=campaign_ref, selected_run_id='original-exp', trace_ref=trace_ref,
            hardware_report_ref=hardware_ref, continuation_ref=continuation_ref, amendment_ref=amendment_ref)
        if defect == 'sigmoid_scope': receipt['wiki_id'] = 'sigmoid-pipeline'
        if defect == 'mixed_sources': receipt['source_keys'] = scope['source_keys']+['l1:sigmoid001-pipeline-final-v1']
        if defect == 'selected_other_run': receipt['selected_run_id'] = 'another-exp'
        if defect == 'untrusted_inventory': receipt['skill_inventory_before_ref'] = after_ref
        promotion_ref = put(receipt)
        calls = []
        def continuation_leaf(reader, reference, **kwargs):
            calls.append(('continuation', reader, reference, kwargs))
            if defect == 'continuation_failed': raise ValueError('continuation leaf rejected')
            return copy.deepcopy(continued_result)
        real_skills, real_sources = promotion._skills, promotion._sources
        def skills_spy(*args):
            calls.append(('skills', args))
            return real_skills(*args)
        def sources_spy(*args):
            calls.append(('sources', args))
            return real_sources(*args)
        monkeypatch.setattr(admission, 'verify_continuation', continuation_leaf)
        monkeypatch.setattr(promotion, '_skills', skills_spy)
        monkeypatch.setattr(promotion, '_sources', sources_spy)
        def replay():
            return admission.verify_continuation_promotion(local, promotion_ref, campaign_ref=campaign_ref,
                trials=trials, amendment_ref=amendment_ref, trusted_before_inventory_ref=before_ref,
                repo=repo, release=release, trusted_review_refs=trusted)
        return SimpleNamespace(**locals())
    return make


def test_promotion_calls_real_single_edit_and_original_source_helpers(proposed):
    f = proposed(); result = f.replay()
    assert result['valid'] and result['operator'] == 'exp' and result['eligible_for_teacher_edit']
    assert not result['eligible_for_publication'] and not result['graph_policy_eligible']
    assert result['continuation']['parent_status'] == 'failed' and not result['edit']['applied']
    assert result['sources']['source_keys'] == promotion.SCOPES['exp-tile8192']['source_keys']
    assert [row[0] for row in f.calls] == ['continuation', 'skills', 'sources']
    assert f.calls[0][1:] == (f.local, f.continuation_ref, dict(campaign_ref=f.campaign_ref,
        trials=f.trials, amendment_ref=f.amendment_ref, trusted_review_refs=f.trusted))
    assert f.calls[1][1] == (f.local, f.receipt, f.release, f.before_ref)
    assert f.calls[2][1] == (f.local, f.receipt, f.campaign, f.repo, f.release)


@pytest.mark.parametrize('defect,reason', [
    ('sigmoid_scope', 'unsupported or mixed'), ('mixed_sources', 'unsupported or mixed'),
    ('selected_other_run', 'selected another continuation'), ('second_skill', 'exactly the one'),
    ('untrusted_inventory', 'trusted previous skill'), ('validation_source', 'validation/test evidence'),
    ('source_operator', 'different-operator source'), ('continuation_failed', 'continuation leaf rejected'),
])
def test_promotion_rejects_mixed_scope_extra_edit_and_failed_continuation(proposed, defect, reason):
    f = proposed(defect)
    with pytest.raises(ValueError, match=reason): f.replay()
