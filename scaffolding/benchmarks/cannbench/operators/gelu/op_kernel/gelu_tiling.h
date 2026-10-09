#pragma once
#include <algorithm>
#include <cstdint>

enum GeluDType : uint32_t { GELU_FLOAT16 = 0, GELU_FLOAT32 = 1, GELU_BFLOAT16 = 2 };
enum GeluMode : uint32_t { GELU_NONE = 0, GELU_TANH = 1 };

struct GeluTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
    uint32_t mode;
};

inline GeluTilingData ComputeGeluTiling(uint64_t n, uint32_t dtype, uint32_t mode, int64_t cores) {
    GeluTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 1024;
    t.dtype = dtype;
    t.mode = mode;
    return t;
}
