#pragma once
#include <algorithm>
#include <cstdint>

enum SwiGluDType : uint32_t { SWIGLU_FLOAT16 = 0, SWIGLU_FLOAT32 = 1, SWIGLU_BFLOAT16 = 2 };

struct SwiGluTilingData {
    uint64_t outputLength;
    uint64_t segmentLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
};

inline SwiGluTilingData ComputeSwiGluTiling(uint64_t outputLength, uint64_t segmentLength,
                                            uint32_t dtype, int64_t cores) {
    SwiGluTilingData t{};
    t.outputLength = outputLength;
    t.segmentLength = segmentLength;
    const uint64_t useful = std::max<uint64_t>(1, (outputLength + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (outputLength + t.blockNum - 1) / t.blockNum;
    t.tileElements = 4096;
    t.dtype = dtype;
    return t;
}
