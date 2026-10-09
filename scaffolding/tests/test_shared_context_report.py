"""Synthetic CPU tests: process is the replication unit, never pair/call."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('shared_context_report', ROOT/'scaffolding/collection/scripts/shared_context_report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
H = 'sha256:' + 'a'*64


def fixture(stages=('ab',), ratios=None, absolute=None, case_ids=('small','large')):
    ratios = ratios or [1.1]*6
    absolute = absolute or [100]*6
    ids = {r:dict(source_hash=H,binary_hash=H,entry='entry_'+r) for r in 'AB'}
    cases = [dict(case_id=c,attributes={'kind':'tensorlist','members':2},input_hash=H,oracle_hash=H,launches_per_call={'A':2,'B':1}) for c in case_ids]
    manifest = dict(protocol_version=report.PROTOCOL,analysis_version=report.ANALYSIS,comparison_id='comparison',run_id='run',task_id='task',attempt_id='attempt',comparison_kind='parent',cases=cases,identities=ids,control_identities=copy.deepcopy(ids),harness_hash=H,hardware=dict(host='cpu-fixture',physical_chip='chip0',logical_device=0,environment_hash=H),qualification_scope={'kind':'synthetic'},seed=1,stages=list(stages),session_plan=[])
    sessions = []
    for phase in stages:
        for r in range(1,7):
            loads = ('AB','BA') if r%2 else ('BA','AB')
            for l in (loads if phase=='qualification' else ('AB',)):
                sid = phase+'-'+str(r)+'-'+l
                buffers = (['normal','swapped'] if r%2 else ['swapped','normal']) if phase=='qualification' else (['swapped'] if phase=='reverse' else ['normal'])
                first = 'AB' if r%2 else 'BA'
                plan = dict(session_id=sid,phase=phase,replicate_id=r,block_id=r if phase=='qualification' else None,load_order=l,buffer_configs=buffers,first_order=first,case_order=list(case_ids))
                manifest['session_plan'].append(plan)
                session = dict(session_id=sid,pid=100+len(sessions),host='cpu-fixture',started_at=1+10*len(sessions),ended_at=10+10*len(sessions),context_id='ctx',stream_id='stream',exit_code=0,identities=copy.deepcopy(ids),samples=[],outputs=[],resource_events=[],lifecycle_events=[],argv=['synthetic'],cwd='/synthetic',log_hash=H)
                for ci,c in enumerate(case_ids):
                    for u in buffers:
                        for j in range(30):
                            order = first if j%2==0 else first[::-1]
                            for position,role in enumerate(order):
                                ns = absolute[r-1]*(ci+1)*(ratios[r-1] if role=='A' and phase=='ab' else 1)
                                sample = dict(sample_id=f'{sid}/{c}/{u}/{j}/{role}',session_id=sid,case_id=c,buffer_config=u,pair_id=j,role=role,order=order,position=position,started_at=session['started_at']+.001*(len(session['samples'])+1),ended_at=session['started_at']+.001*(len(session['samples'])+1)+.0005,raw_duration=ns*100/1e6,raw_unit='ms',to_ns=1e6,repeat=100,ns_per_call=ns,launches_per_call=(1 if role=='B' and phase=='ab' else 2),context_id='ctx',stream_id='stream')
                                session['samples'].append(sample)
                        for role in 'AB':
                            session['outputs'].append(dict(case_id=c,buffer_config=u,role=role,passed=True,validation_scope='last_formal_sample_final_output',pair_id=29))
                session['lifecycle_events']=[dict(type='session_start',session_id=sid,**{k:session[k] for k in ('pid','host','started_at','context_id','stream_id')},load_order=l,first_order=first,device=0,vector_cores=32)]
                for ci,c in enumerate(case_ids):
                    for u in buffers:
                        common=dict(session_id=sid,case_id=c,buffer_config=u)
                        session['lifecycle_events'].extend([dict(type='case_start',**common,case_index=ci,warmup_per_role=10,pairs=30,repeat=100),dict(type='warmup_complete',**common,calls_per_role=10),dict(type='outputs_verified',**common,validator='external_oracle_ack')])
                        for role in 'AB':
                            session['resource_events'].append(dict(case_id=c,buffer_config=u,role=role,allocation_order='AB',input_policy='separate_identical_files',buffers=[dict(index=0,kind='input',bytes=4,address='input_'+role),dict(index=1,kind='output',bytes=4,address='output_'+role)]))
                session['lifecycle_events'].append(dict(type='session_end',session_id=sid,exit_code=0,ended_at=session['ended_at'],context_destroyed=True,stream_destroyed=True))
                sessions.append(session)
    return manifest,sessions


class SharedContextReportTests(unittest.TestCase):
    def test_common_mode_drift_keeps_fixed_ratios(self):
        m,s = fixture(absolute=[100,110,125,130,150,160])
        r = report.analyze(m,s)
        self.assertAlmostEqual(r['phases']['ab']['suite']['speedup'],1.1)
        self.assertEqual(r['phases']['ab']['suite']['n'],6)
        self.assertGreater(r['absolute_drift']['small']['ab']['A_relative_range'],.02)
        self.assertTrue(r['measurement_quality']['observed_checks_pass'])
        self.assertEqual(r['formal_admission'],'not_evaluated')

    def test_variable_process_ratios_widen_interval_despite_zero_cv(self):
        m,s = fixture(ratios=[.8,.9,1,1.1,1.2,1.3])
        r = report.analyze(m,s)
        self.assertTrue(all(v['A']['cv']==0 and v['B']['cv']==0 for v in r['cells']))
        e = r['phases']['ab']['suite']
        self.assertLess(e['ci95'][0],1)
        self.assertGreater(e['ci95'][1],1)
        self.assertEqual(e['df'],5)
        self.assertEqual(e['reproducibility_status'],'mixed_process_directions')
        self.assertEqual(len(e['log_effects']),6)

    def test_equal_case_weight_and_lcb_formula(self):
        m,s = fixture(ratios=[1]*6)
        for session in s:
            for v in session['samples']:
                if v['case_id']=='large' and v['role']=='A':
                    v['ns_per_call'] *= 4; v['raw_duration'] *= 4
        e = report.analyze(m,s)['phases']['ab']['suite']
        self.assertAlmostEqual(e['speedup'],2)
        self.assertAlmostEqual(e['lcb95'],2)
        e=report.effect([0,.01,.02,.03,.04,.05])
        self.assertAlmostEqual(e['lcb95'], math.exp(e['mean_log']-report.T_ONE*e['log_sd']/math.sqrt(6)))

    def test_qualification_and_all_routine_controls(self):
        m,s=fixture(stages=('qualification','before','reverse','ab','after'))
        r=report.analyze(m,s)
        self.assertTrue(r['measurement_quality']['observed_checks_pass'])
        self.assertEqual(len(r['qualification']['small']['conditions']),8)
        self.assertEqual(set(r['qualification']['small']['contrasts']),{'load','buffer','order'})
        self.assertTrue(r['measurement_quality']['routine_controls_complete'])

    def test_aa_load_contrast_full_difference(self):
        m,s=fixture(stages=('qualification',))
        for p,session in zip(m['session_plan'],s):
            for v in session['samples']:
                if p['load_order']=='AB' and v['role']=='A':
                    v['raw_duration'] *= 1.01; v['ns_per_call'] *= 1.01
        r=report.analyze(m,s)
        self.assertAlmostEqual(r['qualification']['small']['contrasts']['load']['mean_log'],math.log(1.01))
        self.assertFalse(r['measurement_quality']['observed_checks_pass'])

    def test_qualification_cv_each_buffer_configuration(self):
        m,s=fixture(stages=('qualification',))
        for session in s:
            for v in session['samples']:
                if v['buffer_config']=='swapped':
                    v['raw_duration']*=2;v['ns_per_call']*=2
        r=report.analyze(m,s)
        self.assertTrue(r['measurement_quality']['observed_checks_pass'])
        self.assertTrue(all(v['A']['cv']==0 for v in r['cells']))

    def test_wide_aa_interval_is_not_equivalence(self):
        summary=report.effect([-.01,.01,-.01,.01,-.01,.01])
        self.assertEqual(report.equivalence(summary),'precision_insufficient')
        self.assertLess(summary['log_ci95'][0],0)
        self.assertGreater(summary['log_ci95'][1],0)

    def test_readonly_verifier_detects_tamper(self):
        m,s=fixture(); r=report.analyze(m,s)
        original=copy.deepcopy((m,s,r))
        self.assertTrue(report.verify_report(m,s,r))
        self.assertEqual((m,s,r),original)
        r['phases']['ab']['suite']['speedup']=99
        with self.assertRaises(ValueError):report.verify_report(m,s,r)

    def test_bad_data_rejected(self):
        mutations=[lambda m,s:s[0]['samples'].pop(),lambda m,s:s[0]['samples'][0].update(ns_per_call=float('nan')),lambda m,s:s[0]['samples'][0].update(ns_per_call=0),lambda m,s:s[0]['samples'][0].pop('raw_unit'),lambda m,s:s[0]['samples'][0].update(to_ns=1),lambda m,s:s[0]['samples'][1].update(sample_id=s[0]['samples'][0]['sample_id']),lambda m,s:s[0]['samples'][0].update(buffer_config='swapped'),lambda m,s:s[0]['samples'][0].update(context_id='other'),lambda m,s:s[0].update(exit_code=1),lambda m,s:s[0]['outputs'][0].update(passed=False),lambda m,s:s[0]['samples'][0].update(launches_per_call=50),lambda m,s:s[0]['identities']['A'].update(entry='wrong'),lambda m,s:s[0]['samples'][0].update(extra=True),lambda m,s:m['session_plan'][0].update(case_order=['small']),lambda m,s:s.pop()]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                m,s=fixture();mutation(m,s)
                with self.assertRaises((ValueError,ValidationError)):report.analyze(m,s)

    def test_lifecycle_resources_and_timestamps_required(self):
        changes=[lambda s:s[0]['lifecycle_events'].pop(2),lambda s:s[0]['resource_events'].pop(),lambda s:s[0]['samples'][1].update(started_at=s[0]['started_at']),lambda s:s[0]['resource_events'][1]['buffers'][1].update(address=s[0]['resource_events'][0]['buffers'][1]['address'])]
        for change in changes:
            m,s=fixture();change(s)
            with self.assertRaises(ValueError):report.analyze(m,s)

    def test_unbalanced_and_missing_qualification_rejected(self):
        m,s=fixture(stages=('qualification',))
        m['session_plan'][0]['buffer_configs']=['normal']
        with self.assertRaises(ValueError):report.analyze(m,s)
        m,s=fixture();m['session_plan'][0]['first_order']='BA'
        with self.assertRaises(ValueError):report.analyze(m,s)


if __name__=='__main__':unittest.main()
