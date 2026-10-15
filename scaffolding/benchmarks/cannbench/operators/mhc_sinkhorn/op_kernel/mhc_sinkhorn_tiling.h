#pragma once
#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <vector>
struct MhcSinkhornTilingData{uint64_t batch,matrixSize,blockLength;uint32_t n,iterStep,blockNum;float eps;};
inline MhcSinkhornTilingData ComputeMhcSinkhornTiling(const std::vector<uint64_t>&shape,uint32_t iter,float eps,int64_t cores){
 if(shape.size()!=3||shape[1]!=shape[2]||shape[0]<1||shape[0]>16384||shape[1]<2||shape[1]>16)throw std::invalid_argument("expected [B,N,N], B<=16384, 2<=N<=16");
 if(iter<1||iter>40||eps<0)throw std::invalid_argument("iter_step or eps outside supported range");MhcSinkhornTilingData t{};t.batch=shape[0];t.n=static_cast<uint32_t>(shape[1]);t.matrixSize=shape[1]*shape[1];t.iterStep=iter;t.eps=eps;
 uint64_t avail=static_cast<uint64_t>(std::max<int64_t>(1,cores)),matrixBytes=t.matrixSize*4,alignment=64/std::gcd<uint64_t>(matrixBytes,64);
 t.blockNum=static_cast<uint32_t>(std::min<uint64_t>(avail,t.batch));uint64_t raw=(t.batch+t.blockNum-1)/t.blockNum;t.blockLength=((raw+alignment-1)/alignment)*alignment;return t;
}
