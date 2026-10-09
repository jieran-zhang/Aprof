#pragma once
#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
enum MoeDType:uint32_t{MOE_FP16=0,MOE_FP32=1,MOE_BF16=2};
struct MoeGatingTilingData{uint64_t rows,experts,k,outputNumel,blockRows;uint32_t blockNum,dtype,hasFinished;};
inline MoeGatingTilingData ComputeMoeGatingTiling(uint64_t rows,uint64_t experts,uint64_t k,uint32_t dtype,bool hasFinished,int64_t cores){if(!rows||!experts||!k||k>experts||experts>2048||k>1024)throw std::invalid_argument("invalid shape or k");MoeGatingTilingData t{};t.rows=rows;t.experts=experts;t.k=k;t.outputNumel=rows*k;t.dtype=dtype;t.hasFinished=hasFinished;t.blockNum=uint32_t(std::min<uint64_t>(std::max<int64_t>(1,cores),rows));uint64_t alignRows=16/std::gcd<uint64_t>(k,16),raw=(rows+t.blockNum-1)/t.blockNum;t.blockRows=((raw+alignRows-1)/alignRows)*alignRows;return t;}
