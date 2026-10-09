#pragma once
#include <algorithm>
#include <cstdint>
enum UniqueDType:uint32_t{UNIQUE_FP16=0,UNIQUE_FP32=1,UNIQUE_BF16=2,UNIQUE_INT8=3,UNIQUE_INT32=4,UNIQUE_INT64=5,UNIQUE_UINT8=6};
struct UniqueTilingData{uint64_t numel,blockLength;uint32_t blockNum,dtype,itemSize,radixPasses,needInverse;};
inline UniqueTilingData ComputeUniqueTiling(uint64_t n,uint32_t dtype,bool inv,int64_t cores){UniqueTilingData t{};t.numel=n;t.dtype=dtype;t.needInverse=inv;t.itemSize=(dtype==UNIQUE_INT8||dtype==UNIQUE_UINT8)?1:(dtype==UNIQUE_FP16||dtype==UNIQUE_BF16)?2:(dtype==UNIQUE_FP32||dtype==UNIQUE_INT32)?4:8;t.radixPasses=t.itemSize;t.blockNum=uint32_t(std::max<int64_t>(1,cores));t.blockLength=((n+t.blockNum-1)/t.blockNum+7)/8*8;return t;}
