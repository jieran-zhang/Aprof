"""Teacher SDK-contract build provenance; no compiler execution or admission.

Only contracts carrying sdk_resource_evidence require this credential. Old
receipts keep their original checks. Archived replay reads bytes, never code.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex

SDK = Path('/usr/local/Ascend/cann-9.0.0')
MODULES = ['lib64/cmake/asc-config.cmake'] + [
    'compiler/tikcpp/ascendc_kernel_cmake/' + name for name in (
        'asc_modules/CMakeASCCompiler.cmake.in', 'asc_modules/CMakeASCInformation.cmake',
        'asc_modules/CMakeDetermineASCCompiler.cmake', 'asc_modules/CMakeTestASCCompiler.cmake',
        'asc_modules/FindASC.cmake', 'fwk_modules/config.cmake', 'fwk_modules/func.cmake',
        'fwk_modules/intf.cmake')]
TOOLS = {'compiler': str(SDK/'bin/bisheng'), 'cmake': '/usr/bin/cmake',
         'make': '/usr/bin/gmake', 'cxx': '/usr/bin/c++',
         'linker': str(SDK/'aarch64-linux/ccec_compiler/bin/ld.lld')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def raw(pointer, reader=None):
    require(set(pointer) == {'path', 'sha256'}, 'invalid SDK evidence pointer')
    path = Path(pointer['path'])
    require(path.is_absolute() and '..' not in path.parts, 'unsafe SDK evidence path')
    data = (reader.verify_artifact(pointer['sha256']) if reader else path).read_bytes()
    require(digest(data) == pointer['sha256'], 'SDK evidence bytes changed')
    return data


def value(pointer, reader=None):
    return json.loads(raw(pointer, reader))


def pointer(path, local):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': local.register_artifact(path)}


def contract_from_review(review_pointer, reader=None):
    return value(value(review_pointer, reader)['contract_ref'], reader)


def environment():
    # Complete environment, not an overlay: no inherited ASCFLAGS, CC/CXX,
    # CPATH, compiler launcher, preload, debug or instrumentation controls.
    return {'PATH': str(SDK/'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'ASCEND_HOME_PATH': str(SDK), 'ASCEND_CANN_PACKAGE_PATH': str(SDK),
            'ASC_DIR': str(SDK/'lib64/cmake'), 'CMAKE_PREFIX_PATH': str(SDK/'lib64/cmake'),
            'CMAKE_GENERATOR': 'Unix Makefiles',
            'LD_LIBRARY_PATH': ':'.join(str(p) for p in [SDK/'lib64', SDK/'aarch64-linux/lib64',
                Path('/usr/local/Ascend/driver/lib64'), Path('/usr/local/Ascend/driver/lib64/common'),
                Path('/usr/local/Ascend/driver/lib64/driver')])}


def declared_sources(contract):
    evidence = contract['sdk_resource_evidence']
    refs = {}
    facility = evidence['sdk_facility_observations']
    entries = [(x['source_path'], x['source_sha256']) for x in evidence['sdk_source_excerpts'].values()]
    entries += [(x['path'], x['sha256']) for x in facility['selected_sdk_headers']]
    for path, reference in entries:
        require(Path(path).is_relative_to(SDK) and '..' not in Path(path).parts
                and refs.get(path, reference) == reference, 'conflicting/non-SDK contract source')
        refs[path] = reference
    compiler = facility['compiler']
    require(compiler['path'] == TOOLS['compiler'], 'SDK contract compiler path differs')
    refs[compiler['path']] = compiler['sha256']
    return refs


def freeze(local, contract_pointer):
    contract = value(contract_pointer)
    if 'sdk_resource_evidence' not in contract:
        return None
    expected = declared_sources(contract)
    names = set(expected) | {str(SDK/name) for name in MODULES} | set(TOOLS.values())
    files = {name: pointer(name, local) for name in sorted(names)}
    require(all(files[name]['sha256'] == ref for name, ref in expected.items()),
            'installed SDK differs from the anonymous contract')
    binding = {'schema_version': 1, 'kind': 'sdk_contract_build_binding_v1',
               'contract_ref': contract_pointer, 'files': files, 'environment': environment(),
               'tools': TOOLS, 'sdk_root': str(SDK)}
    reference = local.register_json(binding)
    return {'path': str(local.verify_artifact(reference)), 'sha256': reference}


def verify_binding(binding, *, reader=None, live=False):
    require(binding['schema_version'] == 1 and binding['kind'] == 'sdk_contract_build_binding_v1'
            and binding['environment'] == environment() and binding['tools'] == TOOLS
            and binding['sdk_root'] == str(SDK), 'SDK binding policy differs')
    expected = declared_sources(value(binding['contract_ref'], reader))
    names = set(expected) | {str(SDK/name) for name in MODULES} | set(TOOLS.values())
    require(set(binding['files']) == names, 'SDK binding source roster differs')
    for name, ref in binding['files'].items():
        raw(ref, reader)
        if live:
            require(str(Path(name).resolve(strict=True)) == ref['path'] and digest(Path(name).read_bytes()) == ref['sha256'],
                    'SDK/tool alias or bytes changed before/after build')
    require(all(binding['files'][name]['sha256'] == ref for name, ref in expected.items()),
            'SDK build differs from reviewed contract')


def dependencies(text):
    require(':' in text, 'missing compiler depfile target')
    names = shlex.split(text.replace('\\\n', ' ').split(':', 1)[1])
    require(names and all(Path(p).is_absolute() and '\0' not in p for p in names),
            'nonabsolute compiler dependency')
    return sorted(set(names))


def metadata_paths(assembly, operator):
    build = Path(assembly)/'build'; target = build/'CMakeFiles'/f'{operator}.dir'
    result = {'cache': build/'CMakeCache.txt', 'flags': target/'flags.make',
              'rules': target/'build.make', 'link': target/'link.txt',
              'modules': build/'CMakeFiles/Makefile.cmake',
              'dependencies': target/'op_host'/f'{operator}.asc.o.d'}
    return result


def parse_effective(texts, assembly, operator, binding):
    source = Path(assembly)/'source'; build = Path(assembly)/'build'
    cache = dict(re.findall(r'^([^#/\r\n][^:=\r\n]*):[^=\r\n]+=([^\r\n]*)$', texts['cache'], re.M))
    expected = {'CMAKE_ASC_COMPILER': TOOLS['compiler'], 'CMAKE_CXX_COMPILER': TOOLS['cxx'],
                'CMAKE_MAKE_PROGRAM': TOOLS['make'], 'CMAKE_COMMAND': TOOLS['cmake'],
                'ASC_DIR': str(SDK/'lib64/cmake'), 'CMAKE_BUILD_TYPE': 'Release',
                'CMAKE_ASC_LLD_LINKER': TOOLS['linker'],
                'CMAKE_GENERATOR': 'Unix Makefiles', 'CMAKE_HOME_DIRECTORY': str(source)}
    require(all(cache.get(k) == v for k,v in expected.items()), 'effective CMake toolchain/target differs')
    require(cache.get('ASCEND_CANN_PACKAGE_PATH', str(SDK)) == str(SDK)
            and cache.get('CMAKE_ASC_RUN_MODE', '') in ('', 'npu')
            and all(not cache.get(k, '') for k in ('CMAKE_ASC_FLAGS', 'CMAKE_ASC_FLAGS_RELEASE',
                'CMAKE_ASC_COMPILER_LAUNCHER', 'CMAKE_TOOLCHAIN_FILE')), 'extra ASC/cache controls')
    flags = dict(re.findall(r'^(ASC_[A-Z_]+) = *(.*)$', texts['flags'], re.M))
    includes = [f'-I{source}/op_host', f'-I{source}/op_kernel']
    require(flags.get('ASC_DEFINES') == '' and shlex.split(flags.get('ASC_FLAGS', '')) == ['--npu-arch=dav-2201']
            and shlex.split(flags.get('ASC_INCLUDES', '')) == includes, 'instrumentation or ASC flags/includes differ')
    obj = f'CMakeFiles/{operator}.dir/op_host/{operator}.asc.o'
    wanted = [TOOLS['compiler'], *includes, '-fPIC', '--npu-arch=dav-2201', '-MD', '-MT', obj,
              '-MF', obj+'.d', '-o', obj, '-c', '--asc-aicore-lang', str(source/'op_host'/f'{operator}.asc')]
    commands = []
    for line in texts['rules'].splitlines():
        if line.startswith('\t') and '--asc-aicore-lang' in line:
            for key, val in flags.items(): line = line.replace('$('+key+')', val)
            commands.append(shlex.split(line))
    require(commands == [wanted], 'effective ASC compile command differs')
    link = shlex.split(texts['link'])
    require(link[:4] == [TOOLS['compiler'], obj, '-o', operator] and not any(
            x.startswith(('@','-D','--run-mode','--npu-arch')) for x in link), 'effective link command differs')
    modules = {m for m in re.findall(r'"([^"\n]+)"', texts['modules']) if m.startswith(str(SDK)+'/')}
    require(modules == {str(SDK/name) for name in MODULES}, 'effective SDK CMake source closure differs')
    return {'compile_argv': wanted, 'link_argv': link, 'sdk_cmake_sources': sorted(modules),
            'dependencies': dependencies(texts['dependencies'])}


def finish(local, binding_pointer, assembly, operator):
    binding = value(binding_pointer); verify_binding(binding, live=True)
    paths = metadata_paths(assembly, operator)
    metadata = {k: pointer(p, local) for k,p in paths.items()}
    texts = {k: raw(p).decode() for k,p in metadata.items()}
    effective = parse_effective(texts, assembly, operator, binding)
    # Record the emitted dependency list without an SDK walk/extra compile.
    # The driver may omit device-pass headers; reviewed device headers are
    # separately bound before/after build. The model cannot write SDK trees.
    deps = {name: pointer(name, local) for name in effective['dependencies']}
    receipt = {'schema_version': 1, 'kind': 'sdk_contract_build_evidence_v1',
               'binding_ref': binding_pointer, 'assembly': str(assembly), 'operator': operator,
               'metadata': metadata, 'effective': effective, 'dependencies': deps,
               'scope': 'effective source/toolchain/flags identity; not total compiler UB admission'}
    ref = local.register_json(receipt)
    return {'path': str(local.verify_artifact(ref)), 'sha256': ref}


def verify(build, proof, *, reader=None):
    attempt = value(build['attempt_ref'], reader)
    review = value(attempt['independent_review'], reader)
    contract = value(review['contract_ref'], reader)
    if 'sdk_resource_evidence' not in contract:
        require('sdk_build_ref' not in build, 'legacy build unexpectedly claims SDK credential')
        return
    require('sdk_build_ref' in build, 'SDK evidence contract requires actual build credential')
    receipt = value(build['sdk_build_ref'], reader); binding = value(receipt['binding_ref'], reader)
    require(binding['contract_ref'] == review['contract_ref'], 'build uses a different reviewed SDK contract')
    verify_binding(binding, reader=reader)
    assembly = str(Path(build['binary']['path']).parent.parent)
    require(receipt['schema_version'] == 1 and receipt['kind'] == 'sdk_contract_build_evidence_v1'
            and receipt['assembly'] == assembly and receipt['operator'] == proof['operator'], 'SDK build identity differs')
    expected = metadata_paths(assembly, proof['operator'])
    require(set(receipt['metadata']) == set(expected) and all(receipt['metadata'][k]['path'] == str(p)
            for k,p in expected.items()), 'SDK metadata source paths differ')
    texts = {k:raw(p, reader).decode() for k,p in receipt['metadata'].items()}
    effective = parse_effective(texts, assembly, proof['operator'], binding)
    require(effective == receipt['effective'] and set(receipt['dependencies']) == set(effective['dependencies']),
            'SDK effective commands/dependency roster differs')
    for name, ref in receipt['dependencies'].items():
        raw(ref, reader)
        for selected in binding['files'].values():
            if ref['path'] == selected['path']:
                require(ref == selected, 'compiled SDK dependency differs from prebuild identity')
    require(all(command.get('environment') == binding['environment'] for command in build['commands']),
            'actual configure/build environment differs from frozen SDK binding')
