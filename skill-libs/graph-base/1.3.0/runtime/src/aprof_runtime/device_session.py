"""Long-lived probe process; native processes still verify their current context."""
import json
from pathlib import Path
import select
import subprocess
import time
from .execution_policy import append, diagnostics, wait


class DeviceSession:
    def __init__(self, argv, root, fallback):
        self.argv, self.root, self.fallback = argv, Path(root), fallback
        self.root.mkdir(parents=True, exist_ok=True)
        self.stderr = (self.root/'probe-session.stderr').open('wb')
        self.process = subprocess.Popen([*argv, '--session'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr, start_new_session=True)
        self.started = time.monotonic()
        self.queries = 0

    def __call__(self, argv, *, cwd, env, timeout_seconds):
        if argv != self.argv:
            return self.fallback(argv, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
        began = time.monotonic()
        self.process.stdin.write(b'query\n'); self.process.stdin.flush()
        warned = False
        while not select.select([self.process.stdout], [], [], .1)[0]:
            if not warned and time.monotonic()-began > max(0, timeout_seconds):
                append(self.root/'checkpoints.jsonl', {'event':'probe_target_exceeded', 'diagnostics':diagnostics(self.process.pid), 'action':'continue'})
                warned = True
            if self.process.poll() is not None:
                raise RuntimeError('probe session exited; see probe-session.stderr')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('probe session closed without observation')
        value = json.loads(line)
        self.queries += 1
        append(self.root/'device-observations.jsonl', {'pid':self.process.pid, 'started_monotonic':began,
            'elapsed_seconds':time.monotonic()-began, **value})
        return {'pid':self.process.pid, 'returncode':0, 'stdout':json.dumps(value['identity']),
                'stderr':json.dumps(value['observation']), 'timed_out':False}

    def close(self):
        self.process.stdin.close()
        wait(self.process, target_seconds=30, checkpoint=self.root/'checkpoints.jsonl')
        self.stderr.close()
        append(self.root/'session-costs.jsonl', {'acl_initializations':1, 'query_count':self.queries,
            'lifetime_seconds':time.monotonic()-self.started, 'pid':self.process.pid})
