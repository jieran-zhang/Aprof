from __future__ import annotations
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('device_timing',ROOT/'scaffolding/collection/scripts/cannbench_device_timing.py')
timing=importlib.util.module_from_spec(spec); spec.loader.exec_module(timing)


def measurement(cases=(1,2), ratio=.8):
    rows=[]
    for case in cases:
        for i in range(30):
            # Cases differ by 1000x. Flattening raw latency would spuriously fail CV.
            value=1000.0**case*(1+(i%3-1)*.001)
            sample={'elapsed_ns':value,'device':0,'unit':'ns','source':'acl_event'}
            rows.append({'case_id':case,'round':i,'order':['baseline','candidate'] if i%2==0 else ['candidate','baseline'],
                         'baseline':sample,'candidate':dict(sample,elapsed_ns=value*ratio)})
    return {'unit':'ns','source':'acl_event','device':0,'case_ids':list(cases),'records':rows,'complete':True}


def conditioned_measurement(count=2, reverse=True):
    raw=measurement()
    raw.update(precondition_samples=count,reverse_startup=reverse,checkpoint_every_pair=False,warmup=10,repeat=100)
    startup=['candidate','baseline'] if reverse else ['baseline','candidate']
    raw['case_executions']=[{'case_id':case,'startup_order':startup} for case in raw['case_ids']]
    for row in raw['records']:
        row['preconditioning']={}
        for label in ('baseline','candidate'):
            row[label].update(warmup=10,repeat=100,sample_index=row['round']*(count+1)+count)
            row['preconditioning'][label]=[dict(row[label],sample_index=row['round']*(count+1)+offset,
                elapsed_ns=1e9*(offset+1)) for offset in range(count)]
    return raw


def graph_measurement():
    raw=conditioned_measurement()
    raw.update(capture_replay=True,execution_mode='acl_graph_replay',captured_operator_calls=100,
               timing_scope='complete_operator_device_graph_event_interval')
    for row in raw['records']:
        for label in ('baseline','candidate'):
            for sample in [row[label],*row['preconditioning'][label]]:
                sample.update(execution_mode='acl_graph_replay',captured_operator_calls=100)
    return raw


def single_context_measurement(count=1,reverse=False):
    raw=conditioned_measurement(count,reverse)
    raw.update(single_live_context=True,context_lifecycle='one_process_per_role_sample',
               verification_output_scope='last_process_output_per_role',pairs=30,host='fixture')
    for row in raw['records']:
        row.update(context_lifecycle=raw['context_lifecycle'],device=0,host=raw['host'])
        row['order']=['candidate','baseline'] if bool(row['round']%2)^reverse else ['baseline','candidate']
        for label in ('baseline','candidate'):
            row[label]['sample_index']=count
            for index,sample in enumerate(row['preconditioning'][label]):sample['sample_index']=index
    for execution in raw['case_executions']:
        case=execution['case_id'];base=case*10000
        execution.pop('startup_order')
        commands={label:{'argv':['/fixture/'+label,'--output',f'/fixture/case-{case:02d}-{label}.bin'],
                         'cwd':'/fixture/'+label} for label in ('baseline','candidate')}
        execution.update(context_lifecycle=raw['context_lifecycle'],commands=commands,started_at=base,
                         finished_at=base+200,exit_status=0,context_sessions=[],
                         verifications={label:{'started_at':base+180,'finished_at':base+190,'exit_status':0}
                                        for label in ('baseline','candidate')})
        for row in (row for row in raw['records'] if row['case_id']==case):
            for label in row['order']:
                position=len(execution['context_sessions']);start=base+2*position
                execution['context_sessions'].append({'round':row['round'],'label':label,**commands[label],
                    'log_path':f'/fixture/case-{case:02d}-round-{row["round"]:03d}-{label}.log',
                    'started_at':start,'finished_at':start+1,'started_monotonic_ns':start*1000000000,
                    'finished_monotonic_ns':(start+1)*1000000000,'exit_status':0,'pid':100+position,
                    'preconditioning_sample_indices':list(range(count)),'formal_sample_index':count})
    return raw


class DeviceTimingTests(unittest.TestCase):
    def test_equal_case_aggregation_is_not_flattened(self):
        report=timing.summarize_multicase(measurement(),[1,2])
        self.assertTrue(report['stable']); self.assertTrue(report['performance_eligible'])
        self.assertEqual(len(report['gate_projection']['baseline_samples_ns']),30)
        self.assertAlmostEqual(report['speedup'],1.25)
        self.assertAlmostEqual(report['per_case'][0]['regression'],-.2)
        self.assertAlmostEqual(report['gate_projection']['heldout_regressions'][0],-.2)
        self.assertAlmostEqual(report['gate_projection']['baseline_samples_ns'][1],1000**1.5)
    def test_one_case_noise_cannot_be_hidden_by_aggregation(self):
        raw=measurement()
        for row in raw['records']:
            if row['case_id']==1: row['candidate']['elapsed_ns']*=.5 if row['round']%2 else 1.5
        report=timing.summarize_multicase(raw,[1,2])
        self.assertFalse(report['stable']); self.assertEqual(report['gate_projection']['baseline_samples_ns'],[])
        self.assertEqual(len(report['per_case'][0]['candidate_samples_ns']),30)
    def test_missing_duplicate_bad_order_unit_and_device_fail_closed(self):
        for fault in ('missing','duplicate','unit','nan','device','order','incomplete'):
            raw=measurement()
            if fault=='missing': raw['records'].pop()
            elif fault=='duplicate': raw['records'].append(raw['records'][0])
            elif fault=='unit': raw['records'][0]['candidate']['unit']='us'
            elif fault=='nan': raw['records'][0]['candidate']['elapsed_ns']=float('nan')
            elif fault=='device': raw['records'][0]['candidate']['device']=1
            elif fault=='order': raw['records'][0]['order'].reverse()
            else: raw['complete']=False
            with self.subTest(fault=fault):
                result=timing.summarize_multicase(raw,[1,2]); self.assertFalse(result['stable'])
                self.assertEqual(result['gate_projection']['candidate_samples_ns'],[])
                json.dumps(result,allow_nan=False)
    def test_case_regression_is_not_hidden(self):
        raw=measurement()
        for row in raw['records']:
            if row['case_id']==1: row['candidate']['elapsed_ns']=row['baseline']['elapsed_ns']*1.04
        report=timing.summarize_multicase(raw,[1,2])
        self.assertTrue(report['stable']); self.assertFalse(report['performance_eligible'])
        self.assertAlmostEqual(report['max_case_regression'],.04)
    def test_noisy_failure_still_has_raw_case_evidence(self):
        raw=measurement(); raw['complete']=False
        report=timing.summarize_multicase(raw,[1,2]); self.assertIsNone(report['speedup_lcb_95'])
        self.assertEqual(len(report['per_case']),2)
    def test_instrument_all_hosts_without_touching_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in timing.OPERATORS:
                source=ROOT/'scaffolding/benchmarks/cannbench/operators'/name
                original=(source/'op_host'/f'{name}.asc').read_bytes()
                manifest=timing.instrument(source,Path(tmp)/name)
                changed=(Path(tmp)/name/'op_host'/f'{name}.asc').read_text()
                self.assertEqual(original,(source/'op_host'/f'{name}.asc').read_bytes())
                self.assertIn('aprof::Run(stream, device,',changed)
                self.assertEqual(manifest['operator'],name)
                if name=='foreach_norm':
                    self.assertIn('2*lengths.size()',changed)
                    self.assertIn('foreach_norm_finalize_kernel<<<1',changed)
                with self.assertRaises(FileExistsError): timing.instrument(source,Path(tmp)/name)
    def test_canonical_destination_is_rejected(self):
        source=ROOT/'scaffolding/benchmarks/cannbench/operators/exp'
        with self.assertRaises(ValueError): timing.instrument(source,source)
    def test_prepare_is_read_only_and_command_paths_are_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'inputs'
            info=timing.prepared_commands(ROOT/'scaffolding/benchmarks/cannbench/operators/foreach_norm',1,3,root)
            self.assertFalse(root.exists()); self.assertIsNone(info['argv'])
            metadata=Path(info['metadata']); metadata.parent.mkdir(parents=True)
            metadata.write_text(json.dumps({'lengths':[1,2],'dtype':'float16','scalar':1,'input':'/tmp/input','output':'/tmp/output'}))
            info=timing.prepared_commands(ROOT/'scaffolding/benchmarks/cannbench/operators/foreach_norm',1,3,root)
            self.assertIn('1,2',info['argv']); self.assertEqual(info['argv'][-1],'3')

    def test_preconditioning_is_retained_but_excluded_from_performance_projection(self):
        expected=timing.summarize_multicase(measurement(),[1,2])
        for count in (0,1,2):
            for reverse in (False,True):
                raw=conditioned_measurement(count,reverse)
                before=copy.deepcopy(raw)
                with self.subTest(count=count,reverse=reverse):
                    self.assertEqual(timing.summarize_multicase(raw,[1,2]),expected)
                    self.assertEqual(raw,before)

    def test_preconditioning_missing_extra_and_misindexed_evidence_fails_closed(self):
        mutations=[
            lambda raw:raw['records'][0].pop('preconditioning'),
            lambda raw:raw['records'][0]['preconditioning'].pop('candidate'),
            lambda raw:raw['records'][0]['preconditioning'].__setitem__('unknown',[]),
            lambda raw:raw['records'][0]['preconditioning']['candidate'].pop(),
            lambda raw:raw['records'][0]['preconditioning']['candidate'].append({}),
            lambda raw:raw['records'][0]['preconditioning']['candidate'][0].__setitem__('sample_index',1),
            lambda raw:raw['records'][0]['preconditioning']['candidate'][0].pop('sample_index'),
            lambda raw:raw['records'][1]['candidate'].__setitem__('sample_index',1),
            lambda raw:raw['records'][0]['candidate'].pop('sample_index'),
            lambda raw:raw['case_executions'][0].pop('startup_order'),
            lambda raw:raw['case_executions'][0].__setitem__('startup_order',['baseline','candidate']),
            lambda raw:raw.pop('precondition_samples'),
        ]
        for index,mutate in enumerate(mutations):
            raw=conditioned_measurement();mutate(raw)
            with self.subTest(mutation=index):
                report=timing.summarize_multicase(raw,[1,2])
                self.assertFalse(report['stable']);self.assertFalse(report['performance_eligible'])
                self.assertEqual(report['gate_projection']['candidate_samples_ns'],[])
                json.dumps(report,allow_nan=False)

    def test_invalid_preconditioning_values_and_metadata_are_rejected(self):
        faults=[('elapsed_ns',value) for value in [float('nan'),float('inf'),True,0,-1,'100']]
        faults += [('sample_index',False),('sample_index',-1),('device',1),('device',False),
                   ('unit','us'),('source','host_clock'),('warmup',11),('warmup',True),('repeat',99)]
        for field,value in faults:
            raw=conditioned_measurement()
            raw['records'][0]['preconditioning']['baseline'][0][field]=value
            with self.subTest(field=field,value=value):
                report=timing.summarize_multicase(raw,[1,2])
                self.assertFalse(report['stable']);json.dumps(report,allow_nan=False)
        for field in ('warmup','repeat','device','source','unit'):
            raw=conditioned_measurement();raw['records'][0]['preconditioning']['baseline'][0].pop(field)
            self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])
        raw=conditioned_measurement();raw['records'][0]['preconditioning']['baseline'][0]=None
        self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])

    def test_malformed_protocol_and_undeclared_preconditioning_are_rejected(self):
        faults=[('precondition_samples',v) for v in [-1,True,1.5,'2',None]]
        faults += [('reverse_startup',1),('checkpoint_every_pair',0),('warmup',None),('repeat',False)]
        for field,value in faults:
            raw=conditioned_measurement();raw[field]=value
            with self.subTest(field=field,value=value):
                self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])
        raw=measurement();raw['records'][0]['preconditioning']={'baseline':[],'candidate':[]}
        self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])

    def test_new_api_options_reject_invalid_types_before_collection(self):
        options=[{'precondition_samples':value} for value in [-1,True,1.5,'1']]
        options += [{'reverse_startup':1},{'checkpoint_every_pair':0},{'single_live_context':1}]
        for option in options:
            with self.subTest(option=option),self.assertRaises(ValueError):
                timing.collect_pair_suite('/nonexistent','/nonexistent',[1],0,'/nonexistent',**option)

    def test_cli_passes_new_controls_without_running_hardware(self):
        argv=['timing','measure','--baseline','base','--candidate','candidate','--cases','1,8',
              '--device','0','--output','result','--precondition-samples','2','--reverse-startup','--case-checkpoints-only']
        with mock.patch.object(timing.sys,'argv',argv),mock.patch.object(timing,'collect_pair_suite',return_value={}) as collect, mock.patch('builtins.print'):
            timing.main()
        self.assertEqual(collect.call_args.kwargs,{'external_lock':False,'precondition_samples':2,
                         'reverse_startup':True,'checkpoint_every_pair':False,'reuse_verifier':False,'capture_replay':False,
                         'single_live_context':False})

    def test_single_context_indices_reset_and_preconditioning_stays_out_of_projection(self):
        expected=timing.summarize_multicase(measurement(),[1,2])
        expected.update(single_live_context=True,context_lifecycle='one_process_per_role_sample',
                        verification_output_scope='last_process_output_per_role')
        for count in (0,1,2):
            for reverse in (False,True):
                with self.subTest(count=count,reverse=reverse):
                    raw=single_context_measurement(count,reverse);before=copy.deepcopy(raw)
                    self.assertEqual(timing.summarize_multicase(raw,[1,2]),expected)
                    self.assertEqual(raw,before)

    def test_single_context_lifecycle_and_complete_session_evidence_are_required(self):
        mutations=[
            lambda raw:raw.pop('single_live_context'),
            lambda raw:raw.__setitem__('single_live_context',False),
            lambda raw:raw.__setitem__('single_live_context',1),
            lambda raw:raw.pop('context_lifecycle'),
            lambda raw:raw.pop('verification_output_scope'),
            lambda raw:raw.pop('precondition_samples'),
            lambda raw:raw.__setitem__('pairs',31),
            lambda raw:raw.__setitem__('pairs',True),
            lambda raw:raw['records'][0].pop('context_lifecycle'),
            lambda raw:raw['records'][1]['baseline'].__setitem__('sample_index',3),
            lambda raw:raw['records'][1]['preconditioning']['candidate'][0].__setitem__('sample_index',2),
            lambda raw:raw['records'][0]['order'].reverse(),
            lambda raw:raw['case_executions'][0].pop('context_sessions'),
            lambda raw:raw['case_executions'][0]['context_sessions'].pop(),
            lambda raw:raw['case_executions'][0]['context_sessions'].append({}),
            lambda raw:raw['case_executions'][0].__setitem__('startup_order',['baseline','candidate']),
            lambda raw:raw['case_executions'][0].pop('context_lifecycle'),
            lambda raw:raw['case_executions'][0].pop('verifications'),
            lambda raw:raw['case_executions'][0]['verifications']['baseline'].__setitem__('exit_status',1),
            lambda raw:raw['case_executions'][0]['verifications']['baseline'].__setitem__('started_at',10001),
        ]
        for index,mutate in enumerate(mutations):
            raw=single_context_measurement();mutate(raw)
            with self.subTest(mutation=index):
                result=timing.summarize_multicase(raw,[1,2])
                self.assertFalse(result['stable']);self.assertEqual(result['gate_projection']['baseline_samples_ns'],[])
                json.dumps(result,allow_nan=False)

    def test_single_context_session_timestamps_identity_exit_and_native_indices_fail_closed(self):
        faults=[('round',1),('round',False),('label','candidate'),('argv',['/unexpected']),('cwd','/different'),
                ('log_path','/fixture/case-01-round-000-candidate.log'),('pid',None),('pid',False),
                ('exit_status',1),('exit_status',False),('started_at',float('nan')),('finished_at',9999),
                ('started_monotonic_ns',None),('finished_monotonic_ns',0),('formal_sample_index',2),
                ('formal_sample_index',True),('preconditioning_sample_indices',[]),
                ('preconditioning_sample_indices',[False]),('error',{'type':'RuntimeError'})]
        for key,value in faults:
            raw=single_context_measurement();raw['case_executions'][0]['context_sessions'][0][key]=value
            with self.subTest(key=key,value=value):
                result=timing.summarize_multicase(raw,[1,2]);self.assertFalse(result['stable'])
                json.dumps(result,allow_nan=False)
        for key in ('started_at','started_monotonic_ns'):
            raw=single_context_measurement();sessions=raw['case_executions'][0]['context_sessions']
            sessions[1][key]=sessions[0][key]
            self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])
        raw=single_context_measurement()
        raw['case_executions'][1]['context_sessions'][0]['started_monotonic_ns']=1
        self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])

    def test_single_context_cli_is_explicit(self):
        argv=['timing','measure','--baseline','base','--candidate','candidate','--device','0','--output','result',
              '--single-live-context','--reverse-startup']
        with mock.patch.object(timing.sys,'argv',argv),mock.patch.object(timing,'collect_pair_suite',return_value={}) as collect,mock.patch('builtins.print'):
            timing.main()
        self.assertTrue(collect.call_args.kwargs['single_live_context'])
        self.assertTrue(collect.call_args.kwargs['reverse_startup'])

    def test_graph_mode_preserves_aggregation_but_records_a_distinct_scope(self):
        expected=timing.summarize_multicase(conditioned_measurement(),[1,2])
        expected.update(execution_mode='acl_graph_replay',captured_operator_calls=100,
                        timing_scope='complete_operator_device_graph_event_interval')
        self.assertEqual(timing.summarize_multicase(graph_measurement(),[1,2]),expected)

    def test_mixed_or_misdeclared_graph_samples_are_rejected(self):
        mutations=[
            lambda raw:raw.__setitem__('capture_replay',False),
            lambda raw:raw.__setitem__('execution_mode','host_loop'),
            lambda raw:raw.__setitem__('captured_operator_calls',99),
            lambda raw:raw.__setitem__('timing_scope','complete_operator_device_event_interval'),
            lambda raw:raw['records'][0]['baseline'].pop('execution_mode'),
            lambda raw:raw['records'][0]['candidate'].__setitem__('captured_operator_calls',1),
            lambda raw:raw['records'][0]['candidate'].__setitem__('captured_operator_calls',True),
            lambda raw:raw['records'][0]['preconditioning']['baseline'][0].pop('captured_operator_calls'),
            lambda raw:raw['records'][0]['preconditioning']['candidate'][0].__setitem__('execution_mode','host_loop')]
        for index,mutate in enumerate(mutations):
            raw=graph_measurement();mutate(raw)
            with self.subTest(mutation=index):
                report=timing.summarize_multicase(raw,[1,2])
                self.assertFalse(report['stable']);json.dumps(report,allow_nan=False)
        raw=measurement();raw['records'][0]['candidate'].update(execution_mode='acl_graph_replay',captured_operator_calls=100)
        self.assertFalse(timing.summarize_multicase(raw,[1,2])['stable'])

    def test_reused_verifier_markers_do_not_change_mathematical_summary(self):
        raw=measurement();expected=timing.summarize_multicase(raw,[1,2])
        raw.update(verification_protocol='in_process_reuse_v1',verifier_source_hash='sha256:'+'a'*64)
        self.assertEqual(timing.summarize_multicase(raw,[1,2]),expected)

    def test_cli_enables_reuse_and_graph_capture_explicitly(self):
        argv=['timing','measure','--baseline','base','--candidate','candidate','--device','0','--output','result',
              '--reuse-verifier','--capture-replay']
        with mock.patch.object(timing.sys,'argv',argv),mock.patch.object(timing,'collect_pair_suite',return_value={}) as collect,mock.patch('builtins.print'):
            timing.main()
        self.assertTrue(collect.call_args.kwargs['reuse_verifier'])
        self.assertTrue(collect.call_args.kwargs['capture_replay'])


class CollectionControlTests(unittest.TestCase):
    def collect(self, root, *, cases=(1,2), fail_at=None, verification_failure=False, inherited_capture=None,
                close_failure=False, startup_failure=False, **options):
        root=Path(root);baseline=root/'baseline';candidate=root/'candidate';prepared=root/'prepared';out=root/'result'
        for tree in (baseline,candidate):
            (tree/'op_host').mkdir(parents=True);(tree/'op_host/exp.asc').write_text('fixture')
            (tree/'build').mkdir();(tree/'build/exp').write_bytes(b'fake executable: never launched')
            (tree/'scripts').mkdir()
            (tree/'scripts/verify_result.py').write_text('''import argparse, json
from pathlib import Path
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--metadata',required=True)
    path=Path(parser.parse_args().metadata);metadata=json.loads(path.read_text())
    result={'passed':not metadata.get('fail_verification',False)}
    (path.parent/'result.json').write_text(json.dumps(result));print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)
if __name__ == '__main__': main()
''')
        input_path=root/'input.bin';input_path.write_bytes(b'input')
        for case in cases:
            path=prepared/f'case_{case:02d}/metadata.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'numel':1,'dtype':'float32','input':str(input_path),
                'base':-1,'scale':1,'shift':0,'output':str(root/'unused.bin'),'fail_verification':verification_failure}))
        calls=[];checkpoints=[];children=[]
        class Child:
            def __init__(self,argv,cwd,env,log_path,timeout):
                self.label=Path(cwd).name;self.index=0;self.log=SimpleNamespace(closed=False)
                self.capture=env.get('APROF_CAPTURE_REPLAY')
                self.process=SimpleNamespace(pid=100+len(children),returncode=None)
                if startup_failure:raise RuntimeError('injected startup failure')
                children.append(self);calls.append(('start',self.label))
            def sample(self):
                if fail_at==(self.label,self.index):raise RuntimeError('injected sample failure')
                row={'elapsed_ns':1000.0,'operator':'exp','device':0,'unit':'ns','source':'acl_event',
                     'warmup':10,'repeat':100,'sample_index':self.index}
                if self.capture=='1':row.update(execution_mode='acl_graph_replay',captured_operator_calls=100)
                calls.append(('sample',self.label,self.index));self.index+=1
                return row
            def close(self,abort=False):
                self.log.closed=True;calls.append(('close',self.label,abort))
                self.process.returncode=-15 if abort else 1 if close_failure else 0
                if close_failure and not abort:raise RuntimeError('injected close failure')
        original_dump=timing.dump
        original_verifier=timing.ReusedVerifier
        def preload(path):
            calls.append(('preload',str(path)))
            verifier=original_verifier(path)
            original_run=verifier.run
            def run(metadata,**kwargs):
                if not all(child.log.closed for child in children):raise AssertionError('verification ran with live timing children')
                calls.append(('verify',str(metadata)))
                return original_run(metadata,**kwargs)
            verifier.run=run
            return verifier
        def checkpoint(value,path):
            if Path(path).name=='raw_measurements.json':checkpoints.append(copy.deepcopy(value))
            original_dump(value,path)
        completed=timing.subprocess.CompletedProcess([],0,stdout='verified fixture output')
        result=None;error=None
        environment={} if inherited_capture is None else {'APROF_CAPTURE_REPLAY':inherited_capture}
        with mock.patch.object(timing,'TimingChild',Child), mock.patch.object(timing,'ReusedVerifier',side_effect=preload), mock.patch.object(timing.subprocess,'run',return_value=completed) as verify, mock.patch.object(timing,'dump',side_effect=checkpoint), mock.patch.dict(timing.os.environ,environment,clear=True):
            try:
                result=timing.collect_pair_suite(baseline,candidate,cases,0,out,input_root=prepared,external_lock=True,**options)
            except Exception as failure:error=failure
        raw=json.loads((out/'raw_measurements.json').read_text())
        return SimpleNamespace(raw=raw,result=result,error=error,calls=calls,checkpoints=checkpoints,
                               children=children,verification_count=verify.call_count)

    def test_reverse_startup_native_indices_and_case_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=self.collect(tmp,precondition_samples=2,reverse_startup=True,checkpoint_every_pair=False)
        self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
        self.assertEqual([call for call in state.calls if call[0]=='start'],
                         [('start','candidate'),('start','baseline')]*2)
        self.assertEqual(state.verification_count,4)
        self.assertEqual([(len(x['records']),x['complete']) for x in state.checkpoints],[(30,False),(60,False),(60,True)])
        self.assertTrue(all(x['startup_order']==['candidate','baseline'] for x in state.raw['case_executions']))
        for row in state.raw['records']:
            for label in ('baseline','candidate'):
                self.assertEqual([x['sample_index'] for x in row['preconditioning'][label]],
                                 [row['round']*3,row['round']*3+1])
                self.assertEqual(row[label]['sample_index'],row['round']*3+2)
        first_samples=[call for call in state.calls if call[0]=='sample'][:12]
        self.assertEqual([call[1] for call in first_samples],['baseline']*3+['candidate']*6+['baseline']*3)

    def test_default_collection_keeps_legacy_raw_structure_and_pair_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:state=self.collect(tmp,cases=(1,))
        self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
        self.assertEqual(len(state.checkpoints),31)
        self.assertFalse({'precondition_samples','reverse_startup','checkpoint_every_pair'} & state.raw.keys())
        self.assertNotIn('startup_order',state.raw['case_executions'][0])
        self.assertTrue(all('preconditioning' not in row for row in state.raw['records']))
        self.assertEqual([call for call in state.calls if call[0]=='start'],[('start','baseline'),('start','candidate')])

    def test_failure_retains_each_native_precondition_without_pair_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=self.collect(tmp,cases=(1,),precondition_samples=2,checkpoint_every_pair=False,fail_at=('baseline',1))
        self.assertIsNotNone(state.error);self.assertFalse(state.raw['complete'])
        self.assertEqual(len(state.checkpoints),1);self.assertEqual(state.verification_count,0)
        [row]=state.raw['records']
        self.assertEqual([x['sample_index'] for x in row['preconditioning']['baseline']],[0])
        self.assertEqual(row['preconditioning']['candidate'],[])
        self.assertIsNone(row['baseline']);self.assertIsNone(row['candidate'])
        self.assertTrue(all(child.log.closed for child in state.children))
        self.assertFalse(timing.summarize_multicase(state.raw,[1])['stable'])

    def test_reuse_preloads_once_and_fully_verifies_both_outputs_after_children_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=self.collect(tmp,reuse_verifier=True)
            results=list((Path(tmp)/'result').glob('*-verification/result.json'))
            self.assertEqual(len(results),4)
            self.assertTrue(all(json.loads(path.read_text())['passed'] for path in results))
        self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
        self.assertEqual(state.calls[0][0],'preload')
        self.assertEqual(len([x for x in state.calls if x[0]=='preload']),1)
        self.assertEqual(len([x for x in state.calls if x[0]=='verify']),4)
        self.assertEqual(state.verification_count,0)
        self.assertEqual(state.raw['verification_protocol'],'in_process_reuse_v1')
        self.assertTrue(state.raw['verifier_source_hash'].startswith('sha256:'))
        for execution in state.raw['case_executions']:
            self.assertTrue(all(value['exit_status']==0 for value in execution['verifications'].values()))

    def test_reuse_failure_retains_log_result_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=self.collect(tmp,cases=(1,),reuse_verifier=True,verification_failure=True)
            result=Path(tmp)/'result/case-01-baseline-verification/result.json'
            self.assertFalse(json.loads(result.read_text())['passed'])
            self.assertIn('false',(Path(tmp)/'result/case-01-baseline-verify.log').read_text())
        self.assertIsInstance(state.error,timing.subprocess.CalledProcessError)
        self.assertFalse(state.raw['complete'])
        self.assertEqual(state.raw['case_executions'][0]['verifications']['baseline']['exit_status'],1)

    def test_graph_env_is_explicit_and_inherited_enable_is_cleared_by_default(self):
        for enabled in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                state=self.collect(tmp,cases=(1,),capture_replay=enabled,inherited_capture='1')
            self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
            self.assertTrue(all(child.capture==('1' if enabled else None) for child in state.children))
            self.assertEqual('capture_replay' in state.raw,enabled)

    def test_single_context_has_only_one_live_child_and_preserves_every_session(self):
        for reverse in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                state=self.collect(tmp,single_live_context=True,precondition_samples=2,reverse_startup=reverse,
                                   checkpoint_every_pair=False,reuse_verifier=True)
            self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
            self.assertEqual(len(state.children),120)
            active=0
            for call in state.calls:
                if call[0]=='start':active+=1;self.assertEqual(active,1)
                elif call[0]=='close':active-=1;self.assertEqual(active,0)
                elif call[0]=='verify':self.assertEqual(active,0)
            self.assertEqual(len([call for call in state.calls if call[0]=='verify']),4)
            self.assertEqual([(len(x['records']),x['complete']) for x in state.checkpoints],[(30,False),(60,False),(60,True)])
            for execution in state.raw['case_executions']:
                self.assertNotIn('startup_order',execution)
                self.assertEqual(len(execution['context_sessions']),60)
                self.assertEqual(len({session['log_path'] for session in execution['context_sessions']}),60)
                for session in execution['context_sessions']:
                    self.assertEqual(session['argv'],execution['commands'][session['label']]['argv'])
                    self.assertEqual(session['preconditioning_sample_indices'],[0,1])
                    self.assertEqual(session['formal_sample_index'],2)
                    self.assertEqual(session['exit_status'],0)
            for row in state.raw['records']:
                self.assertEqual(row['order'],['candidate','baseline'] if bool(row['round']%2)^reverse else ['baseline','candidate'])
                self.assertEqual([row[label]['sample_index'] for label in ('baseline','candidate')],[2,2])

    def test_single_context_zero_preconditioning_and_subprocess_verifier_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=self.collect(tmp,cases=(1,),single_live_context=True)
        self.assertIsNone(state.error);self.assertTrue(state.result['stable'])
        self.assertEqual(state.raw['precondition_samples'],0)
        self.assertEqual(state.verification_count,2)
        self.assertEqual(len(state.checkpoints),31)
        self.assertTrue(all(row['baseline']['sample_index']==0 for row in state.raw['records']))

    def test_single_context_failure_retains_partial_session_and_stops_before_next_role(self):
        for failure in ({'fail_at':('baseline',1)},{'close_failure':True},{'startup_failure':True}):
            with tempfile.TemporaryDirectory() as tmp:
                state=self.collect(tmp,cases=(1,),single_live_context=True,precondition_samples=2,
                                   checkpoint_every_pair=False,reuse_verifier=True,**failure)
            self.assertIsNotNone(state.error);self.assertFalse(state.raw['complete'])
            self.assertEqual(len(state.checkpoints),1)
            [execution]=state.raw['case_executions'];[session]=execution['context_sessions']
            self.assertIn('error',session);self.assertIsNotNone(session['finished_at'])
            self.assertEqual(len(state.children),0 if failure.get('startup_failure') else 1)
            self.assertTrue(all(child.log.closed for child in state.children))
            self.assertFalse(any(call[0]=='verify' for call in state.calls))
            self.assertFalse(timing.summarize_multicase(state.raw,[1])['stable'])


class ReusedVerifierTests(unittest.TestCase):
    def verifier(self,root,body):
        path=Path(root)/'verify_result.py'
        path.write_text(body)
        return path,timing.ReusedVerifier(path)

    def test_main_is_not_run_at_preload_and_stream_argv_cwd_are_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,verifier=self.verifier(tmp,'''import argparse, json
from pathlib import Path
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--metadata',required=True)
    value=parser.parse_args().metadata
    print(value);(Path.cwd()/'result.json').write_text(value)
if __name__ == '__main__': main()
''')
            self.assertFalse((Path(tmp)/'result.json').exists())
            argv=timing.sys.argv;stdout=timing.sys.stdout;stderr=timing.sys.stderr;cwd=Path.cwd()
            for value in ('first','second'):
                result=verifier.run(value,cwd=tmp)
                self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,value+'\n')
                self.assertEqual((Path(tmp)/'result.json').read_text(),value)
                self.assertIs(timing.sys.argv,argv);self.assertIs(timing.sys.stdout,stdout);self.assertIs(timing.sys.stderr,stderr)
                self.assertEqual(Path.cwd(),cwd)
            self.assertFalse((Path(tmp)/'__pycache__').exists())

    def test_exit_and_exception_semantics_are_retained(self):
        for action,code,text in [('raise SystemExit(0)',0,''),('raise SystemExit(3)',3,''),
                                 ('raise SystemExit("failure")',1,'failure'),('raise RuntimeError("broken")',1,'RuntimeError: broken')]:
            with tempfile.TemporaryDirectory() as tmp:
                path,verifier=self.verifier(tmp,'def main():\n    '+action+"\nif __name__ == '__main__': main()\n")
                argv=timing.sys.argv;stdout=timing.sys.stdout;stderr=timing.sys.stderr
                result=verifier.run('metadata')
                self.assertEqual(result.returncode,code);self.assertIn(text,result.stdout)
                self.assertIs(timing.sys.argv,argv);self.assertIs(timing.sys.stdout,stdout);self.assertIs(timing.sys.stderr,stderr)

    def test_unsupported_top_levels_and_global_state_are_rejected_without_fallback(self):
        sources=['print("side effect")\ndef main():pass\n',
                 'def main():pass\n',
                 'STATE=[]\ndef main():pass\n',
                 'def main():\n    global STATE\n    STATE=1\n',
                 'import sys\ndef main():pass\n']
        for source in sources:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'verify_result.py';path.write_text(source)
                with self.assertRaises(ValueError):timing.ReusedVerifier(path)

    def test_changed_source_after_preload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,verifier=self.verifier(tmp,"def main():pass\nif __name__ == '__main__': main()\n")
            path.write_text(path.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'changed after preload'):verifier.run('metadata')

if __name__=='__main__': unittest.main()
