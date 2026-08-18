#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>

enum CumminDType : uint32_t { CUMMIN_FLOAT16=0, CUMMIN_FLOAT32=1, CUMMIN_INT32=2, CUMMIN_BFLOAT16=3 };
struct CumminTilingData {
    uint64_t totalLength;
    uint64_t outer;
    uint64_t axisLength;
    uint64_t inner;
    uint64_t sequenceCount;
    uint64_t groupCount;
    uint64_t workCount;
    uint32_t blockNum;
    uint32_t dtype;
};
inline CumminTilingData ComputeCumminTiling(const std::vector<uint64_t>& shape, int64_t dim,
                                             uint32_t dtype) {
    if (shape.empty() || shape.size() > 8) throw std::invalid_argument("rank must be in [1,8]");
    const int64_t rank=static_cast<int64_t>(shape.size());
    if (dim<0) dim+=rank;
    if (dim<0 || dim>=rank) throw std::invalid_argument("dim out of range");
    CumminTilingData t{}; t.dtype=dtype; t.outer=1; t.inner=1; t.axisLength=shape[dim];
    for (int64_t i=0;i<dim;++i) t.outer*=shape[i];
    for (int64_t i=dim+1;i<rank;++i) t.inner*=shape[i];
    t.sequenceCount=t.outer*t.inner; t.totalLength=t.sequenceCount*t.axisLength;
    t.groupCount=(t.inner+31)/32; t.workCount=t.outer*t.groupCount;
    t.blockNum=static_cast<uint32_t>(t.workCount<32?t.workCount:32);
    if (t.blockNum==0) t.blockNum=1;
    return t;
}
