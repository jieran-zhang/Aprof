"""Portable prepared-input cache behavior; these tests execute CPU-only generators."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = Path(os.environ.get('APROF_SKILL_LIB', ROOT / 'skill-libs/graph-base/0.4.1'))
if RELEASE.name != '0.5.0':
    pytest.skip('0.5.0 preparation helper tests require selected 0.5.0 release', allow_module_level=True)
SCRIPT = RELEASE / 'skills/ascendc-aprof-profiling/scripts/prepare_workload.py'
spec = importlib.util.spec_from_file_location('prepare_workload_v050', SCRIPT)
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


@pytest.fixture
def config(tmp_path):
    generator = tmp_path / 'generator.py'
    generator.write_text('''import json,sys
from pathlib import Path
output=Path(sys.argv[1]);oracle=Path(sys.argv[2]);counter=Path(sys.argv[3])
count=int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(count+1))
(output/'input.bin').write_bytes(b'input')
(output/'expected.bin').write_bytes(oracle.read_bytes())
(output/'metadata.json').write_text(json.dumps({'input':str(output/'input.bin'),'expected':str(output/'expected.bin')}))
''')
    oracle = tmp_path / 'oracle.txt'
    oracle.write_text('reference bytes')
    return dict(schema_version='1.0.0', workload={'shape':[1024], 'dtype':'float16', 'seed':1},
                dependencies={'python':sys.executable, 'generator':str(generator), 'oracle':str(oracle)},
                commands=[['{dep:python}','{dep:generator}','{output_dir}','{dep:oracle}',str(tmp_path/'counter.txt')]],
                outputs=['input.bin','expected.bin','metadata.json'], timeout_seconds=10)


def prepare(config,tmp_path,name='call'):
    return cache.prepare(config,tmp_path/'cache',tmp_path/(name+'.json'))


def test_miss_hit_generate_once_preserve_absolute_metadata_and_entry_receipt(config,tmp_path):
    first=prepare(config,tmp_path,'first')
    assert first['status']=='prepared'
    output=Path(first['output_dir'])
    metadata=json.loads((output/'metadata.json').read_text())
    assert Path(metadata['input'])==output/'input.bin'
    assert Path(metadata['input']).read_bytes()==b'input'
    entry_bytes=(output.parent/'entry.json').read_bytes()
    second=prepare(config,tmp_path,'second')
    assert second['status']=='hit'
    assert second['output_dir']==first['output_dir']
    assert second['entry_receipt_hash']==first['entry_receipt_hash']
    assert (output.parent/'entry.json').read_bytes()==entry_bytes
    assert (tmp_path/'counter.txt').read_text()=='1'
    assert second['preparation_seconds']==0
    assert second['candidate_correctness_cached'] is False
    assert json.loads((tmp_path/'first.json').read_text())['status']=='prepared'
    assert json.loads((tmp_path/'second.json').read_text())['status']=='hit'


def test_same_dependency_bytes_from_other_candidate_share_cache(config,tmp_path):
    first=prepare(config,tmp_path,'first')
    candidate=tmp_path/'candidate';candidate.mkdir()
    other=copy.deepcopy(config)
    for key in ('generator','oracle'):
        original=Path(config['dependencies'][key]); target=candidate/original.name
        shutil.copyfile(original,target);other['dependencies'][key]=str(target)
    second=prepare(other,tmp_path,'second')
    assert second['status']=='hit' and second['cache_key']==first['cache_key']
    assert (tmp_path/'counter.txt').read_text()=='1'


@pytest.mark.parametrize('kind',['workload','oracle','generator','command','environment'])
def test_semantic_identity_change_invalidates(config,tmp_path,kind):
    first=prepare(config,tmp_path,'first')
    if kind=='workload': config['workload']['seed']=2
    elif kind in ('oracle','generator'):
        path=Path(config['dependencies'][kind]);path.write_text(path.read_text()+'\n# changed')
    elif kind=='command': config['commands'][0].append('new-contract-argument')
    else: config['environment']={'SEED':'2'}
    second=prepare(config,tmp_path,'second')
    assert second['status']=='prepared' and second['cache_key']!=first['cache_key']
    assert (tmp_path/'counter.txt').read_text()=='2'


def test_changed_producer_invalidates_cache(config,tmp_path,monkeypatch):
    first=prepare(config,tmp_path,'first')
    changed=tmp_path/'new_prepare.py';changed.write_text(SCRIPT.read_text()+'\n# producer revision\n')
    monkeypatch.setattr(cache,'__file__',str(changed))
    second=prepare(config,tmp_path,'second')
    assert second['status']=='prepared' and second['cache_key']!=first['cache_key']


@pytest.mark.parametrize('kind',['output','missing','extra','symlink','receipt','log'])
def test_tampered_or_incomplete_entry_is_never_a_hit(config,tmp_path,kind):
    first=prepare(config,tmp_path,'first')
    output=Path(first['output_dir'])
    if kind=='output': (output/'input.bin').write_bytes(b'changed')
    elif kind=='missing': (output/'input.bin').unlink()
    elif kind=='extra': (output/'extra.bin').write_bytes(b'untracked')
    elif kind=='symlink':
        (output/'input.bin').unlink();(output/'input.bin').symlink_to(output/'expected.bin')
    elif kind=='receipt': (output.parent/'entry.json').write_text('{}')
    else: (output.parent/'logs/command-000.stdout.log').write_text('changed')
    with pytest.raises(ValueError): prepare(config,tmp_path,'second')
    assert (tmp_path/'counter.txt').read_text()=='1'
    assert json.loads((tmp_path/'second.json').read_text())['status']=='failed'


def test_dependency_changed_during_prepare_fails_and_retains_logs(config,tmp_path):
    generator=Path(config['dependencies']['generator'])
    generator.write_text(generator.read_text()+"\nPath(__file__).write_text(Path(__file__).read_text()+'# mutation\\n')\n")
    with pytest.raises(RuntimeError,match='identity changed'):
        prepare(config,tmp_path,'failed')
    attempts=list((tmp_path/'cache/entries').glob('*/attempts/*'))
    assert len(attempts)==1
    assert (attempts[0]/'failure.json').is_file()
    receipt=json.loads((attempts[0]/'logs/command-000.json').read_text())
    assert receipt['exit_code']==0 and receipt['error']
    assert not list((tmp_path/'cache/entries').glob('*/ready.json'))


def test_failed_command_never_hits_retry_uses_new_stable_attempt(config,tmp_path):
    generator=Path(config['dependencies']['generator'])
    generator.write_text('''import sys
from pathlib import Path
marker=Path(sys.argv[3])
if not marker.exists():
 marker.write_text('failed once');print('failure evidence',file=sys.stderr);raise SystemExit(7)
out=Path(sys.argv[1]);(out/'input.bin').write_bytes(b'ok')
''')
    config['outputs']=['input.bin']
    with pytest.raises(RuntimeError,match='exited 7'): prepare(config,tmp_path,'failed')
    success=prepare(config,tmp_path,'retry')
    assert success['status']=='prepared'
    assert prepare(config,tmp_path,'hit')['status']=='hit'
    attempts=list((tmp_path/'cache/entries').glob('*/attempts/*'))
    assert len(attempts)==2
    failures=[p for p in attempts if (p/'failure.json').exists()]
    assert len(failures)==1
    assert (failures[0]/'logs/command-000.stderr.log').read_text().strip()=='failure evidence'


def test_partial_entry_outputs_are_not_reused(config,tmp_path):
    key,_,_=cache.identity(config)
    entry=tmp_path/'cache/entries'/key.removeprefix('sha256:')
    partial=entry/'attempts'/('a'*32)
    (partial/'outputs').mkdir(parents=True)
    (partial/'outputs/input.bin').write_bytes(b'partial')
    result=prepare(config,tmp_path)
    assert result['status']=='prepared'
    assert result['output_dir']!=str(partial/'outputs')
    assert (partial/'outputs/input.bin').read_bytes()==b'partial'


def test_interpreter_symlink_resolves_and_cache_symlink_refused(config,tmp_path):
    interpreter=tmp_path/'python-link';interpreter.symlink_to(Path(sys.executable).resolve())
    config['dependencies']['python']=str(interpreter)
    assert prepare(config,tmp_path,'first')['status']=='prepared'
    alias=tmp_path/'cache-alias';alias.symlink_to(tmp_path/'cache',target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):
        cache.prepare(config,alias,tmp_path/'refused.json')


def test_competing_prepare_does_not_run_twice(config,tmp_path):
    generator=Path(config['dependencies']['generator'])
    generator.write_text('import time\ntime.sleep(0.5)\n'+generator.read_text())
    config_file=tmp_path/'config.json';config_file.write_text(json.dumps(config))
    first=subprocess.Popen([sys.executable,str(SCRIPT),'--config',str(config_file),'--cache-dir',str(tmp_path/'cache'),'--receipt',str(tmp_path/'first.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(200):
            if list((tmp_path/'cache/locks').glob('*/owner.json')): break
            time.sleep(.01)
        else: pytest.fail('first process did not acquire lock')
        with pytest.raises(RuntimeError,match='busy'):
            prepare(config,tmp_path,'competing')
        stdout,stderr=first.communicate(timeout=10)
        assert first.returncode==0,stderr
    finally:
        if first.poll() is None: first.kill();first.wait()
    assert (tmp_path/'counter.txt').read_text()=='1'
    assert prepare(config,tmp_path,'after')['status']=='hit'


def test_no_shell_or_path_escape_and_no_receipt_overwrite(config,tmp_path):
    bad=copy.deepcopy(config);bad['commands'][0][0]='python3'
    with pytest.raises(ValueError,match='explicitly hashed'):
        prepare(bad,tmp_path,'bad-command')
    bad=copy.deepcopy(config);bad['outputs']=['../escape']
    with pytest.raises(ValueError,match='relative'):
        prepare(bad,tmp_path,'bad-path')
    prepare(config,tmp_path,'once')
    with pytest.raises(FileExistsError): prepare(config,tmp_path,'once')


def test_ambient_environment_not_hidden_cache_input(config,tmp_path,monkeypatch):
    monkeypatch.setenv('UNDECLARED_PREP_INPUT','do-not-inherit')
    generator=Path(config['dependencies']['generator'])
    generator.write_text('import os\nassert "UNDECLARED_PREP_INPUT" not in os.environ\n'+generator.read_text())
    assert prepare(config,tmp_path)['status']=='prepared'


def test_timeout_retains_failure_and_never_publishes_ready(config,tmp_path):
    generator=Path(config['dependencies']['generator'])
    generator.write_text('import time\nprint("before timeout",flush=True)\ntime.sleep(5)\n')
    config['timeout_seconds']=0.05
    with pytest.raises(RuntimeError): prepare(config,tmp_path,'timeout')
    attempts=list((tmp_path/'cache/entries').glob('*/attempts/*'))
    assert len(attempts)==1 and (attempts[0]/'failure.json').exists()
    assert not list((tmp_path/'cache/entries').glob('*/ready.json'))
    receipt=json.loads((attempts[0]/'logs/command-000.json').read_text())
    assert receipt['error']['type']=='TimeoutExpired'
    assert receipt['exit_code'] is not None
    assert receipt['elapsed_seconds']<2
