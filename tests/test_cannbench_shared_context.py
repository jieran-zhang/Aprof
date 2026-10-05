"""CPU supervisor contract tests; no ACL initialization, builds, or device calls."""
import copy
import importlib.util
import json
import io
from pathlib import Path
import sys
import tempfile
import time
import contextlib
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from jsonschema import ValidationError
import cannbench_shared_context as supervisor
from test_shared_context_report import fixture


class SharedSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)
        self.manifest,self.sessions=fixture(case_ids=('small',))
        self.session=self.sessions[0]
        self.plan=self.manifest['session_plan'][0]
        self.build={'operator':'exp','roles':{}}
        for r in 'AB':
            binary=self.directory/(r+'.so');binary.write_bytes(r.encode())
            identity=self.session['identities'][r]
            identity['binary_hash']=supervisor.sha(binary)
            self.build['roles'][r]=dict(source_sha256=identity['source_hash'][7:],binary_sha256=identity['binary_hash'][7:],kernel_symbols=identity['entry'],binary=str(binary))
        self.execution={'opdir':str(self.directory)}
        self.argv=['synthetic-native']
        self.journal=self.native_journal(self.session)

    def native_journal(self,session):
        sid=session['session_id'];start=session['lifecycle_events'][0]
        result=[dict(type='process_start',session_id=sid,pid=session['pid'],host=session['host'],started_at=session['started_at']-.1),copy.deepcopy(start)]
        for r in self.plan['load_order']:
            build=self.build['roles'][r]
            result.append(dict(type='module',session_id=sid,role=r,path=build['binary'],source_sha256=build['source_sha256'],operator_name='exp',kernel_symbols=build['kernel_symbols'],entry_address='0x100' if r=='A' else '0x200'))
        for c in self.plan['case_order']:
            for u in self.plan['buffer_configs']:
                events=[e for e in session['lifecycle_events'] if e.get('case_id')==c and e.get('buffer_config')==u]
                result.append(copy.deepcopy(events[0]))
                result.extend(dict(type='resources',session_id=sid,**e) for e in session['resource_events'] if e['case_id']==c and e['buffer_config']==u)
                result.append(copy.deepcopy(events[1]))
                result.extend(dict(type='sample',**e) for e in session['samples'] if e['case_id']==c and e['buffer_config']==u)
                result.extend(dict(type='output',session_id=sid,case_id=c,buffer_config=u,role=r,path=str(self.directory/f'{c}_{u}_{r}.bin'),validation_scope='final_call_of_final_formal_sample',validation_status='pending_external_oracle',complete_calls_since_prepare=3010) for r in 'AB')
                result.append(copy.deepcopy(events[2]))
        result.append(copy.deepcopy(session['lifecycle_events'][-1]))
        return result

    def normalize(self,journal=None):
        rows=self.journal if journal is None else journal
        (self.directory/'journal.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return supervisor.normalize(self.plan,self.directory,self.build,self.execution,self.argv,0,self.session['outputs'])

    def test_schedule_covers_six_units_and_balanced_qualification(self):
        cases=['1','8','14','20'];phases=['qualification','before','reverse','ab','after']
        plan=supervisor.schedule('comparison',phases,cases)
        self.assertEqual(len(plan),36)
        for phase in phases:
            rows=[p for p in plan if p['phase']==phase]
            self.assertTrue(all(set(p['case_order'])==set(cases) for p in rows))
            self.assertEqual(sum(p['first_order']=='AB' for p in rows),len(rows)//2)
            if phase=='qualification':
                self.assertEqual({(p['block_id'],p['load_order']) for p in rows},{(b,l) for b in range(1,7) for l in ('AB','BA')})
                self.assertTrue(all(set(p['buffer_configs'])=={'normal','swapped'} for p in rows))
            else:
                self.assertEqual({p['replicate_id'] for p in rows},set(range(1,7)))
                self.assertTrue(all(p['buffer_configs']==(['swapped'] if phase=='reverse' else ['normal']) for p in rows))
        self.assertEqual(plan,supervisor.schedule('comparison',phases,cases))

    def test_launch_count_uses_source_chunk_and_tensorlist_members(self):
        source=self.directory/'source';(source/'op_host').mkdir(parents=True)
        host=source/'op_host/foreach_addcdiv_scalar.asc'
        host.write_text('constexpr uint64_t kChunkElements = 2ULL * 4;')
        self.assertEqual(supervisor.count_launches('foreach_addcdiv_scalar',source,{'lengths':[1,8,9]}),4)
        self.assertEqual(supervisor.count_launches('foreach_norm',source,{'lengths':[1,8,9]}),6)
        host.write_text('constexpr uint64_t kChunkElements = __import__("os").system("false");')
        with self.assertRaises(ValueError):supervisor.count_launches('foreach_addcdiv_scalar',source,{'lengths':[1]})

    def test_normalization_preserves_all_samples_and_lifecycle(self):
        normalized=self.normalize()
        self.assertEqual(normalized['samples'],self.session['samples'])
        self.assertEqual(normalized['lifecycle_events'],self.session['lifecycle_events'])
        self.assertEqual(normalized['resource_events'],self.session['resource_events'])
        self.assertEqual(normalized['log_hash'],supervisor.sha(self.directory/'journal.jsonl'))
        supervisor.stats.validate_schema([normalized],'shared-context-sessions.schema.json')

    def test_normalization_rejects_duplicate_or_foreign_module_identity(self):
        mutations=[lambda rows:rows.insert(3,copy.deepcopy(rows[2])),lambda rows:rows[2].update(session_id='foreign'),lambda rows:rows[2].update(path='/different/module.so'),lambda rows:rows[2].update(operator_name='wrong_operator'),lambda rows:rows[3].update(entry_address=rows[2]['entry_address'])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                rows=copy.deepcopy(self.journal);mutate(rows)
                with self.assertRaises(ValueError):self.normalize(rows)

    def test_normalization_rejects_failure_unknown_and_wrong_exit(self):
        for event in [dict(type='failure',session_id=self.plan['session_id'],error='native failed'),dict(type='unexpected',session_id=self.plan['session_id'])]:
            rows=copy.deepcopy(self.journal);rows.insert(-1,event)
            with self.assertRaises(ValueError):self.normalize(rows)
        rows=copy.deepcopy(self.journal);rows[-1]['exit_code']=1
        with self.assertRaises(ValueError):self.normalize(rows)

    def test_normalization_rejects_formal_sample_before_warmup_and_process_mismatch(self):
        rows=copy.deepcopy(self.journal)
        index=next(i for i,row in enumerate(rows) if row['type']=='sample')
        sample=rows.pop(index)
        warmup=next(i for i,row in enumerate(rows) if row['type']=='warmup_complete')
        rows.insert(warmup,sample)
        with self.assertRaises(ValueError):self.normalize(rows)
        rows=copy.deepcopy(self.journal);rows[0]['pid']+=1
        with self.assertRaises(ValueError):self.normalize(rows)
        rows=copy.deepcopy(self.journal)
        next(row for row in rows if row['type']=='output')['complete_calls_since_prepare']=10
        with self.assertRaises(ValueError):self.normalize(rows)

    def test_normalization_rejects_duplicate_json_keys_and_truncated_json(self):
        self.normalize()
        journal_path=self.directory/'journal.jsonl'
        contents=journal_path.read_text()
        bad=contents.replace('"type": "module"','"type": "module", "type": "module"',1)
        for text in (bad,contents+'{"type":'):
            journal_path.write_text(text)
            with self.assertRaises(ValueError):supervisor.normalize(self.plan,self.directory,self.build,self.execution,self.argv,0,self.session['outputs'])

    def test_frozen_plan_rejected_before_sessions_exist(self):
        manifest,_=fixture(stages=('qualification',))
        supervisor.stats.validate_plan(manifest)
        manifest['session_plan'][0]['buffer_configs']=['normal']
        with self.assertRaises(ValueError):supervisor.stats.validate_plan(manifest)
        manifest,_=fixture()
        manifest['control_identities']['B']['source_hash']='sha256:'+'b'*64
        with self.assertRaises(ValueError):supervisor.stats.validate_plan(manifest)

    def test_session_verification_failure_kills_native_and_preserves_failure(self):
        directory=self.directory/'failed-session'
        metadata=self.directory/'metadata.json';metadata.write_text('{}')
        execution={**self.execution,'metadata':{'small':str(metadata)},'cpu':'0','physical_device':0}
        build={**self.build,'runner':{'path':'not-executed-native'}}
        request=dict(type='validation_required',case_id='small',buffer_config='normal',outputs={r:str(directory/f'small_normal_{r}.bin') for r in 'AB'})
        process=mock.Mock(pid=12345,returncode=None,stdout=io.StringIO(json.dumps(request)+'\n'),stdin=io.StringIO())
        process.poll.return_value=None
        def wait(**kwargs):process.returncode=-15;return -15
        process.wait.side_effect=wait
        verifier=mock.Mock();verifier.run.side_effect=lambda *args,**kwargs:time.sleep(1)
        previous_handler=supervisor.signal.getsignal(supervisor.signal.SIGALRM)
        with mock.patch.object(supervisor,'command_from_metadata',return_value=['native','--n','1']),mock.patch.object(supervisor.subprocess,'Popen',return_value=process),mock.patch.object(supervisor.os,'killpg') as kill:
            with self.assertRaises(RuntimeError):supervisor.execute_session(self.plan,directory,build,execution,verifier,.03)
        kill.assert_called_once_with(12345,supervisor.signal.SIGTERM)
        self.assertEqual(supervisor.signal.getsignal(supervisor.signal.SIGALRM),previous_handler)
        completion=supervisor.load(directory/'completion.json')
        self.assertEqual(completion['error']['type'],'TimeoutError')
        self.assertTrue((directory/'started.json').exists())
        self.assertTrue((directory/'validations.json').exists())
        self.assertFalse((directory/'normalized.json').exists())

    def evidence_bundle(self):
        out=self.directory/'bundle';out.mkdir()
        manifest,sessions=fixture(case_ids=('small',))
        manifest['task_id']='exp'
        manifest['cases'][0]['launches_per_call']={'A':1,'B':1}
        for session in sessions:
            for sample in session['samples']:sample['launches_per_call']=1
        inputs=out/'input.bin';inputs.write_bytes(b'input')
        metadata=out/'metadata.json';metadata.write_text(json.dumps({'input':str(inputs)}))
        verifier=out/'scripts/verify_result.py';verifier.parent.mkdir();verifier.write_text('# fixture')
        environment=out/'environment.json';environment.write_text('{}')
        def ref(p):return {'path':str(p),'sha256':supervisor.sha(p)}
        row=dict(case_id='small',attributes=manifest['cases'][0]['attributes'],metadata=ref(metadata),verifier=ref(verifier),inputs={'input':ref(inputs)},oracle_file=None)
        bindings=out/'bindings.json';supervisor.save(bindings,{'cases':[row]})
        manifest['cases'][0]['input_hash']=supervisor.stats.digest(row['inputs'])
        manifest['cases'][0]['oracle_hash']=supervisor.stats.digest({'verifier':row['verifier'],'oracle_file':None,'attributes':row['attributes']})
        build=copy.deepcopy(self.build)
        build['harness']={}
        source=out/'source'
        (source/'op_host').mkdir(parents=True);(source/'op_kernel').mkdir()
        (source/'op_host/exp.asc').write_text('// original host')
        (source/'op_kernel/exp.h').write_text('// original kernel')
        (source/'CMakeLists.txt').write_text('# frozen source build')
        from shared_context_build import source_hash
        for role,v in build['roles'].items():
            generated=out/role;(generated/'op_host').mkdir(parents=True);(generated/'op_kernel').mkdir()
            adapter=generated/'op_host/exp.asc';adapter.write_text('// prepared '+role)
            (generated/'op_kernel/exp.h').write_bytes((source/'op_kernel/exp.h').read_bytes())
            patch=out/(role+'.harness.patch');patch.write_text('// patch '+role)
            v.update(source_dir=str(source),source_sha256=source_hash(source),cmake_sha256=supervisor.sha(source/'CMakeLists.txt')[7:],adapter_sha256=supervisor.sha(adapter)[7:],patch_sha256=supervisor.sha(patch)[7:])
        build['runner']={'path':str(inputs),'sha256':supervisor.sha(inputs)[7:]}
        build_path=out/'build.json';supervisor.save(build_path,build)
        ids=supervisor.identities(build)
        manifest['identities']=copy.deepcopy(ids);manifest['control_identities']=copy.deepcopy(ids)
        manifest['hardware']['environment_hash']=supervisor.sha(environment)
        manifest['hardware']['physical_chip']='0'
        manifest['hardware']['host']=supervisor.socket.gethostname()
        for session in sessions:
            session['host']=manifest['hardware']['host']
            session['lifecycle_events'][0]['host']=manifest['hardware']['host']
        manifest['harness_hash']=supervisor.stats.digest({'ab':build['harness'],'control':build['harness']})
        snapshot=out/'supervisor-snapshot.py';snapshot.write_bytes(Path(supervisor.__file__).read_bytes())
        execution=dict(supervisor_snapshot=str(snapshot),physical_device=0,cpu='0',build=str(build_path),build_hash=supervisor.sha(build_path),control_build=str(build_path),control_build_hash=supervisor.sha(build_path),input_bindings=str(bindings),input_bindings_hash=supervisor.sha(bindings),environment=str(environment),environment_hash=supervisor.sha(environment),metadata={'small':str(metadata)},opdir=str(out),verifier_hash=supervisor.sha(verifier),supervisor_hash=supervisor.sha(supervisor.__file__),native_hashes={label:{r:supervisor.sha(v['binary']) for r,v in build['roles'].items()} for label in ('ab','control')})
        normalized=[]
        original_directory,original_plan=self.directory,self.plan
        original_build=self.build;self.build=build
        for plan,session in zip(manifest['session_plan'],sessions):
            directory=out/plan['session_id'];directory.mkdir()
            session['identities']=copy.deepcopy(ids)
            offset=time.time()+10
            for key in ('started_at','ended_at'):session[key]+=offset
            for e in session['samples']:
                e['started_at']+=offset;e['ended_at']+=offset
            session['lifecycle_events'][0]['started_at']=session['started_at'];session['lifecycle_events'][-1]['ended_at']=session['ended_at']
            self.directory,self.plan=directory,plan
            rows=self.native_journal(session)
            (directory/'journal.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            result=supervisor.normalize(plan,directory,build,execution,self.argv,0,session['outputs'])
            supervisor.save(directory/'normalized.json',result)
            supervisor.save(directory/'completion.json',{'argv':self.argv,'exit_code':0})
            supervisor.save(directory/'validations.json',session['outputs'])
            normalized.append(result)
        self.directory,self.plan=original_directory,original_plan
        qout=out/'method-qualification';qout.mkdir()
        template,qsessions=fixture(stages=('qualification',),case_ids=('small',))
        qmanifest=copy.deepcopy(manifest)
        qmanifest['stages']=['qualification'];qmanifest['session_plan']=template['session_plan']
        for c in qmanifest['cases']:c['launches_per_call']['B']=c['launches_per_call']['A']
        qmanifest['qualification_scope']={'status':'qualification_requested','report':None,'input_bindings_hash':execution['input_bindings_hash']}
        qnormalized=[]
        for plan,session in zip(qmanifest['session_plan'],qsessions):
            directory=qout/plan['session_id'];directory.mkdir()
            session['identities']=copy.deepcopy(ids);session['host']=manifest['hardware']['host'];session['lifecycle_events'][0]['host']=session['host']
            for sample in session['samples']:sample['launches_per_call']=1
            self.directory,self.plan=directory,plan
            rows=self.native_journal(session)
            (directory/'journal.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            result=supervisor.normalize(plan,directory,build,execution,self.argv,0,session['outputs'])
            supervisor.save(directory/'normalized.json',result);supervisor.save(directory/'completion.json',{'argv':self.argv,'exit_code':0});supervisor.save(directory/'validations.json',session['outputs'])
            qnormalized.append(result)
        self.directory,self.plan=original_directory,original_plan
        for name,value in [('manifest',qmanifest),('execution-plan',execution),('sessions',qnormalized),('report',supervisor.stats.analyze(qmanifest,qnormalized))]:supervisor.save(qout/(name+'.json'),value)
        manifest['qualification_scope']=supervisor.qualification_binding(manifest,execution['input_bindings_hash'],qout/'report.json')
        for name,value in [('manifest',manifest),('execution-plan',execution),('sessions',normalized),('report',supervisor.stats.analyze(manifest,normalized))]:supervisor.save(out/(name+'.json'),value)
        self.build=original_build
        return out

    def test_supervisor_verify_directory_is_read_only_and_checks_raw(self):
        out=self.evidence_bundle()
        def snapshot():return {str(p.relative_to(out)):(p.read_bytes(),p.stat().st_mtime_ns) for p in out.rglob('*') if p.is_file()}
        before=snapshot()
        with mock.patch.object(supervisor,'execute_session',side_effect=AssertionError('verify launched hardware')),mock.patch.object(supervisor,'health',side_effect=AssertionError('verify touched hardware')),mock.patch.object(supervisor.socket,'gethostname',return_value='archive-review-host'):
            self.assertTrue(supervisor.verify_directory(out))
        self.assertEqual(before,snapshot())
        journal=next(out.glob('ab-*/journal.jsonl'))
        journal.write_text(journal.read_text().replace('"raw_duration":','"raw_duration": 2, "discarded_duration":',1))
        with self.assertRaises((ValueError,ValidationError)):
            supervisor.verify_directory(out)

    def test_prepare_freezes_manifest_and_rejects_bad_plan_without_hardware(self):
        bundle=self.evidence_bundle();execution=supervisor.load(bundle/'execution-plan.json')
        args=SimpleNamespace(output=str(self.directory/'prepared'),build=execution['build'],control_build=None,input_bindings=execution['input_bindings'],cases='small',phases='qualification',device=0,environment=execution['environment'],comparison_id='prepared',run_id='run',attempt_id='attempt',comparison_kind='parent',qualification_report=None,opdir=str(bundle),cpu='0')
        with mock.patch.object(supervisor,'execute_session',side_effect=AssertionError('prepare launched native')),mock.patch.object(supervisor,'health',side_effect=AssertionError('prepare touched hardware')):
            manifest=supervisor.prepare(args)
        supervisor.stats.validate_plan(manifest)
        self.assertEqual(len(manifest['session_plan']),12)
        self.assertEqual(manifest['cases'][0]['attributes'],{'kind':'tensorlist','members':2})
        self.assertFalse((Path(args.output)/'collection-started.json').exists())
        args.output=str(self.directory/'invalid');args.phases='qualification,qualification'
        with self.assertRaises(ValueError):supervisor.prepare(args)
        self.assertFalse(Path(args.output).exists())

    def test_routine_prepare_requires_and_freezes_external_qualification(self):
        out=self.evidence_bundle();execution=supervisor.load(out/'execution-plan.json')
        args=SimpleNamespace(output=str(self.directory/'routine-prepared'),build=execution['build'],control_build=None,input_bindings=execution['input_bindings'],cases='small',phases='before,reverse,ab,after',device=0,environment=execution['environment'],comparison_id='routine',run_id='run',attempt_id='attempt',comparison_kind='parent',qualification_report=None,opdir=str(out),cpu='0')
        with mock.patch.object(supervisor,'execute_session',side_effect=AssertionError('prepare launched hardware')):
            with self.assertRaisesRegex(ValueError,'requires --qualification-report'):supervisor.prepare(args)
            self.assertFalse(Path(args.output).exists())
            args.qualification_report=str(out/'method-qualification/report.json')
            manifest=supervisor.prepare(args)
        scope=manifest['qualification_scope']
        self.assertEqual(scope['status'],'externally_qualified')
        self.assertEqual(scope['report_hash'],supervisor.sha(args.qualification_report))
        self.assertGreater(scope['bound_at'],0)
        self.assertEqual(len(manifest['session_plan']),24)

    def test_qualification_scope_and_frozen_evidence_cannot_be_borrowed(self):
        out=self.evidence_bundle();manifest=supervisor.load(out/'manifest.json');execution=supervisor.load(out/'execution-plan.json')
        scope=manifest['qualification_scope'];path=scope['report']
        changes=[lambda m:m['hardware'].update(physical_chip='other'),lambda m:m['hardware'].update(environment_hash='sha256:'+'b'*64),lambda m:m.update(harness_hash='sha256:'+'b'*64),lambda m:m['control_identities']['A'].update(binary_hash='sha256:'+'b'*64),lambda m:m['cases'][0].update(case_id='unqualified'),lambda m:m['cases'][0]['attributes'].update(members=99),lambda m:m['cases'][0].update(input_hash='sha256:'+'b'*64),lambda m:m['cases'][0].update(oracle_hash='sha256:'+'b'*64),lambda m:m['cases'][0]['launches_per_call'].update(A=99)]
        for change in changes:
            modified=copy.deepcopy(manifest);change(modified)
            with self.assertRaises(ValueError):supervisor.qualification_binding(modified,execution['input_bindings_hash'],path)
        with self.assertRaises(ValueError):supervisor.qualification_binding(manifest,'sha256:'+'b'*64,path)
        frozen=copy.deepcopy(scope);frozen['bound_at']=1
        with self.assertRaisesRegex(ValueError,'not completed'):supervisor.qualification_binding(manifest,execution['input_bindings_hash'],frozen=frozen)
        report_path=Path(path);report_path.write_bytes(report_path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'evidence or binding changed'):supervisor.qualification_binding(manifest,execution['input_bindings_hash'],frozen=scope)

    def test_collect_rejects_unbound_routine_before_native_or_health(self):
        out=self.evidence_bundle();manifest=supervisor.load(out/'manifest.json')
        manifest['qualification_scope']={'status':'requires_external_qualification'}
        supervisor.save(out/'manifest.json',manifest,replace=True)
        with mock.patch.object(supervisor,'execute_session',side_effect=AssertionError('unqualified native launch')),mock.patch.object(supervisor,'health',side_effect=AssertionError('unqualified hardware touch')):
            with self.assertRaisesRegex(ValueError,'lacks a frozen external qualification'):
                supervisor.collect(SimpleNamespace(output=str(out),timeout=1))
        self.assertFalse((out/'collection-started.json').exists())

    def test_failed_qualification_is_rejected_even_when_report_replays(self):
        out=self.evidence_bundle();manifest=supervisor.load(out/'manifest.json');execution=supervisor.load(out/'execution-plan.json')
        qout=out/'method-qualification';qmanifest=supervisor.load(qout/'manifest.json');build=supervisor.load(execution['control_build']);sessions=[]
        for plan in qmanifest['session_plan']:
            directory=qout/plan['session_id'];journal=directory/'journal.jsonl'
            rows=[json.loads(line) for line in journal.read_text().splitlines()]
            for row in rows:
                if row['type']=='sample' and row['role']=='A':row['raw_duration']*=1.01;row['ns_per_call']*=1.01
            journal.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            validations=supervisor.load(directory/'validations.json')
            normalized=supervisor.normalize(plan,directory,build,execution,self.argv,0,validations)
            supervisor.save(directory/'normalized.json',normalized,replace=True);sessions.append(normalized)
        report=supervisor.stats.analyze(qmanifest,sessions)
        self.assertFalse(report['measurement_quality']['observed_checks_pass'])
        supervisor.save(qout/'sessions.json',sessions,replace=True);supervisor.save(qout/'report.json',report,replace=True)
        self.assertTrue(supervisor.verify_directory(qout))
        with self.assertRaisesRegex(ValueError,'did not pass'):supervisor.qualification_binding(manifest,execution['input_bindings_hash'],qout/'report.json')

    def test_attestation_rejects_changed_sources_cmake_or_generated_kernels(self):
        out=self.evidence_bundle();execution=supervisor.load(out/'execution-plan.json');manifest=supervisor.load(out/'manifest.json')
        for path in (out/'source/op_kernel/exp.h',out/'source/CMakeLists.txt',out/'A/op_kernel/exp.h',out/'B/op_host/exp.asc',out/'A.harness.patch'):
            original=path.read_bytes();path.write_bytes(original+b' changed')
            try:
                with self.assertRaises(ValueError):supervisor.attest_files(manifest,execution)
            finally:path.write_bytes(original)
        supervisor.attest_files(manifest,execution)

    def test_attestation_rejects_changed_input_bytes_before_hardware(self):
        out=self.evidence_bundle();execution=supervisor.load(out/'execution-plan.json');manifest=supervisor.load(out/'manifest.json')
        supervisor.attest_files(manifest,execution)
        (out/'input.bin').write_bytes(b'changed input')
        with self.assertRaises(ValueError):supervisor.attest_files(manifest,execution)

    def test_collection_stops_at_first_failure_and_keeps_partial_sessions(self):
        out=self.evidence_bundle()
        # A prepared collection has no previous completed results.
        for name in ('sessions.json','report.json'): (out/name).unlink()
        execution=supervisor.load(out/'execution-plan.json')
        first=supervisor.load(next(out.glob('ab-*/normalized.json')))
        verifier=SimpleNamespace(source_hash=execution['verifier_hash'])
        with mock.patch.object(supervisor,'ReusedVerifier',return_value=verifier),mock.patch.object(supervisor,'exclusive_host',return_value=contextlib.nullcontext()),mock.patch.object(supervisor,'health'),mock.patch.object(supervisor,'execute_session',side_effect=[first,RuntimeError('native failed'),AssertionError('must stop')]) as execute:
            with self.assertRaises(RuntimeError):supervisor.collect(SimpleNamespace(output=str(out),timeout=1))
        self.assertEqual(execute.call_count,2)
        self.assertEqual(len(supervisor.load(out/'sessions.partial.json')),1)
        self.assertEqual(supervisor.load(out/'collection-completion.json')['completed_sessions'],1)
        self.assertFalse((out/'sessions.json').exists())
        self.assertFalse((out/'report.json').exists())

    def test_post_failure_health_error_still_records_collection_completion(self):
        out=self.evidence_bundle()
        for name in ('sessions.json','report.json'):(out/name).unlink()
        execution=supervisor.load(out/'execution-plan.json')
        verifier=SimpleNamespace(source_hash=execution['verifier_hash'])
        with mock.patch.object(supervisor,'ReusedVerifier',return_value=verifier),mock.patch.object(supervisor,'exclusive_host',return_value=contextlib.nullcontext()),mock.patch.object(supervisor,'health',side_effect=[None,RuntimeError('health after failed')]),mock.patch.object(supervisor,'execute_session',side_effect=RuntimeError('native failed')):
            with self.assertRaises(RuntimeError):supervisor.collect(SimpleNamespace(output=str(out),timeout=1))
        completed=supervisor.load(out/'collection-completion.json')
        self.assertEqual(completed['completed_sessions'],0)
        self.assertIsNotNone(completed['error'])
        self.assertIn('native failed',json.dumps(completed))
        self.assertIn('health after failed',json.dumps(completed))

    def test_verifier_recomputation_is_read_only(self):
        manifest,sessions=fixture()
        report=supervisor.stats.analyze(manifest,sessions)
        for name,value in [('manifest',manifest),('sessions',sessions),('report',report)]:
            (self.directory/(name+'.json')).write_bytes(supervisor.stats.canonical(value))
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.directory.iterdir()}
        with mock.patch.object(sys,'argv',['shared_context_report.py','verify','--manifest',str(self.directory/'manifest.json'),'--sessions',str(self.directory/'sessions.json'),'--report',str(self.directory/'report.json')]):
            supervisor.stats.main()
        after={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.directory.iterdir()}
        self.assertEqual(before,after)


if __name__=='__main__':unittest.main()
