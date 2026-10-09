// Independent diagnostic runner: never used for paired timing or gate decisions.
#include "abi.h"
#include "acl/acl.h"
#include <dlfcn.h>
#include <cstdlib>
#include <unistd.h>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
void check(aclError code){if(code!=ACL_SUCCESS)throw std::runtime_error("ACL error "+std::to_string(code));}
std::string quote(const std::string& value){std::ostringstream out;out<<'"';for(unsigned char c:value){if(c=='"'||c=='\\')out<<'\\'<<c;else if(c<32)out<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c);else out<<c;}out<<'"';return out.str();}
std::string pointer(void* p){std::ostringstream out;out<<p;return quote(out.str());}
}
int main(int argc,char** argv){
 std::map<std::string,std::string> args;
 const std::set<std::string> allowed={"--mode","--role-library","--role","--expected-source","--expected-kernels","--launches-per-call","--case-args","--output","--journal","--device"};
 for(int i=1;i<argc;i+=2){if(i+1>=argc||!allowed.count(argv[i])||!args.emplace(argv[i],argv[i+1]).second){std::cerr<<"invalid option\n";return 2;}}
 for(const auto& name:allowed)if(!args.count(name)){std::cerr<<"missing "<<name<<'\n';return 2;}
 aclrtContext context=nullptr;aclrtStream stream=nullptr;bool initialized=false;void* module=nullptr;void* state=nullptr;const SCAPI* api=nullptr;
 int status=1;unsigned warmups=0,profile_calls=0;uint64_t launches=0;std::string error,context_id,stream_id;std::ofstream journal;
 try{
  if(args["--mode"]!="profile"&&args["--mode"]!="correctness")throw std::runtime_error("invalid mode");
  if(args["--role"]!="A"&&args["--role"]!="B")throw std::runtime_error("invalid role");
  std::ifstream existing(args["--journal"]);if(existing.good())throw std::runtime_error("refuse overwrite journal");
  journal.open(args["--journal"]);if(!journal)throw std::runtime_error("cannot create journal");
  std::ifstream input(args["--case-args"]);std::string line,extra;if(!std::getline(input,line)||std::getline(input,extra))throw std::runtime_error("expected exactly one case TSV row");
  std::vector<std::string> tokens;std::stringstream row(line);std::string token;while(std::getline(row,token,'\t'))tokens.push_back(token);
  if(tokens.size()<3)throw std::runtime_error("empty case arguments");std::vector<char*> av;for(auto& t:tokens)av.push_back(t.data());
  check(aclInit(nullptr));initialized=true;check(aclrtCreateContext(&context,std::stoi(args["--device"])));check(aclrtSetCurrentContext(context));check(aclrtCreateStream(&stream));context_id=pointer(context);stream_id=pointer(stream);
  module=dlopen(args["--role-library"].c_str(),RTLD_NOW|RTLD_LOCAL);if(!module)throw std::runtime_error(dlerror());
  auto get=reinterpret_cast<SCGetAPI>(dlsym(module,"sc_get_api"));if(!get)throw std::runtime_error("missing role ABI");api=get();
  if(!api||api->abi_version!=SC_ABI_VERSION||!api->identity||!api->prepare||!api->launch||!api->export_output||!api->destroy||!api->launch_count||!api->error)throw std::runtime_error("invalid role ABI");
  const auto* id=api->identity();if(!id||id->abi_version!=SC_ABI_VERSION||!id->role||!id->source_sha256||!id->kernel_symbols||id->role!=args["--role"]||id->source_sha256!=args["--expected-source"]||id->kernel_symbols!=args["--expected-kernels"])throw std::runtime_error("role identity mismatch");
  auto call=[&](int rc){if(rc)throw std::runtime_error(api->error());};
  int64_t cores=0;check(aclrtGetDeviceInfo(std::stoi(args["--device"]),ACL_DEV_ATTR_VECTOR_CORE_NUM,&cores));if(cores<=0)throw std::runtime_error("invalid vector cores");
  call(api->prepare(static_cast<int>(av.size()),av.data(),cores,stream,&state));if(!state)throw std::runtime_error("empty prepared state");launches=api->launch_count(state);
  if(!launches||launches!=std::stoull(args["--launches-per-call"]))throw std::runtime_error("complete launch count mismatch");
  // Preparation, H2D, and output export are outside the captured operator window.
  const unsigned warmup_target=args["--mode"]=="profile"?10:0;
  const unsigned call_target=args["--mode"]=="profile"?5:1;
  for(unsigned i=0;i<warmup_target;++i){call(api->launch(state));++warmups;}check(aclrtSynchronizeStream(stream));
  for(unsigned i=0;i<call_target;++i){call(api->launch(state));++profile_calls;}check(aclrtSynchronizeStream(stream));
  call(api->export_output(state,args["--output"].c_str()));status=0;
 }catch(const std::exception& e){error=e.what();std::cerr<<error<<'\n';}
 if(state&&api)api->destroy(state);if(module)dlclose(module);
 bool stream_destroyed=!stream||aclrtDestroyStream(stream)==ACL_SUCCESS;
 bool context_destroyed=!context||aclrtDestroyContext(context)==ACL_SUCCESS;
 bool finalized=!initialized||aclFinalize()==ACL_SUCCESS;
 if(!stream_destroyed||!context_destroyed||!finalized){status=1;error+=" resource cleanup failed";}
 char host[256]={};gethostname(host,sizeof(host)-1);const char* physical=std::getenv("ASCEND_RT_VISIBLE_DEVICES");
 if(journal){journal<<"{\"version\":\"shared_context_profile_native_v1\",\"pid\":"<<getpid()<<",\"host\":"<<quote(host)<<",\"physical_device\":"<<quote(physical?physical:"")<<",\"logical_device\":"<<quote(args["--device"])<<",\"mode\":"<<quote(args["--mode"])<<",\"role\":"<<quote(args["--role"])<<",\"source_sha256\":"<<quote(args["--expected-source"])<<",\"kernel_symbols\":"<<quote(args["--expected-kernels"])<<",\"context_id\":"<<(context_id.empty()?"null":context_id)<<",\"stream_id\":"<<(stream_id.empty()?"null":stream_id)<<",\"warmup_complete_calls\":"<<warmups<<",\"profile_complete_calls\":"<<profile_calls<<",\"launches_per_call\":"<<launches<<",\"output\":"<<quote(args["--output"])<<",\"validation_scope\":"<<quote(args["--mode"]=="profile"?"final_call_of_five_profile_iterations":"single_complete_correctness_call")<<",\"stream_destroyed\":"<<(stream_destroyed?"true":"false")<<",\"context_destroyed\":"<<(context_destroyed?"true":"false")<<",\"finalized\":"<<(finalized?"true":"false")<<",\"exit_code\":"<<status<<",\"error\":"<<quote(error)<<"}\n";journal.flush();if(!journal)return 1;}
 return status;
}
