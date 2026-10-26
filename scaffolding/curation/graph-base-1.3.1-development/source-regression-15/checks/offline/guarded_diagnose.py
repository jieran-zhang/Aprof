"""Run a copied package tool under an explicit Python audit policy."""
import argparse
from collections import Counter
import datetime
import json
import os
from pathlib import Path
import runpy
import sys
import time
import traceback

parser = argparse.ArgumentParser()
parser.add_argument('--root', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--mode', choices=('release', 'replay', 'diagnose'), required=True)
args = parser.parse_args()
assert sys.flags.isolated == 1, 'requires Python -I'
sys.dont_write_bytecode = True
root = os.path.realpath(args.root)
out = os.path.realpath(args.out)
python_roots = sorted({os.path.realpath(sys.base_prefix), os.path.realpath(sys.prefix)})
os.chdir(root)
counts = Counter()
blocked = []
phase = 'self_test'

def inside(path, base):
    return path == base or path.startswith(base + os.sep)

def canonical(path):
    if isinstance(path, int):
        return None
    return os.path.realpath(os.fsdecode(path))

def deny(event, target, reason):
    blocked.append({'phase': phase, 'event': event, 'target': str(target), 'reason': reason})
    raise PermissionError(f'offline audit denied {event}: {target} ({reason})')

def check_path(event, value, write=False):
    if value is None:
        value = os.getcwd()
    path = canonical(value)
    if path is None:
        return
    if write:
        if not inside(path, out):
            deny(event, path, 'writes permitted only in offline review output')
    elif not any(inside(path, base) for base in [root, out, *python_roots]):
        deny(event, path, 'read/visit outside copied package, review output and Python runtime')

def audit(event, values):
    counts[event] += 1
    if event.startswith('socket.'):
        deny(event, values, 'network/socket operations forbidden')
    if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.spawn', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'pty.spawn'}:
        deny(event, values, 'subprocess/exec/fork forbidden; no compiler or external backend')
    if event.startswith('ctypes.'):
        deny(event, values, 'ctypes native escape forbidden')
    if event == 'open':
        path, mode, flags = values
        write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        check_path(event, path, write)
    elif event in {'os.listdir', 'os.scandir', 'os.chdir'}:
        check_path(event, values[0])
    elif event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown', 'os.truncate', 'os.utime'}:
        check_path(event, values[0], True)
    elif event in {'os.rename', 'os.link'}:
        check_path(event, values[0], True)
        check_path(event, values[1], True)
    elif event == 'os.symlink':
        deny(event, values, 'symlink creation forbidden')
    elif event == 'import' and len(values) > 1 and values[1]:
        check_path(event, values[1])

sys.addaudithook(audit)
self_tests = []
for label, target in [
    ('original_repository', '/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/README.md'),
    ('raw_task_input', '/tmp/aprof-raw15-suoslncl/SOURCE-FILES.json'),
    ('execution_output', '/tmp/aprof-raw15-autonomous-c/case-14/R2-reasoning.json'),
    ('maintenance_workspace', '/tmp/aprof-selection-maintenance-vdxp89ro/README.md'),
    ('upstream_checkout_anywhere_outside_allowlist', '/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/cannbot-skills/README.md'),
]:
    try:
        with open(target, 'rb') as handle:
            handle.read(1)
    except PermissionError:
        self_tests.append({'test': label, 'blocked': True})
    else:
        raise AssertionError('audit self-test did not block ' + label)
import socket
try:
    socket.socket()
except PermissionError:
    self_tests.append({'test': 'socket_creation', 'blocked': True})
else:
    raise AssertionError('audit self-test did not block socket creation')
phase = 'tool_execution'
started = time.monotonic()
error = None
exit_code = 0
if args.mode == 'release':
    script = root + '/tools/release.py'
    tool_args = ['--root', root, '--allow-unsealed']
elif args.mode == 'diagnose':
    script = out + '/diagnose_replay.py'
    tool_args = ['--root', root, '--out', out]
else:
    script = root + '/tools/replay_source_regression.py'
    tool_args = ['--root', root, '--case', 'case-01', '--case', 'case-08', '--case', 'case-14', '--output', out + '/replay-result.json']
sys.argv = [script, *tool_args]
try:
    runpy.run_path(script, run_name='__main__')
except SystemExit as exc:
    exit_code = int(exc.code or 0)
    if exit_code:
        error = repr(exc)
except BaseException as exc:
    exit_code = 1
    error = repr(exc)
    traceback.print_exc()
finally:
    summary = {
        'mode': args.mode, 'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python_isolated': bool(sys.flags.isolated), 'dont_write_bytecode': sys.dont_write_bytecode,
        'root': root, 'cwd': os.getcwd(), 'argv': sys.argv, 'python_runtime_allowlist': python_roots,
        'read_allowlist': [root, out, *python_roots], 'write_allowlist': [out],
        'rules': ['Resolve paths via realpath; deny reads/directory visits/import files outside allowlist',
                  'Deny all copied package writes; only review output writes allowed',
                  'Deny all socket.* audit events', 'Deny subprocess/exec/spawn/fork and ctypes.*',
                  'No symlinks in copied package; deny new symlinks'],
        'self_tests': self_tests, 'blocked_events': blocked,
        'tool_execution_blocked_count': sum(v['phase'] == 'tool_execution' for v in blocked),
        'audit_event_counts': dict(counts), 'elapsed_seconds': round(time.monotonic() - started, 3),
        'exit_code': exit_code, 'error': error,
        'limitations': ['Python audit policy is not an OS-level sandbox.',
                        'Hook starts after isolated interpreter initialization and standard runner imports.',
                        'Python stat/access metadata operations are not all audited; native code outside audited interfaces is not comprehensively sandboxed.',
                        'Python standard library and installed runtime dependencies remain readable; package data/code must come from the copy.'],
    }
    with open(out + '/' + args.mode + '-audit.json', 'w') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
sys.exit(exit_code)
