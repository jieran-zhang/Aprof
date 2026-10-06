#!/usr/bin/env python3
"""Source-preserving CANNBench Level2 preparation and output contracts.

The generated adapter executes the original host preparation once, captures its
actual conditional launch sequence, and defers its original output conversion.
It never edits the operator source or executes a device command on import.

Measurement v2 currently requires equal output/workspace layouts across roles
for the normal/swapped address control. A plan changing global workspace count
or size must fail the explicit compatibility check and undergo a new measurement
policy review and qualification; unused capacity is not silently normalized.
"""
from __future__ import annotations
import hashlib
from contextlib import contextmanager
import json
import math
import re
from pathlib import Path

OPERATORS = ('apply_adam_w', 'apply_rotary_pos_emb', 'arg_max', 'cross_entropy_loss',
             'cummin', 'dynamic_quant', 'gather', 'gcd', 'grid_sampler_3d',
             'group_norm', 'maximum', 'resize_bilinear', 'rms_norm', 'scatter',
             'softmax', 'unsorted_segment_sum')
OUTPUT_KEYS = {'apply_rotary_pos_emb': ('query_out', 'key_out'),
               'cummin': ('values', 'indices'), 'dynamic_quant': ('output_y', 'output_scale')}
DTYPE_BYTES = {'float16': 2, 'bfloat16': 2, 'float32': 4, 'float64': 8,
               'int8': 1, 'uint8': 1, 'int16': 2, 'int32': 4, 'int64': 8, 'bool': 1}


def operator_name(opdir):
    path = Path(opdir)
    names = [op for op in OPERATORS if (path/'op_host'/f'{op}.asc').is_file()]
    if len(names) != 1:
        raise ValueError('expected one recognized Level2 host source')
    return names[0]


def output_paths(operator, metadata, output):
    keys = OUTPUT_KEYS.get(operator, ('output',))
    if output is None:
        return {key: str(metadata[key]) for key in keys}
    output = Path(output)
    if len(keys) == 1:
        return {keys[0]: str(output)}
    return {key: str(output.with_name(output.name + '.' + key)) for key in keys}


def command_from_metadata(opdir, metadata, device=0, output=None):
    op = operator_name(opdir)
    m = dict(metadata)
    m.update(output_paths(op, m, output))
    shape = lambda x: ','.join(map(str, x))
    args = {}
    if op == 'apply_adam_w':
        a = m['attrs']
        args = {'numel': m['numel'], 'dtype': m['dtype'], 'input-dir': m['input_dir'], 'output': m['output'],
                'lr': a['lr'], 'beta1': a['beta1'], 'beta2': a['beta2'], 'weight-decay': a['weight_decay'],
                'epsilon': a.get('epsilon', 1e-8), 'step': a.get('step', 1), 'maximize': int(a.get('maximize', False))}
    elif op == 'apply_rotary_pos_emb':
        args = {'shape': shape(m['shape']), 'cos-shape': shape(m['cos_shape']), 'dtype': m['dtype'],
                'layout': m['layout'], 'mode': m['rotary_mode'], **{k: m[k] for k in ('query','key','cos','sin')},
                'query-out': m['query_out'], 'key-out': m['key_out']}
    elif op in ('arg_max', 'cummin', 'softmax'):
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'dim': m['dim'], 'input': m['input']}
        if op == 'arg_max': args['keepdim'] = int(m['keepdim'])
        args.update({k: m[k] for k in OUTPUT_KEYS.get(op, ('output',))})
    elif op == 'cross_entropy_loss':
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'reduction': m['reduction'],
                'ignore': m['ignore_index'], 'input': m['input'], 'target': m['target'], 'output': m['output']}
    elif op == 'dynamic_quant':
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'input': m['input'], 'y': m['output_y'], 'scale': m['output_scale']}
    elif op == 'gather':
        args = {'x-shape': shape(m['input_shapes'][0]), 'index-shape': shape(m['input_shapes'][1]),
                'x-dtype': m['dtypes'][0], 'index-dtype': m['dtypes'][1], 'dim': m['dim'],
                'x': m['x'], 'index': m['index'], 'output': m['output']}
    elif op in ('gcd', 'maximum'):
        args = {'x1-shape': shape(m['input_shapes'][0]), 'x2-shape': shape(m['input_shapes'][1]),
                'dtype': m['dtype'], 'x1': m['x1'], 'x2': m['x2'], 'output': m['output']}
    elif op == 'grid_sampler_3d':
        args = {'x-shape': shape(m['input_shapes'][0]), 'grid-shape': shape(m['input_shapes'][1]), 'dtype': m['dtype'],
                'interpolation': m['interpolation_mode'], 'padding': m['padding_mode'], 'align-corners': int(m['align_corners']),
                'x': m['x'], 'grid': m['grid'], 'output': m['output']}
    elif op == 'group_norm':
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'groups': m['num_groups'], 'epsilon': m['epsilon'],
                **{k: m[k] for k in ('x','gamma','beta','output')}}
    elif op == 'resize_bilinear':
        args = {'shape': shape(m['shape']), 'output-size': shape(m['resolved_output_size']), 'dtype': m['dtype'],
                'align-corners': int(m['align_corners']), 'input': m['input'], 'output': m['output']}
    elif op == 'rms_norm':
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'epsilon': m['epsilon'],
                **{k: m[k] for k in ('x','gamma','output')}}
    elif op == 'scatter':
        args = {'data-shape': shape(m['data_shape']), 'index-shape': shape(m['index_shape']),
                'data-dtype': m['data_dtype'], 'index-dtype': m['index_dtype'], 'dim': m['dim'], 'reduce': m['reduce'] or 'none',
                **{k: m[k] for k in ('data','indices','updates','output')}}
    elif op == 'unsorted_segment_sum':
        args = {'shape': shape(m['shape']), 'dtype': m['dtype'], 'id-dtype': m['id_dtype'], 'num-segments': m['num_segments'],
                **{k: m[k] for k in ('data','ids','output')}}
    args['device'] = device
    return [str(Path(opdir)/'build'/op), *[str(v) for k, value in args.items() for v in ('--'+k, value)]]


def output_metadata(operator, metadata, output_bundle):
    """Unpack named outputs after native execution; keep single outputs unchanged."""
    result = dict(metadata)
    paths = output_paths(operator, metadata, output_bundle)
    result.update(paths)
    keys = OUTPUT_KEYS.get(operator, ('output',))
    if len(keys) == 1:
        return result
    bundle = Path(output_bundle)
    # Each native WriteFile contributes uint64 byte count followed by exact bytes.
    import struct
    rows = []
    with bundle.open('rb') as stream:
        for key in keys:
            header = stream.read(8)
            if len(header) != 8: raise ValueError('truncated output bundle length')
            length = struct.unpack('<Q', header)[0]
            if not length or length > bundle.stat().st_size: raise ValueError('invalid output bundle length')
            target = Path(paths[key])
            digest = hashlib.sha256()
            with target.open('xb') as out:
                remaining = length
                while remaining:
                    block = stream.read(min(remaining, 8*1024*1024))
                    if not block: raise ValueError('truncated output bundle')
                    out.write(block); digest.update(block); remaining -= len(block)
            rows.append({'name': key, 'path': str(target), 'bytes': length, 'sha256': 'sha256:'+digest.hexdigest()})
        if stream.read(1): raise ValueError('extra output bundle data')
    manifest = bundle.with_name(bundle.name+'.outputs.json')
    with manifest.open('x') as out:
        json.dump({'version':'level2_output_bundle_v1', 'operator':operator, 'outputs':rows}, out, indent=2)
    return result


def repeat_for_baseline_us(duration_us):
    if not isinstance(duration_us, (int,float)) or not math.isfinite(duration_us) or duration_us <= 0:
        raise ValueError('positive finite baseline pilot duration required')
    return 1 if duration_us > 10_000 else 10


def _split_args(value):
    out=[]; start=0; depth=0
    for i,c in enumerate(value):
        if c in '([{': depth+=1
        elif c in ')]}': depth-=1
        elif c==',' and depth==0: out.append(value[start:i].strip());start=i+1
    out.append(value[start:].strip())
    return out


def _call_end(text, start):
    opening=text.index('(',start); depth=1; index=opening+1; quote=None; escaped=False
    while depth:
        c=text[index]
        if quote:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c==quote: quote=None
        elif c in '\"\'': quote=c
        elif c=='(':depth+=1
        elif c==')':depth-=1
        index+=1
    return opening,index


def _replace_calls(text, name, fn):
    matches=list(re.finditer(r'\b'+re.escape(name)+r'\s*\(',text))
    for match in reversed(matches):
        opening,end=_call_end(text,match.start())
        text=text[:match.start()]+fn(_split_args(text[opening+1:end-1]))+text[end:]
    return text


def generate_adapter(source, operator, role, source_sha):
    """Transform a reviewed host, preserving tiling expressions and control flow."""
    if operator not in OPERATORS or role not in ('A','B'): raise ValueError('unsupported role/operator')
    source=Path(source)
    original=(source/'op_host'/f'{operator}.asc').read_text()
    match=re.search(r'\bint\s+main\s*\(',original)
    if not match: raise ValueError('host main missing')
    prefix,main=original[:match.start()],original[match.start():]
    kernels=list(dict.fromkeys(re.findall(r'\b(\w+)\s*<<<',main)))
    if not kernels:raise ValueError('no direct kernel launches')
    # Include every definition so dormant dispatch entries cannot collide across DSOs.
    kernel_text='\n'.join(p.read_text() for p in (source/'op_kernel').glob('*') if p.is_file())
    definitions=re.findall(r'extern\s+"C"\s+__global__[^\n{]*?\bvoid\s+(\w+)\s*\(',kernel_text)
    rename={k:f'sc_{role}_{source_sha[:12]}_{k}' for k in dict.fromkeys(kernels+definitions)}
    first=main.find('ACL_MEMCPY_DEVICE_TO_HOST')
    if first<0:raise ValueError('host output copy missing')
    # Capture output conversion through the final WriteFile/throw statement.
    begin=max(main.rfind(';',0,first),main.rfind('}',0,first))+1
    writes=list(re.finditer(r'\bWriteFile\s*\(',main))
    if not writes:raise ValueError('host output write missing')
    _,end_call=_call_end(main,writes[-1].start())
    end=main.index(';',end_call)+1
    exporter=main[begin:end]
    if '<<<' in exporter or 'ACL_MEMCPY_HOST_TO_DEVICE' in exporter:
        raise ValueError('output block overlaps launch/preparation')
    outputs=[]
    def output_copy(args):
        if args[-1] != 'ACL_MEMCPY_DEVICE_TO_HOST': raise ValueError('unexpected output copy direction')
        outputs.append(args[2])
        return 'level2::export_copy('+','.join(args)+')'
    exporter=_replace_calls(exporter,'aclrtMemcpy',output_copy)
    exporter=_replace_calls(exporter,'WriteFile',lambda a:'level2::write_output('+','.join(['""',*a[1:]])+')')
    exporter=exporter.replace('aclrtMemcpy(', 'level2::export_copy(')
    mark=''.join('s->mark_output('+p+');' for p in outputs)
    main=main[:begin]+' '+mark+' s->exporter=[=](std::ostream &bundle){'+exporter+'}; '+main[end:]
    # Kernels capture values, and resolve each pointer against CURRENT resource mapping.
    pattern=r'(\w+)\s*<<<(.*?)>>>\((.*?)\);'
    def capture(m):
        args=m[3]
        args=re.sub(r'static_cast\s*<\s*uint8_t\s*\*\s*>\s*\(([^()]*)\)',r's->mapped(\1)',args)
        if 'static_cast' in args or any('*' in x for x in _split_args(args)):
            raise ValueError('unreviewed kernel argument expression')
        return 's->kernel([=](){'+m[1]+'<<<'+m[2]+'>>>('+args+');});'
    main=re.sub(pattern,capture,main,flags=re.S)
    if '<<<' not in main:raise ValueError('missing captured launch')
    mapping={'aclInit':'init','aclFinalize':'finalize','aclrtSetDevice':'set_device','aclrtResetDevice':'reset_device',
             'aclrtCreateStream':'create_stream','aclrtDestroyStream':'destroy_stream','aclrtMalloc':'allocate',
             'aclrtMallocHost':'allocate_host','aclrtFree':'free_device','aclrtFreeHost':'free_host',
             'aclrtMemcpy':'copy','aclrtMemset':'zero','aclrtSynchronizeStream':'synchronize'}
    for before,after in mapping.items():main=re.sub(r'\b'+before+r'\s*\(',f'level2::{after}(',main)
    main=re.sub(r'\bmain\s*\(', 'prepare_original(', main,count=1)
    opening=main.index('{');main=main[:opening+1]+' auto *s=level2::current; '+main[opening+1:]
    header=''.join(f'#define {k} {v}\n' for k,v in rename.items())
    code=header+prefix+'\n#include "level2_adapter_common.h"\n'+main
    multi='true' if operator in OUTPUT_KEYS else 'false'
    code+='''\nstatic int prepare(int argc,char **argv,int64_t cores,void *stream,void **out) {
 return shared_context::guarded([&]{
  auto owned=std::make_unique<level2::State>(stream);auto *s=owned.get();
  level2::current=s;
  try { if(prepare_original(argc,argv)!=0) throw std::runtime_error("original host preparation failed"); }
  catch(...) {level2::current=nullptr;throw;}
  level2::current=nullptr;
  if(!s->kernel_count || !s->exporter)throw std::runtime_error("incomplete captured operator");
  s->bundled='''+multi+'''; *out=owned.release();
 });
}
'''
    identity={'role':role,'operator_name':operator,'source_sha256':source_sha,'kernel_symbols':','.join(rename[k] for k in kernels)}
    code+='static const SCIdentity ident={SC_ABI_VERSION,'+','.join(json.dumps(x) for x in identity.values())+'};\n'
    code+='static const SCIdentity *identity(){return &ident;}\n'
    code+='extern "C" __attribute__((visibility("default"))) const SCAPI *sc_get_api(){static const SCAPI api={SC_ABI_VERSION,identity,prepare,level2::launch,level2::export_output,level2::destroy,level2::launch_count,level2::resources,shared_context::error};return &api;}\n'
    return code,identity,original


def launch_contract(operator, source, metadata):
    host=(Path(source)/'op_host'/f'{operator}.asc').read_text()
    names=list(dict.fromkeys(re.findall(r'\b(\w+)\s*<<<',host)))
    dispatch=Path(source).parent/'dispatch-launch.json'
    dispatch_selection=None
    if dispatch.exists():
        from shared_context_build import source_hash
        from aprof_runtime.planning import select_dispatch
        data=json.loads(dispatch.read_text())
        if data.get('version')!='level2_dispatch_launch_v1' or data.get('source_sha256')!=source_hash(Path(source)):
            raise ValueError('dispatch launch contract source identity differs')
        if data['dispatch_plan']['operator']!=operator:raise ValueError('dispatch plan operator differs')
        dispatch_selection=select_dispatch(data['dispatch_plan'],workload_metadata(operator,metadata))
        entry=data['sequences'][str(dispatch_selection['tiling_key'])]
        names=entry['kernels']
        if dispatch_selection['kernel_entry'] not in names:raise ValueError('selected dispatch entry absent from launch sequence')
        declared=data
    else:
        declared=None
    if dispatch_selection is not None:
        pass
    elif operator=='cross_entropy_loss':
        names=[('cross_entropy_kernel' if metadata['reduction']=='none' else 'cross_entropy_reduce')]
    elif operator=='scatter':
        half=metadata['data_dtype']=='float16' and metadata.get('reduce') in ('add','multiply')
        names=['scatter_half_to_float_kernel','scatter_kernel','scatter_float_to_half_kernel'] if half else ['scatter_kernel']
    elif operator!='unsorted_segment_sum' and len(names)!=1:
        raise ValueError('changed launch topology requires metadata-based dispatch-launch.json')
    all_names=set(re.findall(r'\b(\w+)\s*<<<',host))
    if not names or not set(names)<=all_names:raise ValueError('launch contract references absent source kernel')
    resets=(entry.get('auxiliary_tasks',[]) if declared is not None else
            ['device_to_device_copy'] if operator=='scatter' else ['device_memset'] if operator=='unsorted_segment_sum' else [])
    result={'kernels':names,'launches_per_call':len(names),'required_auxiliary_tasks':resets,
            'output_keys':list(OUTPUT_KEYS.get(operator,('output',))), 'task_type_policy':'verify_captured_serial_tasks'}
    if dispatch_selection is not None:result['expected_dispatch']=dispatch_selection
    return result



def verify_build_dispatch(identity):
    """Bind optional sibling dispatch bytes to the compiled role's build manifest."""
    paths=[]
    for field,path in [('dispatch_contract',Path(identity['source_dir']).parent/'dispatch-launch.json')]:
        pointer=identity.get(field)
        if path.exists()!=bool(pointer):raise ValueError('unbound or missing '+field)
        if pointer:
            if Path(pointer['path']).resolve()!=path.resolve() or pointer['sha256']!='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('compiled '+field+' identity differs')
            paths.append(path)
    return paths



def native_kernel_sequence(identity, kernels):
    expected=['sc_'+identity['role']+'_'+identity['source_sha256'][:12]+'_'+name for name in kernels]
    compiled=identity['kernel_symbols'].split(',')
    if not set(expected)<=set(compiled):raise ValueError('declared entry is absent from compiled role identity')
    return expected


def is_level2(opdir):
    return any((Path(opdir)/'op_host'/f'{op}.asc').is_file() for op in OPERATORS)


def dispatch_command(opdir, metadata, device, output=None):
    if is_level2(opdir): return command_from_metadata(opdir, metadata, device, output)
    from cannbench_device_timing import command_from_metadata as legacy
    return legacy(opdir, metadata, device, output)


def verification_metadata(opdir, metadata, output):
    if is_level2(opdir): return output_metadata(operator_name(opdir), metadata, output)
    return dict(metadata, output=str(output))


def prepared_commands(opdir, case_id, device, input_root=None):
    if not is_level2(opdir):
        from cannbench_device_timing import prepared_commands as legacy
        return legacy(opdir, case_id, device, input_root)
    import sys
    opdir=Path(opdir).resolve(); inputs=Path(input_root).resolve() if input_root else opdir/'build/cases'
    metadata=inputs/f'case_{case_id:02d}'/'metadata.json'
    return {'prepare_argv':[sys.executable,str(opdir/'scripts/gen_data.py'),'--case',str(case_id),'--output',str(inputs)],
            'metadata':str(metadata),'execute_argv':command_from_metadata(opdir,json.loads(metadata.read_text()),device) if metadata.exists() else None,
            'verify_argv':[sys.executable,str(opdir/'scripts/verify_result.py'),'--metadata',str(metadata)],'cwd':str(opdir)}


def input_paths(metadata):
    """All concrete input/oracle files, including AdamW's directory interface."""
    excluded={'output','query_out','key_out','values','output_y','output_scale'}
    # 'indices' is an input for scatter and an output for cummin.
    if 'values' in metadata: excluded.add('indices')
    paths={str(Path(v).resolve()) for k,v in metadata.items() if k not in excluded and isinstance(v,str) and Path(v).is_file()}
    if 'input_dir' in metadata:
        directory=Path(metadata['input_dir'])
        for name in ('var','grad','m','v'):
            p=directory/(name+'.bin')
            if not p.is_file():raise ValueError('missing AdamW input: '+str(p))
            paths.add(str(p.resolve()))
    return sorted(paths)


def verify_output_metadata(operator, metadata, output_bundle):
    """Read-only replay of a previously unpacked output bundle and its hashes."""
    import struct
    import level2_verification_storage as evidence_storage
    result=dict(metadata);result.update(output_paths(operator,metadata,output_bundle))
    keys=OUTPUT_KEYS.get(operator,('output',))
    if len(keys)==1:return result
    bundle=Path(output_bundle)
    manifest=json.loads(evidence_storage.read_bytes(bundle.with_name(bundle.name+'.outputs.json')))
    if manifest.get('version')!='level2_output_bundle_v1' or manifest.get('operator')!=operator:
        raise ValueError('output bundle manifest identity mismatch')
    if [r['name'] for r in manifest['outputs']]!=list(keys):raise ValueError('output bundle names differ')
    with evidence_storage.open_binary(bundle) as stream:
        for key,row in zip(keys,manifest['outputs']):
            header=stream.read(8)
            if len(header)!=8:raise ValueError('truncated output header')
            size=struct.unpack('<Q',header)[0]; h=hashlib.sha256()
            if row['bytes']!=size or row['path']!=result[key]:raise ValueError('output bundle size/path differs')
            with evidence_storage.open_binary(Path(result[key])) as separate:
                remaining=size
                while remaining:
                    block=stream.read(min(remaining,8*1024*1024))
                    if not block or separate.read(len(block))!=block:raise ValueError('unpacked output differs from bundle')
                    h.update(block);remaining-=len(block)
                if separate.read(1):raise ValueError('extra unpacked output data')
            if row['sha256']!='sha256:'+h.hexdigest():raise ValueError('output hash differs')
        if stream.read(1):raise ValueError('extra bundle data')
    return result


class Level2Verifier:
    """Reuse the exact, repository-reviewed verifier; freeze local imports as well.

    The original file and its dependencies are executed unchanged. Import caches
    for generic sibling module names are isolated to this operator, preventing a
    different operator's gen_data/cases modules from satisfying the imports.
    """
    def __init__(self, path):
        import ast
        import importlib.util
        import sys
        self.path=Path(path).resolve()
        operator=operator_name(self.path.parents[1]);self.operator=operator
        canonical=Path(__file__).resolve().parents[1]/'benchmarks/cannbench/operators'/operator/'scripts/verify_result.py'
        if operator not in OPERATORS or self.path.read_bytes()!=canonical.read_bytes():
            raise ValueError('Level2 reusable verifier must match the frozen canonical oracle')
        self.dependencies={p:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in self.path.parent.iterdir()
                           if p.is_file() and p.suffix in ('.py','.csv','.yaml','.yml')}
        self.source_hash=self.dependencies[self.path]
        tree=ast.parse(self.path.read_bytes())
        mains=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main']
        if len(mains)!=1 or mains[0].args.args:raise ValueError('zero-argument verifier main required')
        spec=importlib.util.spec_from_file_location('_aprof_level2_'+self.source_hash[7:],self.path)
        self.module=importlib.util.module_from_spec(spec)
        names=[p.stem for p in self.path.parent.glob('*.py')]
        previous={name:sys.modules.pop(name,None) for name in names}
        previous_path=list(sys.path);previous_bytecode=sys.dont_write_bytecode
        try:
            sys.path.insert(0,str(self.path.parent));sys.dont_write_bytecode=True
            exec(compile(self.path.read_bytes(),str(self.path),'exec'),self.module.__dict__)
        finally:
            sys.path[:]=previous_path;sys.dont_write_bytecode=previous_bytecode
            for name,old in previous.items():
                sys.modules.pop(name,None)
                if old is not None:sys.modules[name]=old
        if 'torch' in sys.modules:sys.modules['torch'].set_num_threads(2)

    @contextmanager
    def execution_metadata(self, metadata_path):
        """Relocate USS mmap scratch by copying identical metadata bytes locally.

        Original input/output paths and oracle source are unchanged. The actual
        argv path, executed metadata bytes and copied result are all preserved.
        """
        import tempfile
        import shutil
        original=Path(metadata_path).resolve()
        if self.operator!='unsorted_segment_sum':
            yield original,None
            return
        metadata=json.loads(original.read_text())
        if any(not Path(metadata[k]).is_absolute() for k in ('data','ids','output')):
            raise ValueError('local oracle execution requires absolute data/output paths')
        def pointer(path):return {'path':str(path),'sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}
        archive=original.with_name('executed-metadata.json')
        if archive.exists() or original.with_name('result.json').exists():raise FileExistsError('oracle relocation artifacts already exist')
        with tempfile.TemporaryDirectory(prefix='aprof-oracle-uss-',dir='/tmp') as raw:
            scratch=Path(raw);actual=scratch/'metadata.json';shutil.copyfile(original,actual)
            shutil.copyfile(actual,archive)
            info={'version':'level2_oracle_metadata_relocation_v1','reason':'original oracle writes mmap workspace beside metadata',
                  'original_metadata':pointer(original),'executed_metadata_archive':pointer(archive),
                  'execution_metadata_path':str(actual),'execution_metadata_sha256':pointer(actual)['sha256'],
                  'metadata_bytes_identical':True,'oracle_source':pointer(self.path),
                  'dependencies':[{'path':str(p),'sha256':h} for p,h in self.dependencies.items()],
                  'result_artifacts':[],'temporary_directory_removed':False}
            if actual.read_bytes()!=original.read_bytes():raise ValueError('oracle metadata copy differs')
            try:
                yield actual,info
            finally:
                result=scratch/'result.json'
                if result.is_file():
                    target=original.with_name('result.json');shutil.copyfile(result,target)
                    info['result_artifacts'].append({'execution_path':str(result),'archive':pointer(target)})
        info['temporary_directory_removed']=True

    def run(self, metadata_path, *, cwd=None):
        for path,expected in self.dependencies.items():
            if 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise ValueError('oracle dependency changed after preload: '+str(path))
        from cannbench_device_timing import ReusedVerifier
        with self.execution_metadata(metadata_path) as (actual,relocation):
            result=ReusedVerifier.run(self,actual,cwd=cwd)
        if relocation is not None:result.oracle_relocation=relocation
        for path,expected in self.dependencies.items():
            if 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('oracle dependency changed during call')
        return result



def verify_oracle_relocation(info, metadata_path, verifier_path):
    """Read-only closure for an unchanged oracle executed with local metadata."""
    original=Path(metadata_path).resolve();verifier=Path(verifier_path).resolve()
    def pointer(path):return {'path':str(path),'sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}
    if info.get('version')!='level2_oracle_metadata_relocation_v1' or info.get('original_metadata')!=pointer(original):raise ValueError('oracle relocation original metadata differs')
    if info.get('oracle_source')!=pointer(verifier) or not info.get('metadata_bytes_identical') or not info.get('temporary_directory_removed'):raise ValueError('oracle relocation source/cleanup differs')
    archive=original.with_name('executed-metadata.json')
    if info.get('executed_metadata_archive')!=pointer(archive) or archive.read_bytes()!=original.read_bytes():raise ValueError('executed oracle metadata differs')
    actual=Path(info['execution_metadata_path'])
    if not actual.is_absolute() or actual.parent.parent!=Path('/tmp') or not actual.parent.name.startswith('aprof-oracle-uss-') or actual.name!='metadata.json':raise ValueError('unexpected oracle scratch path')
    if info.get('execution_metadata_sha256')!=pointer(original)['sha256']:raise ValueError('oracle scratch metadata hash differs')
    expected_dependencies=[pointer(p) for p in verifier.parent.iterdir() if p.is_file() and p.suffix in ('.py','.csv','.yaml','.yml')]
    if sorted(info.get('dependencies',[]),key=lambda x:x['path'])!=sorted(expected_dependencies,key=lambda x:x['path']):raise ValueError('oracle relocation dependencies differ')
    result=original.with_name('result.json')
    if info.get('result_artifacts')!=[{'execution_path':str(actual.with_name('result.json')),'archive':pointer(result)}]:raise ValueError('oracle copied result differs')
    if json.loads(result.read_text()).get('passed') is not True:raise ValueError('oracle copied result did not pass')
    return [archive,result]


def reusable_verifier(path):
    if is_level2(Path(path).parents[1]):return Level2Verifier(path)
    from cannbench_device_timing import ReusedVerifier
    return ReusedVerifier(path)


def workload_metadata(operator, metadata=None):
    """Semantic descriptor shared by host-dispatch plans and the trace verifier.

    Case IDs, filenames, seeds and previously observed performance are excluded.
    """
    if metadata is None:
        metadata=operator;operator=None
    m=metadata
    shape=m.get('shape',m.get('output_shape',m.get('data_shape')))
    if shape is None:shape=m['input_shapes'][0]
    dtype=m.get('dtype',m.get('data_dtype'))
    if dtype is None:dtype=m['dtypes'][0]
    allowed=('dim','keepdim','reduction','ignore_index','rotary_mode','num_groups','epsilon',
             'align_corners','interpolation_mode','padding_mode','reduce','num_segments','id_dtype','index_dtype','token_count','rows','axis','ndim')
    attributes={k:m[k] for k in allowed if k in m and m[k] is not None}
    for k,v in m.get('attrs',{}).items():
        if k not in allowed and k not in ('lr','beta1','beta2','weight_decay','step','maximize'):continue
        if isinstance(v,(str,int,float,bool)):attributes[k]=v
    attributes.setdefault('ndim',len(shape))
    attributes['last_axis_aligned64']=(shape[-1]*DTYPE_BYTES[dtype])%64==0
    if 'dim' in attributes:
        attributes['raw_dim']=attributes['dim'];attributes['dim']%=len(shape);attributes['axis']=attributes['dim']
        axis=attributes['axis'];attributes['last_axis']=axis==len(shape)-1
        attributes['inner']=math.prod(shape[axis+1:]);attributes['axis_length']=shape[axis]
        attributes['sequence_count']=math.prod(shape)//shape[axis]
        attributes['aligned_rows']=(shape[axis]*DTYPE_BYTES[dtype])%32==0
    if m.get('reduce') is None and 'reduce' in m:attributes['reduce']='none'
    if 'input_shapes' in m:
        x,y=m['input_shapes'][:2]
        attributes.update(x1_shape=','.join(map(str,x)),x2_shape=','.join(map(str,y)),same_shape=x==y)
        for prefix,dims in (('x1',x),('x2',y)):
            attributes[prefix+'_ndim']=len(dims)
            for i,n in enumerate(dims):attributes[prefix+'_dim'+str(i)]=n
        if operator=='gather' or 'dtypes' in m:
            axis=attributes['axis'];attributes.update(x_shape=','.join(map(str,x)),index_shape=','.join(map(str,y)),index_dtype=m['dtypes'][1],non_axis_shapes_equal=all(a==b for i,(a,b) in enumerate(zip(x,y)) if i!=axis))
    if operator=='scatter':
        index=m['index_shape'];axis=attributes['axis'];same=all(a==b for i,(a,b) in enumerate(zip(shape,index)) if i!=axis)
        attributes.update(update_numel=math.prod(index),index_non_axis_shapes_equal=same,
            scatter_row_parallel=len(shape)>1 and axis==len(shape)-1 and same and attributes['last_axis_aligned64'],
            scatter_column_parallel=axis==0 and same and (math.prod(shape[1:])*DTYPE_BYTES[dtype])%64==0)
    if operator=='unsorted_segment_sum':
        inner=math.prod(shape[1:]);accum_item=4 if dtype in ('float16','bfloat16') else DTYPE_BYTES[dtype]
        attributes.update(inner=inner,aligned_inner=((inner+15)//16)*16,accumulator_bytes=accum_item,
                          workspace_bytes=m['num_segments']*((inner+15)//16)*16*accum_item)
    if operator=='dynamic_quant':attributes.update(row_length=shape[-1],token_count=math.prod(shape[:-1]))
    if operator=='group_norm':
        groups=m['num_groups']
        if groups<=0 or shape[1]%groups:raise ValueError('group_norm channels must divide groups')
        spatial=math.prod(shape[2:]);attributes.update(group_count=shape[0]*groups,group_elements=shape[1]//groups*spatial,channels_per_group=shape[1]//groups,spatial=spatial)
    if operator=='cross_entropy_loss':
        inner=math.prod(shape[2:]);attributes.update(inner=inner,positions=shape[0]*inner,C=shape[1],gather_safe=inner==1 or inner>=32//DTYPE_BYTES[dtype])
    if operator=='rms_norm':attributes['hidden']=shape[-1]
    if operator=='arg_max':attributes['output_length']=attributes['sequence_count']
    if operator=='softmax':
        item=DTYPE_BYTES[dtype];reduce=attributes['axis_length'];align={'float16':64,'bfloat16':16,'float32':8}[dtype]
        aligned=((reduce+align-1)//align)*align;half_mask=((aligned+7)//8+255)//256*256 if dtype=='float16' else 0
        half_raw_extra=max(0,4*aligned-(2*aligned+16384)) if dtype=='float16' else 0
        attributes.update(reduce=reduce,gather_safe=attributes['inner']>=32//item,ub_bytes=(2*item+8)*aligned+16384+4096+32+half_mask+half_raw_extra)
    output_shape=m.get('output_shape')
    if operator=='gather':output_shape=m['input_shapes'][1]
    elif operator=='grid_sampler_3d':
        x,grid=m['input_shapes'];output_shape=[x[0],x[1],*grid[1:4]]
    elif operator in ('maximum','gcd'):
        x,y=m['input_shapes'];rank=max(len(x),len(y));xx=[1]*(rank-len(x))+x;yy=[1]*(rank-len(y))+y
        if any(a!=b and a!=1 and b!=1 for a,b in zip(xx,yy)):raise ValueError('incompatible broadcast metadata')
        output_shape=[max(a,b) for a,b in zip(xx,yy)]
        attributes['rhs_last_axis']=xx==output_shape and all(n==1 for n in yy[:-1]) and yy[-1]==output_shape[-1]
    if operator=='unsorted_segment_sum':output_shape=[m['num_segments'],*shape[1:]]
    if output_shape is not None:
        attributes['output_numel']=math.prod(output_shape)
        if output_shape:attributes['output_row_aligned64']=(output_shape[-1]*DTYPE_BYTES[dtype])%64==0
        if operator=='grid_sampler_3d':attributes['spatial_aligned64']=(math.prod(output_shape[2:])*DTYPE_BYTES[dtype])%64==0
    if 'cos_shape' in m:
        attributes.update(layout=m['layout'],mode=m['rotary_mode'],cos_batched=len(m['cos_shape'])>2,head_dim=shape[-1])
    return {'shape':list(shape),'dtype':str(dtype),'layout':str(m.get('layout','ND')),'attributes':attributes}
