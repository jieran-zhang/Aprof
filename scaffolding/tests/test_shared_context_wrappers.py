"""Tiny, CPU-only wrapper evidence fixtures; every execution and ledger is mocked."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scaffolding/collection/scripts'))
import run_shared_context_qualification as qualification
import run_shared_context_diagnostic as diagnostic
import shared_context_wrapper_evidence as evidence


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.run=Path(self.temp.name)/'run';self.task=self.run/'tasks/exp'
        self.baseline=self.task/'baseline';(self.baseline/'op_host').mkdir(parents=True);(self.baseline/'op_kernel').mkdir();(self.baseline/'scripts').mkdir()
        for name,text in [('op_host/exp.asc','host'),('op_kernel/exp.h','kernel'),('CMakeLists.txt','cmake'),('scripts/verify_result.py','oracle')]: (self.baseline/name).write_text(text)
        self.archive=self.task/'baseline-source.tar';self.make_archive(self.baseline,self.archive)
        self.binding={'path':str(self.archive),'sha256':evidence.sha(self.archive)};self.write(self.task/'baseline-binding.json',self.binding)
        self.build=self.make_build(self.task/'aa-build',self.baseline,self.baseline)
        inputs=self.task/'inputs';data=self.task/'input.bin';data.write_bytes(b'input');rows=[]
        for case in range(1,21):
            attributes={'case_id':case,'dtype':'float32','numel':1,'shape':[1]}
            metadata=inputs/f'case_{case:02d}/metadata.json';self.write(metadata,{'input':str(data),**attributes})
            rows.append(dict(case_id=case,metadata=self.ref(metadata),inputs={'input':self.ref(data)},verifier=self.ref(self.baseline/'scripts/verify_result.py'),oracle_file=None,attributes=attributes))
        self.write(self.task/'input-bindings.json',{'cases':rows});self.write(self.run/'bootstrap/environment.json',{})
        runner=self.run/'tools/diagnostic/runner';runner.parent.mkdir(parents=True);runner.write_bytes(b'runner')
        self.write(runner.parent/'profile-build.json',{'runner':str(runner),'runner_hash':evidence.sha(runner)})
        self.make_memory_plan()
        self.ledger=mock.Mock();self.ledger.state={'tasks':{'exp':{'stages':{}}}};self.output=io.StringIO()

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n')

    def ref(self,path):return {'path':str(path),'sha256':evidence.sha(path)}

    def make_archive(self,source,path):
        from prepare_trace_pilot import create_source_snapshot
        return create_source_snapshot(source,path,root_label='synthetic-wrapper-test')

    def make_build(self,directory,source_a,source_b):
        directory.mkdir(parents=True,exist_ok=True);roles={}
        for role,source in [('A',source_a),('B',source_b)]:
            binary=directory/(role+'.so');binary.write_bytes(role.encode()+b'binary')
            generated=directory/role;adapter=generated/'op_host/exp.asc';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text('prepared '+role)
            kernel=generated/'op_kernel/exp.h';kernel.parent.mkdir(parents=True,exist_ok=True);kernel.write_bytes((source/'op_kernel/exp.h').read_bytes())
            roles[role]=dict(adapter_sha256=evidence.sha(adapter)[7:],source_dir=str(source),source_sha256=evidence.source_hash(source),cmake_sha256=evidence.sha(source/'CMakeLists.txt')[7:],binary=str(binary),binary_sha256=evidence.sha(binary)[7:],kernel_symbols='exp_'+role)
        build={'operator':'exp','roles':roles};self.write(directory/'build_manifest.json',build);return build

    def make_memory_plan(self):
        from shared_context_memory_plan import plan
        build_path=self.task/'aa-build/build_manifest.json';audit={'version':'shared_context_resource_audit_v1','harness':[],'adapters':[]};sizeof={'entries':[]}
        for role,identity in self.build['roles'].items():
            directory=build_path.parent/role;adapter=directory/'op_host/exp.asc';kernel=directory/'op_kernel/exp.h'
            entry=dict(role=role,operator='exp',type='ExpTilingData',adapter_path=str(adapter),adapter_sha256=evidence.sha(adapter)[7:],header_path=str(kernel),header_sha256=evidence.sha(kernel)[7:],kernel_path=str(kernel),kernel_sha256=evidence.sha(kernel)[7:],source_sha256=identity['source_sha256'])
            audit['adapters'].append(entry)
            proof={k:entry[k] for k in ('adapter_sha256','header_sha256','kernel_sha256','source_sha256','type')};proof.update(bytes=40,alignof=8,size_t_bytes=8)
            proof_path=self.run/'bootstrap'/('sizeof-'+role+'.json');self.write(proof_path,proof)
            sizeof['entries'].append(dict(**proof,compiler_command=['synthetic-asc'],compiler_sha256='a'*64,compiler_version='synthetic test only',cmake_parameters=['-S','.'],evidence_path=str(proof_path),evidence_sha256=evidence.sha(proof_path)[7:]))
        audit_path=self.run/'bootstrap/resource-preflight-audit.json';sizeof_path=self.run/'bootstrap/sizeof-metadata.json';self.write(audit_path,audit);self.write(sizeof_path,sizeof)
        records=[]
        for row in evidence.load(self.task/'input-bindings.json')['cases']:
            request=dict(case=row['attributes'],cores=48,buffer_configs=['normal','swapped'],roles={r:str(build_path.parent/r/'op_host/exp.asc') for r in ('A','B')})
            records.append({'case_id':row['case_id'],'request':request,'plan':plan(audit,sizeof,request)})
        self.write(self.task/'baseline-memory-plan.json',{'label':'baseline','prospective':True,'provenance':{'audit':evidence.sha(audit_path),'sizeof':evidence.sha(sizeof_path)},'cases':records})

    def prepare(self,args):
        out=Path(args.output);out.mkdir();self.write(out/'manifest.json',{'prepared':True})

    def test_qualification_interrupt_and_truncated_row_finish_ledger_with_costs(self):
        def execute(*unused,**kwargs):
            session=self.task/'qualification/session';session.mkdir();self.write(session/'started.json',{})
            rows=[{'type':'process_start'},{'type':'warmup_complete','calls_per_role':10},{'type':'sample','repeat':100}]
            (session/'journal.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"type":"sample",')
            raise KeyboardInterrupt('controller stop')
        with mock.patch.object(qualification,'prepare',side_effect=self.prepare),mock.patch.object(qualification,'Ledger',return_value=self.ledger),mock.patch.object(qualification,'run_process',side_effect=execute),contextlib.redirect_stdout(self.output):
            result=qualification.run(self.run,'exp',[1])
        self.assertEqual(result['status'],'execution_failed');self.assertEqual(result['error']['type'],'KeyboardInterrupt')
        finish=self.ledger.finish_stage.call_args.kwargs;self.assertEqual(finish['outcome'],'failed');self.assertEqual(finish['formal_samples'],1)
        self.assertEqual(finish['actual_costs']['native_sessions_attempted'],1);self.assertEqual(finish['actual_costs']['timed_complete_calls'],100)
        self.assertEqual(finish['actual_costs']['warmup_complete_calls'],20);self.assertEqual(finish['actual_costs']['unparsed_raw_rows'],1)
        self.assertTrue((self.task/'qualification-result.json').exists());self.assertTrue((self.task/'qualification/producers/run_shared_context_qualification.py').exists())
        self.assertTrue((self.task/'qualification/session/journal.jsonl').read_text().endswith('{"type":"sample",'))

    def test_success_exit_without_report_is_archived_failure(self):
        with mock.patch.object(qualification,'prepare',side_effect=self.prepare),mock.patch.object(qualification,'Ledger',return_value=self.ledger),mock.patch.object(qualification,'run_process'),contextlib.redirect_stdout(self.output):
            result=qualification.run(self.run,'exp',[1])
        self.assertEqual(result['status'],'execution_failed');self.assertIn('did not produce a report',result['error']['message'])
        self.ledger.finish_stage.assert_called_once()

    def rewrite_archive(self,change):
        with tarfile.open(self.archive) as archive:
            entries=[(member,archive.extractfile(member).read()) for member in archive if member.isfile()]
        change(entries)
        with tarfile.open(self.archive,'w',format=tarfile.PAX_FORMAT) as archive:
            for member,data in entries:
                member.size=len(data);archive.addfile(member,io.BytesIO(data))
        self.binding=self.ref(self.archive)

    def test_real_snapshot_manifest_is_validated_against_tar_contents(self):
        bound=evidence.archive_native_binding(self.binding,self.build,('A','B'))
        self.assertEqual(bound['snapshot_kind'],'aprof_source_snapshot_v1');self.assertEqual(bound['snapshot_file_count'],4)
        self.binding.update(file_count=4,manifest_sha256=bound['snapshot_manifest_hash'])
        evidence.archive_native_binding(self.binding,self.build,('A',))
        self.binding['manifest_sha256']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'manifest hash differs'):evidence.archive_native_binding(self.binding,self.build,('A',))

    def test_changed_manifest_file_hash_or_unlisted_tar_file_is_rejected(self):
        original=self.archive.read_bytes()
        for mutation in ('hash','omitted','unknown_root'):
            self.archive.write_bytes(original)
            def change(entries):
                if mutation=='unknown_root':
                    member=tarfile.TarInfo('UNDECLARED.json');entries.append((member,b'{}'));return
                index=next(i for i,(m,data) in enumerate(entries) if m.name=='APROF_SOURCE_SNAPSHOT.json')
                member,data=entries[index];manifest=json.loads(data)
                if mutation=='hash':manifest['files'][0]['sha256']='sha256:'+'0'*64
                else:manifest['files'].pop()
                entries[index]=(member,json.dumps(manifest).encode())
            self.rewrite_archive(change)
            with self.assertRaisesRegex(ValueError,'unknown archive root|manifest files do not match'):
                evidence.archive_native_binding(self.binding,self.build,('A',))

    def test_extra_native_dependency_cannot_borrow_baseline_archive(self):
        (self.baseline/'op_kernel/unarchived.h').write_text('extra')
        with self.assertRaisesRegex(ValueError,'coverage differs'):evidence.archive_native_binding(self.binding,self.build,('A',))
        with mock.patch.object(qualification,'prepare') as prepare,mock.patch.object(qualification,'Ledger',return_value=self.ledger),mock.patch.object(qualification,'run_process') as execute,contextlib.redirect_stdout(self.output):
            result=qualification.run(self.run,'exp',[1])
        self.assertFalse(result['ledger_stage_started']);prepare.assert_not_called();execute.assert_not_called();self.ledger.start_stage.assert_not_called()

    def test_native_source_bytes_must_match_candidate_archive(self):
        candidate=self.task/'candidates/exp002';source=candidate/'source';shutil.copytree(self.baseline,source)
        (source/'op_kernel/exp.h').write_text('candidate kernel');archive=candidate/'source.tar';self.make_archive(source,archive)
        wrong_build=self.make_build(candidate/'ab-build',self.baseline,self.baseline)
        with self.assertRaisesRegex(ValueError,'differs from archive'):evidence.archive_native_binding(self.ref(archive),wrong_build,('B',))

    def diagnostic_args(self,stage='correctness',cases=None):
        return SimpleNamespace(run=str(self.run),operator='exp',candidate='baseline',group='one',stage=stage,cases=cases or ','.join(map(str,range(1,21))))

    def complete_case(self,directory,stage='correctness'):
        directory.mkdir(parents=True)
        self.write(directory/'native.json',{'exit_code':0,'mode':stage,'warmup_complete_calls':0 if stage=='correctness' else 10,'profile_complete_calls':1 if stage=='correctness' else 5,'launches_per_call':2})
        self.write(directory/'native.execution.json',{'exit_code':0,'error':None})
        self.write(directory/'verify.execution.json',{'exit_code':0,'error':None})
        self.write(directory/('correctness.json' if stage=='correctness' else 'profile-summary.json'),{'passed':True} if stage=='correctness' else {'complete':True,'launch_count':10})
        if stage=='profile':self.write(directory/'output-validation.json',{'passed':True})

    def test_interrupted_correctness_retains_completed_cases_and_does_not_refund(self):
        args=self.diagnostic_args()
        def execute(*unused,**kwargs):
            self.assertTrue(self.ledger.start_stage.called)
            self.complete_case(self.task/'correctness-one/evidence/case_01')
            raise KeyboardInterrupt('stop after first case')
        with mock.patch.object(diagnostic,'Ledger',return_value=self.ledger),mock.patch.object(diagnostic,'run_process',side_effect=execute),contextlib.redirect_stdout(self.output):
            result=diagnostic.run(args)
        self.assertEqual(result['completed_cases'],[1]);self.assertEqual(result['status'],'failed')
        finish=self.ledger.finish_stage.call_args.kwargs;self.assertEqual(finish['outcome'],'failed')
        self.assertEqual(finish['actual_costs']['diagnostic_cases_completed'],1);self.assertEqual(finish['actual_costs']['native_kernel_launches_submitted'],2)
        self.assertEqual(finish['formal_samples'],0);self.ledger.start_stage.assert_called_once();self.ledger.finish_stage.assert_called_once()

    def test_profile_costs_and_commands_are_frozen_before_execution(self):
        args=self.diagnostic_args('profile','1,8')
        def execute(command,cwd,directory,**kwargs):
            plan=self.ledger.start_stage.call_args.kwargs['plan']
            self.assertIn([str(x) for x in command],plan['commands']);self.assertTrue(plan['frozen_files'])
            child=Path(command[command.index('--output')+1]);self.complete_case(child,'profile');self.write(child/'completion.json',{'status':'passed'})
        with mock.patch.object(diagnostic,'Ledger',return_value=self.ledger),mock.patch.object(diagnostic,'run_process',side_effect=execute),contextlib.redirect_stdout(self.output):result=diagnostic.run(args)
        self.assertEqual(result['status'],'passed');self.assertEqual(result['completed_cases'],[1,8])
        costs=self.ledger.finish_stage.call_args.kwargs['actual_costs'];self.assertEqual(costs['native_complete_calls'],30);self.assertEqual(costs['profile_launches_captured'],20)
        self.assertEqual(costs['native_kernel_launches_submitted'],60);self.assertEqual(costs['warmup_complete_calls'],20)
        self.assertFalse(result['paired_performance_evaluated'])

    def test_profile_success_without_native_and_oracle_proof_is_failure(self):
        args=self.diagnostic_args('profile','1')
        def execute(command,*unused,**kwargs):
            child=Path(command[command.index('--output')+1]);self.write(child/'profile-summary.json',{'complete':True,'launch_count':5});self.write(child/'completion.json',{'status':'passed'})
        with mock.patch.object(diagnostic,'Ledger',return_value=self.ledger),mock.patch.object(diagnostic,'run_process',side_effect=execute),contextlib.redirect_stdout(self.output):result=diagnostic.run(args)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['completed_cases'],[])
        self.assertEqual(self.ledger.finish_stage.call_args.kwargs['outcome'],'failed')

    def test_changed_producer_cannot_execute_under_frozen_reference(self):
        path=self.run/'producer.py';path.write_text('version one');refs=evidence.producers([path]);out=self.run/'snapshot';out.mkdir()
        evidence.snapshot_producers(out,refs);path.write_text('version two')
        with self.assertRaisesRegex(ValueError,'identity changed'):evidence.verify_refs(refs)
        self.assertEqual((out/'producers/producer.py').read_text(),'version one')

    def test_memory_plan_missing_or_stale_fails_before_stage_start(self):
        path=self.task/'baseline-memory-plan.json';original=path.read_bytes();path.unlink()
        with mock.patch.object(diagnostic,'Ledger',return_value=self.ledger),mock.patch.object(diagnostic,'run_process') as execute,contextlib.redirect_stdout(self.output):result=diagnostic.run(self.diagnostic_args('profile','1'))
        self.assertEqual(result['status'],'failed');execute.assert_not_called();self.ledger.start_stage.assert_not_called()
        path.write_bytes(original)
        sizeof=self.run/'bootstrap/sizeof-metadata.json';sizeof.write_bytes(sizeof.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'stale audit/sizeof'):evidence.memory_preflight(self.run,self.task,'baseline',self.task/'aa-build/build_manifest.json',[1])

    def test_retrospective_baseline_not_future_qualification_or_candidate_plan(self):
        path=self.task/'baseline-memory-plan.json';value=evidence.load(path);value['prospective']=False;self.write(path,value)
        bound=evidence.memory_preflight(self.run,self.task,'baseline',self.task/'aa-build/build_manifest.json',[1])
        self.assertFalse(bound['prospective'])
        with self.assertRaisesRegex(ValueError,'prospective'):evidence.memory_preflight(self.run,self.task,'baseline',self.task/'aa-build/build_manifest.json',[1],qualification=True)
        self.write(self.task/'exp001-memory-plan.json',value)
        with self.assertRaisesRegex(ValueError,'label mismatch'):evidence.memory_preflight(self.run,self.task,'exp001',self.task/'aa-build/build_manifest.json',[1])

    def test_memory_plan_case_and_source_scope_and_freeze(self):
        path=self.task/'baseline-memory-plan.json';value=evidence.load(path)
        binding=evidence.memory_preflight(self.run,self.task,'baseline',self.task/'aa-build/build_manifest.json',[1,20],qualification=True)
        self.assertEqual(binding['case_ids'],[1,20]);self.assertIn(str(path),binding['frozen_files'])
        value['cases'][0]['request']['case']['numel']=2;self.write(path,value)
        with self.assertRaisesRegex(ValueError,'case differs'):evidence.memory_preflight(self.run,self.task,'baseline',self.task/'aa-build/build_manifest.json',[1])
        with self.assertRaisesRegex(ValueError,'identity changed'):evidence.verify_refs(binding['frozen_files'])

    def test_recorded_stage_without_output_does_not_reexecute_idempotent_start(self):
        args=self.diagnostic_args('profile','1');self.ledger.state['tasks']['exp']['stages']['baseline-profile-one']={'attempts':[{'outcome':None}]}
        with mock.patch.object(diagnostic,'Ledger',return_value=self.ledger),mock.patch.object(diagnostic,'run_process') as execute,contextlib.redirect_stdout(self.output):result=diagnostic.run(args)
        self.assertEqual(result['status'],'failed');self.assertFalse(result['ledger_stage_started'])
        execute.assert_not_called();self.ledger.start_stage.assert_not_called();self.ledger.finish_stage.assert_not_called()

    def test_malformed_diagnostic_json_preserves_cost_error(self):
        out=self.task/'malformed';path=out/'evidence/case_01/native.json';self.write(path,['unexpected array'])
        costs,completed,errors=evidence.diagnostic_costs(out,'correctness',[1])
        self.assertEqual(costs['native_sessions_attempted'],1);self.assertEqual(completed,[]);self.assertTrue(errors)

    def test_path_escape_and_duplicate_cases_rejected_before_ledger(self):
        args=self.diagnostic_args('profile','1,1')
        with self.assertRaises(ValueError):diagnostic.run(args)
        args=self.diagnostic_args('profile','1');args.group='../escape'
        with self.assertRaises(ValueError):diagnostic.run(args)


if __name__=='__main__':unittest.main()
