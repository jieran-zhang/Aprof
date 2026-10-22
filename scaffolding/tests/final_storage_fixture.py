"""Explicit fake analyzer with real ledger, using pinned historical writer bytes."""
from aprof_layout import skill_lib
from contextlib import contextmanager
from copy import deepcopy
import base64, gzip, importlib.util, json, os, tempfile
from pathlib import Path
import sys
import pytest
ROOT=Path(os.environ.get('APROF_TEST_REPO',Path(__file__).resolve().parents[2]))
sys.path.extend([str(ROOT/'scaffolding/collection/scripts'),str(skill_lib() / 'runtime/src'),str(ROOT/'scaffolding/tests')])
from test_level2_finalize import Fixture
import level2_finalize as final
import msprof_exploration_campaign as campaign
from msprof_exploration_execute import load, pointer
from run_msprof_exploration_stage import verify_source_snapshot
from shared_context_build import source_hash
_spec=importlib.util.spec_from_file_location('reviewed_storage_test_bytes',Path(__file__).with_name('fixtures')/'final_storage_reviewed_bytes.py')
_blobs=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_blobs)
_temp=tempfile.TemporaryDirectory(prefix='aprof-storage-test-producers-')
FIXTURE_ROOT=Path(_temp.name)
for _name,_source in json.loads(gzip.decompress(base64.b64decode(_blobs.DATA))).items():
    _path=FIXTURE_ROOT/_name;_path.parent.mkdir(parents=True,exist_ok=True);_path.write_text(_source)
SPEC=importlib.util.spec_from_file_location('approved_test_attestor',FIXTURE_ROOT/'approved_v3/level2_final_report_attestation.py')
a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)
assert a.digest(Path(a.__file__).read_bytes())=='sha256:de18e5fed791d14dcc3a4db979a274b40c7ad8da79cf1da023fc244f6ca3d832'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(a.canonical(value))

class FakeRuntime:
    campaign=campaign
    storage_profile={'version':'closed_evidence_facade_epoch_v1',
                     'reviewed_patch_sha256':a.REVIEWED_STORAGE_PATCH,
                     'expected_producer_sha256':dict(a.STORAGE_PRODUCERS)}
    def __init__(self):self.expected={};self.calls=[];self.host_calls=0;self.rechecks=0
    def ledger(self,path):return campaign.Campaign(path)
    def read(self,path):return Path(path).read_bytes()
    def fingerprint(self,path):return a.digest(Path(path).read_bytes())
    def source(self,archive,tree):verify_source_snapshot(archive,tree);return source_hash(tree)
    def producer_paths(self):return [Path(a.__file__)]
    def historical_producer(self,*args):raise ValueError('unattested historical producer')
    @contextmanager
    def reader_session(self):yield
    @contextmanager
    def host_lock(self):self.host_calls+=1;yield
    def reverify(self):self.rechecks+=1
    def analyze(self,directories,plan,calibration):
        self.calls.append(tuple(directories));return deepcopy(self.expected[directories[0]])
    def compare(self,saved,actual,path):
        assert saved==actual,'saved report differs from full replay'
        return {'comparison':{'matched':True,'comparison':'exact'},'historical_producers':[]}


class Small:
    def __init__(self,tmp_path,monkeypatch,*,chain=False,failed=(1,)):
        self.fixture=Fixture(tmp_path,monkeypatch,failed=failed,parent_chain=chain)
        self.run=tmp_path;self.task=self.fixture.task;self.runtime=FakeRuntime()
        self.cal=self.task/'stages/aa-initial/cohort'
        h=source_hash(self.task/'baseline')
        self.make_report(self.cal,{'case_ids':a.ALL_CASES,'comparison_kind':'aa',
                                  'schedule':[{'name':f'p{i}'} for i in range(6)]},{'A':h,'B':h})
        result=final.finalize(tmp_path,'maximum')
        assert result['status'] in ('final_evaluations_completed','closed_no_qualified_candidates'),result
        # Fill the tiny finalizer fixture with real report metadata shape. The
        # analyzer's independent retained expected values are captured here.
        for candidate in result['comparisons']:
            parent=self.task/'candidates'/candidate['candidate_id']
            plan=load(parent/'stages/final/stage-plan.json')
            for row in plan['cohorts']:
                directory=parent/'stages/final'/row['relation'];p=load(directory/'plan.json')
                build=load(p['identity_bindings']['role_build']['path'])
                self.make_report(directory,p,{r:build['roles'][r]['source_sha256'] for r in 'AB'})
            for row in candidate['comparisons']:
                row['report']=pointer(parent/'stages/final'/row['relation']/'report.json')
        save(self.task/'finalization/completion.json',result)
        manifest=load(self.task/'manifest.json');manifest.update(operator='maximum',task_dir=str(self.task));save(self.task/'manifest.json',manifest)
        (self.task/'.recorder.lock').touch();(self.task/'events.jsonl').write_bytes(b'')
        producer=pointer(a.__file__);snapshot=self.run/'bootstrap/source-cas'/producer['sha256'][7:]
        snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(a.__file__).read_bytes())
        self.engineering=self.run/'bootstrap/frozen-engineering-attestor.json'
        save(self.run/'campaign-manifest.json',{'run_id':self.run.name})
        save(self.engineering,{'version':'level2_frozen_engineering_v1','campaign_manifest':pointer(self.run/'campaign-manifest.json'),'files':[{**producer,'snapshot':str(snapshot)}],'task_manifests':[pointer(self.task/'manifest.json')]})
        self.request_sha=pointer(self.task/'finalization/request.json')['sha256']
        self.before_ledger=(self.run/'train/ledger/events.jsonl').read_bytes()

    def make_report(self,directory,plan,hashes):
        save(directory/'plan.json',plan)
        sessions=[]
        for row in plan['schedule']:
            p=directory/row['name'];p.mkdir(exist_ok=True,parents=True);output=p/'tiny-output.bin';output.write_bytes(b'fixed-output')
            sessions.append({'directory':str(p),'artifacts':{str(output):pointer(output)['sha256']}})
        save(directory/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[s['directory'] for s in sessions]})
        report={'case_ids':list(map(str,a.ALL_CASES)),'comparison_kind':plan['comparison_kind'],
                'source_hashes':hashes,'evidence_status':'verified_complete','sessions':sessions,
                'results':[{'case_id':str(c),'buffer_config':b,'qualified_performance_eligible':False,
                            'calibration_status':'invalidated','speedup':.8} for c in a.ALL_CASES for b in ('normal','swapped')]}
        save(directory/'report.json',report);self.runtime.expected[sessions[0]['directory']]=deepcopy(report)

    def inspect(self):return a.audit(self.runtime,self.run,'maximum',self.request_sha,self.engineering,full=False)
    def apply(self):return a.attest(self.runtime,self.run,'maximum',self.request_sha,self.engineering,writers_closed=True)
    def request(self):return load(self.task/'finalization/request.json')



def provision_storage(s):
    paths=[Path(a.__file__),*[FIXTURE_ROOT/'approved_v3'/name for name in a.STORAGE_PRODUCERS]]
    eng=load(s.engineering)
    for file in paths[1:]:
        ref=pointer(file);assert ref['sha256']==a.STORAGE_PRODUCERS[file.name]
        snap=s.run/'bootstrap/source-cas'/ref['sha256'][7:];snap.write_bytes(file.read_bytes())
        eng['files'].append({**ref,'snapshot':str(snap)})
    for ref in s.request()['producers']:
        snap=s.run/'bootstrap/source-cas'/ref['sha256'][7:]
        assert pointer(ref['path'])==ref;snap.write_bytes(Path(ref['path']).read_bytes())
    save(s.engineering,eng);s.runtime.producer_paths=lambda:paths
