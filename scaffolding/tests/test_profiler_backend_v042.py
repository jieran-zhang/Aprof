"""Collector contracts tested with fake processes; real fixture is offline only."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = Path(os.environ.get('APROF_SKILL_LIB', ROOT / 'skill-libs/graph-base/0.4.1'))
if not (RELEASE / 'skills/ascendc-aprof-profiling/scripts/profile_capture.py').is_file():
    pytest.skip('selected release does not contain the versioned profiler collector', allow_module_level=True)
SCRIPTS = RELEASE / 'skills/ascendc-aprof-profiling/scripts'
FIXTURE = Path(__file__).parent / 'fixtures/profiler_v042/real-capture'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


collector = module('profile_capture')
normalizer = module('normalize_profile')
from aprof_runtime.store import EpisodeStore
from aprof_runtime.profile_evidence import load_capture_manifest, normalize_profile, compare_profiles


def executable(path, code):
    path.write_text('#!' + sys.executable + '\n' + code)
    path.chmod(0o755)
    return path


@pytest.fixture
def project(tmp_path):
    source = tmp_path / 'operator'
    source.mkdir()
    (source / 'kernel.cpp').write_text('kernel source\n')
    (source / 'build').mkdir()
    binary = executable(source / 'build/operator', "from pathlib import Path\np=Path('calls.txt')\np.write_text(p.read_text()+'launch\\n' if p.exists() else 'launch\\n')\n")
    # Runtime-generated output is not part of source provenance.
    cwd = tmp_path / 'work'
    cwd.mkdir()
    probe = executable(tmp_path / 'npu-smi', "print('NPU Name : 9392\\nChip Name : Ascend910')\n")
    tool = executable(tmp_path / 'msprof', '''import sys,shlex,subprocess
from pathlib import Path
if '--help' in sys.argv:
 print('msprof op --application --warm-up --launch-count');sys.exit(0)
args=sys.argv[1:]
application=next(x.split('=',1)[1] for x in args if x.startswith('--application='))
subprocess.run(shlex.split(application),check=True)
root=Path(next(x.split('=',1)[1] for x in args if x.startswith('--output=')))
collection=root/'OPPROF_fixture'/'exp_kernel'/'0';collection.mkdir(parents=True)
(collection/'OpBasicInfo.csv').write_text('Op Name,Task Duration(us)\\nexp_kernel,2.5\\n')
(collection/'PipeUtilization.csv').write_text('block_id,aiv_vec_ratio\\n0,0.2\\n1,0.4\\n')
''')
    return dict(backend='auto', architecture='Ascend910C', soc='9392', device=0,
                case_id=1, kernel='exp_kernel', role='baseline', source_dir=str(source),
                binary=str(binary), workload={'shape':[1024], 'dtype':'float16'},
                command=[str(binary)], cwd=str(cwd), warmups=10, repeats=5,
                tool_path=str(tool), npu_smi_path=str(probe), timeout_seconds=10)


@pytest.mark.parametrize('architecture,soc,expected', [('A3','9392','msprof'),('Ascend910C','9392','msprof'),('Ascend950','9599','npu-compute'),('dav-3510','3510','npu-compute')])
def test_supported_routing(architecture,soc,expected):
    assert collector.select_backend('auto',architecture,soc)==expected


@pytest.mark.parametrize('backend,architecture,soc', [('npu-compute','A3','9392'),('auto','Ascend910B',''),('auto','Ascend950','9392')])
def test_no_unsupported_or_mismatched_fallback(backend,architecture,soc):
    with pytest.raises(ValueError):
        collector.select_backend(backend,architecture,soc)


def test_msprof_receipts_independent_samples_and_comparable_identity(project,tmp_path):
    db=tmp_path/'episodes.sqlite'
    result=collector.capture(project,tmp_path/'baseline',db)
    assert (Path(project['cwd'])/'calls.txt').read_text().splitlines()==['launch']*15
    with EpisodeStore(db) as store:
        manifest=load_capture_manifest(store,result['manifest_hash'])
        assert len(set(c['collection'] for c in manifest['captures']))==5
        assert all('--warm-up=0' in c['argv'] and '--launch-count=1' in c['argv'] for c in manifest['captures'])
        assert all(any(x.startswith('--application=') for x in c['argv']) for c in manifest['captures'])
        specs={'duration':{'unit':'us','file':'OpBasicInfo.csv','format':'csv','field':'Task Duration(us)'}}
        profile=normalize_profile(store,result['manifest_hash'],normalizer.expand_specs(manifest,specs))
        assert profile['metrics']['duration']['samples']==[2.5]*5
        assert profile['metrics']['duration']['status']=='available'
        cores={'vector':{'unit':'ratio','file':'PipeUtilization.csv','format':'csv','field':'aiv_vec_ratio'}}
        core_profile=normalize_profile(store,result['manifest_hash'],normalizer.expand_specs(manifest,cores))
        assert len(core_profile['metrics']['vector']['samples'])==5  # ten core rows != ten process samples
        changed=dict(project,role='candidate')
    candidate=collector.capture(changed,tmp_path/'candidate',db)
    with EpisodeStore(db) as store:
        cm=load_capture_manifest(store,candidate['manifest_hash'])
        cp=normalize_profile(store,candidate['manifest_hash'],normalizer.expand_specs(cm,specs))
        assert compare_profiles(store,profile,cp,'duration')


def test_capture_failure_retains_logs_and_never_publishes_success(project,tmp_path):
    executable(Path(project['binary']),"raise SystemExit(9)\n")
    with pytest.raises(RuntimeError):
        collector.capture(project,tmp_path/'failed',tmp_path/'db')
    assert (tmp_path/'failed/failure.json').exists()
    assert (tmp_path/'failed/warmup-000.execution.json').exists()
    assert not (tmp_path/'failed/capture-manifest.json').exists()


def test_declared_a3_must_match_actual_board(project,tmp_path):
    executable(Path(project['npu_smi_path']),"print('Ascend950 dav-3510')\n")
    with pytest.raises(ValueError,match='actual npu-smi'):
        collector.capture(project,tmp_path/'wrong-board',tmp_path/'db')
    assert not (Path(project['cwd'])/'calls.txt').exists()


def test_nonzero_device_requires_physical_mapping(project,tmp_path):
    project['device']=3
    with pytest.raises(ValueError,match='physical_device'):
        collector.capture(project,tmp_path/'wrong-device',tmp_path/'db')


def test_output_collision_does_not_overwrite(project,tmp_path):
    (tmp_path/'existing').mkdir()
    with pytest.raises(FileExistsError):
        collector.capture(project,tmp_path/'existing',tmp_path/'db')


def test_terminal_receipts_and_symlinks(tmp_path):
    report=tmp_path/'good.npu-rep';report.write_bytes(b'report')
    assert collector.terminal_path('npu-compute: report= '+str(report),'report',tmp_path,tmp_path)==report
    for text in ('target succeeded','npu-compute: report= missing.npu-rep','npu-compute: report= ../escape.npu-rep'):
        with pytest.raises(ValueError):
            collector.terminal_path(text,'report',tmp_path,tmp_path)
    (tmp_path/'alias.npu-rep').symlink_to(report)
    with pytest.raises(ValueError,match='symlink'):
        collector.terminal_path('npu-compute: report= alias.npu-rep','report',tmp_path,tmp_path)


def test_different_collections_never_merged(tmp_path):
    for name in ('collection-p1-0001','collection-p1-0002'):
        directory=tmp_path/name;directory.mkdir();(directory/'summary.jsonl').write_text('{}\n')
    with pytest.raises(ValueError,match='exactly one collection'):
        collector.collection_directory(tmp_path,'npu-compute','kernel')
    assert collector.collection_directory(tmp_path,'npu-compute','kernel','collection-p1-0001')==tmp_path/'collection-p1-0001'
    with pytest.raises(ValueError,match='safe relative'):
        collector.collection_directory(tmp_path,'npu-compute','kernel','../escape')


def test_real_950_fixture_preserves_original_bytes():
    manifest=json.loads((FIXTURE/'fixture-manifest.json').read_text())
    for item in manifest['files']:
        path=FIXTURE/item['name']
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
    assert manifest['device']=={'chip_info':'Ascend950PR_9599 V100','arch_info':'3510'}


def test_npu_compute_real_fixture_offline_receipt_flow(project,tmp_path):
    executable(Path(project['npu_smi_path']),"print('Ascend950PR_9599 V100 arch3510')\n")
    tool=executable(tmp_path/'npu-compute', f'''import sys,json,shutil
from pathlib import Path
args=sys.argv[1:]
if '--list-sections' in args:
 print('Pipeline PipeUtilization Memory MemoryL0 MemoryUB L2Cache ArithmeticUtilization ResourceConflictRatio');sys.exit(0)
export=Path(args[args.index('--export')+1])
if '--import' in args:
 target=export/'collection-p1-0001';target.mkdir()
 for name in ['summary.jsonl','HardwareInfo.jsonl','PipeUtilization.csv']:
  shutil.copyfile(Path({str(FIXTURE)!r})/name,target/name)
 print('npu-compute: unpacked= '+str(target))
else:
 export.write_bytes(b'offline mock archive; no real hardware capture')
 print('npu-compute: report= '+str(export))
''')
    project.update(architecture='Ascend950',soc='9599',tool_path=str(tool),warmups=0,repeats=1,sections=['PipeUtilization'],kernel='add_custom(unsigned char*, unsigned char*, unsigned char*, AddCustomTilingData)')
    result=collector.capture(project,tmp_path/'npu-offline',tmp_path/'db')
    with EpisodeStore(tmp_path/'db') as store:
        manifest=load_capture_manifest(store,result['manifest_hash'])
        assert '--warm-up=0' not in manifest['captures'][0]['argv']
        specs={'aiv_time':{'unit':'us','file':'summary.jsonl','format':'jsonl','field':'aiv_time(us)','where':{'category':'PipeUtilization'}}}
        profile=normalize_profile(store,result['manifest_hash'],normalizer.expand_specs(manifest,specs))
        metric=profile['metrics']['aiv_time']
        assert metric['samples']==[31.998788]
        assert metric['status']=='unstable'  # one report is never five independent samples
        unavailable={'aic_time':{'unit':'us','file':'summary.jsonl','format':'jsonl','field':'aic_time(us)','where':{'category':'PipeUtilization'}}}
        missing=normalize_profile(store,result['manifest_hash'],normalizer.expand_specs(manifest,unavailable))
        assert missing['metrics']['aic_time']['status']=='missing'
        assert missing['metrics']['aic_time']['value'] is None


@pytest.mark.parametrize('changed', ['binary', 'source', 'tool'])
def test_identity_mutation_rejected_and_failure_receipt_retained(project, tmp_path, changed):
    target = Path(project['binary']) if changed == 'binary' else (
        Path(project['source_dir']) / 'kernel.cpp' if changed == 'source' else Path(project['tool_path']))
    executable(Path(project['binary']), "from pathlib import Path\np=Path(" + repr(str(target)) + ")\np.write_text(p.read_text()+'# changed during execution\\n')\n")
    out = tmp_path / 'mutating'
    with pytest.raises(RuntimeError, match='retained receipt'):
        collector.capture(project, out, tmp_path / 'db')
    receipt = json.loads((out / 'warmup-000.execution.json').read_text())
    assert receipt['exit_code'] == 0
    assert 'identity changed during launch' in receipt['error']['message']
    field = {'binary':'binary_hash', 'source':'source_hash', 'tool':'tool_hash'}[changed]
    assert receipt['identity_checks']['before'][field] != receipt['identity_checks']['after'][field]
    assert (out / 'failure.json').is_file()
    assert not (out / 'capture-manifest.json').exists()
