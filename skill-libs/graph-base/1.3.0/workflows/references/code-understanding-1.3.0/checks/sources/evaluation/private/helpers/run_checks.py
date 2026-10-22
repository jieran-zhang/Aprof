#!/usr/bin/env python3
"""CPU-only structural checks. No SDK/NPU build, no kernel execution, no gold input.

Tiling is called directly from the supplied pure C++ headers. Address and format
checks model the frozen API contract, not a hardware simulator. The event graph
checks ordering guarantees, not device failure or numerical output.
"""
from pathlib import Path
import errno, hashlib, json, math, os, re, shutil, struct, subprocess, sys
ROOT=Path(__file__).resolve().parents[2]
PUB=ROOT/'public'
RESULT=ROOT/'private/results'
RESULT.mkdir(parents=True,exist_ok=True)

def read(p):return (PUB/p).read_text()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def interval(start,n):return [start,start+n]
def align32(n):return ((n+31)//32)*32

compiler=shutil.which('g++') or shutil.which('c++')
assert compiler,'A normal C++ compiler is required to call the original tiling headers.'
binary=RESULT/'tiling_probe'
buildtmp=RESULT/'compiler-tmp';buildtmp.mkdir(exist_ok=True)
env=dict(os.environ,TMPDIR=str(buildtmp))
command=[compiler,'-std=c++17','-O0','-Wall','-Wextra','-pedantic',str(Path(__file__).with_name('tiling_probe.cpp')),'-o',str(binary)]
built=subprocess.run(command,text=True,capture_output=True,env=env)
(RESULT/'tiling_compile.stdout').write_text(built.stdout)
(RESULT/'tiling_compile.stderr').write_text(built.stderr)
assert built.returncode==0,built.stderr
execution='ordinary executable'
try:
    probe=subprocess.run([str(binary)],text=True,capture_output=True,env=env,check=True)
except PermissionError:
    # /dev/shm may be mounted noexec; memfd keeps execution in memory and all files under ROOT.
    assert hasattr(os,'memfd_create'),'noexec filesystem needs memfd support'
    fd=os.memfd_create('aprof-tiling-probe',0)
    os.write(fd,binary.read_bytes())
    os.lseek(fd,0,os.SEEK_SET)
    probe=subprocess.run([f'/proc/self/fd/{fd}'],pass_fds=(fd,),text=True,capture_output=True,env=env,check=True)
    os.close(fd)
    execution='memfd because eval storage is noexec'
plans=json.loads(probe.stdout)
(RESULT/'tiling_actual.json').write_text(json.dumps(plans,indent=2)+'\n')
checks=[]
def passed(name,details):checks.append({'check':name,'status':'pass','details':details})

# Directly-called tiling, then independent coverage checks rather than a second tiling formula.
e=plans['exp'];assert e==plans['renamed']
assert [e[k] for k in ['total','blocks','blockLength','tile','dtype']]==[25019,3,8340,4096,2]
assert math.isclose(e['multiplier'],0.5*math.log(2),rel_tol=1e-6)
assert math.isclose(e['shift'],-math.log(2),rel_tol=1e-6)
parts=[];covered=[]
for b in range(e['blocks']):
    off=b*e['blockLength'];length=max(0,min(e['blockLength'],e['total']-off))
    tiles=[min(e['tile'],length-t) for t in range(0,length,e['tile'])]
    parts.append({'block':b,'element_start':off,'length_elements':length,'tile_counts_elements':tiles,'byte_start':2*off,'tail_blockLen_bytes':2*tiles[-1]})
    covered.extend(range(off,off+length))
assert covered==list(range(25019))
assert [p['tile_counts_elements'] for p in parts]==[[4096,4096,148],[4096,4096,148],[4096,4096,147]]
passed('C01_C06_original_header_tiling',{'direct_header_call':True,'plans':parts,'explicit_ub_bytes_bf16':2*4096*2+2*4096*4})

# The source recognizer is intentionally strict: a changed snippet requires updating this model.
copy=read('case-02/source/current/data_copy_pad.asc')
for literal in ['constexpr uint32_t SRC_ROWS = 5;','constexpr uint32_t SRC_COLS = 13;','constexpr uint32_t DST_COLS = 16;',
                'constexpr uint32_t DST_TOTAL_LENGTH = SRC_ROWS * 24;',
                'DataCopyExtParams copyParams{srcRows, srcCols * sizeof(float), 28, 1, 0};',
                'DataCopyExtParams copyParams{srcRows, srcCols * sizeof(T), 1, 20, 0};',
                'padParams.paddingValue = (T)0;','AscendC::Duplicate<T>(srcLocal, (T)0, dstTotalLength);',
                'inputByteSize = SRC_ROWS * 20 * elementSize;', 'size_t outputByteSize = SRC_ROWS * 18 * elementSize;',
                'aclrtMemset(zDevice, outputByteSize, 0xA5, outputByteSize);']:
    assert literal in copy,literal
rows,cols=5,13;data_bytes=cols*4;right=3*4;gm_gap=28;ub_gap=1*32
input_bytes=b''.join(struct.pack('<f',100*r+c) for r in range(rows) for c in range(20))
ub=bytearray(rows*24*4)
gm_read=[];ub_rows=[]
for r in range(rows):
    s=r*(data_bytes+gm_gap);d=r*(align32(data_bytes+right)+ub_gap)
    assert s+data_bytes<=len(input_bytes) and d+data_bytes+right<=len(ub)
    ub[d:d+data_bytes]=input_bytes[s:s+data_bytes]
    ub[d+data_bytes:d+data_bytes+right]=b'\0'*right
    gm_read.append(interval(s,data_bytes))
    ub_rows.append({'data_bytes':interval(d,data_bytes),'right_pad_bytes':interval(d+data_bytes,right),'gap_bytes':interval(d+64,32)})
output=bytearray([0xA5]*(rows*18*4));writes=[]
for r in range(rows):
    s=r*(align32(data_bytes)+1*32);d=r*(data_bytes+20)
    assert s+data_bytes<=len(ub) and d+data_bytes<=len(output)
    output[d:d+data_bytes]=ub[s:s+data_bytes]
    assert struct.unpack('<13f',output[d:d+data_bytes])==tuple(100*r+c for c in range(cols))
    assert output[d+data_bytes:d+72]==bytes([0xA5])*20
    writes.append(interval(d,data_bytes))
assert all(ub[r*96+52:(r+1)*96]==bytes(44) for r in range(rows))
(RESULT/'copy_output_cpu.bin').write_bytes(output)
passed('C02_contract_byte_address_model',{'input_allocation_bytes':len(input_bytes),'gm_read_bytes':gm_read,'ub_allocation_bytes':len(ub),
    'ub_rows':ub_rows,'output_allocation_bytes':len(output),'gm_write_bytes':writes,'gm_gap_bytes_per_row':20,
    'gm_gaps_remain_hex':'A5','cpu_output_sha256':hashlib.sha256(output).hexdigest(),
    'scope':'Byte-copy model of the documented contract; not hardware execution.'})

mk=read('case-03/source/op_kernel/maximum_kernel.asc')
for literal in ['else if constexpr (std::is_same<T, half>::value)',
                'KernelMaximumHalfLastAxisBroadcast op; op.Init(x1, x2, y, t); op.Process();',
                'AscendC::DataCopyPad(b, x2_[off % row_], p, pad);',
                'const uint64_t rowRemain = row_ - (off % row_);',
                'bi += coord * t->x2Stride[dim];']:
    assert literal in mk,literal
mapping={}
for label in ['P','Q','R']:
    p=plans[label]
    assert [p[k] for k in ['total','blockLength','blocks','tile','rank','sameShape']]==[6,6,1,4096,2,0]
    assert p['outShape']==[2,3] and p['x1Stride']==[3,1]
    scalar=[]
    for i in range(p['total']):
        rem=i;bi=0
        for dim in range(p['rank']-1,-1,-1):
            coord=rem%p['outShape'][dim];rem//=p['outShape'][dim]
            bi+=coord*p['x2Stride'][dim]
        scalar.append(bi)
    mapping[label]=scalar
assert mapping['P']==mapping['Q']==[0,0,0,1,1,1]
assert mapping['R']==[0,1,2,0,1,2]
half_requests=[];off=0;row=plans['P']['outShape'][-1]
while off<6:
    count=min(6-off,plans['P']['tile'],row-(off%row))
    start=off%row
    half_requests.append({'out_element_start':off,'count_elements':count,'x2_element_indices':list(range(start,start+count)),
                          'x2_read_bytes':interval(2*start,2*count),'P_x2_allocation_bytes':4,
                          'P_outside_allocation_bytes':[i for i in range(2*start,2*(start+count)) if i>=4]})
    off+=count
assert [r['P_outside_allocation_bytes'] for r in half_requests]==[[4,5],[4,5]]
x1=[1,4,8,2,5,9];x2q=[3,7];x2r=[3,7,6]
qout=[max(a,x2q[b]) for a,b in zip(x1,mapping['Q'])]
rout=[max(a,x2r[b]) for a,b in zip(x1,mapping['R'])]
assert qout==[3,4,8,7,7,9] and rout==[3,7,8,3,7,9]
passed('C03_original_header_and_selected_address_paths',{'tilings_from_original_function':{k:plans[k] for k in ['P','Q','R']},
    'intended_or_scalar_x2_indices':mapping,'selected_half_copy_requests':half_requests,'Q_finite_result':qout,'R_finite_result':rout,
    'P_result':'not predicted: requested read crosses actual host allocation','scope':'Dispatch/address model recognized against exact source fragments, not kernel execution or NumPy.'})

# NZ packing and LoadData block models use labeled elements, so no numerical oracle can mask a format error.
def nz_index(r,c,rows):return (c//16)*rows*16+r*16+c%16

def pack_nz(rows,cols):
    packed=[None]*(rows*cols)
    for r in range(rows):
        for c in range(cols):packed[nz_index(r,c,rows)]=(r,c)
    assert None not in packed
    assert len(set(packed))==rows*cols
    return packed

M,K,N=256,128,128
az=pack_nz(M,K);bz=pack_nz(K,N)
a2201=[None]*(M*K);b2201=[None]*(K*N)
for mb in range(M//16):
    for kb in range(K//16):
        src=mb*256+kb*(M//16)*256;dst=mb*K*16+kb*256
        a2201[dst:dst+256]=az[src:src+256]
for kb in range(K//16):
    for nb in range(N//16):
        src=kb*256+nb*(K//16)*256;dst=kb*N*16+nb*256
        for k_inner in range(16):
            for n_inner in range(16):b2201[dst+n_inner*16+k_inner]=bz[src+k_inner*16+n_inner]
for r in range(M):
    for k in range(K):
        ai=(r//16)*K*16+(k//16)*256+(r%16)*16+k%16
        assert a2201[ai]==(r,k)
for k in range(K):
    for n in range(N):
        bi=(k//16)*N*16+(n//16)*256+(n%16)*16+k%16
        assert b2201[bi]==(k,n)
assert az[nz_index(17,33,M)]==(17,33)
assert nz_index(17,33,M)==8465
assert (17//16)*K*16+(33//16)*256+(17%16)*16+33%16==2577
cm=read('case-04/source/matmul_leakyrelu_basic_api.asc')
for literal in ['a1Local[i * 512 / sizeof(half)]','b1Local[i * 512 / sizeof(half)]',
                'LoadData2DParams{0, baseK / CUBE_BLOCK, baseM / CUBE_BLOCK, 0, 0, false, 0}',
                'LoadData2DParams{0, baseN / CUBE_BLOCK, baseK / CUBE_BLOCK, 0, 0, true, 0}',
                'CrossCoreSetFlag<0x2, PIPE_FIX>(0);','CrossCoreWaitFlag<0x2>(0);']:
    assert literal in cm,literal
assign=[];covered=[]
for j in range(4):
    start=(j//2)*M*N+(j%2)*(M//2*N);count=M//2*N
    assign.append({'AIV':j,'paired_AIC':j//2,'start_half_elements':start,'count_half_elements':count,'start_bytes':2*start})
    covered.extend(range(start,start+count))
assert covered==list(range(512*128))
passed('C04_C06_format_and_mixed_core_mapping',{'A_NZ_17_33_half_offset':8465,'A_2201_Zz_17_33_half_offset':2577,
    'A_3510_NZ_17_33_half_offset':8465,'A_L0_formats_differ':True,'AIV_regions':assign,
    'format_scope':'Labeled block packing/transpose under frozen ND2NZ/LoadData contract; not an SDK simulator.'})

# Source-linked logical slot selection and per-pipeline partial order.
base=read('case-05/source/baseline/mmad.asc');variant=read('case-05/source/variant/mmad.asc')
wait='                    AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(mte1DBFlag);'
assert base.count(wait)==1 and wait not in variant
assert variant==base.replace(wait,'                    // TEST_DELTA: reverse wait removed in this variant.',1)
assert 'uint32_t a1ReadIdx = (kBlockIdx / stepKa) % 2;' in base
assert 'uint32_t b1ReadIdx = (kBlockIdx / stepKb) % 2;' in base
assert 'mte1DBFlag ^= 1;' in base
trace=[{'k':k,'A1_slot':(k//8)%2,'B1_slot':(k//4)%2,'L0_slot':k%2,'A_offset_in_chunk':k%8,'B_offset_in_chunk':k%4} for k in range(10)]
assert [x['A1_slot'] for x in trace]==[0]*8+[1]*2
assert [x['B1_slot'] for x in trace]==[0]*4+[1]*4+[0]*2

def graph(reverse,n=10):
    edges={f'{pipe}{i}':set() for pipe in ['L','M'] for i in range(n)}
    for i in range(n):
        edges[f'L{i}'].add(f'M{i}')
        if i+1<n:
            edges[f'L{i}'].add(f'L{i+1}');edges[f'M{i}'].add(f'M{i+1}')
        if reverse and i+2<n:edges[f'M{i}'].add(f'L{i+2}')
    return edges

def reachable(g,a,b):
    todo=[a];seen=set()
    while todo:
        p=todo.pop()
        if p==b:return True
        if p in seen:continue
        seen.add(p);todo.extend(g[p])
    return False

def topo(g):
    degree={x:0 for x in g}
    for out in g.values():
        for v in out:degree[v]+=1
    order=[]
    while degree:
        ready=sorted((x for x,d in degree.items() if d==0),key=lambda x:(x[0]!='L',int(x[1:])))
        assert ready,'cycle in event graph'
        u=ready[0];order.append(u);del degree[u]
        for v in g[u]:degree[v]-=1
    return order

baseline_graph=graph(wait in base);variant_graph=graph(wait in variant)
assert reachable(baseline_graph,'M0','L2') and not reachable(variant_graph,'M0','L2')
assert reachable(baseline_graph,'M1','L3') and not reachable(variant_graph,'M1','L3')
order=topo(variant_graph);assert order.index('L2')<order.index('M0')
l1={'A_ping':[0,131072],'A_pong':[131072,262144],'B_ping':[262144,393216],'B_pong':[393216,524288]}
assert all(l1[a][1]<=l1[b][0] for a,b in zip(list(l1)[:-1],list(l1)[1:]))
passed('C05_slot_addresses_and_event_partial_order',{'first_ten_K_iterations':trace,'L1_byte_ranges':l1,
    'L0A_byte_ranges':{'ping':[0,16384],'pong':[32768,49152]},'L0B_byte_ranges':{'ping':[0,32768],'pong':[32768,65536]},
    'baseline_M0_before_L2':True,'variant_M0_before_L2_guaranteed':False,'variant_valid_order_for_retained_data_edges':order,
    'scope':'Dataflow partial order only; remaining unmatched flag lifecycle is not simulated; no hardware failure or corruption asserted.'})

# Renaming equivalence is token-aware; strings/comments are not broadly rewritten.
delta=json.loads(read('case-06/source/DELTA.json'))
def rename_cpp(text,mapping):
    token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b[A-Za-z_]\w*\b')
    return token.sub(lambda m:mapping.get(m.group(),m.group()),text)
for original,renamed in [('op_host/exp.asc','op_host/nacre.asc'),('op_kernel/exp_kernel.asc','op_kernel/nacre_stage.asc'),('op_kernel/exp_tiling.h','op_kernel/nacre_plan.h')]:
    text=read('case-06/source/vector/'+renamed)
    text=text.replace('"nacre_plan.h"','"exp_tiling.h"').replace('"../op_kernel/nacre_stage.asc"','"../op_kernel/exp_kernel.asc"')
    assert rename_cpp(text,{v:k for k,v in delta['changes']['vector'].items()})==read('case-01/source/'+original)
assert rename_cpp(read('case-06/source/cube/mica.asc'),{v:k for k,v in delta['changes']['cube'].items()})==cm
contract_hashes={sha(PUB/f'case-{i:02}/workload/sdk-contract.md') for i in range(1,7)}
assert len(contract_hashes)==1 and sha(PUB/'shared/SDK_CONTRACT.md') in contract_hashes
passed('C06_rename_equivalence_and_common_contract',{'vector_files_restored_exactly':3,'cube_file_restored_exactly':True,'common_contract_sha256':next(iter(contract_hashes))})

summary={'schema':'aprof.code-understanding-cpu-checks/v1','status':'pass','checks_passed':len(checks),'checks':checks,
    'ordinary_cpp_header_build':{'command':command,'returncode':built.returncode,'execution':execution,'compiler':compiler},
    'not_run':['NPU hardware','Ascend SDK build','device compiler','hardware simulator','evaluation agents'],
    'reads_gold':False}
(RESULT/'cpu_checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'pass','checks_passed':len(checks),'results':str(RESULT/'cpu_checks.json'),'tiling_probe_execution':execution},ensure_ascii=False))
