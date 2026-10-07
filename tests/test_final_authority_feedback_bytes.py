"""Real tiny ledger/attestation: feedback identities bind original JSON bytes."""
from pathlib import Path
import importlib.util,json,os,sys
import pytest
ROOT=Path(os.environ.get('APROF_TEST_REPO',Path(__file__).resolve().parents[1]))
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'scripts'),str(ROOT/'src')]
from test_final_report_authority import provision_storage,read
from test_final_report_attestation import Small,load,pointer
import test_level2_finalize as producer_fixture
spec=importlib.util.spec_from_file_location('feedback_bytes_authority',Path(__file__).parents[1]/'scripts/level2_final_report_authority.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def formatted_proof(tmp_path,monkeypatch,*,failed=True,indent=2):
    original=producer_fixture.save
    def formatted(path,value):
        path=Path(path)
        if path.parent.name=='feedback' and path.name=='maximum001.json':
            path.parent.mkdir(parents=True,exist_ok=True)
            # Alter representation before observe/freeze, so genuine ledger and
            # final request bind these original bytes without retrospective edits.
            path.write_text(json.dumps(value,sort_keys=False,ensure_ascii=False,indent=indent))
        else:original(path,value)
    monkeypatch.setattr(producer_fixture,'save',formatted)
    s=Small(tmp_path,monkeypatch,failed=(1,) if failed else ())
    provision_storage(s);result=s.apply();att=load(result['attestation']['path'])
    session=Path(att['comparisons'][0]['session_directories'][0])
    feedback=s.request()['source_attempts'][0]['feedback']
    assert f.digest(f.canonical(load(feedback['path'])))!=feedback['sha256']
    assert pointer(feedback['path'])==feedback
    return s,result,session,feedback


@pytest.mark.parametrize('failed',[True,False])
@pytest.mark.parametrize('indent',[2,None])
def test_original_formatted_feedback_is_bound_without_reencoding(tmp_path,monkeypatch,failed,indent):
    s,r,p,feedback=formatted_proof(tmp_path,monkeypatch,failed=failed,indent=indent)
    ledger=(s.run/'train/ledger/events.jsonl').read_bytes()
    value=f.authority(p,read)
    assert feedback in value['protected'] and value['report']==pointer(p.parent/'report.json')
    assert value['historical_report_authority'] is False
    assert (s.run/'train/ledger/events.jsonl').read_bytes()==ledger


@pytest.mark.parametrize('change',['whitespace','semantic'])
def test_changed_original_feedback_bytes_fail_even_after_prior_acceptance(tmp_path,monkeypatch,change):
    s,r,p,feedback=formatted_proof(tmp_path,monkeypatch)
    assert f.authority(p,read)['report']==pointer(p.parent/'report.json')
    path=Path(feedback['path']);value=load(path)
    if change=='semantic':value['measurement_error']={'changed':'must reject'}
    path.write_bytes(f.canonical(value))
    with pytest.raises(ValueError,match='bound authority bytes differ'):f.authority(p,read)


def test_original_canonical_feedback_remains_accepted(tmp_path,monkeypatch):
    s=Small(tmp_path,monkeypatch);provision_storage(s);result=s.apply()
    att=load(result['attestation']['path']);p=Path(att['comparisons'][0]['session_directories'][0])
    assert f.authority(p,read)['report']==pointer(p.parent/'report.json')
