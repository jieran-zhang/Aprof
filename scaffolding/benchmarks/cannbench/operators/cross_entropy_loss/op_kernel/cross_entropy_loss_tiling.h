#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
enum CeDType:uint32_t{CE_F16=0,CE_F32=1,CE_BF16=2};
struct CeTiling{uint64_t N,C,inner,positions,posPerBlock;uint32_t blockNum,dtype,reduction,alignedC;int64_t ignoreIndex;};
inline CeTiling ComputeCe(uint64_t N,uint64_t C,uint64_t inner,uint32_t dtype,uint32_t reduction,int64_t ignore,int64_t cores){if(!N||!C||C>16384||!inner)throw std::invalid_argument("invalid shape");CeTiling t{};t.N=N;t.C=C;t.inner=inner;t.positions=N*inner;t.dtype=dtype;t.reduction=reduction;t.ignoreIndex=ignore;t.alignedC=((C+63)/64)*64;t.blockNum=static_cast<uint32_t>(std::min<uint64_t>(t.positions,std::max<int64_t>(1,cores)));t.posPerBlock=(t.positions+t.blockNum-1)/t.blockNum;return t;}
