import json
from pathlib import Path

import pytest

from level2_correctness_output_dedup import deduplicate, digest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def fixture(tmp_path):
    stage = tmp_path / 'train/tasks/cummin/candidates/cummin001/stages/correctness'
    cases = []; verified = []
    for cid in range(1, 21):
        case = f'case_{cid:02d}'; outputs = []; standalone = {}
        for name in ('values', 'indices'):
            data = (case + name).encode()
            source = stage / 'evidence' / case / f'output.bin.{name}'
            target = stage / 'standalone' / case / f'output.bin.{name}'
            source.parent.mkdir(parents=True, exist_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data); target.write_bytes(data)
            sha = digest(source)
            outputs.append({'name': name, 'path': str(source), 'bytes': len(data), 'sha256': sha})
            standalone[name] = {'path': str(target), 'sha256': sha}
        write(stage / 'evidence' / case / 'output.bin.outputs.json',
              {'version': 'level2_output_bundle_v1', 'operator': 'cummin', 'outputs': outputs})
        cases.append({'case_id': cid, 'outputs': standalone})
        verified.append({'case_id': str(cid), 'passed': True})
    write(stage / 'result.json', {'kind': 'correctness', 'status': 'passed', 'ended_at': 1})
    write(stage / 'standalone/completion.json', {'status': 'passed', 'planned_cases': list(range(1, 21)), 'completed': cases})
    write(stage / 'evidence/completion.json', {'status': 'passed', 'planned_cases': [str(i) for i in range(1, 21)], 'completed': verified})
    return stage


def test_closed_pairs_keep_both_logical_paths_and_replay(tmp_path):
    stage = fixture(tmp_path)
    result = deduplicate(stage, writers_closed=True)
    assert result['logical_pairs'] == 40
    assert result['source_bytes_preserved'] is True
    for cid in range(1, 21):
        for name in ('values', 'indices'):
            source = stage / 'evidence' / f'case_{cid:02d}' / f'output.bin.{name}'
            target = stage / 'standalone' / f'case_{cid:02d}' / f'output.bin.{name}'
            assert source.stat().st_ino == target.stat().st_ino
            assert digest(source) == digest(target)
    assert deduplicate(stage, writers_closed=True)['receipt'] == result['receipt']


def test_changed_output_or_open_writer_fails_closed(tmp_path):
    stage = fixture(tmp_path)
    with pytest.raises(ValueError, match='writers'):
        deduplicate(stage)
    target = stage / 'standalone/case_01/output.bin.values'
    target.write_bytes(b'changed')
    with pytest.raises(ValueError, match='identity|bytes'):
        deduplicate(stage, writers_closed=True)
    assert not (stage / 'correctness-output-dedup/completion.json').exists()
