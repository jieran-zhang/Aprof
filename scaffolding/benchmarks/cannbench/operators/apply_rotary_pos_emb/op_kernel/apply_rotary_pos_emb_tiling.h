#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
enum RopeDType:uint32_t{ROPE_F16=0,ROPE_F32=1,ROPE_BF16=2};
struct RopeTilingData{uint64_t total,rows,rowsPerBlock;uint32_t blockNum,B,S,N,D,layout,interleaved,cosBatched,dtype;};
inline RopeTilingData ComputeRopeTiling(uint32_t B,uint32_t S,uint32_t N,uint32_t D,uint32_t layout,bool interleaved,bool cosBatched,uint32_t dtype,int64_t cores){
 if(!B||!S||!N||D<2||(D&1)||layout>1)throw std::invalid_argument("invalid BSND/BNSD shape or attributes");
 RopeTilingData t{};t.B=B;t.S=S;t.N=N;t.D=D;t.layout=layout;t.interleaved=interleaved;t.cosBatched=cosBatched;t.dtype=dtype;t.rows=static_cast<uint64_t>(B)*S*N;t.total=t.rows*D;
 uint64_t available=static_cast<uint64_t>(std::max<int64_t>(1,cores));t.blockNum=static_cast<uint32_t>(std::min(t.rows,available));t.rowsPerBlock=(t.rows+t.blockNum-1)/t.blockNum;return t;
}
