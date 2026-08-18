#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>
enum TopKDtype : uint32_t { TOPK_INT8, TOPK_UINT8, TOPK_INT32, TOPK_INT64, TOPK_FLOAT16, TOPK_FLOAT32, TOPK_BFLOAT16 };
struct TopKTilingData {
    uint64_t outer, axis, inner, sequenceCount, outputNumel;
    uint32_t k, dtype, itemBytes, blockNum, largest;
};
inline TopKTilingData ComputeTopKTiling(const std::vector<uint64_t>& shape, int64_t dimArg, uint32_t k,
                                        bool largest, uint32_t dtype, uint32_t itemBytes, int64_t cores) {
    if(shape.empty()||shape.size()>8) throw std::invalid_argument("rank must be in [1,8]");
    int64_t dim=dimArg<0?dimArg+static_cast<int64_t>(shape.size()):dimArg;
    if(dim<0||dim>=static_cast<int64_t>(shape.size())) throw std::invalid_argument("dim out of range");
    if(k==0||k>shape[dim]||k>2048) throw std::invalid_argument("k out of supported range [1,min(axis,2048)]");
    TopKTilingData t{};t.outer=1;t.inner=1;t.axis=shape[dim];t.k=k;t.dtype=dtype;t.itemBytes=itemBytes;t.largest=largest;
    for(int64_t d=0;d<dim;++d)t.outer*=shape[d];for(size_t d=dim+1;d<shape.size();++d)t.inner*=shape[d];
    t.sequenceCount=t.outer*t.inner;t.outputNumel=t.sequenceCount*k;
    // A core owns whole outer slabs for strided axes. Splitting inner lanes across cores can make
    // scalar GM stores from separate vector cores share a cache line and lose writes.
    const bool stridedRowsCacheAligned=t.inner>1 && (t.inner*itemBytes)%32==0;
    const uint64_t workUnits=(t.inner>1&&!stridedRowsCacheAligned)?t.outer:t.sequenceCount;
    t.blockNum=std::max<uint32_t>(1,std::min<uint64_t>(std::max<int64_t>(1,cores),workUnits));return t;
}
