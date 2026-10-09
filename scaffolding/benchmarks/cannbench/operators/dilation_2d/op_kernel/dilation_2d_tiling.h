#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
struct Dilation2DTilingData{uint64_t outputNumel,blockLength;uint32_t n,h,w,c,kh,kw,outH,outW,strideH,strideW,rateH,rateW,padTop,padLeft,blockNum;};
inline Dilation2DTilingData ComputeDilation2DTiling(uint32_t n,uint32_t h,uint32_t w,uint32_t c,uint32_t kh,uint32_t kw,uint32_t sh,uint32_t sw,uint32_t rh,uint32_t rw,bool same,const uint32_t*pads,int64_t cores){
 if(!n||!h||!w||!c||!kh||!kw||!sh||!sw||!rh||!rw)throw std::invalid_argument("dimensions/strides/rates must be positive");Dilation2DTilingData t{};t.n=n;t.h=h;t.w=w;t.c=c;t.kh=kh;t.kw=kw;t.strideH=sh;t.strideW=sw;t.rateH=rh;t.rateW=rw;uint32_t eh=(kh-1)*rh+1,ew=(kw-1)*rw+1;
 if(same){t.outH=(h+sh-1)/sh;t.outW=(w+sw-1)/sw;uint32_t ph=std::max<int64_t>(static_cast<int64_t>((t.outH-1)*sh+eh)-h,0),pw=std::max<int64_t>(static_cast<int64_t>((t.outW-1)*sw+ew)-w,0);t.padTop=ph/2;t.padLeft=pw/2;}
 else{uint32_t paddedH=h+pads[0]+pads[1],paddedW=w+pads[2]+pads[3];if(paddedH<eh||paddedW<ew)throw std::invalid_argument("effective filter exceeds padded input");t.outH=(paddedH-eh)/sh+1;t.outW=(paddedW-ew)/sw+1;t.padTop=pads[0];t.padLeft=pads[2];}
 t.outputNumel=static_cast<uint64_t>(n)*t.outH*t.outW*c;t.blockNum=std::max<uint32_t>(1,std::min<uint64_t>(std::max<int64_t>(1,cores),(t.outputNumel+4095)/4096));t.blockLength=(t.outputNumel+t.blockNum-1)/t.blockNum;t.blockLength=((t.blockLength+15)/16)*16;return t;}
