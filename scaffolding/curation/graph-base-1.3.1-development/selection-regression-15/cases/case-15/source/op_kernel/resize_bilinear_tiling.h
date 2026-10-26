#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>
enum ResizeDType:uint32_t { RESIZE_FP16=0,RESIZE_FP32=1,RESIZE_BF16=2 };
struct ResizeBilinearTilingData {
 uint64_t n,c,inH,inW,outH,outW,inputSpatial,outputSpatial,outputNumel,blockLength;
 float inHf,inWf,outHf,outWf;
 uint32_t blockNum,dtype,alignCorners;
};
inline ResizeBilinearTilingData ComputeResizeBilinearTiling(const std::vector<uint64_t>&shape,uint64_t oh,uint64_t ow,uint32_t dtype,bool align,int64_t cores){
 if(shape.size()!=4||!oh||!ow)throw std::invalid_argument("expected non-empty x[N,C,H,W] and output size");for(auto v:shape)if(!v)throw std::invalid_argument("zero dimension");
 ResizeBilinearTilingData t{};t.n=shape[0];t.c=shape[1];t.inH=shape[2];t.inW=shape[3];t.outH=oh;t.outW=ow;t.inputSpatial=t.inH*t.inW;t.outputSpatial=oh*ow;t.outputNumel=t.n*t.c*t.outputSpatial;t.inHf=float(t.inH);t.inWf=float(t.inW);t.outHf=float(oh);t.outWf=float(ow);t.dtype=dtype;t.alignCorners=align;
 uint64_t a=dtype==RESIZE_FP32?16:32,avail=uint64_t(std::max<int64_t>(1,cores)),useful=std::max<uint64_t>(1,(t.outputNumel+a-1)/a);t.blockNum=uint32_t(std::min(avail,useful));uint64_t raw=(t.outputNumel+t.blockNum-1)/t.blockNum;t.blockLength=((raw+a-1)/a)*a;return t;
}
