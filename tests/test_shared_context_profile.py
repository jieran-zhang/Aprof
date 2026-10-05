"""CPU-only diagnostic protocol/CSV tests. Never compile or load native code."""
import contextlib
import csv
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
profile=importlib.import_module('cannbench_shared_context_profile')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.build={'operator':'foreach_norm','roles':{'A':{'source_dir':str(self.root),'source_sha256':'a'*64,'binary_sha256':'b'*64,'binary':str(self.root/'A.so'),'kernel_symbols':'partial_A,finalize_A'}}}

    def csv(self,name,rows):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['Op Name','Duration(us)']);writer.writeheader();writer.writerows(rows)
        return path

    def test_norm_profile_captures_five_full_lists_and_both_stages(self):
        contract=profile.protocol(self.build,'A',{'lengths':[1,2,3]})
        self.assertEqual(contract['launch_skip_before_match'],60);self.assertEqual(contract['launch_count'],30)
        self.csv('OpBasicInfo.csv',[{'Op Name':k,'Duration(us)':'1.0'} for _ in range(15) for k in ('partial_A','finalize_A')])
        self.csv('Memory.csv',[{'Op Name':'partial_A','Duration(us)':'1.0'} for _ in range(100)])
        result=profile.summarize_csv(self.root,contract)
        self.assertEqual(result['observed_kernel_counts'],{'partial_A':15,'finalize_A':15})
        self.assertEqual(len(result['kernel_launches']),30);self.assertEqual(len(result['artifacts']),2)
        self.assertFalse(result['gate'])

    def test_missing_stage_wrong_identity_and_missing_launch_fail(self):
        contract=profile.protocol(self.build,'A',{'lengths':[1]})
        for kernels in (['partial_A']*10,['partial_A','finalize_A']*4,['partial_A','wrong']*5):
            self.csv('OpBasicInfo.csv',[{'Op Name':k,'Duration(us)':'1'} for k in kernels])
            with self.assertRaises(ValueError):profile.summarize_csv(self.root,contract)

    def test_correctness_has_one_call_no_warmup_no_profiler_budget_limit(self):
        contract=profile.protocol(self.build,'A',{'lengths':[1]*101},mode='correctness')
        self.assertEqual(contract['warmup_complete_calls'],0);self.assertEqual(contract['profile_complete_calls'],1)
        self.assertEqual(contract['launch_skip_before_match'],0);self.assertEqual(contract['profiler_replay_warmup'],0)
        command=profile.native_command('/runner',self.build,'A',contract,self.root/'case.tsv',self.root)
        self.assertEqual(command[command.index('--mode')+1],'correctness');self.assertNotIn('msprof',command)
        with self.assertRaises(ValueError):profile.msprof_command('/runner',self.build,'A',contract,self.root/'case.tsv',self.root)
        with self.assertRaises(ValueError):profile.protocol(self.build,'A',{'lengths':[1]*101})

    def test_msprof_command_uses_kernel_counts_not_complete_call_counts(self):
        contract=profile.protocol(self.build,'A',{'lengths':[1,1]})
        command=profile.msprof_command('/runner',self.build,'A',contract,self.root/'case.tsv',self.root)
        self.assertIn('--launch-skip-before-match=40',command);self.assertIn('--launch-count=20',command)
        self.assertIn('--warm-up=10',command);self.assertIn('--mode',command)

    def correctness_fixture(self):
        source=self.root/'source';(source/'op_host').mkdir(parents=True);(source/'op_kernel').mkdir()
        (source/'op_host/exp.asc').write_text('// host');(source/'op_kernel/exp.h').write_text('// kernel')
        binary=self.root/'role.so';binary.write_bytes(b'role')
        role={'source_dir':str(source),'source_sha256':profile.source_hash(source),'binary_sha256':profile.sha(binary)[7:],'binary':str(binary),'kernel_symbols':'exp_A'}
        build={'operator':'exp','roles':{'A':role}};build_path=self.root/'build.json';build_path.write_text(json.dumps(build))
        runner=self.root/'runner';runner.write_bytes(b'runner');code=self.root/'runner.cpp';code.write_text('// diagnostic');abi=self.root/'abi.h';abi.write_text('// abi')
        runner_build={'runner':str(runner),'runner_hash':profile.sha(runner),'source_snapshot':str(code),'source_hash':profile.sha(code),'abi_snapshot':str(abi),'abi_hash':profile.sha(abi)}
        runner_path=self.root/'runner-build.json';runner_path.write_text(json.dumps(runner_build))
        opdir=self.root/'operator';(opdir/'scripts').mkdir(parents=True);(opdir/'scripts/verify_result.py').write_text('# original oracle')
        inputs=self.root/'inputs'
        for i in range(1,21):
            folder=inputs/f'case_{i:02d}';folder.mkdir(parents=True);(folder/'metadata.json').write_text('{"special": NaN, "nested": {"positive": Infinity, "negative": -Infinity}}')
        args=SimpleNamespace(output=str(self.root/'correctness'),cases=','.join(map(str,range(1,21))),role_build=str(build_path),runner_build=str(runner_path),role='A',input_root=str(inputs),opdir=str(opdir),device=0,cpu='0',timeout=1)
        return args,role

    def test_twenty_case_correctness_uses_only_native_calls_and_original_verifier(self):
        args,role=self.correctness_fixture();calls=[]
        def run(argv,*unused,**kwargs):
            calls.append(argv)
            if '--mode' in argv:
                self.assertEqual(argv[argv.index('--mode')+1],'correctness')
                output=Path(argv[argv.index('--output')+1]);output.write_bytes(b'correct')
                journal=Path(argv[argv.index('--journal')+1])
                journal.write_text(json.dumps(dict(version='shared_context_profile_native_v1',host=profile.socket.gethostname(),physical_device='0',logical_device='0',mode='correctness',exit_code=0,role='A',source_sha256=role['source_sha256'],kernel_symbols='exp_A',warmup_complete_calls=0,profile_complete_calls=1,launches_per_call=1,output=str(output),validation_scope='single_complete_correctness_call',stream_destroyed=True,context_destroyed=True,finalized=True,context_id='ctx',stream_id='stream')))
        with mock.patch.object(profile,'exclusive_host',return_value=contextlib.nullcontext()),mock.patch.object(profile,'health'),mock.patch.object(profile,'command_from_metadata',return_value=['unused','--n','1']),mock.patch.object(profile,'run_logged',side_effect=run):
            result=profile.correctness(args)
        self.assertEqual(result['passed'],20);self.assertFalse(result['performance_evaluated'])
        self.assertEqual(len(calls),40);self.assertFalse(any('msprof' in command for command in calls))
        self.assertEqual(sum('--metadata' in command for command in calls),20)
        restored=profile.read_metadata(Path(args.output)/'case_01/verification-metadata.json')
        self.assertTrue(math.isnan(restored['special']));self.assertEqual(restored['nested']['positive'],math.inf)
        completion=json.loads((Path(args.output)/'completion.json').read_text());self.assertEqual(completion['status'],'passed')

    def test_historical_timestamped_csv_header_and_directory_identity(self):
        contract=profile.protocol(self.build,'A',{'lengths':[1]})
        header='Op Name,Op Type,Task Duration(us),Block Dim,Mix Block Dim,Device Id,Pid,Current Freq,Rated Freq,\n'
        for kernel in ('partial_A','finalize_A'):
            for index in range(5):
                path=self.root/'OPPROF_fixture'/kernel/str(index)/'OpBasicInfo_20260908120356481.csv'
                path.parent.mkdir(parents=True);path.write_text(header+kernel+',vector,1.0,4,NA,0,123,1850,1850,\n')
        result=profile.summarize_csv(self.root,contract)
        self.assertEqual(result['launch_count'],10)
        path=next(self.root.rglob('*.csv'));path.write_text(path.read_text().replace('Op Name,','Kernel Name,',1))
        self.assertEqual(profile.summarize_csv(self.root,contract)['launch_count'],10)

    def test_opaque_metadata_does_not_relax_finite_report_json(self):
        path=self.root/'metadata.json';path.write_text('{"x":NaN,"nested":{"a":Infinity}}')
        metadata=profile.read_metadata(path)
        self.assertTrue(math.isnan(metadata['x']))
        profile.save_metadata(self.root/'oracle.json',metadata)
        self.assertTrue(math.isinf(profile.read_metadata(self.root/'oracle.json')['nested']['a']))
        with self.assertRaises(ValueError):profile.save(self.root/'report.json',metadata)

    def test_signal_during_popen_is_deferred_until_owned_handle_cleanup(self):
        process=mock.Mock(pid=12345,returncode=-15);process.communicate.return_value=('interrupted','')
        previous=profile.signal.getsignal(profile.signal.SIGTERM)
        def launch(*args,**kwargs):
            profile.signal.getsignal(profile.signal.SIGTERM)(profile.signal.SIGTERM,None)
            return process
        with mock.patch.object(profile.subprocess,'Popen',side_effect=launch),mock.patch.object(profile.os,'killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):profile.run_logged(['native'],self.root/'interrupted',{'ASCEND_RT_VISIBLE_DEVICES':'3'},1)
        kill.assert_called_once_with(12345,profile.signal.SIGTERM)
        self.assertEqual(profile.signal.getsignal(profile.signal.SIGTERM),previous)
        record=json.loads((self.root/'interrupted.execution.json').read_text())
        self.assertEqual(record['physical_device'],'3');self.assertEqual(record['host'],profile.socket.gethostname())

    def test_timeout_reaps_process_group_and_retains_logs(self):
        process=mock.Mock(pid=12345,returncode=-15)
        process.communicate.side_effect=[subprocess.TimeoutExpired(['native'],.01),('partial','timeout')]
        with mock.patch.object(profile.subprocess,'Popen',return_value=process),mock.patch.object(profile.os,'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):profile.run_logged(['native'],self.root/'process',{},.01)
        kill.assert_called_once_with(12345,profile.signal.SIGTERM)
        record=json.loads((self.root/'process.execution.json').read_text());self.assertEqual(record['error']['type'],'TimeoutExpired')
        self.assertEqual((self.root/'process.stdout.log').read_text(),'partial')


if __name__=='__main__':unittest.main()
