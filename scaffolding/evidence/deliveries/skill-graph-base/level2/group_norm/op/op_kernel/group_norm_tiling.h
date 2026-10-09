#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>
#include <cstring>
#include <algorithm>
enum GroupNormDType:uint32_t{GN_FLOAT16=0,GN_FLOAT32=1,GN_BFLOAT16=2};
struct GroupNormTilingData{uint64_t totalLength,spatial,groupElements,groupCount;uint32_t N,C,numGroups,channelsPerGroup,blockNum,dtype,tileElements;float epsilon,invGroupElements;uint64_t exactGroupsPerBlock,epsilonBits;};
inline GroupNormTilingData ComputeGroupNormTiling(const std::vector<uint64_t>&s,uint32_t groups,uint32_t dtype,float eps){
 if(s.size()<2||s.size()>8||groups==0||s[1]%groups||!(eps>0))throw std::invalid_argument("invalid group norm shape/attrs");GroupNormTilingData t{};t.N=s[0];t.C=s[1];t.numGroups=groups;t.channelsPerGroup=t.C/groups;t.spatial=1;for(size_t i=2;i<s.size();++i)t.spatial*=s[i];t.groupElements=static_cast<uint64_t>(t.channelsPerGroup)*t.spatial;t.groupCount=static_cast<uint64_t>(t.N)*groups;t.totalLength=t.groupCount*t.groupElements;t.dtype=dtype;t.epsilon=eps;t.invGroupElements=1.0f/static_cast<float>(t.groupElements);t.blockNum=static_cast<uint32_t>(t.groupCount<32?t.groupCount:32);t.tileElements=4096;return t;}

// Only the exact small-FP32 entry uses these extra fields. Baseline fields and
// schedule for every other route retain the original Compute function values.
inline uint64_t GnExactGcd(uint64_t a,uint64_t b){while(b){uint64_t r=a%b;a=b;b=r;}return a;}
inline uint64_t SelectGroupNormKey(const GroupNormTilingData&t){
 if(t.dtype==GN_FLOAT32&&t.groupElements>=1&&t.groupElements<=128)return 33;
 if(t.groupElements>128&&t.groupElements<=4096)return 30;
 if(t.groupElements>4096)return t.groupCount>=48?31:32;
 return 0;
}
inline void ConfigureExactGroupNorm(GroupNormTilingData&t,double epsilon){
 if(t.N==0||t.C==0||t.groupElements==0||t.groupCount==0)throw std::invalid_argument("empty group norm input unsupported");
 std::memcpy(&t.epsilonBits,&epsilon,8);
 if(SelectGroupNormKey(t)!=33)return;
 const uint64_t alignment=64/GnExactGcd(t.groupElements*4,64);
 const uint64_t cores=std::min<uint64_t>(t.groupCount,32),average=(t.groupCount+cores-1)/cores;
 t.exactGroupsPerBlock=((average+alignment-1)/alignment)*alignment;
 t.blockNum=static_cast<uint32_t>((t.groupCount+t.exactGroupsPerBlock-1)/t.exactGroupsPerBlock);
}
