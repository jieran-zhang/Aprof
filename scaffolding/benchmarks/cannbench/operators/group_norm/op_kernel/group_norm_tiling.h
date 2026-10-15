#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>
enum GroupNormDType:uint32_t{GN_FLOAT16=0,GN_FLOAT32=1,GN_BFLOAT16=2};
struct GroupNormTilingData{uint64_t totalLength,spatial,groupElements,groupCount;uint32_t N,C,numGroups,channelsPerGroup,blockNum,dtype,tileElements;float epsilon,invGroupElements;};
inline GroupNormTilingData ComputeGroupNormTiling(const std::vector<uint64_t>&s,uint32_t groups,uint32_t dtype,float eps){
 if(s.size()<2||s.size()>8||groups==0||s[1]%groups||!(eps>0))throw std::invalid_argument("invalid group norm shape/attrs");GroupNormTilingData t{};t.N=s[0];t.C=s[1];t.numGroups=groups;t.channelsPerGroup=t.C/groups;t.spatial=1;for(size_t i=2;i<s.size();++i)t.spatial*=s[i];t.groupElements=static_cast<uint64_t>(t.channelsPerGroup)*t.spatial;t.groupCount=static_cast<uint64_t>(t.N)*groups;t.totalLength=t.groupCount*t.groupElements;t.dtype=dtype;t.epsilon=eps;t.invGroupElements=1.0f/static_cast<float>(t.groupElements);t.blockNum=static_cast<uint32_t>(t.groupCount<32?t.groupCount:32);t.tileElements=4096;return t;}
