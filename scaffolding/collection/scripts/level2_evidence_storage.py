"""Composition of reviewed verification/native readers and LOCAL raw archives.

No capture or sampling behavior is changed. Unarchived and Level1 paths delegate
unchanged to the previous reader. Raw overrides are read-only shadow scopes.
"""
from __future__ import annotations
import contextlib
import contextvars
import io
import hashlib
import importlib.util
from pathlib import Path
import level2_verification_storage as prior
import level2_raw_archive_storage as raw
VERSION=raw.VERSION
_CACHE=contextvars.ContextVar('closed_raw_reader_cache',default=None)
_OVERRIDES=contextvars.ContextVar('closed_raw_reader_overrides',default=None)


def reader_for_session(session):
    session=Path(session)
    destination=Path((_OVERRIDES.get() or {}).get(str(session),raw.default_destination(session)))
    if str(session) not in (_OVERRIDES.get() or {}) and not destination.exists() and not destination.is_symlink():return None
    key=(str(session),str(destination));cache=_CACHE.get()
    if cache is None or key not in cache:
        value=raw.RawArchive(session,raw.pointer(destination/'seal.json'))
        if cache is not None:cache[key]=value
    else:value=cache[key];value._unchanged()
    return value


def resolve_raw(path):
    p=Path(path);matches=[]
    for i,part in enumerate(p.parts[:-1]):
        if part!='raw':continue
        session=Path(*p.parts[:i]);destination=Path((_OVERRIDES.get() or {}).get(str(session),raw.default_destination(session)))
        if str(session) in (_OVERRIDES.get() or {}) or destination.exists() or destination.is_symlink():matches.append(session)
    raw.require(len(matches)<=1,'ambiguous raw archive scope')
    if not matches:return None
    value=reader_for_session(matches[0]);value.name(path);return value


def resolve(path):return resolve_raw(path) or prior.resolve(Path(path))


def reverify_cached():
    prior.reverify_cached()
    for reader in (_CACHE.get() or {}).values():reader.reverify_cached()


@contextlib.contextmanager
def reader_session(overrides=None):
    token=None;other=None
    try:
        if overrides is not None:raw.require(_OVERRIDES.get() is None,'nested raw overrides prohibited')
        token=_CACHE.set({}) if _CACHE.get() is None else None
        if overrides is not None:other=_OVERRIDES.set({str(Path(k)):str(Path(v)) for k,v in overrides.items()})
        with prior.reader_session():
            # Every explicit shadow is a declaration, even when its directory or
            # seal is absent. Validate before yielding; never read loose fallback.
            if overrides is not None:
                for session in _OVERRIDES.get():reader_for_session(session)
            yield
            # Raw closure rereads protected verification/native metadata: keep
            # both earlier caches alive through this final validation.
            if token is not None:reverify_cached()
    finally:
        if token is not None:_CACHE.reset(token)
        if other is not None:_OVERRIDES.reset(other)


@contextlib.contextmanager
def open_binary(path):
    value=resolve_raw(path)
    with (value.open_binary(path) if value is not None else prior.open_binary(path)) as stream:yield stream


def read_bytes(path):
    value=resolve_raw(path)
    if value is None:return prior.read_bytes(path)
    with value.open_binary(path) as stream:data=stream.read(raw.MAX_METADATA+1)
    raw.require(len(data)<=raw.MAX_METADATA,'raw metadata size exceeds bound');return data


def fingerprint(path):
    value=resolve_raw(path)
    return value.fingerprint(path) if value is not None else prior.fingerprint(path)


def is_file(path):return resolve_raw(path) is not None or prior.is_file(path)


def evidence_binding(path,expected=None):
    value=resolve_raw(path)
    result=value.evidence_binding(path,expected or value.fingerprint(path)['sha256']) if value is not None else prior.evidence_binding(path,expected)
    if result is not None and 'bytes' in result:
        raw.require(result.get('version') in (prior.VERSION,prior.ANCHORED_VERSION,prior.FINAL_VERSION)
                    and isinstance(result['bytes'],bytes)
                    and 'sha256:'+hashlib.sha256(result['bytes']).hexdigest()==result['origin']['sha256'],
                    'verification payload differs from metadata binding')
        # The legacy verification API includes cached bytes. Catalogs carry only
        # exact logical identities; the complete tar is retained separately.
        result={k:v for k,v in result.items() if k!='bytes'}
    if result is not None:
        raw.require(set(result)=={'version','origin','seal','archive','producer','closed_evidence'},
                    'unknown storage metadata binding fields')
    return result


def event_bindings(facts):return facts['event_bindings'] if 'event_bindings' in facts else prior.event_bindings(facts)


def logical_files(directory):
    directory=Path(directory);result=list(prior.logical_files(directory));seals=set()
    if directory.is_dir():seals.update(directory.rglob('raw-archive-storage/seal.json'))
    for session,destination in (_OVERRIDES.get() or {}).items():
        if Path(session).is_relative_to(directory):seals.add(Path(destination)/'seal.json')
    for seal in sorted(seals):
        value=raw.load_ref(raw.pointer(seal));session=Path(value['logical_root']).parent
        reader=reader_for_session(session)
        result.extend(reader.logical_files())
    return sorted(set(result))


def verify_raw_storage(request,directory,execution):
    directory=Path(directory);value=reader_for_session(directory)
    if value is not None:
        raw.require(request==value.request and execution==raw.load_ref(raw.pointer(directory/'msprof.execution.json')),'raw report request/execution differs')
        return value.verify_transport()
    from msprof_raw_storage import verify
    return verify(request,directory,execution)


def parse_profile(directory,journal,build,cases,repeat):
    directory=Path(directory);value=reader_for_session(directory.parent)
    if value is not None:return raw.parse_profile(value,journal,build,cases,repeat)
    import cannbench_msprof_timing as timing
    return timing.parse_profile(directory,journal,build,cases,repeat)


def catalog_bindings(facts):
    """Reconstruct only the explicit retrospective authority catalog slots.

    This is metadata reconstruction, not archive validation. Callers must copy
    and validate every returned archive and origin using the trusted readers.
    Archived producer snapshots remain inert.
    """
    authorities=[]
    value=facts.get('report_authority')
    if isinstance(value,dict) and value.get('kind')=='retrospective_final_report_authority_v1':authorities.append(value)
    for row in facts.get('sessions',[]):
        value=row.get('facts',{}).get('report_authority')
        if isinstance(value,dict) and value.get('kind')=='retrospective_final_report_authority_v1':authorities.append(value)
    archives={};origins={}
    if not authorities:return {'archives':archives,'origins':origins}
    trusted=Path(__file__).resolve().with_name('level2_final_report_authority.py')
    raw.require(trusted.is_file() and not trusted.is_symlink(),'trusted final catalog reader missing')
    spec=importlib.util.spec_from_file_location('_trusted_final_catalog_reader',trusted)
    final_authority=importlib.util.module_from_spec(spec);spec.loader.exec_module(final_authority)
    for value in authorities:
        result=final_authority.reconstruct_catalog(value)
        for key,binding in result['archives'].items():
            raw.require(key not in archives or archives[key]==binding,'conflicting authority catalog archive')
            archives[key]=binding
        for origin,row in result['origins'].items():
            raw.require(origin not in origins or origins[origin]==row,'conflicting authority catalog origin')
            origins[origin]=row
    return {'archives':archives,'origins':origins}
