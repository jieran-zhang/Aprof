#include "abi.h"
#include "acl/acl.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>

namespace {
void check(aclError rc) {if(rc!=ACL_SUCCESS) throw std::runtime_error("ACL error "+std::to_string(rc));}
std::string quote(const std::string &s) {std::ostringstream o;o<<'"';for(unsigned char c:s){if(c=='"'||c=='\\')o<<'\\'<<c;else if(c<32)o<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c);else o<<c;}o<<'"';return o.str();}
std::string ptr(void *p) {std::ostringstream o;o<<p;return quote(o.str());}
std::vector<std::string> split(const std::string &s,char delimiter) {std::vector<std::string> v;std::stringstream in(s);std::string item;while(std::getline(in,item,delimiter))v.push_back(item);return v;}
double now() {return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
struct Role {
 void *module=nullptr,*state=nullptr;const SCAPI *api=nullptr;
 ~Role(){clear();if(module)dlclose(module);}
 void clear(){if(state){api->destroy(state);state=nullptr;}}
 void call(int status) {if(status)throw std::runtime_error(api->error());}
 void load(const std::string &path,char expected) {
  module=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);if(!module)throw std::runtime_error(dlerror());
  auto get=reinterpret_cast<SCGetAPI>(dlsym(module,"sc_get_api"));if(!get)throw std::runtime_error("missing sc_get_api");api=get();
  if(!api||api->abi_version!=SC_ABI_VERSION||!api->identity||!api->prepare||!api->launch||!api->export_output||!api->destroy||!api->launch_count||!api->resources||!api->error)throw std::runtime_error("invalid role ABI");
  auto id=api->identity();if(id->abi_version!=SC_ABI_VERSION||std::string(id->role)!=std::string(1,expected))throw std::runtime_error("role identity mismatch");
 }
};
struct Events {
 aclrtEvent start=nullptr,end=nullptr;
 Events(){check(aclrtCreateEvent(&start));try {check(aclrtCreateEvent(&end));}catch(...){aclrtDestroyEvent(start);throw;}}
 ~Events(){if(end)aclrtDestroyEvent(end);if(start)aclrtDestroyEvent(start);}
 float measure(Role &r,aclrtStream stream) {check(aclrtRecordEvent(start,stream));for(int i=0;i<100;++i)r.call(r.api->launch(r.state));check(aclrtRecordEvent(end,stream));check(aclrtSynchronizeEvent(end));float ms=0;check(aclrtEventElapsedTime(&ms,start,end));if(!std::isfinite(ms)||ms<=0)throw std::runtime_error("nonpositive/nonfinite ACL interval");return ms;}
};
std::vector<SCResource*> all_buffers(Role &r) {
 size_t n;auto resources=r.api->resources(r.state,&n);std::vector<SCResource*> out;
 for(size_t i=0;i<n;++i)out.push_back(resources+i);
 return out;
}
std::vector<SCResource*> mutable_buffers(Role &r) {
 size_t n;auto resources=r.api->resources(r.state,&n);std::vector<SCResource*> out;
 for(size_t i=0;i<n;++i)if(std::string(resources[i].kind)=="output"||std::string(resources[i].kind)=="workspace")out.push_back(resources+i);
 return out;
}
void compatible(const std::vector<SCResource*> &a,const std::vector<SCResource*> &b) {
 if(a.size()!=b.size())throw std::runtime_error("buffer swap unsupported: different resource count");
 for(size_t i=0;i<a.size();++i)if(a[i]->bytes!=b[i]->bytes||std::string(a[i]->kind)!=b[i]->kind)throw std::runtime_error("buffer swap unsupported: incompatible resource layout");
}
void swap_buffers(Role &a,Role &b) {
 auto aa=mutable_buffers(a),bb=mutable_buffers(b);compatible(aa,bb);
 for(size_t i=0;i<aa.size();++i)std::swap(aa[i]->pointer,bb[i]->pointer);
}
// Every physical slot survives independent case re-preparation. Inputs/tilings
// stay with their logical role; only output/workspace slot assignments cross.
// A detached slot belongs to this pool; attached slots belong to the role state.
struct BufferPool {
 std::vector<SCResource> slots[2];
 ~BufferPool(){for(auto &v:slots)for(auto &r:v)if(r.pointer)aclrtFree(r.pointer);}
 void detach(Role (&roles)[2]) {
  for(int role=0;role<2;++role){slots[role].clear();for(auto r:all_buffers(roles[role])){slots[role].push_back(*r);r->pointer=nullptr;}}
 }
 void attach(Role (&roles)[2]) {
  if(slots[0].empty())return;
  // Check every layout before transferring ownership.
  for(int role=0;role<2;++role){auto target=all_buffers(roles[role]);std::vector<SCResource*> saved;for(auto &r:slots[role])saved.push_back(&r);compatible(target,saved);}
  for(int role=0;role<2;++role){auto target=all_buffers(roles[role]);for(size_t i=0;i<target.size();++i){
    // Transfer newly prepared immutable content outside the timed interval.
    const std::string kind=target[i]->kind;
    if(kind=="input"||kind=="tiling")check(aclrtMemcpy(slots[role][i].pointer,slots[role][i].bytes,target[i]->pointer,target[i]->bytes,ACL_MEMCPY_DEVICE_TO_DEVICE));
    check(aclrtFree(target[i]->pointer));target[i]->pointer=slots[role][i].pointer;slots[role][i].pointer=nullptr;}slots[role].clear();}
 }
};
bool safe_id(const std::string &s){return !s.empty()&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isalnum(c)||c=='_'||c=='-';});}
}
int main(int argc,char **argv) {
 std::map<std::string,std::string> args;
 for(int i=1;i<argc;i+=2){if(i+1>=argc){std::cerr<<"expected --name value\n";return 2;}if(!args.emplace(argv[i],argv[i+1]).second){std::cerr<<"duplicate option\n";return 2;}}
 auto arg=[&](std::string name,std::string fallback=""){auto i=args.find(name);return i==args.end()?fallback:i->second;};
 aclrtContext context=nullptr;aclrtStream stream=nullptr;bool initialized=false,context_destroyed=false,stream_destroyed=false;int status=1;std::ofstream journal;
 std::string session=arg("--session-id");
 try {
  const std::set<std::string> allowed={"--role-a","--role-b","--cases","--output-dir","--session-id","--load-order","--buffer-configs","--first-order","--device","--verify-handshake"};
  for(auto &a:args)if(!allowed.count(a.first))throw std::runtime_error("unknown option "+a.first);
  for(auto n:{"--role-a","--role-b","--cases","--output-dir","--session-id"})if(arg(n).empty())throw std::runtime_error(std::string("missing ")+n);
  if(!safe_id(session))throw std::runtime_error("invalid session ID");
  auto load_order=arg("--load-order","AB"),first_order=arg("--first-order","AB");
  if((load_order!="AB"&&load_order!="BA")||(first_order!="AB"&&first_order!="BA"))throw std::runtime_error("invalid role order");
  auto configs=split(arg("--buffer-configs","normal"),',');std::set<std::string> unique_configs;
  for(auto &c:configs)if((c!="normal"&&c!="swapped")||!unique_configs.insert(c).second)throw std::runtime_error("invalid buffer configuration");
  if(configs.empty())throw std::runtime_error("empty buffer configurations");
  std::ifstream casefile(arg("--cases"));if(!casefile)throw std::runtime_error("cannot open cases TSV");
  std::vector<std::vector<std::string>> cases;std::set<std::string> ids;std::string line;
  while(std::getline(casefile,line)){if(line.empty())continue;auto c=split(line,'\t');if(c.size()<3||!safe_id(c[0])||!ids.insert(c[0]).second)throw std::runtime_error("invalid/duplicate case row");cases.push_back(c);}
  if(cases.empty())throw std::runtime_error("no cases");
  const std::filesystem::path output=arg("--output-dir");std::filesystem::create_directories(output);
  if(std::filesystem::exists(output/"journal.jsonl"))throw std::runtime_error("refuse overwrite journal");
  journal.open(output/"journal.jsonl");if(!journal)throw std::runtime_error("cannot open journal");journal<<std::setprecision(17);
  auto emit=[&](const std::string &body){journal<<"{\"session_id\":"<<quote(session)<<","<<body<<"}\n";journal.flush();if(!journal)throw std::runtime_error("journal write failed");};
  int device=std::stoi(arg("--device","0"));
  char host[256]={};gethostname(host,sizeof(host)-1);
  emit("\"type\":\"process_start\",\"pid\":"+std::to_string(getpid())+",\"host\":"+quote(host)+",\"started_at\":"+std::to_string(now()));
  check(aclInit(nullptr));initialized=true;
  check(aclrtCreateContext(&context,device));check(aclrtSetCurrentContext(context));check(aclrtCreateStream(&stream));
  int64_t cores=0;check(aclrtGetDeviceInfo(device,ACL_DEV_ATTR_VECTOR_CORE_NUM,&cores));if(cores<=0)throw std::runtime_error("invalid vector core count");
  emit("\"type\":\"session_start\",\"pid\":"+std::to_string(getpid())+",\"host\":"+quote(host)+",\"started_at\":"+std::to_string(now())+",\"load_order\":"+quote(load_order)+",\"first_order\":"+quote(first_order)+",\"context_id\":"+ptr(context)+",\"stream_id\":"+ptr(stream)+",\"device\":"+std::to_string(device)+",\"vector_cores\":"+std::to_string(cores));
  {
   Role roles[2];
   for(char role:load_order){auto &r=roles[role-'A'];r.load(arg(role=='A'?"--role-a":"--role-b"),role);auto id=r.api->identity();emit("\"type\":\"module\",\"role\":"+quote(id->role)+",\"path\":"+quote(arg(role=='A'?"--role-a":"--role-b"))+",\"source_sha256\":"+quote(id->source_sha256)+",\"operator_name\":"+quote(id->operator_name)+",\"kernel_symbols\":"+quote(id->kernel_symbols)+",\"entry_address\":"+ptr(reinterpret_cast<void *>(r.api->launch)));}
   if(std::string(roles[0].api->identity()->operator_name)!=roles[1].api->identity()->operator_name||std::string(roles[0].api->identity()->kernel_symbols)==roles[1].api->identity()->kernel_symbols||roles[0].api->launch==roles[1].api->launch)throw std::runtime_error("role entries not distinct or different operators");
   Events events;
   for(size_t case_index=0;case_index<cases.size();++case_index){auto &c=cases[case_index];std::vector<char*> av;for(auto &v:c)av.push_back(v.data());
    BufferPool pool;
    for(size_t config_index=0;config_index<configs.size();++config_index){auto &config=configs[config_index];
     for(auto &r:roles){r.clear();r.call(r.api->prepare(av.size(),av.data(),cores,stream,&r.state));if(!r.state||!r.api->launch_count(r.state))throw std::runtime_error("empty prepared operator");}
     pool.attach(roles);
     if(config=="swapped")swap_buffers(roles[0],roles[1]);
     std::string common="\"case_id\":"+quote(c[0])+",\"buffer_config\":"+quote(config);
     emit("\"type\":\"case_start\","+common+",\"case_index\":"+std::to_string(case_index)+",\"warmup_per_role\":10,\"pairs\":30,\"repeat\":100");
     for(int i=0;i<2;++i){size_t n;auto resources=roles[i].api->resources(roles[i].state,&n);std::string list="[";for(size_t j=0;j<n;++j){if(j)list+=",";list+="{\"index\":"+std::to_string(j)+",\"kind\":"+quote(resources[j].kind)+",\"bytes\":"+std::to_string(resources[j].bytes)+",\"address\":"+ptr(resources[j].pointer)+"}";}list+="]";emit("\"type\":\"resources\","+common+",\"role\":"+quote(std::string(1,'A'+i))+",\"allocation_order\":\"AB\",\"input_policy\":\"separate_identical_files\",\"buffers\":"+list);}
     for(int w=0;w<10;++w)for(auto &r:roles)r.call(r.api->launch(r.state));check(aclrtSynchronizeStream(stream));
     emit("\"type\":\"warmup_complete\","+common+",\"calls_per_role\":10");
     for(int pair=0;pair<30;++pair){std::string order=(pair%2==0)?first_order:(first_order=="AB"?"BA":"AB");
      for(int position=0;position<2;++position){char role=order[position];auto &r=roles[role-'A'];double started=now();float ms=events.measure(r,stream);std::ostringstream row;row<<std::setprecision(17)<<"\"type\":\"sample\","<<common<<",\"sample_id\":"<<quote(session+"/"+c[0]+"/"+config+"/"+std::to_string(pair)+"/"+role)<<",\"pair_id\":"<<pair<<",\"role\":"<<quote(std::string(1,role))<<",\"order\":"<<quote(order)<<",\"position\":"<<position<<",\"started_at\":"<<started<<",\"ended_at\":"<<now()<<",\"raw_duration\":"<<ms<<",\"raw_unit\":\"ms\",\"to_ns\":1000000,\"repeat\":100,\"ns_per_call\":"<<double(ms)*10000<<",\"launches_per_call\":"<<r.api->launch_count(r.state)<<",\"context_id\":"<<ptr(context)<<",\"stream_id\":"<<ptr(stream);emit(row.str());}
     }
     for(int i=0;i<2;++i){auto path=output/(c[0]+"_"+config+"_"+std::string(1,'A'+i)+".bin");roles[i].call(roles[i].api->export_output(roles[i].state,path.c_str()));emit("\"type\":\"output\","+common+",\"role\":"+quote(std::string(1,'A'+i))+",\"path\":"+quote(path.string())+",\"validation_scope\":\"final_call_of_final_formal_sample\",\"validation_status\":\"pending_external_oracle\",\"complete_calls_since_prepare\":3010");}
     if(arg("--verify-handshake","no")=="yes") {
      std::cout<<"{\"type\":\"validation_required\","<<common<<",\"outputs\":{\"A\":"<<quote((output/(c[0]+"_"+config+"_A.bin")).string())<<",\"B\":"<<quote((output/(c[0]+"_"+config+"_B.bin")).string())<<"}}"<<std::endl;
      std::string ack;
      if(!std::getline(std::cin,ack)||ack!="ok")throw std::runtime_error("external oracle rejected or missing verification acknowledgement");
      emit("\"type\":\"outputs_verified\","+common+",\"validator\":\"external_oracle_ack\"");
     }
     if(config_index+1<configs.size()) {
      if(config=="swapped")swap_buffers(roles[0],roles[1]);
      pool.detach(roles);
     }
     for(auto &r:roles)r.clear();
    }
   }
  }
  check(aclrtDestroyStream(stream));stream=nullptr;stream_destroyed=true;check(aclrtDestroyContext(context));context=nullptr;context_destroyed=true;check(aclFinalize());initialized=false;status=0;
 } catch(const std::exception &e){std::cerr<<e.what()<<"\n";if(journal)journal<<"{\"type\":\"failure\",\"session_id\":"<<quote(session)<<",\"error\":"<<quote(e.what())<<"}\n";}
 if(stream)stream_destroyed=aclrtDestroyStream(stream)==ACL_SUCCESS;if(context)context_destroyed=aclrtDestroyContext(context)==ACL_SUCCESS;if(initialized)aclFinalize();
 if(journal)journal<<"{\"type\":\"session_end\",\"session_id\":"<<quote(session)<<",\"exit_code\":"<<status<<",\"ended_at\":"<<std::setprecision(17)<<now()<<",\"context_destroyed\":"<<(context_destroyed?"true":"false")<<",\"stream_destroyed\":"<<(stream_destroyed?"true":"false")<<"}\n";
 return status;
}
