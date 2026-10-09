#pragma once
#include "adapter_common.h"
#include <map>
#include <cstring>
namespace level2 {
struct State: shared_context::State {
 std::vector<void*> hosts;
 std::map<const void*,size_t> origin;
 std::vector<std::function<void()>> steps;
 std::function<void(std::ostream&)> exporter;
 uint64_t kernel_count=0;
 bool bundled=false;
 explicit State(void *stream):shared_context::State(stream){}
 ~State(){for(auto p:hosts)aclrtFreeHost(p);}
 uint8_t *mapped(const void *p){if(!p)return nullptr;auto i=origin.find(p);if(i==origin.end())throw std::runtime_error("unregistered device pointer");return ptr(i->second);}
 void mark_output(const void *p){memory.at(origin.at(p)).kind="output";}
 void kernel(std::function<void()> f){steps.push_back(std::move(f));++kernel_count;}
};
inline thread_local State *current=nullptr;
inline thread_local std::ostream *export_stream=nullptr;
inline aclError init(const char*){return ACL_SUCCESS;}
inline aclError finalize(){return ACL_SUCCESS;}
inline aclError set_device(int){return ACL_SUCCESS;}
inline aclError reset_device(int){return ACL_SUCCESS;}
inline aclError create_stream(aclrtStream *stream){*stream=current->stream;return ACL_SUCCESS;}
inline aclError destroy_stream(aclrtStream){return ACL_SUCCESS;}
inline aclError allocate(void **p,size_t bytes,aclrtMemMallocPolicy policy){auto rc=aclrtMalloc(p,bytes,policy);if(rc==ACL_SUCCESS){current->origin[*p]=current->memory.size();current->memory.push_back({*p,bytes,"workspace"});}return rc;}
inline aclError allocate_host(void **p,size_t bytes){auto rc=aclrtMallocHost(p,bytes);if(rc==ACL_SUCCESS)current->hosts.push_back(*p);return rc;}
inline aclError free_device(void*){return ACL_SUCCESS;}
inline aclError free_host(void*){return ACL_SUCCESS;}
// Required per-call device initialization uses the runner stream. The original
// synchronous host APIs are normalized to asynchronous device tasks followed by
// explicit synchronization so profiler task accounting includes their cost.
inline aclError copy(void *dest,size_t capacity,const void *src,size_t bytes,aclrtMemcpyKind kind){
 if(kind==ACL_MEMCPY_HOST_TO_DEVICE){current->memory.at(current->origin.at(dest)).kind="input";return aclrtMemcpy(dest,capacity,src,bytes,kind);}
 if(kind!=ACL_MEMCPY_DEVICE_TO_DEVICE)throw std::runtime_error("unreviewed preparation copy kind");
 auto *s=current;s->steps.push_back([=]{shared_context::check(aclrtMemcpyAsync(s->mapped(dest),capacity,s->mapped(src),bytes,kind,s->stream));shared_context::check(aclrtSynchronizeStream(s->stream));});return ACL_SUCCESS;
}
inline aclError zero(void *dest,size_t capacity,int value,size_t count){auto *s=current;s->steps.push_back([=]{shared_context::check(aclrtMemsetAsync(s->mapped(dest),capacity,value,count,s->stream));shared_context::check(aclrtSynchronizeStream(s->stream));});return ACL_SUCCESS;}
inline aclError synchronize(aclrtStream stream){auto *s=current;s->steps.push_back([=]{shared_context::check(aclrtSynchronizeStream(stream));});return ACL_SUCCESS;}
inline aclError export_copy(void *dest,size_t capacity,const void *src,size_t bytes,aclrtMemcpyKind kind){if(kind!=ACL_MEMCPY_DEVICE_TO_HOST)throw std::runtime_error("unreviewed export copy kind");return aclrtMemcpy(dest,capacity,current->mapped(src),bytes,kind);}
inline bool write_output(const std::string&,const void *data,size_t bytes){if(!export_stream)throw std::runtime_error("missing output stream");if(current->bundled){uint64_t length=bytes;unsigned char header[8];for(unsigned i=0;i<8;++i)header[i]=(length>>(8*i))&255;export_stream->write(reinterpret_cast<char*>(header),8);}export_stream->write(static_cast<const char*>(data),bytes);return bool(*export_stream);}
inline int launch(void *state){return shared_context::guarded([&]{auto*s=static_cast<State*>(state);for(auto &step:s->steps)step();});}
inline int export_output(void *state,const char *path){return shared_context::guarded([&]{auto*s=static_cast<State*>(state);std::ofstream out(path,std::ios::binary);if(!out)throw std::runtime_error("output open failed");current=s;export_stream=&out;try{s->exporter(out);}catch(...){current=nullptr;export_stream=nullptr;throw;}current=nullptr;export_stream=nullptr;if(!out)throw std::runtime_error("output write failed");});}
inline void destroy(void *s){delete static_cast<State*>(s);}
inline uint64_t launch_count(void *s){return static_cast<State*>(s)->kernel_count;}
inline SCResource *resources(void *v,size_t *n){auto*s=static_cast<State*>(v);*n=s->memory.size();return s->memory.data();}
}
