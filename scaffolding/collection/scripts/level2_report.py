#!/usr/bin/env python3
"""Read-only Level2 progress and measured effects; never starts or selects work.

Only registered ledger candidates count as rounds. Saved performance reports are
replayed through the existing CPU-only observation analyzer before aggregation.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
sys.dont_write_bytecode = True
import msprof_exploration_campaign as campaign
import msprof_exploration_report as analysis
from msprof_search_protocol import LITE_PROTOCOL, LITE_ANALYSIS

VERSION = 'level2_optimization_report_v1'


def require(value, message):
    if not value: raise ValueError(message)


class Evidence:
    def __init__(self): self.rows = {}
    def add(self, path, *, expected=None, role='evidence'):
        path = Path(path).resolve()
        digest = analysis.sha(path)
        require(expected is None or digest == expected, 'evidence hash differs: ' + str(path))
        key = hashlib.sha256((str(path) + '\0' + digest).encode()).hexdigest()
        ref = {'id': key, 'path': str(path), 'sha256': digest}
        if key not in self.rows: self.rows[key] = {**ref, 'roles': []}
        if role not in self.rows[key]['roles']: self.rows[key]['roles'].append(role)
        return ref
    def pointer(self, ref, role='evidence'):
        require(isinstance(ref, dict) and {'path','sha256'} <= ref.keys(), 'missing bound evidence pointer')
        return self.add(ref['path'], expected=ref['sha256'], role=role)
    def read(self, ref, role='evidence'):
        checked = self.pointer(ref, role)
        return analysis.load(checked['path']), checked
    def tree(self, value, role):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                self.pointer(value, role)
            else:
                for item in value.values(): self.tree(item, role)
        elif isinstance(value, list):
            for item in value: self.tree(item, role)


def aggregate_effects(report, selections):
    """Average case logs within each process using its explicit sampling protocol."""
    require(report.get('evidence_status') == 'verified_complete', 'report is not verified complete')
    lite = report.get('protocol') == LITE_PROTOCOL
    if lite:
        require(report.get('analysis_version') == LITE_ANALYSIS, 'lite analysis version differs')
    process_count = 2 if lite else 6
    summarize = analysis.descriptive_effect if lite else analysis.effect
    mapping = {str(row['case_id']): row for row in selections}
    require(len(mapping) == len(selections), 'duplicate dispatch case selection')
    declared = [str(case) for case in report['case_ids']]
    require(len(declared) == len(set(declared)), 'duplicate measured case')
    cells, groups = {}, defaultdict(list)
    for row in report['results']:
        case, config = str(row['case_id']), row['buffer_config']
        require(case in mapping and config in ('normal','swapped'), 'measured case/config lacks dispatch selection')
        require((case,config) not in cells, 'duplicate measured case/config cell')
        effect = summarize(row['log_effects'])
        for key in ('speedup','mean_log'):
            if key in row: require(math.isclose(row[key], effect[key], rel_tol=1e-12, abs_tol=1e-12), 'saved effect differs from protocol process logs')
        if lite:
            require(row.get('ci95') is None and row.get('log_ci95') is None,
                    'lite report cannot claim a confidence interval')
        selected = mapping[case]
        cell = {'case_id': int(case), 'buffer_config': config,
                **{k:selected[k] for k in ('tiling_key','kernel_entry','group_id')}, **effect}
        for key in ('cv_status','calibration_status','coarse_observed_controls','measurement_quality','limitations'):
            if key in row: cell[key] = row[key]
        if lite: cell['qualified_performance_eligible'] = False
        cells[case,config] = cell
        groups[(selected['tiling_key'],selected['kernel_entry'],selected['group_id'],config)].append(cell)
    require(set(cells) == {(case,config) for case in declared for config in ('normal','swapped')}, 'normal/swapped case coverage is incomplete')
    grouped = []
    for (key,entry,group,config), rows in sorted(groups.items()):
        logs = [statistics.mean(row['log_effects'][i] for row in rows) for i in range(process_count)]
        grouped.append({'tiling_key':key, 'kernel_entry':entry, 'group_id':group, 'buffer_config':config,
            'case_ids':sorted(row['case_id'] for row in rows), 'case_count':len(rows),
            'aggregation':('equal_case_mean_log_within_each_of_two_processes' if lite else
                           'equal_case_mean_log_within_each_of_six_processes'), **summarize(logs),
            'qualified_performance_eligible':False})
    return {'per_case': sorted(cells.values(),key=lambda r:(r['case_id'],r['buffer_config'])),
            'per_tiling_key': grouped, 'replication_unit':'native_process',
            **({'protocol':LITE_PROTOCOL,'analysis_version':LITE_ANALYSIS} if lite else {}),
            'full_twenty_case_suite':set(declared)=={str(i) for i in range(1,21)},
            'metric':report.get('metric'), 'limitations':report.get('limitations',[])}


def stage_rows(state, candidate_id, evidence):
    rows = []
    for sid, stage in state.get('stages',{}).items():
        if stage.get('candidate_id') != candidate_id: continue
        attempts = stage.get('attempts',[])
        require(attempts, 'ledger stage has no attempt')
        last = attempts[-1]
        evidence.tree(last.get('evidence',{}), 'stage_result')
        rows.append({'stage_id':sid,'kind':stage['kind'],'outcome':last.get('outcome'),
            'purpose':stage.get('plan',{}).get('purpose'),
            'status':'running' if last.get('outcome') is None else 'passed' if last['outcome']=='success' else 'failed',
            'native_started':last.get('native_started'),'formal_samples':last.get('formal_samples',0),
            'attempt_count':len(attempts),'evidence':last.get('evidence',{}),
            'actual_costs':last.get('actual_costs',{})})
    return rows


def measured_stages(task, state, item, proposal, evidence):
    """Reanalyze completed real timing cohorts; no collector or oracle calls."""
    results = []
    from shared_context_build import source_hash
    from run_msprof_exploration_stage import verify_source_snapshot
    candidate = task/'candidates'/item['candidate_id']
    evidence.add(candidate/'source.tar',expected=item['source_hash'],role='candidate_source')
    verify_source_snapshot(candidate/'source.tar',candidate/'op')
    baseline_hash = analysis.sha(task/'baseline-source.tar')
    for sid, stage in state['stages'].items():
        if stage['candidate_id'] != item['candidate_id'] or stage['kind'] != 'timing': continue
        attempt = stage['attempts'][-1]
        if attempt.get('outcome') != 'success': continue
        result, result_ref = evidence.read(attempt['evidence']['result'], 'timing_stage_result')
        require(result.get('status')=='passed' and result.get('native_started') is True, 'timing result lacks successful real native execution')
        directory = Path(result_ref['path']).parent
        plan = stage['plan']
        lite = plan.get('protocol') == LITE_PROTOCOL
        require(not lite or plan.get('purpose') == 'search', 'lite measurements cannot serve as final evaluation')
        expected_relations = {'direct_parent':item['source_parent']['candidate_id'] or 'baseline'}
        if not lite and item['source_parent']['source_hash'] != baseline_hash:
            expected_relations['original_baseline']='baseline'
        require(plan['comparisons']==campaign.comparisons(item,baseline_hash,search_lite=lite),'timing lineage differs from registered parent')
        require({row['relation']:row['control_candidate_id'] for row in plan['cohorts']}==expected_relations
                and len(plan['cohorts'])==len(expected_relations),'timing cohort control sources differ')
        stage_plan, _ = evidence.read({'path':str(directory/'stage-plan.json'),'sha256':analysis.sha(directory/'stage-plan.json')},'timing_stage_plan')
        require(stage_plan == plan, 'stage plan differs from immutable ledger')
        for cohort in plan['cohorts']:
            relation = cohort['relation']
            control_id = expected_relations[relation]
            control = task if control_id=='baseline' else task/'candidates'/control_id
            archive = control/('baseline-source.tar' if control_id=='baseline' else 'source.tar')
            control_source = control/('baseline' if control_id=='baseline' else 'op')
            expected_control = baseline_hash if control_id=='baseline' else item['source_parent']['source_hash']
            evidence.add(archive,expected=expected_control,role='measured_control_source')
            verify_source_snapshot(archive,control_source)
            frozen, plan_ref = evidence.read(cohort['plan'], 'cohort_plan')
            require((frozen.get('protocol') == LITE_PROTOCOL) == lite,
                    'cohort protocol differs from timing stage')
            output = directory / relation
            saved_ref = evidence.add(output/'report.json',role='measured_report')
            saved = analysis.load(saved_ref['path'])
            completion_ref = evidence.add(output/'group-completion.json',role='cohort_completion')
            completion = analysis.load(completion_ref['path'])
            require(completion.get('status')=='passed', 'timing cohort did not complete')
            evidence.tree(completion.get('sessions',[]),'native_cohort_evidence')
            calibration_ref = cohort.get('calibration_report') or plan.get('calibration_report')
            if lite:
                require(calibration_ref is None, 'lite search must not reuse an A/A qualification')
                calibration, checked_calibration = None, None
            elif calibration_ref is None:
                path = task/'stages/aa-initial/cohort/report.json'
                calibration_ref = {'path':str(path),'sha256':analysis.sha(path)}
            if not lite:
                calibration, checked_calibration = evidence.read(calibration_ref,'aa_calibration')
            provenance = []
            actual = analysis.analyze_task_cohort(completion['completed_sessions'],frozen,
                calibration=calibration,provenance_out=provenance)
            analysis.compare_saved_report(saved,actual,evidence_path=Path(saved_ref['path']),provenance_out=provenance)
            require((actual.get('protocol') == LITE_PROTOCOL) == lite,
                    'measured report protocol differs from timing stage')
            require(actual.get('operator')==proposal['operator'] and actual.get('comparison_kind')=='ab', 'measured operator/comparison differs')
            require(actual['source_hashes']=={'A':source_hash(control_source),'B':source_hash(candidate/'op')},'measured implementation/control differs from registered sources')
            require([str(c) for c in actual['case_ids']]==[str(c) for c in plan['case_ids']], 'timing case coverage differs from ledger')
            aggregate = aggregate_effects(actual,proposal['dispatch_selections'])
            results.append({'stage_id':sid,'purpose':plan['purpose'],'relation':relation,
                'control_candidate_id':cohort['control_candidate_id'],'report':saved_ref,'plan':plan_ref,
                'completion':completion_ref,'calibration':checked_calibration,
                'source_hashes':actual['source_hashes'],'verification':'raw_observations_replayed_read_only',
                'producer_resolution':provenance, **aggregate})
    return results


def final_selection(selection, baseline_hash, rounds, evidence):
    if selection is None: return {'status':'pending'}
    require(isinstance(selection,dict) and isinstance(selection.get('reason'),str) and selection['reason'].strip(), 'final selection requires a reason')
    evidence.tree(selection.get('evidence',[]),'final_selection_basis')
    cid = selection.get('candidate_id')
    if cid == 'baseline':
        require(selection.get('source_hash')==baseline_hash,'selected baseline source differs')
        return {**selection,'status':'selected_baseline'}
    row = next((r for r in rounds if r['candidate_id']==cid),None)
    require(row is not None and row['source_hash']==selection.get('source_hash'),'selection is not a registered source')
    require(row.get('round_feedback_closed',row['feedback_closed']) and row['status']=='measured' and row['measurements'],'selected candidate has no complete measured feedback')
    return {**selection,'status':'selected_measured_candidate'}



def selection_reconsiderations(task, evidence):
    """Honor explicit public acceptance holds without rerunning numeric proof.

    Only small decision metadata is opened. This is a conservative readiness
    gate, not a source-failure classifier, selection writer or resolution API.
    An unrelated event or edited winner cannot clear a recorded hold.
    """
    def canonical_path(path):
        path=Path(path)
        require(path.is_absolute() and '..' not in path.parts and path==path.resolve()
                and not any(p.is_symlink() for p in (path,*path.parents)), 'noncanonical selection hold evidence')
        return path
    def document(ref, role):
        path=canonical_path(ref['path'])
        require(path.suffix=='.json' and path.is_relative_to(task/'finalization')
                and path.stat().st_size<=1024*1024, 'selection hold must bind small task finalization metadata')
        return evidence.read(ref,role)[0]
    def decode(line):
        def pairs(items):
            value={}
            for key,item in items:
                require(key not in value, 'duplicate public event JSON key');value[key]=item
            return value
        return json.loads(line,object_pairs_hook=pairs)
    task=canonical_path(task);journal=task/'events.jsonl'
    if not journal.exists():
        require(not journal.is_symlink(), 'dangling public event journal')
        return []
    canonical_path(journal)
    data=journal.read_bytes();require(not data or data.endswith(b'\n'), 'partial public event journal')
    previous=None;holds=[]
    for i,line in enumerate(data.splitlines()):
        row=decode(line);body={k:v for k,v in row.items() if k!='hash'}
        payload=(json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
        require(row.get('sequence')==i and type(row['sequence']) is int and row.get('previous_hash')==previous
                and row.get('hash')=='sha256:'+hashlib.sha256(payload).hexdigest(), 'public event chain differs')
        previous=row['hash']
        if row.get('kind')!='final_selection_reconsideration_required': continue
        value=row['value']
        require(isinstance(value,dict) and set(value)=={'reconsideration','numeric_proof','selection_unchanged'},
                'invalid selection reconsideration event')
        note=document(value['reconsideration'],'selection_reconsideration')
        original=document(value['selection_unchanged'],'held_original_selection')
        proof=document(value['numeric_proof'],'selection_reconsideration_numeric_metadata')
        require(note.get('version')=='level2_final_selection_reconsideration_v1'
                and note.get('operator')==task.name and note.get('status')=='selected_source_fails_additional_legal_workload'
                and note.get('original_selection')==value['selection_unchanged']
                and note.get('numeric_proof')==value['numeric_proof'], 'selection reconsideration identity differs')
        require(proof.get('operator')==task.name and proof.get('original_selection')==value['selection_unchanged']
                and proof.get('original_source_hash')==original.get('source_hash'), 'held numeric metadata source differs')
        holds.append({'event_binding':{'journal_path':str(journal),'sequence':i,'event_hash':row['hash'],
                      'kind':row['kind']},**value,'candidate_id':original.get('candidate_id'),
                      'source_hash':original.get('source_hash'),'required_resolution':note.get('required_resolution')})
    if holds:
        # This report snapshot records its read journal, while each durable hold
        # remains identified by a prefix event hash, not a timeless full-file hash.
        evidence.add(journal,expected='sha256:'+hashlib.sha256(data).hexdigest(),role='selection_readiness_journal_snapshot')
    return holds


def withhold_unresolved_selection(record, task, evidence):
    holds=selection_reconsiderations(task,evidence)
    if not holds: return record
    selected=record['final_selection']
    selected['declared_selection_status']=selected['status']
    selected.update(status='reconsideration_required',current_safe=False,acceptance_ready=False)
    record['selection_readiness']={'status':'reconsideration_required','acceptance_ready':False,
        'unresolved':holds,'automatic_resolution_supported':False}
    record['issues'].append('Final acceptance withheld: explicit selection reconsideration requires a reviewed append-only resolution.')
    record['status']='blocked'
    return record

def runtime_closure(task, ledger, cid, evidence):
    """Reuse the finalizer's read-only lifecycle audit, including baseline."""
    import level2_finalize as finalizer
    state=ledger.state['tasks'][task.name]
    current=max((row for row in state['stages'].values() if row['candidate_id']==cid and row['kind']=='runtime'),
                key=lambda row:row['attempts'][-1]['start_order'])
    parent=task if cid is None else task/'candidates'/cid
    value=finalizer.runtime_evidence(ledger,task.name,cid,parent,current)
    evidence.add(Path(finalizer.__file__),role='runtime_closure_verifier')
    evidence.pointer(current['attempts'][-1]['evidence']['runtime'],'runtime_assessment')
    evidence.tree(value,'runtime_native_evidence')


def qualified_source(task, state, item, feedback, evidence, *, ledger):
    """Qualification follows current safety and bound guards, never gain."""
    cid = item['candidate_id']
    if not campaign._safe_source(state, cid): return False
    ref = feedback.get('semantic_guards') if feedback is not None else None
    if ref is None: return False
    parent = task/'candidates'/cid
    require(Path(ref['path']).resolve()==parent/'boundary-validation/completion.json', 'boundary evidence belongs to another candidate')
    guard, _ = evidence.read(ref, 'candidate_boundary_validation')
    from level2_iteration import boundary_result
    require(boundary_result(task,parent,task.name,cid)==guard, 'bound boundary validation differs')
    evidence.tree(guard, 'boundary_execution')
    if guard.get('status')!='passed': return False
    require(not guard.get('error') and not guard.get('verification_error') and guard.get('cases')
        and all(r.get('expected_process_passed') is True and r.get('dispatch_log_passed') is True for r in guard['cases']),
        'passed boundary validation lacks successful actual checks')
    runtime_closure(task,ledger,cid,evidence)
    return True


def source_failure(task, state, item, feedback, evidence):
    """Replay the same positive proof as the finalizer before counting a failure."""
    import level2_failure_classification as classifier
    cid=item['candidate_id'];parent=task/'candidates'/cid
    declared=feedback.get('failure_classification')
    require(isinstance(declared,dict),'source failure has no positive classification')
    evidence.add(Path(classifier.__file__),role='source_failure_classifier')
    first=next((row for row in feedback.get('stages',[]) if row.get('status')!='passed'),None)
    actual_stage=None
    if first is not None:
        stage=state['stages'].get(first['stage_id'])
        require(stage is not None and stage['candidate_id']==cid,'failure stage belongs to another source')
        latest=max((row for row in state['stages'].values() if row['candidate_id']==cid and row['kind']==stage['kind']),
                   key=lambda row:row['attempts'][-1]['start_order'])
        require(latest['stage_id']==stage['stage_id'] and stage['attempts'][-1]['outcome'] not in (None,'success'),
                'failure proof does not describe the current failed stage')
        ref=stage['attempts'][-1]['evidence'].get('result')
        require(first.get('result')==ref,'failure feedback result differs from ledger')
        actual_stage,_=evidence.read(ref,'source_failure_stage')
        require(actual_stage.get('candidate_id')==cid and actual_stage.get('stage_id')==stage['stage_id']
                and actual_stage.get('status')=='failed'
                and all(first.get(k)==actual_stage.get(k) for k in ('kind','status','error')),
                'failure feedback differs from executed stage')
    guard=None
    if feedback.get('semantic_guards') is not None:
        ref=feedback['semantic_guards']
        require(Path(ref['path']).resolve()==parent/'boundary-validation/completion.json','failure guard belongs to another source')
        guard,_=evidence.read(ref,'source_failure_guard')
    actual=classifier.classify_failure(task,parent,stage=actual_stage,guard=guard)
    require(actual['status']=='source_attempt_failed' and actual==declared,
            'source failure lacks unchanged positive classification evidence')
    evidence.tree(actual,'source_failure_classification')
    return actual


def final_evaluation(state, config, rounds, baseline_hash):
    """All safety-qualified sources need frozen full-suite comparisons."""
    qualified = [r['candidate_id'] for r in rounds if r.get('qualified_current')]
    summary = {'status':'pending','candidate_ids':qualified,'candidates':[]}
    if not state.get('frozen'): return summary
    require(len(rounds)==state.get('new_source_attempts')==state.get('new_rounds_started')==3,
            'final freeze does not contain exactly three actual source rounds')
    roster = [{k:v for k,v in item.items() if k not in {'feedback_closed','observation_ids','current_round_started'}}
              for item in state['candidates'].values()]
    require(state.get('frozen_roster')=={'candidates':roster,'sha256':campaign.digest(roster)},
            'frozen source roster differs from registered sources')
    require(len(state.get('selection',[]))==len(qualified) and set(state['selection'])==set(qualified)
            and set(state.get('final_plans',{}))==set(qualified),
            'frozen final evaluation must include every currently qualified candidate')
    for cid in qualified:
        item = state['candidates'][cid]
        plan = state['final_plans'][cid]
        campaign._timing_plan(plan,item,baseline_hash,policy=config['policy'],repeat_by_case=config['task'].get('repeat_by_case'))
        require(plan['purpose']=='final' and plan['case_ids']==campaign.ALL_CASES, 'frozen final plan omits workload cases')
        stages = [stage for stage in state['stages'].values() if stage['candidate_id']==cid
                  and stage['kind']=='timing' and stage['plan'].get('purpose')=='final']
        require(len(stages)<=1, 'candidate has ambiguous final stage identity')
        status = 'pending'
        if stages:
            stage = stages[0]
            require(stage['plan']==plan, 'executed final stage differs from frozen final plan')
            outcome = stage['attempts'][-1]['outcome']
            if outcome is not None and outcome!='success': status='failed'
            elif outcome=='success':
                row = next(r for r in rounds if r['candidate_id']==cid)
                measured = [m for m in row['measurements'] if m['stage_id']==stage['stage_id']
                            and m['purpose']=='final' and m['full_twenty_case_suite']]
                expected = {'direct_parent'}
                if item['source_parent']['source_hash']!=baseline_hash: expected.add('original_baseline')
                require(len(measured)==len(expected) and {m['relation'] for m in measured}==expected,
                        'successful final stage lacks all twenty-case parent/original comparisons')
                status='complete'
        summary['candidates'].append({'candidate_id':cid,'status':status})
    statuses = [r['status'] for r in summary['candidates']]
    summary['status'] = 'failed' if 'failed' in statuses else 'pending' if 'pending' in statuses else 'complete'
    return summary


def task_report(run, split, operator, task, manifest, ledger, selection, evidence):
    manifest_ref = evidence.add(task/'manifest.json',role='task_manifest')
    require(manifest.get('version')=='msprof_task_time_exploration_v2' and manifest.get('operator')==operator
        and manifest.get('split')==split and manifest.get('run_id')==run.name
        and manifest.get('task_dir')==str(task),'fresh task manifest identity differs')
    baseline_hash = manifest['baseline']['sha256']
    evidence.pointer(manifest['baseline'],'baseline_source')
    record = {'operator':operator,'split':split,'source_split':manifest['source_split'],'manifest':manifest_ref,
        'status':'incomplete','expected_rounds':3,'registered_rounds':0,'started_rounds':0,'completed_rounds':0,
        'rounds':[],'baseline':{'source_hash':baseline_hash,'stages':[]},'final_selection':{'status':'pending'},
        'final_evaluation':'pending','issues':[]}
    if ledger is None:
        record['pending_reason']='ledger_not_created; preflight and draft candidates do not count as formal rounds'
        record['final_selection']=final_selection(selection,baseline_hash,[],evidence)
        return withhold_unresolved_selection(record,task,evidence)
    require(ledger.config['schema_version']==campaign.FRESH_SCHEMA,'report requires a fresh campaign ledger')
    state = ledger.state['tasks'][operator]
    require(ledger.config['tasks'][operator]['baseline_source_hash']==baseline_hash,'ledger baseline differs from manifest')
    record['baseline']['stages']=stage_rows(state,None,evidence)
    record['baseline']['current_safe']=campaign._safe_source(state,None)
    if record['baseline']['current_safe']:
        try: runtime_closure(task,ledger,None,evidence)
        except (ValueError,KeyError,OSError,TypeError) as exc:
            record['baseline']['current_safe']=False
            record['issues'].append('baseline runtime closure: '+str(exc))
    for number,item in enumerate((c for c in state['candidates'].values() if not c.get('inherited')),1):
        row={'round':number,'candidate_id':item['candidate_id'],'source_hash':item['source_hash'],
             'source_parent':item['source_parent'],'decision_basis':item['decision_basis'],
             'feedback_closed':item['feedback_closed'],'round_feedback_closed':False,'started':item['current_round_started'],
             'status':'incomplete','qualified_current':False,'measurements':[],'issues':[]}
        record['rounds'].append(row)
        try:
            artifacts=item['artifacts'];proposal,proposal_ref=evidence.read(artifacts['proposal'],'registered_proposal')
            require(proposal.get('candidate_id')==item['candidate_id'] and proposal.get('implementation_source_hash')==item['source_hash'],'registered proposal source differs')
            row.update(optimization_stage=proposal['optimization_stage'],proposal=proposal_ref,
                dispatch_selections=proposal['dispatch_selections'],architecture_profile_ref=proposal['architecture_profile_ref'],
                parallel_plan_ref=proposal['parallel_plan_ref'],dispatch_plan_ref=proposal['dispatch_plan_ref'])
            evidence.tree(artifacts,'registered_artifact')
            row['stages']=stage_rows(state,item['candidate_id'],evidence)
            if any(s['kind']=='timing' and s['status']=='passed' for s in row['stages']):
                row['measurements']=measured_stages(task,state,item,proposal,evidence)
            observations=[];latest_feedback=None
            for oid in item['observation_ids']:
                observed=state['observations'][oid]
                matches=[p for p in (task/'feedback').glob('*.json') if analysis.sha(p)==observed['report_ref']]
                require(matches,'recorded feedback file is absent')
                ref={'path':str(matches[0]),'sha256':observed['report_ref']}
                feedback,checked=evidence.read(ref,'closed_feedback')
                require(feedback==observed['feedback'] and feedback.get('source_hash')==item['source_hash'],'closed feedback differs from ledger')
                observations.append({'observation_id':oid,'feedback':checked,'status':feedback['status'],
                    'closed':observed.get('close_feedback') is True,
                    'infrastructure_blocked':observed.get('quality',{}).get('infrastructure_blocked') is True})
                latest_feedback=feedback
            row['observations']=observations
            row['round_feedback_closed']=bool(observations) and observations[-1]['closed']
            if observations:
                row['status']={'measured':'measured','infrastructure_blocked':'blocked','source_attempt_failed':'failed'}.get(observations[-1]['status'],'blocked')
                if observations[-1]['infrastructure_blocked']: row['status']='blocked'
                if row['status']=='measured': require(row['measurements'],'measured feedback lacks a complete real timing stage')
                if row['status']=='failed':
                    row['failure_classification']=source_failure(task,state,item,latest_feedback,evidence)
            elif any(s['status']=='failed' for s in row['stages']): row['status']='failed'
            row['qualified_current']=qualified_source(task,state,item,latest_feedback,evidence,ledger=ledger)
            if row['status']=='measured': require(row['qualified_current'],'measured source lacks current correctness/runtime/boundary qualification')
            if row['status']=='failed': require(not row['qualified_current'],'source failure contradicts current safety qualification')
        except (ValueError,KeyError,OSError,TypeError) as exc:
            row['status']='blocked';row['issues'].append(str(exc))
    record['registered_rounds']=len(record['rounds'])
    record['started_rounds']=sum(row['started'] for row in record['rounds'])
    record['completed_rounds']=sum(row['started'] and row['round_feedback_closed'] and row['status'] in ('measured','failed')
                                   and not row['issues'] for row in record['rounds'])
    try: record['final_selection']=final_selection(selection,baseline_hash,record['rounds'],evidence)
    except (ValueError,KeyError,OSError,TypeError) as exc: record['issues'].append(str(exc))
    chosen=record['final_selection']
    selected_safe = chosen['status']=='selected_baseline' and record['baseline']['current_safe']
    if chosen['status']=='selected_measured_candidate':
        selected_safe=next(row for row in record['rounds'] if row['candidate_id']==chosen['candidate_id'])['qualified_current']
    try:
        evaluation=final_evaluation(state,{'policy':ledger.config.get('policy'),
            'task':ledger.config['tasks'][operator]},record['rounds'],baseline_hash)
        record['final_evaluation']=evaluation['status'];record['evaluation_roster']=evaluation
    except (ValueError,KeyError,OSError,TypeError) as exc: record['issues'].append(str(exc))
    record['final_selection']['current_safe']=bool(selected_safe)
    if record['issues'] or any(r['status']=='blocked' for r in record['rounds']): record['status']='blocked'
    elif record['completed_rounds']==3 and record['final_evaluation']=='complete' and selected_safe: record['status']='complete'
    elif record['final_evaluation']=='failed' or any(r['status']=='failed' for r in record['rounds']): record['status']='failed'
    return withhold_unresolved_selection(record,task,evidence)


def build_report(run):
    run=Path(run).resolve();require(run.is_dir(),'run directory does not exist')
    evidence=Evidence();issues=[];ledgers={};roster={}
    producer=evidence.add(Path(__file__),role='read_only_report_producer')
    path=run/'campaign-manifest.json'
    if path.exists():
        evidence.add(path,role='campaign_manifest');manifest=analysis.load(path)
        require(manifest.get('version')==campaign.FRESH_SCHEMA,'not a fresh campaign manifest')
        roster={(split,op) for split,tasks in manifest['operators'].items() for op in tasks}
        roster_status='frozen'
    else:
        roster={(split,p.parent.name) for split in ('train','validation') for p in (run/split/'tasks').glob('*/manifest.json')}
        roster_status='partial_manifest'
    require(roster,'no declared fresh tasks')
    selection_path=run/'final-selection.json';selections={}
    if selection_path.exists():
        evidence.add(selection_path,role='explicit_final_selection');document=analysis.load(selection_path)
        require(document.get('version')=='level2_final_selection_v1' and isinstance(document.get('selections'),dict),'invalid final selection document')
        selections=document['selections'];require(set(selections)<={op for _,op in roster},'selection names an undeclared operator')
    for split in sorted({split for split,_ in roster}):
        directory=run/split/'ledger'
        if not directory.exists(): ledgers[split]=None;continue
        try:
            ledger=campaign.Campaign(directory);ledger.verify();ledgers[split]=ledger
            for name in ('config.json','config.sha256.json','events.jsonl'):evidence.add(directory/name,role='immutable_ledger')
        except (ValueError,KeyError,OSError,TypeError) as exc:
            ledgers[split]=None;issues.append({'split':split,'error':str(exc)})
    operators=[]
    for split,op in sorted(roster):
        task=run/split/'tasks'/op
        try:
            row=task_report(run,split,op,task,analysis.load(task/'manifest.json'),ledgers[split],selections.get(op),evidence)
            if any(issue['split']==split for issue in issues):row['status']='blocked';row['issues'].append('ledger verification failed')
        except (ValueError,KeyError,OSError,TypeError) as exc:
            row={'operator':op,'split':split,'status':'blocked','issues':[str(exc)],'rounds':[],
                 'registered_rounds':0,'started_rounds':0,'completed_rounds':0,'final_selection':{'status':'pending'}}
        operators.append(row)
    counts={status:sum(row['status']==status for row in operators) for status in ('complete','incomplete','blocked','failed')}
    status='complete' if roster_status=='frozen' and counts['complete']==len(operators) else 'blocked' if counts['blocked'] else 'failed' if counts['failed'] else 'incomplete'
    has_lite=any(measured.get('protocol')==LITE_PROTOCOL for operator in operators
                 for row in operator.get('rounds',[]) for measured in row.get('measurements',[]))
    return {'version':VERSION,'run_id':run.name,'run_directory':str(run),'status':status,'roster_status':roster_status,
        'producer':producer,
        'read_only':True,'hardware_executed':False,'formal_admission':'not_evaluated','graph_policy_eligible':False,'episode_ref':None,
        'operator_count':len(operators),'status_counts':counts,'registered_rounds':sum(r['registered_rounds'] for r in operators),
        'completed_rounds':sum(r['completed_rounds'] for r in operators),'operators':operators,
        'evidence_index':list(evidence.rows.values()),'issues':issues,
        'limitations':['Drafts and preflight pilots are not formal source rounds.',
            'Ratios summarize operator task sums per complete call, excluding host submission and inter-task gaps.',
            ('Normal and swapped configurations remain separate; each key aggregate preserves its protocol: two descriptive processes for lite search, six for full evaluation.'
             if has_lite else 'Normal and swapped configurations remain separate; key aggregates preserve six process units.'),
            ('Lite search ranges are descriptive and have no confidence interval; loading, first-order and buffer-order effects are confounded. Full-protocol loading and interaction controls remain limited.'
             if has_lite else 'Independent loading and interaction controls remain outside this six-process analysis.'),
            'This report never chooses a source, authors a next round, or writes a training episode.']}


def markdown(report):
    lines=[f"Level2 optimization: {report['status']}",f"Registered rounds: {report['registered_rounds']}; closed rounds: {report['completed_rounds']}",'',
           '| Operator | Status | Registered / closed | Final source | Final evaluation |','|---|---|---:|---|---|']
    for row in report['operators']:
        selected=row['final_selection'];lines.append(f"| {row['operator']} | {row['status']} | {row['registered_rounds']} / {row['completed_rounds']} | {selected.get('candidate_id','pending')} | {row.get('final_evaluation','pending')} |")
    lines+=['','Per-case normal/swapped effects, key aggregates and exact evidence references are in the JSON report.']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path);parser.add_argument('--markdown',type=Path);args=parser.parse_args()
    result=build_report(args.run);data=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
    for path,body in ((args.output,data),(args.markdown,markdown(result))):
        if path is not None:
            target=path.resolve();run=args.run.resolve()
            require(not any(target.is_relative_to(run/split/'ledger') for split in ('train','validation')),'report cannot write into a ledger')
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('x') as stream:stream.write(body)
    if args.output is None:print(data,end='')


if __name__=='__main__':main()
