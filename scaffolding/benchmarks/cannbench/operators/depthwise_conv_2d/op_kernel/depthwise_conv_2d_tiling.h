#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum DepthwiseConvDType:uint32_t { DEPTHWISE_FP16=0,DEPTHWISE_FP32=1,DEPTHWISE_BF16=2 };
struct DepthwiseConv2DTilingData {
 uint64_t n,c,inH,inW,kH,kW,outH,outW,inputSpatial,kernelSpatial,outputSpatial,outputNumel,blockLength;
 uint32_t strideH,strideW,padH,padW,dilationH,dilationW,blockNum,dtype;
};
inline DepthwiseConv2DTilingData ComputeDepthwiseConv2DTiling(
 const std::vector<uint64_t>&x,const std::vector<uint64_t>&w,const std::vector<uint64_t>&kernel,
 const std::vector<uint64_t>&stride,const std::vector<uint64_t>&padding,const std::vector<uint64_t>&dilation,
 uint64_t groups,uint32_t dtype,int64_t cores){
 if(x.size()!=4||w.size()!=3||kernel.size()!=2||stride.size()!=2||padding.size()!=2||dilation.size()!=2)throw std::invalid_argument("invalid rank or attribute length");
 for(auto v:x)if(!v)throw std::invalid_argument("zero input dimension");for(auto v:w)if(!v)throw std::invalid_argument("zero weight dimension");
 if(groups!=x[1]||w[0]!=x[1]||w[1]!=kernel[0]||w[2]!=kernel[1])throw std::invalid_argument("depthwise shape/groups constraint failed");
 if(!stride[0]||!stride[1]||!dilation[0]||!dilation[1])throw std::invalid_argument("stride and dilation must be positive");
 uint64_t effH=dilation[0]*(kernel[0]-1)+1,effW=dilation[1]*(kernel[1]-1)+1;
 if(x[2]+2*padding[0]<effH||x[3]+2*padding[1]<effW)throw std::invalid_argument("non-positive output dimension");
 DepthwiseConv2DTilingData t{};t.n=x[0];t.c=x[1];t.inH=x[2];t.inW=x[3];t.kH=kernel[0];t.kW=kernel[1];
 t.strideH=stride[0];t.strideW=stride[1];t.padH=padding[0];t.padW=padding[1];t.dilationH=dilation[0];t.dilationW=dilation[1];
 t.outH=(x[2]+2*padding[0]-effH)/stride[0]+1;t.outW=(x[3]+2*padding[1]-effW)/stride[1]+1;
 t.inputSpatial=t.inH*t.inW;t.kernelSpatial=t.kH*t.kW;t.outputSpatial=t.outH*t.outW;t.outputNumel=t.n*t.c*t.outputSpatial;t.dtype=dtype;
 uint64_t align=dtype==DEPTHWISE_FP32?16:32,avail=uint64_t(std::max<int64_t>(1,cores)),useful=std::max<uint64_t>(1,(t.outputNumel+align-1)/align);
 t.blockNum=uint32_t(std::min(avail,useful));uint64_t raw=(t.outputNumel+t.blockNum-1)/t.blockNum;t.blockLength=((raw+align-1)/align)*align;return t;
}
