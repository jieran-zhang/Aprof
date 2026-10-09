#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
enum UssDataType:uint32_t{USS_F16=0,USS_F32=1,USS_BF16=2,USS_I32=3,USS_I64=4};
enum UssIdType:uint32_t{USS_ID_I32=0,USS_ID_I64=1};
struct UssTiling{uint64_t N,inner,alignedInner,numSegments,outputLength,workspaceLength,convertBlockLength;uint32_t dataType,idType,convertBlockNum;};
inline UssTiling ComputeUss(uint64_t N,uint64_t inner,uint64_t seg,uint32_t dt,uint32_t it,int64_t cores){if(!N||!inner||!seg)throw std::invalid_argument("invalid shape");UssTiling t{};t.N=N;t.inner=inner;t.alignedInner=((inner+15)/16)*16;t.numSegments=seg;t.outputLength=seg*inner;t.workspaceLength=seg*t.alignedInner;t.dataType=dt;t.idType=it;t.convertBlockNum=static_cast<uint32_t>(std::max<int64_t>(1,cores));t.convertBlockLength=(t.outputLength+t.convertBlockNum-1)/t.convertBlockNum;return t;}
