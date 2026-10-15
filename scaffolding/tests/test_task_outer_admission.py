"""Small CPU-only wiring: synthetic receipts/CSV, real parser and source proof.

No capture, export, NPU, full campaign or original oracle execution is performed.
SDK inventory I/O is substituted with a small local roster; the resulting data
is deliberately not hardware or publication evidence.
"""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import struct
import shutil
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))
import task_outer_admission as driver
from aprof_runtime.errors import ContractError
from aprof_runtime.local_evidence import LocalEvidence
from test_task_rule_admission import fixture as roster_fixture


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return path


def screen_wire(pid):
    common = dict(schema_version='1.0.0', protocol=driver.SCREEN_PROTOCOL, operator='exp', pid=pid,
        device=0, context_address='11', stream_address='22', warmup=10, repeat=100, prime_repeat=100,
        pairs=6, launches_per_operator={r: 1 for r in driver.ROLES}, role_symbols={r: 'launch_'+r for r in driver.ROLES},
        buffers={'inputs': [{'name': n, 'address': str(100+i*100), 'bytes': 12}
            for i,n in enumerate(('input', 'baseline_tiling', 'candidate_tiling'))],
            'outputs': [{'name':'output', 'address':'500', 'bytes':12}], 'workspaces': []})
    wire = [dict(common, kind='ready', started_monotonic_ns=1, finished_monotonic_ns=2),
            dict(common, kind='prime', started_monotonic_ns=3, finished_monotonic_ns=4,
                 order=['baseline','candidate','candidate','baseline'])]
    for i in range(6):
        start = 10 + i * 10
        order = list(driver.ROLES[::1 if i%2 == 0 else -1])
        row = dict(common, kind='pair', pair_index=i, order=order,
                   started_monotonic_ns=start, finished_monotonic_ns=start+6)
        for j,role in enumerate(order):
            row[role] = dict(implementation=role, launches_per_operator=1,
                started_monotonic_ns=start+1+j*2, finished_monotonic_ns=start+2+j*2)
        wire.append(row)
    wire.append(dict(common, kind='complete', started_monotonic_ns=80, finished_monotonic_ns=86,
        input_bytes_unchanged=True, untimed_verifications=[dict(implementation=r, launches_per_operator=1,
        started_monotonic_ns=81+i*2, finished_monotonic_ns=82+i*2) for i,r in enumerate(driver.ROLES)]))
    return wire


def table():
    calls = 'A'*10+'B'*10+'A'*100+'B'*200+'A'*100
    calls += ''.join(('A'*100+'B'*100) if i%2==0 else ('B'*100+'A'*100) for i in range(6))+'AB'
    stream = io.StringIO(); rows = csv.writer(stream)
    rows.writerow(['Op Name','Task Start Time(us)','Task Duration(us)','Task Type','Stream ID','Task ID','Device_id'])
    for i,r in enumerate(calls):
        rows.writerow(['aprof_'+('baseline' if r=='A' else 'candidate')+'_exp_kernel', i*10,1,'AI_VECTOR_CORE',7,i,0])
    return stream.getvalue()


def make_screen_fixture(root):
    screen, local = driver.screen, LocalEvidence(root / 'records')
    roles = {r: screen.rule.ROUND / 'exp' / r for r in driver.ROLES}
    proof = screen.assemble('exp', roles, root / 'assembly',
        expected_roles={r: screen.base.inventory(screen.rule.source_tree(p)) for r,p in roles.items()},
        expected_headers=screen.rule.HEADERS)
    assembly = root / 'assembly'; binary = assembly / 'build/exp'; binary.parent.mkdir(); binary.write_text('CPU fixture only')
    review = local.register_artifact(assembly / 'source-review.json')
    route = save(root / 'cpu-route.json', {'purpose':'CPU fixture only', 'hardware':False})
    attempt = save(assembly / 'build-attempt.json', dict(source_review_hash=review, independent_review='CPU',
        route={'path':str(route), 'sha256':local.register_artifact(route)}))
    build = save(assembly / 'build-receipt.json', dict(status='passed',error=None,source_review_hash=review,
        binary={'path':str(binary),'sha256':local.register_artifact(binary)},
        attempt_ref={'path':str(attempt),'sha256':local.register_artifact(attempt)},
        commands=[dict(argv=proof['commands'][s],cwd=str(assembly/'source'),exit_status=0,error=None) for s in ('configure','build')]))
    prepared = root / 'prepared'
    for cid in range(1,21):
        folder = prepared / f'case_{cid:02d}'; folder.mkdir(parents=True)
        inp = folder/'input.bin'; inp.write_bytes(struct.pack('fff',-1,0,1))
        save(folder/'metadata.json',dict(case_id=cid,shape=[3],numel=3,dtype='float32',input=str(inp),
            output=str(folder/'output.bin'),base=-1,scale=1,shift=0))
    output=root/'screen'; output.mkdir(); scratch=root/'screen-scratch'
    profiler=root/'msprof'; profiler.write_text('CPU no profiler')
    config=screen.rule.task_config(assembly,build,prepared,scratch,run_id='screen-screen',session_id='screen',
        candidate_id='screen',physical_device=0,profiler=profiler)
    scratch.mkdir()
    config['expected_case_ids']=driver.CASES['exp']; config['cases']=[c for c in config['cases'] if c['case_id'] in config['expected_case_ids']]
    files=set(config['build']['receipt_files']+[str(binary),str(profiler)])
    for c in config['cases']:
        files.update(c['prepared_files'])
        for cmd in c['verify_commands'].values(): files.update([cmd[0],cmd[1]])
    frozen={'files':{p:local.register_artifact(p) for p in sorted(files)},
        'sources':{r:proof['roles'][r]['files'] for r in driver.ROLES},
        'build_sources':screen.base.inventory(screen.rule.source_tree(assembly/'source')), 'producer_files':{p:local.register_artifact(screen.timing.RELEASE/p) for p in screen.timing.PRODUCER_FILES}}
    def small_inventory(value, case=None):
        if case is None: return deepcopy(frozen)
        selected=set(config['build']['receipt_files']+[str(binary),str(profiler)]+case['prepared_files'])
        for cmd in case['verify_commands'].values(): selected.update([cmd[0],cmd[1]])
        return dict(deepcopy(frozen),files={p:frozen['files'][p] for p in sorted(selected)})
    identity=screen.timing.shared.bind_identity(config,frozen,local)
    for path,ref in proof['producer_files'].items(): assert local.register_artifact(path)==ref
    expected=dict(operator='exp',run_id='round',candidate_id='rule',
        source_hashes={r:local.register_artifact(proof['historical_source_binding']['roles'][r]['path']) for r in driver.ROLES})
    plan=dict(schema_version=1,protocol=driver.SCREEN_PROTOCOL,operator='exp',case_ids=driver.CASES['exp'],repeat=100,pairs=6,
        prepared_dir=str(prepared),output_dir=str(output),physical_device=0,profiler=str(profiler))
    protocol=dict(expected,screen_plan_ref=local.register_json(plan),source_review_ref=review,
        binary_hashes={r:local.register_artifact(binary) for r in driver.ROLES},input_inventory_ref=local.register_json(frozen['files']))
    storage=local.register_json(dict(mode='local_profile_only',work_root=str(output),scratch_root=str(scratch),collection_started_at=100))
    registration=local.register_json(dict(protocol=driver.SCREEN_PROTOCOL,config_ref=local.register_json(config),storage_ref=storage,
        identity=identity,inventory=frozen,case_ids=plan['case_ids'],source_review_ref=review,build_receipt_ref=local.register_artifact(build),
        created_at=101,attempt_policy='exactly_once_no_resume_no_resampling',exploration_only=True))
    def execution(prefix,argv,env,at,pid,text=''):
        stdout=Path(str(prefix)+'.stdout.log');stdout.write_text(text)
        stderr=Path(str(prefix)+'.stderr.log');stderr.write_text('')
        raw=dict(argv=argv,cwd=str(assembly/'source'),environment=env,started_at=at,ended_at=at+.1,
            timeout_seconds=10,pid=pid,exit_code=0,error=None,stdout_hash=local.register_artifact(stdout),stderr_hash=local.register_artifact(stderr))
        raw['log_hash']=local.register_artifact(save(Path(str(prefix)+'.execution.json'),raw))
        return raw
    sessions=[];parts={}
    for i,case in enumerate(config['cases']):
        cid=case['case_id'];directory=output/f'case-{cid:02d}';directory.mkdir()
        profile=scratch/directory.name/'profile';profile.mkdir(parents=True)
        raw=profile/'PROF_CPU/host/data/task.data';raw.parent.mkdir(parents=True);raw.write_text('synthetic raw '+str(cid))
        log=profile/'PROF_CPU/mindstudio_profiler_log/collection_host.log';log.parent.mkdir();log.write_text('original\n')
        capturemap={raw.relative_to(profile).as_posix():local.register_artifact(raw),log.relative_to(profile).as_posix():local.snapshot_file(log)}
        log.write_text('original\nexport appended\n')
        csvpath=profile/'PROF_CPU/mindstudio_profiler_output/op_summary.csv';csvpath.parent.mkdir();csvpath.write_text(table())
        final={p.relative_to(profile).as_posix():local.register_artifact(p) for p in screen.timing.old.safe_files(profile)}
        start=102+i*5;wire=screen_wire(200+i)
        cap=execution(directory/'capture',screen.timing.shared.expanded(case['command'],directory)+['--aprof-screen','six_pairs'],
            {'APROF_TASK_PROFILE_DIR':str(profile)},start+.1,200+i,''.join('APROF_TASK_SCREEN_JSON:'+json.dumps(m)+'\n' for m in wire))
        export=execution(directory/'export',screen.timing.export_argv(config,profile/'PROF_CPU'),{},start+1,400+i)
        part=driver.partition(csvpath.read_text(),wire,operator='exp',device=0,role_kernel_names=proof['role_kernel_names'],expected_pid=200+i)
        sess=dict(case_id=cid,started_at=start,finished_at=start+4,status='passed',error=None,capture=cap,export=export,
            identity_before_ref=local.register_json(small_inventory(config,case)),identity_after_ref=local.register_json(small_inventory(config,case)),
            capture_files_ref=local.register_json(capturemap),profile_files_ref=local.register_json(final),task_table_ref=final[csvpath.relative_to(profile).as_posix()],
            native_messages_ref=local.register_json(wire),partition_ref=local.register_json(part),oracles={},output_hashes={},summary=driver.case_summary(cid,part))
        for j,role in enumerate(driver.ROLES):
            paths=screen.timing.shared.expanded(case['output_files'][role],directory)
            for p in paths: Path(p).write_bytes(bytes(12));sess['output_hashes'][p]=local.register_artifact(p)
            cmd=screen.timing.shared.expanded(case['verify_commands'][role],directory)
            verdict={'passed':True,'case_id':cid,'controlled_cpu_fixture':True}
            record=execution(directory/(role+'-oracle'),cmd,{},start+2+j*.5,600+i*2+j,json.dumps(verdict))
            record['result_ref']=local.register_artifact(save(Path(cmd[cmd.index('--result')+1]),verdict))
            sess['oracles'][role]=record
        local.register_artifact(save(directory/'session.json',sess));sessions.append(sess);parts[cid]=part
    result=dict(protocol=driver.SCREEN_PROTOCOL,status='passed',error=None,exploration_only=True,eligible_for_formal_admission=False,
        gate_projection={},archive_performed=False,started_at=100,finished_at=135,registration_ref=registration,sessions=sessions,
        summary=driver.summarize('exp',parts))
    ref=local.register_artifact(save(output/'screen-result.json',result))
    return local,ref,dict(protocol_ref=local.register_json(protocol),expected=expected,window=[99,136]),small_inventory,result


@pytest.fixture(scope='module')
def screen_fixture(tmp_path_factory):
    return make_screen_fixture(tmp_path_factory.mktemp('outer-screen'))


def test_real_screen_parser_and_source_binding_are_read_only(screen_fixture,monkeypatch):
    local,ref,kwargs,inventory,_=screen_fixture
    monkeypatch.setattr(driver.screen.timing,'inventory',inventory)
    monkeypatch.setattr(driver,'PROFILE_DEPENDENCY_PATHS',(str(Path(local.directory).parent/'msprof'),))
    before=deepcopy(local.__dict__)
    result=driver.verify_task_screen(local,ref,**kwargs)
    assert result['valid'] and result['task_count']==6*1622 and not result['admission_authority']
    assert local.__dict__==before
    assert driver.correctness.adapter is driver.screen.rule


@pytest.mark.parametrize('fault',['bare_summary','missing_case','pid','role_argv','oracle_missing','oracle_failure','old_execution',
    'csv_partition','raw_mutation','prefix_rewrite','source_changed','frozen_input'])
def test_screen_replay_rejects_incomplete_or_substituted_evidence(screen_fixture,monkeypatch,fault):
    local,ref,kwargs,inventory,original=screen_fixture
    monkeypatch.setattr(driver.screen.timing,'inventory',inventory)
    monkeypatch.setattr(driver,'PROFILE_DEPENDENCY_PATHS',(str(Path(local.directory).parent/'msprof'),))
    # Overlay JSON reads only, preserving every original artifact and fixture.
    report=deepcopy(original); overrides={ref:report}
    if fault=='bare_summary': overrides[ref]=original['summary']
    elif fault=='missing_case': report['sessions'].pop()
    elif fault in ('pid','role_argv','old_execution'):
        rec=report['sessions'][0]['capture']
        if fault=='pid': rec['pid']+=1
        elif fault=='role_argv': rec['argv'][-1]='formal'
        else: rec['started_at']=1
    elif fault=='oracle_missing': report['sessions'][0]['oracles'].pop('candidate')
    elif fault=='oracle_failure': report['sessions'][0]['oracles']['candidate']['exit_code']=1
    elif fault=='csv_partition': overrides[report['sessions'][0]['partition_ref']]={'task_count':1622,'passed':True}
    elif fault=='raw_mutation':
        session=report['sessions'][0];m=driver.read(local,session['capture_files_ref']);m[next(p for p in m if p.endswith('.data'))]=local.register_json('other raw');overrides[session['capture_files_ref']]=m
    elif fault=='prefix_rewrite':
        session=report['sessions'][0];m=driver.read(local,session['capture_files_ref']);m[next(p for p in m if p.endswith('.log'))]=local.register_json('different prefix');overrides[session['capture_files_ref']]=m
    elif fault=='source_changed':
        monkeypatch.setattr(driver.screen,'checked_build',lambda *a:(_ for _ in ()).throw(ValueError('mechanical source changed')))
    elif fault=='frozen_input':
        protocol=driver.read(local,kwargs['protocol_ref']);overrides[protocol['input_inventory_ref']]={}
    original_read=driver.read
    def read(reader,reference): return deepcopy(overrides[reference]) if reference in overrides else original_read(reader,reference)
    monkeypatch.setattr(driver,'read',read)
    # A modified report/session is assumed freshly content-addressed here; skip
    # only equality to original session JSON so deeper raw joins are exercised.
    if fault not in ('bare_summary','missing_case','source_changed','frozen_input'):
        session_ref=driver.digest((json.dumps(report['sessions'][0],sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
        overrides[session_ref]=report['sessions'][0]
    with pytest.raises((ValueError,KeyError,ContractError)):
        driver.verify_task_screen(local,ref,**kwargs)


def outer_fixture(tmp_path,monkeypatch,fault=None):
    local,report,expected=roster_fixture(tmp_path)
    protocol=driver.read(local,expected['protocol_ref'])
    refs={k:local.register_json({'kind':v}) for k,v in [('correctness','task_rule_correctness'),('boundary','task_rule_boundary'),
        ('screen','screen'),('mechanism','mechanism'),('config','task_config'),('proof','proof'),('registration','task_registration'),('measurement_report','measurement_report')]}
    config=dict(expected_case_ids=list(range(1,21)),cases=[{'case_id':i} for i in range(1,21)],build={'binary':'synthetic'})
    if fault=='subset':config.update(expected_case_ids=[1],cases=[{'case_id':1}])
    refs['config']=local.register_json(config)
    refs['screen_config']=local.register_json(dict(build={'binary':'synthetic'}))
    refs['registration']=local.register_json({'identity':{'cases':{'1':{'prepared_files':{'input':'sha256:input'}}}}})
    protocol['input_inventory_ref']=local.register_json({'input':'sha256:input'})
    protocol['binary_hashes']={r:'sha256:binary' for r in driver.ROLES}
    # Anchor also binds the same prepared input inventory before launch.
    anchor=driver.read(local,expected['anchor_ref']);anchor['input_inventory_ref']=protocol['input_inventory_ref']
    expected['anchor_ref']=local.register_json(anchor);report['anchor_ref']=expected['anchor_ref'];protocol['anchor_ref']=expected['anchor_ref']
    completion=dict(started_at=109,finished_at=110)
    if fault=='late_completion':completion['finished_at']=110.1
    refs['completion']=local.register_json(completion)
    task=dict(passed=True,completion_ref=refs['completion'],proof_ref=refs['proof'],config_ref=refs['config'],task_registration_ref=refs['registration'],build={'binary_ref':'sha256:binary'})
    protocol.update(task_config_ref=refs['config'],profile_configs={r:local.register_json({'role':r}) for r in driver.ROLES})
    if fault=='config':protocol['task_config_ref']=local.register_json({'other':'config'})
    expected['protocol_ref']=local.register_json(protocol); report['protocol_ref']=expected['protocol_ref']
    # Rebind the real immutable registration/event chain to the updated protocol.
    reg=driver.read(local,expected['qualification_registration_ref']);reg['protocol_ref']=expected['protocol_ref'];reg['anchor_ref']=expected['anchor_ref']
    expected['qualification_registration_ref']=local.register_json(reg);report['qualification_registration_ref']=expected['qualification_registration_ref']
    for stage,key in [('correctness','correctness_report_ref'),('boundary','boundary_report_ref'),('screen','screen_report_ref'),
        ('task_measurement','measurement_admission_ref'),('profile','mechanism_report_ref')]:
        selected=refs[{'task_measurement':'completion','profile':'mechanism'}.get(stage,stage)]
        report[key]=selected;report['stage_evidence'][stage]=[selected]
    report['stage_evidence']['task_measurement']=[refs[k] for k in ('completion','proof','config','registration','measurement_report')]
    if fault=='missing_binding':report['stage_evidence']['task_measurement'].remove(refs['proof'])
    oldroster=driver.read(local,report['attempt_roster_ref']); previous=expected['qualification_registration_ref'];chain=[]
    for reference in oldroster['events']:
        event=driver.read(local,reference);event.update(previous_ref=previous,registration_ref=expected['qualification_registration_ref'])
        if event['state']=='completed':event['evidence_refs']=report['stage_evidence'][event['stage']]
        previous=local.register_json(event);chain.append(previous)
    report['attempt_roster_ref']=local.register_json(dict(schema_version=1,registration_ref=expected['qualification_registration_ref'],events=chain))
    calls=[]
    def correct(reader,reference,**kw):
        stage=driver.read(reader,reference)['kind'].removeprefix('task_rule_');calls.append(stage)
        assert kw['window']=={'correctness':[103,104],'boundary':[105,106]}[stage]
        if fault==stage:raise ValueError('leaf rejects '+stage)
        return {'passed':True,'report_ref':reference}
    def screen(reader,reference,**kw):
        calls.append('screen');assert kw['window']==[107,108]
        if fault=='screen':raise ValueError('leaf rejects screen')
        return {'valid':True,'report_ref':reference,'config_ref':refs['screen_config']}
    def profile(reader,reference,**kw):
        calls.append('task_and_profile');assert kw['window']==[111,112] and kw['profile_configs']==protocol['profile_configs']
        if fault=='task_and_profile':raise ValueError('leaf rejects Task or PMU')
        return task
    monkeypatch.setattr(driver.correctness,'verify_rule_correctness',correct)
    monkeypatch.setattr(driver,'verify_task_screen',screen)
    monkeypatch.setattr(driver,'verify_task_profile_window',profile)
    measurement={k:expected[k] for k in driver.IDENTITY};measurement.update(session_id='session',measurement_report_ref=refs['measurement_report'])
    if fault=='dispatcher_ref':expected['execution_ref']=local.register_json({'fake':'passed'})
    if fault=='identity':measurement['candidate_id']='other'
    if fault=='swapped_stage':report['correctness_report_ref']=refs['boundary']
    return local,local.register_json(report),dict(expected=expected,measurement_expected=measurement),calls


def test_outer_wires_real_roster_all_leaves_without_admission_authority(tmp_path,monkeypatch):
    local,ref,kwargs,calls=outer_fixture(tmp_path,monkeypatch)
    result=driver.verify_task_rule_admission(local,ref,**kwargs)
    assert calls==['correctness','boundary','screen','task_and_profile']
    assert result['valid'] and not result['admission_authority'] and not result['eligible_for_publication']
    assert len(result['remaining_requirements'])==3


@pytest.mark.parametrize('fault',['dispatcher_ref','identity','swapped_stage','correctness','boundary','screen',
    'task_and_profile','config','late_completion','missing_binding','subset'])
def test_outer_cannot_override_leaf_or_stage_binding(tmp_path,monkeypatch,fault):
    local,ref,kwargs,_=outer_fixture(tmp_path,monkeypatch,fault)
    with pytest.raises(ValueError): driver.verify_task_rule_admission(local,ref,**kwargs)


def test_archived_or_generic_reader_is_explicitly_unsupported():
    class Archive:
        def verify_artifact(self,ref):pytest.fail('unsupported archive must be rejected before reading')
    with pytest.raises(ValueError,match='retained replay requires source_archive_ref'):
        driver.verify_task_rule_admission(Archive(),'irrelevant',expected={},measurement_expected={})


def test_distinct_serialization_of_identical_source_payload_is_joined(tmp_path,monkeypatch):
    local,ref,kwargs,_=outer_fixture(tmp_path,monkeypatch)
    original=kwargs['expected']['source_hashes']
    for role,digest in original.items():
        value=driver.read(local,digest)
        path=save(tmp_path/(role+'-pretty.json'),value)
        path.write_text(json.dumps(value,indent=2)+'\n')
        kwargs['measurement_expected']['source_hashes']={**kwargs['measurement_expected']['source_hashes'],role:local.register_artifact(path)}
    assert kwargs['measurement_expected']['source_hashes']!=original
    result=driver.verify_task_rule_admission(local,ref,**kwargs)
    assert result['valid'] and result['original_source_hashes']==original


def test_different_source_payload_is_not_a_serialization_exception(tmp_path,monkeypatch):
    local,ref,kwargs,_=outer_fixture(tmp_path,monkeypatch)
    kwargs['measurement_expected']['source_hashes']={**kwargs['measurement_expected']['source_hashes'],
        'candidate':local.register_json({'source':'different'})}
    with pytest.raises(ValueError,match='source bundle contents differ'):
        driver.verify_task_rule_admission(local,ref,**kwargs)


@pytest.fixture(scope='module')
def retained_screen(tmp_path_factory):
    from aprof_runtime.store import EpisodeStore
    from archive_task_rule_sources import archive_task_rule_sources
    root = tmp_path_factory.mktemp('retained-screen')
    workspace = root / 'task'; workspace.mkdir()
    local, ref, kwargs, inventory, result = make_screen_fixture(workspace)
    profiler = str(workspace / 'msprof')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(driver, 'PROFILE_DEPENDENCY_PATHS', (profiler,))
        patch.setattr(driver.screen.timing, 'inventory', inventory)
        assert driver.verify_task_screen(local, ref, **kwargs)['valid']
    database = root / 'retained.sqlite'
    index = local.write_index(workspace / 'local-index.json')
    with EpisodeStore(database) as store:
        for digest in json.loads(index.read_text())['artifacts']:
            assert store.register_artifact(local.verify_artifact(digest)) == digest
        source_ref = archive_task_rule_sources(local, result['registration_ref'], store)
    shutil.rmtree(workspace)
    return database, ref, dict(kwargs, source_archive_ref=source_ref), profiler, result


def retained_reader(database):
    sys.path.insert(0, str(REPO / 'scaffolding/tools'))
    from verify_measurement_publication import ReadonlyCAS
    return ReadonlyCAS(database)


def replay_retained_screen(retained, monkeypatch):
    database, ref, kwargs, profiler, _ = retained
    monkeypatch.setattr(driver, 'PROFILE_DEPENDENCY_PATHS', (profiler,))
    reader = retained_reader(database)
    try:
        return driver.verify_task_screen(reader, ref, **kwargs)
    finally:
        reader.connection.close()


def test_archived_screen_replays_complete_tasks_after_task_directory_removed(retained_screen, monkeypatch):
    result = replay_retained_screen(retained_screen, monkeypatch)
    assert result['valid'] and result['task_count'] == 6 * 1622
    assert result['admission_authority'] is False
    assert not Path(retained_screen[3]).parent.exists()


@pytest.mark.parametrize('kind', ['raw', 'csv', 'output'])
@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_archived_screen_rejects_changed_or_missing_bytes(retained_screen, monkeypatch, kind, damage):
    database, _, _, _, report = retained_screen
    reader = retained_reader(database)
    session = report['sessions'][0]
    if kind == 'csv':
        reference = session['task_table_ref']
    elif kind == 'output':
        reference = next(iter(session['output_hashes'].values()))
    else:
        files = driver.read(reader, session['profile_files_ref'])
        reference = next(ref for name, ref in files.items() if name.endswith('.data'))
    path = reader.verify_artifact(reference); reader.connection.close()
    original = path.read_bytes(); aside = path.with_name(path.name + '.test-missing')
    try:
        if damage == 'missing': path.rename(aside)
        else: path.write_bytes(b'changed' + original[7:])
        with pytest.raises(ValueError): replay_retained_screen(retained_screen, monkeypatch)
    finally:
        if damage == 'missing': aside.rename(path)
        else: path.write_bytes(original)


def test_outer_posttask_branch_preserves_roster_and_calls_each_leaf_once(tmp_path, monkeypatch):
    from aprof_runtime.store import EpisodeStore
    workspace = tmp_path / 'task'; workspace.mkdir()
    local, ref, kwargs, calls = outer_fixture(workspace, monkeypatch)
    source_ref = local.register_json({'post_task_source_supplement': 'wiring fixture'})
    original = driver.correctness.verify_rule_correctness
    def archived(reader, reference, *, source_archive_ref, **kw):
        assert source_archive_ref == source_ref
        return original(reader, reference, **kw)
    monkeypatch.setattr(driver, 'verify_archived_rule_correctness', archived)
    database = tmp_path / 'retained.sqlite'
    index = local.write_index(workspace / 'index.json')
    with EpisodeStore(database) as store:
        for digest in json.loads(index.read_text())['artifacts']:
            assert store.register_artifact(local.verify_artifact(digest)) == digest
    shutil.rmtree(workspace)
    reader = retained_reader(database)
    try:
        result = driver.verify_task_rule_admission(reader, ref, source_archive_ref=source_ref, **kwargs)
    finally:
        reader.connection.close()
    assert result['valid'] and result['scope'] == 'retained_exp_sigmoid_task_components'
    assert result['source_archive_ref'] == source_ref
    assert calls == ['correctness', 'boundary', 'screen', 'task_and_profile']
    assert not result['admission_authority'] and not result['eligible_for_publication']


def test_online_cannot_label_itself_posttask_archive(tmp_path):
    local = LocalEvidence(tmp_path / 'records')
    with pytest.raises(ValueError, match='post-task collection'):
        driver.verify_task_rule_admission(local, 'unused', expected={}, measurement_expected={}, source_archive_ref='unused')
