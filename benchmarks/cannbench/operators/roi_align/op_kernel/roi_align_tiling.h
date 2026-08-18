#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>
enum RoiAlignDType:uint32_t{ROI_ALIGN_FP16=0,ROI_ALIGN_FP32=1};
struct RoiAlignTilingData{
 uint64_t batch,channels,height,width,numRois,outH,outW,outputNumel,blockLength;
 float spatialScale,outHFloat,outWFloat;
 uint32_t samplingRatio,aligned,dtype,blockNum;
};
inline RoiAlignTilingData ComputeRoiAlignTiling(const std::vector<uint64_t>&x,const std::vector<uint64_t>&boxes,
 uint64_t outH,uint64_t outW,float scale,int sampling,bool aligned,uint32_t dtype,int64_t cores){
 if(x.size()!=4||boxes.size()!=2||boxes[1]!=5)throw std::invalid_argument("expected x[B,C,H,W] and boxes[N,5]");
 for(auto v:x)if(!v)throw std::invalid_argument("zero input dimension");
 if(!boxes[0]||!outH||!outW||scale<=0||sampling<0)throw std::invalid_argument("invalid ROIAlign parameter");
 RoiAlignTilingData t{};t.batch=x[0];t.channels=x[1];t.height=x[2];t.width=x[3];t.numRois=boxes[0];
 t.outH=outH;t.outW=outW;t.outputNumel=boxes[0]*x[1]*outH*outW;t.spatialScale=scale;
 t.outHFloat=static_cast<float>(outH);t.outWFloat=static_cast<float>(outW);
 t.samplingRatio=static_cast<uint32_t>(sampling);t.aligned=aligned?1U:0U;t.dtype=dtype;
 const uint64_t available=static_cast<uint64_t>(std::max<int64_t>(1,cores));
 const uint64_t alignment=dtype==ROI_ALIGN_FP16?32:16;
 const uint64_t useful=std::max<uint64_t>(1,(t.outputNumel+4095)/4096);
 t.blockNum=static_cast<uint32_t>(std::min(available,useful));
 const uint64_t raw=(t.outputNumel+t.blockNum-1)/t.blockNum;
 t.blockLength=((raw+alignment-1)/alignment)*alignment;
 return t;
}
