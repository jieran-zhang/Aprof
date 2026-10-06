"""Tiny real-parser regression; no actual campaign raw/CSV/tensor reads."""
import contextlib,copy,hashlib,json,os,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
LIVE=Path(os.environ.get('APROF_TEST_REPO',HERE))
sys.path[:0]=[str(HERE/'scripts'),str(LIVE/'scripts'),str(LIVE/'tests'),str(LIVE/'src')]
import level2_raw_archive_storage as raw
assert Path(raw.__file__).resolve()==HERE/'scripts/level2_raw_archive_storage.py'
import cannbench_msprof_timing as timing
from test_msprof_raw_storage import v2_session

class Projection:
    """Only a tiny file transport for testing the production parse adapter."""
    def __init__(self,root):
        self.logical=root;self.files={p.relative_to(root).as_posix():{} for p in root.rglob('*') if p.is_file()};self.reverified=False
    def fingerprint(self,p):return {'sha256':'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest(),'size_bytes':Path(p).stat().st_size}
    @contextlib.contextmanager
    def open_binary(self,p):
        with Path(p).open('rb') as stream:yield stream
    def reverify_cached(self):self.reverified=True

@pytest.fixture
def parsed(tmp_path):
    s,req,build=v2_session(tmp_path)
    cases=json.loads((s/'cases.json').read_bytes())
    for case in cases:
        case['kernel_sequence']={r:build['roles'][r]['kernel_symbols'].split(',') for r in 'AB'}
        case['expected_dispatch']={r:{'tiling_key':31 if r=='A' else 0,'kernel_entry':case['kernel_sequence'][r][0],'group_id':'many_groups' if r=='A' else 'generic','fallback':r=='B'} for r in 'AB'}
    proxy=Projection(s/'raw');journal=s/'native/journal.jsonl'
    result=timing.parse_profile(proxy.logical,journal,build,cases,10)
    mapping={result[k]:result[k] for k in ('csv','auxiliary_csv')}
    return s,build,cases,proxy,journal,result,mapping

def test_unchanged_real_parser_preserves_current_selected_and_fallback_fields(parsed):
    _,build,cases,proxy,journal,expected,_=parsed
    actual=raw.parse_profile(proxy,journal,build,cases,10)
    assert actual==expected and proxy.reverified
    assert {row['verified_dispatch']['fallback'] for row in actual['samples']}=={False,True}
    assert all(set(row['verified_dispatch'])==raw.DISPATCH for row in actual['samples'])

def test_legacy_baseline_without_dispatch_is_unchanged(parsed):
    _,build,cases,proxy,journal,_,_=parsed
    for case in cases:case.pop('expected_dispatch')
    expected=timing.parse_profile(proxy.logical,journal,build,cases,10)
    assert all('verified_dispatch' not in row for row in expected['samples'])
    assert raw.parse_profile(proxy,journal,build,cases,10)==expected

@pytest.mark.parametrize('field',sorted(raw.DISPATCH))
def test_each_missing_current_field_rejected(parsed,field):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch'].pop(field)
    with pytest.raises(ValueError,match='dispatch fields'):raw.remap_parsed(result,mapping,proxy)

@pytest.mark.parametrize('field,value',[
    ('future_path','/tmp/unchecked'),('unknown',1),('path',False)])
def test_unknown_dispatch_field_rejected(parsed,field,value):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch'][field]=value
    with pytest.raises(ValueError,match='dispatch fields'):raw.remap_parsed(result,mapping,proxy)

@pytest.mark.parametrize('field,value',[
    ('tiling_key',True),('tiling_key',-1),('tiling_key',2**64),('tiling_key','31'),
    ('fallback',0),('fallback',1),('fallback','false'),('fallback',None),
    ('group_id',''),('group_id',{}),('group_id','/tmp/group'),
    ('kernel_entry','/tmp/kernel'),('kernel_entry',None),
    ('captured_kernel_sequence',[]),('captured_kernel_sequence','kernel'),
    ('captured_kernel_sequence',['/tmp/kernel']),('captured_kernel_sequence',[True]),
])
def test_invalid_dispatch_values_and_nested_paths_rejected(parsed,field,value):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch'][field]=value
    with pytest.raises(ValueError):raw.remap_parsed(result,mapping,proxy)

@pytest.mark.parametrize('value',[None,[],False,'dispatch'])
def test_dispatch_must_be_object(parsed,value):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch']=value
    with pytest.raises(ValueError,match='dispatch fields'):raw.remap_parsed(result,mapping,proxy)

def test_maximum_uint64_key_preserved_without_coercion(parsed):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch']['tiling_key']=2**64-1
    assert raw.remap_parsed(result,mapping,proxy)==result

def test_legacy_four_field_object_not_invented_as_supported_schema(parsed):
    *_,proxy,journal,result,mapping=parsed
    result['samples'][0]['verified_dispatch'].pop('fallback')
    with pytest.raises(ValueError,match='dispatch fields'):raw.remap_parsed(result,mapping,proxy)
