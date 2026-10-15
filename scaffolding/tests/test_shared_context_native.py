"""CPU-only tests; fake ACL is linked, no accelerator runtime is loaded."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sc_build',ROOT/'scaffolding/collection/scripts/shared_context_build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

class AdapterTests(unittest.TestCase):
 def test_all_supported_generate_without_acl_lifecycle(self):
  for op in build.SUPPORTED:
   with self.subTest(op=op):
    src=ROOT/'scaffolding/benchmarks/cannbench/operators'/op
    code,ident,_=build.generate_adapter(src,op,'A',build.source_hash(src))
    self.assertIn('sc_A_',code)
    for forbidden in ('aclInit(', 'aclFinalize(', 'aclrtCreateContext(', 'aclrtCreateStream(', 'aclrtResetDevice('): self.assertNotIn(forbidden,code)
    self.assertIn('extern "C"',code)
 def test_supported_cmake_recipes_and_hash(self):
  for op in build.SUPPORTED:
   with self.subTest(op=op):
    source=ROOT/'scaffolding/benchmarks/cannbench/operators'/op
    result=build.validate_source_cmake(source,op,'dav-2201')
    self.assertEqual(result['cmake_sha256'],build.digest(source/'CMakeLists.txt'))
    self.assertEqual(result['npu_arch'],'dav-2201')
 def test_cmake_semantic_changes_fail_closed(self):
  original=(ROOT/'scaffolding/benchmarks/cannbench/operators/exp/CMakeLists.txt').read_text()
  mutations={
   'target_flags':original.replace('--npu-arch=dav-2201','--npu-arch=dav-2201 -O3'),
   'target_definitions':original+'\ntarget_compile_definitions(exp PRIVATE MODE=1)\n',
   'global_flags':original+'\nset(CMAKE_ASC_FLAGS "-O3")\n',
   'global_definitions':original+'\nadd_definitions(-DMODE=1)\n',
   'properties':original+'\nset_source_files_properties(op_host/exp.asc PROPERTIES COMPILE_OPTIONS "-O3")\n',
   'extra_include':original+'\ninclude(extra.cmake)\n',
   'arch':original.replace('dav-2201','dav-3510'),
  }
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)
   for name,text in mutations.items():
    with self.subTest(change=name):
     (source/'CMakeLists.txt').write_text(text)
     with self.assertRaisesRegex(ValueError,'unsupported source CMake'):
      build.validate_source_cmake(source,'exp','dav-2201')
   (source/'CMakeLists.txt').write_text(original.replace('dav-2201','dav-3510'))
   self.assertEqual(build.validate_source_cmake(source,'exp','dav-3510')['npu_arch'],'dav-3510')
 def test_generate_only_records_cmake_hash_and_rejects_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'source';shutil.copytree(ROOT/'scaffolding/benchmarks/cannbench/operators/exp',source)
   args=argparse.Namespace(operator='exp',source_a=str(source),source_b=str(source),output_dir=str(Path(d)/'build'),npu_arch='dav-2201',jobs=1,generate_only=True)
   manifest=build.build(args)
   for role in 'AB':self.assertEqual(manifest['roles'][role]['cmake_sha256'],build.digest(source/'CMakeLists.txt'))
   with (source/'CMakeLists.txt').open('a') as f:f.write('\ntarget_compile_definitions(exp PRIVATE MODE=1)\n')
   args.output_dir=str(Path(d)/'rejected')
   with self.assertRaisesRegex(ValueError,'unsupported source CMake'):build.build(args)
   self.assertFalse(Path(args.output_dir).exists())
 def test_chunk_is_from_actual_host(self):
  with tempfile.TemporaryDirectory() as d:
   target=Path(d)/'source';shutil.copytree(ROOT/'scaffolding/benchmarks/cannbench/operators/foreach_addcdiv_scalar',target)
   host=target/'op_host/foreach_addcdiv_scalar.asc'
   host.write_text(host.read_text().replace('8ULL * 1024 * 1024','3ULL * 1024 * 1024'))
   code,_,_=build.generate_adapter(target,'foreach_addcdiv_scalar','B','f'*64)
   self.assertIn('kChunkElements = 3ULL * 1024 * 1024',code)
   self.assertNotIn('8ULL * 1024 * 1024',code)
   self.assertIn('off+=kChunkElements',code)
 def test_norm_retains_both_launches(self):
  src=ROOT/'scaffolding/benchmarks/cannbench/operators/foreach_norm'
  code,_,_=build.generate_adapter(src,'foreach_norm','B','f'*64)
  self.assertEqual(code.count('s->launches.push_back'),2)
  self.assertIn('for(uint64_t n:lengths)',code)
  self.assertIn('<<<1, nullptr, stream>>>',code)

FAKE_ACL=r'''
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <fstream>
#include <string>
using aclError=int;using aclrtContext=void*;using aclrtStream=void*;using aclrtEvent=void*;
#define ACL_SUCCESS 0
#define ACL_DEV_ATTR_VECTOR_CORE_NUM 1
#define ACL_MEMCPY_DEVICE_TO_DEVICE 3
inline int aclrtMemcpy(void*d,size_t,const void*s,size_t n,int){memcpy(d,s,n);return 0;}
inline void trace(const char*s){std::ofstream f(getenv("FAKE_ACL_LOG"),std::ios::app);f<<s<<"\n";}
inline int aclrtFree(void*p){free(p);return 0;}
inline int aclInit(const char*){trace("init");return 0;}
inline int aclFinalize(){trace("finalize");return 0;}
inline int aclrtCreateContext(void**p,int){*p=(void*)1;trace("context_create");return 0;}
inline int aclrtSetCurrentContext(void*){return 0;}
inline int aclrtCreateStream(void**p){*p=(void*)2;trace("stream_create");return 0;}
inline int aclrtDestroyContext(void*){trace("context_destroy");return 0;}
inline int aclrtDestroyStream(void*){trace("stream_destroy");return 0;}
inline int aclrtGetDeviceInfo(int,int,int64_t*p){*p=8;return 0;}
inline int aclrtCreateEvent(void**p){*p=malloc(1);return 0;}
inline int aclrtDestroyEvent(void*p){free(p);return 0;}
inline int aclrtRecordEvent(void*,void*){return 0;}
inline int aclrtSynchronizeEvent(void*){return 0;}
inline int aclrtSynchronizeStream(void*){return 0;}
inline int aclrtEventElapsedTime(float*p,void*,void*){*p=.1f;return 0;}
'''
FAKE_ROLE=r'''
#include "abi.h"
#include <fstream>
#include <string>
#include <cstdlib>
struct S{unsigned calls=0;uint64_t prepared=0;SCResource mem[4];};
static uint64_t preparations=0;
static const SCIdentity id={1,ROLE,"fake","source",ROLE "_kernel"};
static const SCIdentity* identity(){return &id;}
static int prepare(int,char**,int64_t,void*,void**p){auto s=new S;s->prepared=++preparations;
 const char*kinds[]={"output","input","tiling","workspace"};for(int i=0;i<4;++i){s->mem[i]={malloc(8),8,kinds[i]};*(uint64_t*)s->mem[i].pointer=s->prepared+i;}*p=s;return 0;}
static int launch(void*p){auto s=(S*)p;
 if(*(uint64_t*)s->mem[1].pointer!=s->prepared+1||*(uint64_t*)s->mem[2].pointer!=s->prepared+2)return 1;
 ++s->calls;return 0;}
static int output(void*p,const char*path){std::ofstream f(path);f<<((S*)p)->calls;return 0;}
static void destroy(void*p){for(auto &r:((S*)p)->mem)free(r.pointer);delete (S*)p;}
static uint64_t count(void*){return 2;}
static SCResource*resources(void*p,size_t*n){*n=4;return ((S*)p)->mem;}
static const char*error(){return "fake error";}
extern "C" const SCAPI* sc_get_api(){static const SCAPI a={1,identity,prepare,launch,output,destroy,count,resources,error};return &a;}
'''

class NativeRunnerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('g++'):raise unittest.SkipTest('g++ missing')
  cls.temp=tempfile.TemporaryDirectory();cls.d=Path(cls.temp.name)
  (cls.d/'acl').mkdir();(cls.d/'acl/acl.h').write_text(FAKE_ACL)
  (cls.d/'role.cpp').write_text(FAKE_ROLE)
  harness=ROOT/'scaffolding/benchmarks/cannbench/harness/shared_context'
  subprocess.run(['g++','-std=c++17','-I'+str(cls.d),'-I'+str(harness),str(harness/'runner.cpp'),'-ldl','-o',str(cls.d/'runner')],check=True,capture_output=True)
  for role in 'AB':subprocess.run(['g++','-std=c++17','-shared','-fPIC','-Wl,-Bsymbolic','-I'+str(harness),'-DROLE="'+role+'"',str(cls.d/'role.cpp'),'-o',str(cls.d/f'{role}.so')],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def run_native(self,name,extra=(),ack=''):
  import os
  casefile=self.d/(name+'.tsv');casefile.write_text('c1\t--numel\t1\nc2\t--numel\t2\n')
  out=self.d/name
  cmd=[str(self.d/'runner'),'--role-a',str(self.d/'A.so'),'--role-b',str(self.d/'B.so'),'--cases',str(casefile),'--output-dir',str(out),'--session-id',name,*extra]
  log=self.d/(name+'.acl')
  result=subprocess.run(cmd,input=ack,text=True,capture_output=True,env={**os.environ,'FAKE_ACL_LOG':str(log)})
  rows=[json.loads(x) for x in (out/'journal.jsonl').read_text().splitlines()]
  return result,rows,log.read_text().splitlines(),out
 def test_one_lifecycle_all_cases_balanced_pairs_and_calls(self):
  result,rows,acl,out=self.run_native('success',['--buffer-configs','normal,swapped','--load-order','BA','--first-order','BA'])
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(acl,['init','context_create','stream_create','stream_destroy','context_destroy','finalize'])
  samples=[r for r in rows if r['type']=='sample']
  self.assertEqual(len(samples),240)
  self.assertEqual(len({r['sample_id'] for r in samples}),240)
  resources={(r['case_id'],r['buffer_config'],r['role']):r['buffers'][0]['address'] for r in rows if r['type']=='resources'}
  for case in ('c1','c2'):
   self.assertEqual(resources[case,'normal','A'],resources[case,'swapped','B'])
   self.assertEqual(resources[case,'normal','B'],resources[case,'swapped','A'])
   self.assertNotEqual(resources[case,'normal','A'],resources[case,'normal','B'])
  all_resources={(r['case_id'],r['buffer_config'],r['role'],b['kind']):b['address'] for r in rows if r['type']=='resources' for b in r['buffers']}
  for case in ('c1','c2'):
   for role in 'AB':
    for kind in ('input','tiling'):
     self.assertEqual(all_resources[case,'normal',role,kind],all_resources[case,'swapped',role,kind])
    other='B' if role=='A' else 'A'
    for kind in ('output','workspace'):
     self.assertEqual(all_resources[case,'normal',role,kind],all_resources[case,'swapped',other,kind])
  for case in ('c1','c2'):
   for config in ('normal','swapped'):
    subset=[r for r in samples if r['case_id']==case and r['buffer_config']==config]
    self.assertEqual([r['role'] for r in subset[:4]],list('BAAB'))
    for role in 'AB':
     self.assertEqual((out/f'{case}_{config}_{role}.bin').read_text(),'3010')
     self.assertEqual(sum(r['role']==role for r in subset),30)
     self.assertTrue(all(r['repeat']==100 and r['launches_per_call']==2 and r['raw_unit']=='ms' for r in subset))
 def test_swapped_first_retains_input_tiling_and_crosses_mutable_slots(self):
  result,rows,acl,out=self.run_native('swapped_first',['--buffer-configs','swapped,normal'])
  self.assertEqual(result.returncode,0,result.stderr)
  resources={(r['case_id'],r['buffer_config'],r['role'],b['kind']):b['address'] for r in rows if r['type']=='resources' for b in r['buffers']}
  for case in ('c1','c2'):
   for role in 'AB':
    for kind in ('input','tiling'):
     self.assertEqual(resources[case,'normal',role,kind],resources[case,'swapped',role,kind])
    for kind in ('output','workspace'):
     self.assertEqual(resources[case,'normal',role,kind],resources[case,'swapped','B' if role=='A' else 'A',kind])
 def test_handshake_rejection_preserves_failure_stops_next_case(self):
  result,rows,acl,out=self.run_native('reject',['--verify-handshake','yes'],'fail\n')
  self.assertEqual(result.returncode,1)
  self.assertEqual(json.loads(result.stdout)['type'],'validation_required')
  self.assertEqual({r['case_id'] for r in rows if r['type']=='sample'},{'c1'})
  self.assertEqual(rows[-1]['exit_code'],1)
  self.assertEqual(acl[-3:],['stream_destroy','context_destroy','finalize'])
 def test_handshake_success(self):
  result,rows,acl,out=self.run_native('ack',['--verify-handshake','yes'],'ok\nok\n')
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(sum(r['type']=='outputs_verified' for r in rows),2)

if __name__=='__main__':unittest.main()
