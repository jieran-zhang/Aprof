#!/usr/bin/env python3
"""Verify source byte closure; never read or regenerate runtime measurements."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root,lock):
    value=json.loads(Path(lock).read_text())
    if value['schema_version']!='aprof.source-input-lock/v2' or value['execution_policy']!='soft_targets_local_v1':raise ValueError('wrong input lock policy')
    for name,expected in value['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or digest(p)!=expected:raise ValueError('source changed: '+name)
    for item in value['external_inputs']:
        if digest(Path(item['path']))!=item['sha256']:raise ValueError('external input changed: '+item['path'])
    return {'valid':True,'files':len(value['files']),'external_inputs':len(value['external_inputs']),
        'release_id':value['release_id'],'execution_policy':value['execution_policy'],'sealed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--lock',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.repo.resolve(),a.lock)))
if __name__=='__main__':main()
