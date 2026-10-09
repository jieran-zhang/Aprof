#pragma once
#include "abi.h"
#include <fstream>
#include <functional>
#include <memory>
#include <sstream>
#include <vector>
namespace shared_context {
inline void check(aclError rc) { if(rc != ACL_SUCCESS) throw std::runtime_error("ACL error " + std::to_string(rc)); }
struct State {
 void *stream;
 std::vector<SCResource> memory;
 std::vector<std::pair<size_t,size_t>> outputs;
 std::vector<std::function<void()>> launches;
 explicit State(void *s):stream(s) {}
 ~State() { for(auto &r:memory) if(r.pointer) aclrtFree(r.pointer); }
 size_t alloc(size_t bytes,const char *kind) {
  if(!bytes) throw std::runtime_error("zero size resource");
  void *p=nullptr; check(aclrtMalloc(&p,bytes,ACL_MEM_MALLOC_HUGE_FIRST));
  memory.push_back({p,bytes,kind}); return memory.size()-1;
 }
 uint8_t *ptr(size_t i) { return static_cast<uint8_t *>(memory.at(i).pointer); }
 size_t input(std::ifstream &f,size_t n) {
  std::vector<uint8_t> h(n); if(!f.read(reinterpret_cast<char *>(h.data()),n)) throw std::runtime_error("truncated input");
  size_t i=alloc(n,"input"); check(aclrtMemcpy(ptr(i),n,h.data(),n,ACL_MEMCPY_HOST_TO_DEVICE)); return i;
 }
 size_t input(const std::string &path,size_t n) { std::ifstream f(path,std::ios::binary); auto i=input(f,n); if(f.peek()!=EOF) throw std::runtime_error("input length mismatch"); return i; }
 template<class T> size_t tiling(const T &t) { size_t i=alloc(sizeof(t),"tiling"); check(aclrtMemcpy(ptr(i),sizeof(t),&t,sizeof(t),ACL_MEMCPY_HOST_TO_DEVICE)); return i; }
 size_t output(size_t n,size_t allocation=0) { size_t i=alloc(allocation?allocation:n,"output"); outputs.push_back({i,n}); return i; }
};
inline thread_local std::string last_error;
template<class F> int guarded(F f) { try {f(); return 0;} catch(const std::exception &e) {last_error=e.what();return 1;} }
inline int launch(void *v) { return guarded([&]{for(auto &f:static_cast<State *>(v)->launches) f();}); }
inline int export_output(void *v,const char *path) {return guarded([&]{auto *s=static_cast<State *>(v); std::ofstream f(path,std::ios::binary); if(!f) throw std::runtime_error("output open failed"); for(auto o:s->outputs) {std::vector<uint8_t> h(o.second);check(aclrtMemcpy(h.data(),h.size(),s->ptr(o.first),h.size(),ACL_MEMCPY_DEVICE_TO_HOST));f.write(reinterpret_cast<char *>(h.data()),h.size());} if(!f) throw std::runtime_error("output write failed");});}
inline void destroy(void *v) {delete static_cast<State *>(v);}
inline uint64_t launch_count(void *v) {return static_cast<State *>(v)->launches.size();}
inline SCResource *resources(void *v,size_t *n) {auto *s=static_cast<State *>(v);*n=s->memory.size();return s->memory.data();}
inline const char *error() {return last_error.c_str();}
}
