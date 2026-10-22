#!/usr/bin/env python3
"""Build isolated ASC role DSOs and the sole-context native runner. Never runs NPU.

Host tiling arguments, chunk expression and launch configuration are extracted from
source, not duplicated as optimization constants. Unsupported host shapes fail closed.
The source snapshot is untouched; generated files and a reviewable harness diff are
written under --output-dir, along with source/binary hashes.
"""
from __future__ import annotations
import argparse, difflib, hashlib, json, re, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / 'scaffolding/benchmarks/cannbench/harness/shared_context'
from level2_adapters import OPERATORS as LEVEL2_OPERATORS
SUPPORTED = ('exp','mish','sigmoid','gelu','masked_scale','foreach_addcdiv_scalar','foreach_norm') + LEVEL2_OPERATORS

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_hash(source):
    files = sorted(p for d in ('op_host','op_kernel') for p in (source/d).rglob('*') if p.is_file())
    h=hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(source)).encode()+b'\0'+p.read_bytes()+b'\0')
    return h.hexdigest()

def validate_source_cmake(source: Path, op: str, npu_arch: str):
    """Accept only the explicitly supported direct-invoke build recipe.

    This is deliberately a strict allowlist, not a partial CMake interpreter:
    additional flags, definitions, includes, toolchains, sources, properties or
    commands require review before the harness can claim a faithful build.
    """
    if not re.fullmatch(r'dav-[0-9]+', npu_arch):
        raise ValueError(f'unsupported declared NPU architecture: {npu_arch}')
    cmake=source/'CMakeLists.txt'
    if not cmake.is_file():
        raise ValueError(f'unsupported source build: missing {cmake}')
    if op in LEVEL2_OPERATORS:
        canonical = ROOT/'scaffolding/benchmarks/cannbench/operators'/op/'CMakeLists.txt'
        normalize = lambda text: ' '.join(re.sub(r'^\s*#[^\n]*$', '', text, flags=re.M).split())
        expected = canonical.read_text()
        declared = set(re.findall(r'--npu-arch=(dav-[0-9]+)', expected))
        if declared != {npu_arch} or normalize(cmake.read_text()) != normalize(expected):
            raise ValueError('Level2 CMake differs from reviewed canonical build or architecture')
        return {'cmake_sha256': digest(cmake), 'cmake_guard_version':'level2_canonical_recipe_v1', 'npu_arch':npu_arch}
    expected=f'''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project({op}_direct LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable({op} op_host/{op}.asc)
target_include_directories({op} PRIVATE op_host op_kernel)
target_link_libraries({op} PRIVATE tiling_api register platform unified_dlog dl m graph_base ascendcl ascendc_runtime)
target_link_directories({op} PRIVATE "$ENV{{ASCEND_HOME_PATH}}/lib64" "$ENV{{ASCEND_HOME_PATH}}/aarch64-linux/lib64")
target_compile_options({op} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch={npu_arch}>)
'''
    def normalized(text):
        # Full-line comments and formatting are harmless; all other CMake text
        # must match the frozen recipe, including the declared architecture.
        return ' '.join(re.sub(r'^\s*#[^\n]*$', '', text, flags=re.M).split())
    if normalized(cmake.read_text())!=normalized(expected):
        raise ValueError(
            f'unsupported source CMake configuration: {cmake}; expected the '
            f'approved direct-invoke recipe with only --npu-arch={npu_arch}. '
            'Changed flags/definitions/architecture or other build semantics '
            'require a faithful adapter before building.')
    return {'cmake_sha256':digest(cmake),'cmake_guard_version':'direct_invoke_allowlist_v1',
            'npu_arch':npu_arch}

def one(pattern,text,what):
    values=re.findall(pattern,text,re.S)
    if len(values)!=1: raise ValueError(f'unsupported host: expected exactly one {what}, got {len(values)}')
    return values[0]

def generate_adapter(source: Path, op: str, role: str, sha: str):
    if op in LEVEL2_OPERATORS:
        from level2_adapters import generate_adapter as level2_generate
        return level2_generate(source, op, role, sha)
    host=(source/'op_host'/f'{op}.asc').read_text()
    original_host=host
    # Remove only the old harness branch; preserve the actual standalone path.
    marker='if (aprof::Enabled())'
    while marker in host:
        start=host.index(marker); brace=host.index('{',start); depth=1; end=brace+1
        while depth:
            if host[end]=='{': depth+=1
            elif host[end]=='}': depth-=1
            end+=1
        host=host[:start]+host[end:]
    prefix=host.split('int main(',1)[0]
    prefix=re.sub(r'^#include ["<][^"\n>]*aprof_device_timer\.h[">]\s*$', '', prefix, flags=re.M)
    declarations=one(r'try\s*\{(.*?)device = std::stoi',host,'argument declaration region')
    # Streams/file handles below are native prepared-state concerns.
    compute=one(r'const auto tiling = (Compute\w+Tiling\([^;]+\));',host,'tiling invocation')
    launches=re.findall(r'(\w+)<<<(.*?)>>>\((.*?)\);',host,re.S)
    expected=2 if op=='foreach_norm' else 1
    if len(launches)!=expected: raise ValueError('unsupported host launch count')
    kernels=[x[0] for x in launches]
    launch_symbols={k:f'sc_{role}_{sha[:12]}_{k}' for k in kernels}
    # Preprocessor renaming covers the actual kernel definition and generated stub.
    renamed=''.join(f'#define {k} {v}\n' for k,v in launch_symbols.items())
    code=renamed+prefix+'\n#include "adapter_common.h"\n'
    prep=declarations
    if op.startswith('foreach_'):
        prep+='\nif(lengths.empty() || std::any_of(lengths.begin(),lengths.end(),[](uint64_t n){return n==0;})) throw std::runtime_error("empty tensor");\n'
        if op=='foreach_addcdiv_scalar':
            chunk=one(r'(constexpr uint64_t kChunkElements\s*=\s*[^;]+;)',host,'source chunk expression')
            prep+=chunk+'\nstd::ifstream f1(Arg(argc,argv,"--x1"),std::ios::binary), f2(Arg(argc,argv,"--x2"),std::ios::binary), f3(Arg(argc,argv,"--x3"),std::ios::binary);\n'
            prep+='for(uint64_t tensorLength:lengths) for(uint64_t off=0;off<tensorLength;off+=kChunkElements) {\nconst uint64_t n=std::min<uint64_t>(kChunkElements,tensorLength-off); const size_t bytes=n*elemBytes;\n'
            prep+='auto dx1=s->input(f1,bytes),dx2=s->input(f2,bytes),dx3=s->input(f3,bytes),dy=s->output(bytes);\n'
            mapping={x:f's->ptr({x})' for x in ('dx1','dx2','dx3','dy','dt')}
        else:
            workspace=one(r'aclrtMalloc\(&dpartial,\s*(.*?),\s*ACL_MEM_MALLOC_HUGE_FIRST\)',host,'norm workspace allocation')
            output_allocation=one(r'aclrtMalloc\(&dy,\s*(.*?),\s*ACL_MEM_MALLOC_HUGE_FIRST\)',host,'norm output allocation')
            prep+=f'std::ifstream fi(Arg(argc,argv,"--input"),std::ios::binary);\nauto dpartial=s->alloc({workspace},"workspace");\nfor(uint64_t n:lengths) {{\nconst size_t bytes=n*elemBytes; auto dx=s->input(fi,bytes),dy=s->output(elemBytes,{output_allocation});\n'
            mapping={x:f's->ptr({x})' for x in ('dx','dpartial','dy','dt')}
        prep+=f'const auto tiling={compute}; auto dt=s->tiling(tiling);\n'
    else:
        prep+='if(!n) throw std::runtime_error("empty tensor");\n'
        if op=='masked_scale':
            prep+='auto devX=s->input(Arg(argc,argv,"--x"),xBytes),devMask=s->input(Arg(argc,argv,"--mask"),maskBytes),devOut=s->output(xBytes);\n'
            names=('devX','devMask','devOut','devTiling')
        else:
            prep+='auto devIn=s->input(Arg(argc,argv,"--input"),bytes),devOut=s->output(bytes);\n'
            names=('devIn','devOut','devTiling')
        prep+=f'const auto tiling={compute}; auto devTiling=s->tiling(tiling);\n'
        mapping={x:f's->ptr({x})' for x in names}
    for kernel,grid,args in launches:
        args=re.sub(r'static_cast<uint8_t\s*\*>\((\w+)\)',lambda m:mapping[m[1]],args)
        prep+=f's->launches.push_back([=](){{ {kernel}<<<{grid}>>>({args}); }});\n'
    if op.startswith('foreach_'):
        prep+='}\n'
        files=('f1','f2','f3') if op=='foreach_addcdiv_scalar' else ('fi',)
        for name in files: prep+=f'if({name}.peek()!=EOF) throw std::runtime_error("TensorList input length mismatch");\n'
    code+='''
static int prepare(int argc,char **argv,int64_t cores,void *stream,void **out) {
 return shared_context::guarded([&] {
 auto owned=std::make_unique<shared_context::State>(stream); auto *s=owned.get();
'''+prep+'''
 *out=owned.release();
 });
}
'''
    identity={'role':role,'operator_name':op,'source_sha256':sha,'kernel_symbols':','.join(launch_symbols.values())}
    code+='static const SCIdentity ident={SC_ABI_VERSION,'+','.join(json.dumps(x) for x in identity.values())+'};\n'
    code+='static const SCIdentity *identity(){return &ident;}\n'
    code+='extern "C" __attribute__((visibility("default"))) const SCAPI *sc_get_api() {\n'
    code+='static const SCAPI api={SC_ABI_VERSION,identity,prepare,shared_context::launch,shared_context::export_output,shared_context::destroy,shared_context::launch_count,shared_context::resources,shared_context::error}; return &api; }\n'
    return code,identity,original_host

def build(args):
    sources={role:Path(raw).resolve() for role,raw in [('A',args.source_a),('B',args.source_b)]}
    build_configs={role:validate_source_cmake(source,args.operator,args.npu_arch) for role,source in sources.items()}
    out=Path(args.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    manifest={'version':'shared_context_build_v1','operator':args.operator,'roles':{},'harness':{p.name:digest(p) for p in HARNESS.iterdir() if p.is_file()}}
    for role,raw in [('A',args.source_a),('B',args.source_b)]:
        source=Path(raw).resolve(); sha=source_hash(source)
        code,identity,host=generate_adapter(source,args.operator,role,sha)
        target=out/role
        if target.exists(): raise ValueError(f'refuse overwrite {target}')
        target.mkdir()
        for sub in ('op_host','op_kernel'): shutil.copytree(source/sub,target/sub)
        generated=target/'op_host'/f'{args.operator}.asc'; generated.write_text(code)
        (out/f'{role}.harness.patch').write_text(''.join(difflib.unified_diff(host.splitlines(True),code.splitlines(True),fromfile=f'source/op_host/{args.operator}.asc',tofile=f'prepared/op_host/{args.operator}.asc')))
        manifest['roles'][role]={**identity,**build_configs[role],'source_dir':str(source),'adapter_sha256':digest(generated),'patch_sha256':digest(out/f'{role}.harness.patch'),'binary':str(out/'build'/f'librole_{role}.so')}
        if (source.parent/'dispatch-launch.json').is_file():
            manifest['roles'][role]['dispatch_contract']={'path':str(source.parent/'dispatch-launch.json'),'sha256':'sha256:'+digest(source.parent/'dispatch-launch.json')}
        if args.operator in LEVEL2_OPERATORS:
            manifest['roles'][role]['adapter_contract']='level2_source_capture_stream_async_v2'
    cmake='''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(shared_context LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
'''
    for role in ('A','B'):
        cmake+=f'''add_library(role_{role} SHARED {role}/op_host/{args.operator}.asc)
target_include_directories(role_{role} PRIVATE {role}/op_host {role}/op_kernel "{HARNESS}")
target_link_libraries(role_{role} PRIVATE tiling_api register platform unified_dlog dl m graph_base ascendcl ascendc_runtime)
target_link_directories(role_{role} PRIVATE "$ENV{{ASCEND_HOME_PATH}}/lib64" "$ENV{{ASCEND_HOME_PATH}}/aarch64-linux/lib64")
target_compile_options(role_{role} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch={args.npu_arch}>)
target_link_options(role_{role} PRIVATE "-Wl,-Bsymbolic")
'''
    cmake+=f'''add_executable(shared_context_runner "{HARNESS}/runner.cpp")
target_include_directories(shared_context_runner PRIVATE "$ENV{{ASCEND_HOME_PATH}}/include" "$ENV{{ASCEND_HOME_PATH}}/aarch64-linux/include" "{HARNESS}")
target_link_directories(shared_context_runner PRIVATE "$ENV{{ASCEND_HOME_PATH}}/lib64" "$ENV{{ASCEND_HOME_PATH}}/aarch64-linux/lib64")
target_link_libraries(shared_context_runner PRIVATE ascendcl dl)
'''
    (out/'CMakeLists.txt').write_text(cmake)
    if not args.generate_only:
        subprocess.run(['cmake','-S',str(out),'-B',str(out/'build')],check=True)
        subprocess.run(['cmake','--build',str(out/'build'),'-j',str(args.jobs)],check=True)
        for role in ('A','B'): manifest['roles'][role]['binary_sha256']=digest(manifest['roles'][role]['binary'])
        manifest['runner']={'path':str(out/'build/shared_context_runner'),'sha256':digest(out/'build/shared_context_runner')}
    (out/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operator',required=True,choices=SUPPORTED)
    p.add_argument('--source-a',required=True); p.add_argument('--source-b',required=True)
    p.add_argument('--output-dir',required=True); p.add_argument('--npu-arch',default='dav-2201')
    p.add_argument('--jobs',type=int,default=2); p.add_argument('--generate-only',action='store_true')
    args=p.parse_args(); print(json.dumps(build(args),indent=2))
if __name__=='__main__': main()
