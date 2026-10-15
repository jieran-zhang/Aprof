#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>
enum AdaptivePoolDType:uint32_t { ADAPTIVE_POOL_FP16=0,ADAPTIVE_POOL_FP32=1,ADAPTIVE_POOL_BF16=2 };
struct AdaptiveAvgPool3DTilingData {
 uint64_t n,c,inD,inH,inW,outD,outH,outW,inputSpatial,outputSpatial,outputNumel,blockLength;
 uint32_t blockNum,dtype;
};
inline AdaptiveAvgPool3DTilingData ComputeAdaptiveAvgPool3DTiling(const std::vector<uint64_t>&s,const std::vector<uint64_t>&o,uint32_t dtype,int64_t cores){
 if(s.size()!=5||o.size()!=3)throw std::invalid_argument("expected x[N,C,D,H,W] and three output dimensions");for(auto v:s)if(!v)throw std::invalid_argument("zero input dimension");for(auto v:o)if(!v)throw std::invalid_argument("zero output dimension");
 AdaptiveAvgPool3DTilingData t{};t.n=s[0];t.c=s[1];t.inD=s[2];t.inH=s[3];t.inW=s[4];t.outD=o[0];t.outH=o[1];t.outW=o[2];t.inputSpatial=t.inD*t.inH*t.inW;t.outputSpatial=t.outD*t.outH*t.outW;t.outputNumel=t.n*t.c*t.outputSpatial;t.dtype=dtype;
 uint64_t align=dtype==ADAPTIVE_POOL_FP32?16:32,avail=uint64_t(std::max<int64_t>(1,cores)),useful=std::max<uint64_t>(1,(t.outputNumel+align-1)/align);t.blockNum=uint32_t(std::min(avail,useful));uint64_t raw=(t.outputNumel+t.blockNum-1)/t.blockNum;t.blockLength=((raw+align-1)/align)*align;return t;
}
