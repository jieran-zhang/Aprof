#!/usr/bin/env python3
"""Copy and verify a portable v2 dataset without rewriting signed records.

The published archive is read-only. A bundle includes every referenced evidence
file, record/context CAS object, current revision, and the CPU-only verifier.
Original paths remain provenance; verification reads only bundled bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import tarfile
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
import trace_v2_dataset as v2

VERSION = 'optimization_trace_portable_v2'
LEGACY_VERSION = 'optimization_trace_portable_v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def fingerprint(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return {'sha256': 'sha256:' + digest.hexdigest(), 'size_bytes': size}


def inside(root, name):
    relative = Path(name)
    require(isinstance(name, str) and name and not relative.is_absolute()
            and '..' not in relative.parts and str(relative) == name,
            'unsafe bundle path')
    target = root / relative
    require(not root.is_symlink(), 'symlink bundle root')
    for parent in (target, *target.parents):
        if parent == root:
            break
        require(not parent.is_symlink(), 'symlink bundle member')
    require(target.resolve().is_relative_to(root.resolve()), 'bundle path escapes root')
    return target


def files(root):
    result = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'symlink bundle member')
        if path.is_file():
            result.add(path.relative_to(root).as_posix())
        else:
            require(path.is_dir(), 'unsupported bundle member')
    return result


def synced_copy(source, target, expected=None):
    source, target = Path(source), Path(target)
    if not source.is_file():
        data = v2.external_evidence_bytes(source)
        original = {'sha256': v2.digest_bytes(data), 'size_bytes': len(data)}
        if target.exists():
            require(fingerprint(target) == original, 'conflicting archived verification member')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
        actual = fingerprint(target)
        require(actual == original and (expected is None or actual == expected), 'archived verification bytes differ')
        return actual
    require(source.is_file() and not source.is_symlink(), 'source must be a regular file')
    if target.exists():
        actual = fingerprint(target)
        require(actual == fingerprint(source), 'conflicting bundle member')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as original, target.open('xb') as output:
            shutil.copyfileobj(original, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        actual = fingerprint(target)
        require(actual == fingerprint(source), 'copy changed during transfer')
    if expected is not None:
        require(actual == expected, 'copied evidence differs from signed index')
    return actual


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def storage_binding(path, expected):
    try:
        import level2_verification_storage as storage
    except ModuleNotFoundError as error:
        if error.name != 'level2_verification_storage': raise
        return None
    return storage.evidence_binding(path, expected)


def verify_storage_closure(bundle, manifest, index):
    """Optional maintenance closure; never accesses original evidence locations."""
    name='storage-verification/bindings.json'
    declared=manifest.get('storage_closure')
    if declared is None:
        require(name not in manifest['files'],'undeclared portable storage closure')
        return
    require(declared=={'path':name,'sha256':manifest['files'].get(name,{}).get('sha256')}
            and name in manifest['files'],'portable storage closure binding differs')
    closure=v2.strict_loads(inside(bundle,name).read_bytes())
    require(set(closure)=={'version','origins','archives'} and closure['version']=='level2_verification_portable_v1',
            'invalid portable verification closure')
    signed={row['path']:row['sha256'] for row in index.values()}
    require(set(closure['origins'])<=set(signed),'portable verification origin is outside signed evidence')
    require(set(closure['archives'])==set(closure['origins'].values()),'portable verification archive coverage differs')
    for key,entry in closure['archives'].items():
        require(set(entry)=={'seal','files'},'invalid portable verification archive entry')
        def read(ref):
            require(set(ref)=={'path','sha256'} and ref['path'] in entry['files'],'missing portable verification dependency')
            target=entry['files'][ref['path']]
            require(target=='evidence/sha256/'+ref['sha256'][7:] and target in manifest['files'],
                    'portable verification dependency location differs')
            data=inside(bundle,target).read_bytes()
            require(v2.digest_bytes(data)==ref['sha256'],'portable verification dependency changed')
            if ref['path'] in signed:require(signed[ref['path']]==ref['sha256'],'storage proof differs from signed evidence')
            return data
        seal=v2.strict_loads(read(entry['seal']))
        require(entry['seal']['sha256']==key and seal.get('version')=='level2_closed_verification_storage_v1'
                and seal.get('source_bytes_preserved') is True,'portable verification seal differs')
        session=Path(seal['session']);logical=Path(seal['logical_root'])
        require(session.is_absolute() and '..' not in session.parts and logical==session/'verification',
                'portable verification logical scope differs')
        # Execute only this verifier's installed sibling, never code chosen by
        # the untrusted bundle inventory. Offline CLI has the same sibling.
        helper_name='verifier/level2_verification_storage.py'
        require(helper_name in manifest['files'],'portable verification reader missing')
        trusted_helper=Path(__file__).resolve().with_name('level2_verification_storage.py')
        require(trusted_helper.is_file() and not trusted_helper.is_symlink(),'trusted verification reader missing')
        spec=importlib.util.spec_from_file_location('_portable_closed_verification_reader',trusted_helper)
        storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
        def read_logical(path):
            origin=str(path);target=entry['files'].get(origin)
            require(target in manifest['files'],'missing portable closed verification proof')
            declared_hash=manifest['files'][target]['sha256']
            return read({'path':origin,'sha256':declared_hash})
        facts,expected=storage.closed_from_reader(session,read_logical)
        require(facts==seal['closed_evidence'],'portable closed verification evidence differs')
        read(seal['producer'])
        require(len(seal['members'])==len(expected) and {row['path'] for row in seal['members']}==set(expected),
                'portable full verification roster differs')
        rows={row['relative_path']:row for row in seal['members']}
        require(len(rows)==len(seal['members']),'duplicate portable verification member')
        payloads={}
        with tarfile.open(fileobj=io.BytesIO(read(seal['archive'])),mode='r:') as stream:
            members=stream.getmembers()
            require(len(members)==len(rows) and {m.name for m in members}==set(rows),'portable tar member set differs')
            for member in members:
                row=rows[member.name];relative=Path(member.name);origin=str(logical/relative)
                require(len(relative.parts)==2 and re.fullmatch(r'(?:[1-9]|1[0-9]|20)_(?:normal|swapped)_[AB]',relative.parts[0])
                        and relative.name in {'metadata.json','execution.json','result.json','stdout.log'}
                        and member.isfile() and not member.issym() and not member.islnk() and row['path']==origin,
                        'portable tar member path differs')
                data=stream.extractfile(member).read()
                require(member.size==row['size_bytes'] and v2.digest_bytes(data)==row['sha256']
                        and member.mode==row['mode'] and member.uid==row['uid'] and member.gid==row['gid']
                        and member.mtime==row['mtime_ns']//1000000000,'portable tar member bytes/metadata differ')
                if expected[origin] is not None:require(expected[origin]==row['sha256'],'portable member differs from original report')
                payloads[origin]=row['sha256']
        for origin,value in closure['origins'].items():
            if value==key:require(payloads.get(origin)==signed[origin],'portable logical mapping differs from signed evidence')


def verify(bundle):
    bundle = Path(bundle).absolute()
    require(not bundle.is_symlink(), 'symlink bundle root')
    manifest_path = inside(bundle, 'bundle.json')
    manifest = v2.strict_loads(manifest_path.read_bytes())
    require(set(manifest) == ({'version', 'revision', 'manifest_hash', 'files', 'evidence_map'}
            | ({'storage_closure'} if manifest.get('version')==VERSION else set())),
            'invalid portable manifest fields')
    require(manifest['version'] in (VERSION,LEGACY_VERSION) and isinstance(manifest['files'], dict)
            and isinstance(manifest['evidence_map'], dict), 'unsupported portable bundle')
    require(files(bundle) == set(manifest['files']) | {'bundle.json'}, 'bundle file closure differs')
    for name, expected in manifest['files'].items():
        require(fingerprint(inside(bundle, name)) == expected, 'bundle file hash differs: ' + name)
    root = inside(bundle, 'dataset')
    pointer = v2.strict_loads((root / 'current.json').read_bytes())
    require(isinstance(pointer, dict) and set(pointer) == {'revision', 'manifest_hash'}
            and isinstance(pointer['revision'], str)
            and re.fullmatch('[0-9a-f]{64}', pointer['revision'])
            and isinstance(pointer['manifest_hash'], str)
            and v2.HASH_RE.fullmatch(pointer['manifest_hash']),
            'invalid portable revision pointer')
    require(pointer == {key: manifest[key] for key in ('revision', 'manifest_hash')},
            'bundled revision differs')
    base = inside(bundle, 'dataset/revisions/' + pointer['revision'])
    objects = v2.strict_loads((base / 'record_objects.json').read_bytes())
    contexts = v2.strict_loads((base / 'contexts.json').read_bytes())
    require(isinstance(objects, dict) and isinstance(contexts, dict), 'invalid portable CAS index')
    digests = set(objects.values()) | set(contexts)
    require(all(isinstance(h, str) and v2.HASH_RE.fullmatch(h) for h in digests),
            'invalid portable CAS hash')
    expected_cas = {
        'dataset/' + v2.object_path(Path('.'), h).as_posix(): h for h in digests
    }
    require({name for name in manifest['files'] if name.startswith('dataset/cas/')} == set(expected_cas),
            'portable CAS closure differs')
    # All retained objects count, including earlier records no current row links.
    # A recomputed outer bundle inventory cannot bless a corrupt CAS object.
    for name, digest in expected_cas.items():
        require(fingerprint(inside(bundle, name))['sha256'] == digest,
                'portable CAS filename/content hash differs')
    index = v2.strict_loads((base / 'evidence_index.json').read_bytes())
    require(set(manifest['evidence_map']) == {row['path'] for row in index.values()},
            'portable evidence map must cover exactly the evidence index')
    mapping = {}
    for row in index.values():
        name = manifest['evidence_map'][row['path']]
        require(name == 'evidence/sha256/' + row['sha256'][7:], 'evidence CAS path differs')
        require(manifest['files'].get(name) == {key: row[key] for key in ('sha256', 'size_bytes')},
                'portable evidence hash differs from signed index')
        mapping[row['path']] = inside(bundle, name)
    verify_storage_closure(bundle,manifest,index)
    result = v2.verify(root, deep=True, evidence_paths=mapping,
                       graph_root=inside(bundle, 'skillgraph/versions'))
    return {**result, 'portable': True, 'bundle_version': manifest['version'],
            'original_evidence_locations_accessed': False}


@v2.external_evidence_session()
def export(dataset, destination):
    dataset, destination = Path(dataset).resolve(), Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'destination already exists')
    # Validate before creating a staging directory; this is a copy, not repair.
    v2.verify(dataset, deep=True)
    pointer_bytes = (dataset / 'current.json').read_bytes()
    pointer = v2.strict_loads(pointer_bytes)
    revision = dataset / 'revisions' / pointer['revision']
    index = v2.strict_loads((revision / 'evidence_index.json').read_bytes())
    objects = v2.strict_loads((revision / 'record_objects.json').read_bytes())
    contexts = v2.strict_loads((revision / 'contexts.json').read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.staging-', dir=destination.parent))
    inventory, mapping = {}, {}
    storage_closure={"version":"level2_verification_portable_v1","origins":{},"archives":{}}

    def copy(source, relative, expected=None):
        if relative in inventory:
            require(expected is not None and inventory[relative] == expected,
                    'conflicting repeated evidence identity')
            return
        inventory[relative] = synced_copy(source, inside(staging, relative), expected)

    for name in sorted(files(revision)):
        copy(revision / name, 'dataset/revisions/' + pointer['revision'] + '/' + name)
    copy(dataset / 'current.json', 'dataset/current.json')
    for digest in sorted(set(objects.values()) | set(contexts)):
        source = v2.object_path(dataset, digest)
        copy(source, 'dataset/' + source.relative_to(dataset).as_posix())
    for row in index.values():
        name = 'evidence/sha256/' + row['sha256'][7:]
        require(row['path'] not in mapping or mapping[row['path']] == name,
                'one original path has conflicting evidence hashes')
        mapping[row['path']] = name
        copy(row['path'], name, {key: row[key] for key in ('sha256', 'size_bytes')})
        binding=storage_binding(row['path'],row['sha256'])
        if binding is not None:
            key=binding['seal']['sha256'];storage_closure['origins'][row['path']]=key
            if key not in storage_closure['archives']:
                refs=[binding[k] for k in ('seal','archive','producer')]+binding['closed_evidence']['protected']
                event_path=binding['closed_evidence']['event_binding']['path']
                refs.append({'path':event_path,'sha256':fingerprint(event_path)['sha256']})
                locations={}
                for ref in refs:
                    destination_name='evidence/sha256/'+ref['sha256'][7:]
                    expected=fingerprint(ref['path']);require(expected['sha256']==ref['sha256'],'storage closure changed during export')
                    copy(ref['path'],destination_name,expected);locations[ref['path']]=destination_name
                storage_closure['archives'][key]={'seal':binding['seal'],'files':locations}
    modules=[Path(__file__).resolve(), Path(v2.__file__).resolve()]
    if storage_closure['origins']:
        import level2_verification_storage as storage
        modules.append(Path(storage.__file__).resolve())
    for module in modules:
        copy(module, 'verifier/' + module.name)
    # v1 graph associations use the legacy immutable repository snapshot.
    legacy_graph = v2.ROOT / 'skillgraph/versions/v0001'
    for path in sorted(legacy_graph.glob('*.json')):
        copy(path, 'skillgraph/versions/v0001/' + path.name)
    require((dataset / 'current.json').read_bytes() == pointer_bytes,
            'archive revision changed during export; retry explicitly')
    if storage_closure['origins']:
        target=inside(staging,'storage-verification/bindings.json');target.parent.mkdir(parents=True,exist_ok=True)
        v2.write_synced(target,v2.canonical(storage_closure));inventory['storage-verification/bindings.json']=fingerprint(target)
    manifest = {'version': VERSION, **pointer, 'files': inventory, 'evidence_map': mapping,
                'storage_closure':({'path':'storage-verification/bindings.json','sha256':inventory['storage-verification/bindings.json']['sha256']}
                    if storage_closure['origins'] else None)}
    v2.write_synced(staging / 'bundle.json', v2.canonical(manifest))
    result = verify(staging)
    for path in sorted((p for p in staging.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        sync_directory(path)
    sync_directory(staging)
    require(not destination.exists() and not destination.is_symlink(), 'destination appeared during export')
    os.rename(staging, destination)
    sync_directory(destination.parent)
    return {**result, 'bundle': str(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    publish = commands.add_parser('export')
    publish.add_argument('--dataset', type=Path, required=True)
    publish.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.dataset, args.output) if args.command == 'export' else verify(args.bundle)
    print(v2.canonical(result).decode(), end='')


if __name__ == '__main__':
    main()
