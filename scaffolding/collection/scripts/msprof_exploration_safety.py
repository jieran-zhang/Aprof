#!/usr/bin/env python3
"""Health evidence for new studies; callers own the host lock (never nest it)."""
from __future__ import annotations
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_health(stdout):
    """Parse actual NPU/chip topology and require its explicit empty tables."""
    devices, empty, occupied = [], [], []
    section = pending = None
    saw_topology = saw_processes = False
    for line in stdout.splitlines():
        if not line.startswith('|'):
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if cells[0].startswith('NPU') and 'Health' in cells:
            section, saw_topology = 'topology', True
            continue
        if cells[0].startswith('NPU') and 'Process id' in cells:
            if pending is not None:
                raise ValueError('incomplete topology device row')
            section, saw_processes = 'processes', True
            continue
        if section == 'topology':
            if cells[0].startswith('Chip'):
                continue
            board = re.fullmatch(r'(\d+)\s+(\S+)', cells[0])
            if board and not board[2].isdigit():
                if pending is not None or len(cells) < 2 or cells[1] != 'OK':
                    raise ValueError('incomplete or unhealthy NPU topology')
                pending = (int(board[1]), board[2])
                continue
            chip = re.fullmatch(r'(\d+)\s+(\d+)', cells[0])
            if chip and pending is not None:
                devices.append(dict(npu_id=pending[0], name=pending[1], chip_id=int(chip[1]), physical_device=int(chip[2])))
                pending = None
                continue
            raise ValueError('unrecognized NPU topology row')
        if section == 'processes':
            match = re.fullmatch(r'No running processes found in NPU\s+(\d+)', cells[0])
            if match and len(cells) == 1:
                empty.append(int(match[1]))
                continue
            chip = re.fullmatch(r'(\d+)\s+(\d+)', cells[0])
            if chip and len(cells) >= 3 and cells[1].isdigit():
                occupied.append(dict(npu_id=int(chip[1]), chip_id=int(chip[2]), pid=int(cells[1])))
                continue
            raise ValueError('unrecognized NPU process row')
    if not saw_topology or not saw_processes or not devices or pending is not None:
        raise ValueError('missing or incomplete NPU topology/process table')
    ids = {row['npu_id'] for row in devices}
    pairs = {(d['npu_id'], d['chip_id']) for d in devices}
    if len(pairs) != len(devices) or len({d['physical_device'] for d in devices}) != len(devices):
        raise ValueError('duplicate NPU/chip or physical device topology entry')
    if len(set(empty)) != len(empty) or not set(empty) <= ids:
        raise ValueError('duplicate or unknown empty NPU process table')
    if any((p['npu_id'], p['chip_id']) not in pairs for p in occupied):
        raise ValueError('process references unknown NPU/chip')
    return dict(devices=devices, npu_ids=sorted(ids), empty_npu_ids=sorted(empty),
                processes=occupied, no_device_processes=not occupied and set(empty) == ids)


def query_health(*, timeout=30):
    """Explicit hardware query; preserve nonzero status, parse errors and timeouts."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('health timeout must be positive and finite')
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = '/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common'
    argv = ['/usr/local/sbin/npu-smi', 'info']
    record = dict(schema_version='1.0.0', kind='msprof_exploration_health', argv=argv,
                  host=socket.gethostname(), started_at=now(), exit_code=None, exit_status=None,
                  stdout='', stderr='', no_device_processes=False, status='failed', error=None)
    try:
        result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=timeout)
        record.update(exit_code=result.returncode, exit_status=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode:
            raise RuntimeError('npu-smi exited unsuccessfully')
        record.update(parse_health(result.stdout))
        if not record['no_device_processes']:
            raise RuntimeError('device process inventory is occupied or incomplete')
        record['status'] = 'passed'
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            for key, value in [('stdout', exc.stdout), ('stderr', exc.stderr)]:
                record[key] = value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        record['error'] = dict(type=type(exc).__name__, message=str(exc))
    record['finished_at'] = now()
    return record


def health(out, *, timeout=30):
    """Caller holds exclusive_host. Query once, save evidence, fail closed."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Reserve before querying so reuse cannot touch hardware again.
    with out.open('x') as stream:
        record = query_health(timeout=timeout)
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if record['status'] != 'passed':
        raise RuntimeError(f'device health check failed; see {out}')
    return record
