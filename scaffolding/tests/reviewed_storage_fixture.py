"""Exact historical storage epoch fixtures, independent of the working checkout.

Only literal byte data is decoded here. Production attestor pins stay unchanged;
these copies supply the historical implementation expected by compatibility tests.
"""
import base64
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path


@lru_cache(maxsize=1)
def _snapshots():
    path = Path(__file__).with_name('fixtures') / 'final_storage_reviewed_bytes.py'
    spec = importlib.util.spec_from_file_location('inert_reviewed_storage_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = json.loads(gzip.decompress(base64.b64decode(module.DATA)))
    return {'sha256:' + hashlib.sha256(value.encode()).hexdigest(): value.encode()
            for value in values.values()}


def materialize_reviewed_storage(destination, expected):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    root = os.environ.get('APROF_REVIEWED_STORAGE_ROOT')
    paths = []
    for name, digest in expected.items():
        if root:
            data = (Path(root) / 'scripts' / name).read_bytes()
        elif digest in _snapshots():
            data = _snapshots()[digest]
        else:
            # A newly qualified layout epoch uses the exact current producer bytes.
            data = (Path(__file__).resolve().parents[1] / 'collection/scripts' / name).read_bytes()
        assert 'sha256:' + hashlib.sha256(data).hexdigest() == digest, name
        path = destination / name
        if path.exists():
            assert path.read_bytes() == data, name
        else:
            path.write_bytes(data)
        paths.append(path)
    return paths
