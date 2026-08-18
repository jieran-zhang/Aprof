#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum DynamicQuantDType : uint32_t {
    DYNAMIC_QUANT_FLOAT16 = 0,
    DYNAMIC_QUANT_BFLOAT16 = 1,
};

struct DynamicQuantTilingData {
    uint64_t tokenCount;
    uint64_t rowLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t dtype;
};

inline uint64_t DynamicQuantGcd(uint64_t a, uint64_t b) {
    while (b != 0) { const uint64_t r = a % b; a = b; b = r; }
    return a;
}

inline DynamicQuantTilingData ComputeDynamicQuantTiling(
    const std::vector<uint64_t> &shape, uint32_t dtype, int64_t cores) {
    if (shape.size() < 2 || shape.size() > 8) throw std::invalid_argument("rank must be in [2, 8]");
    DynamicQuantTilingData t{};
    t.rowLength = shape.back();
    if (t.rowLength == 0 || t.rowLength > 16384) throw std::invalid_argument("last dimension must be in [1, 16384]");
    t.tokenCount = 1;
    for (size_t i = 0; i + 1 < shape.size(); ++i) t.tokenCount *= shape[i];
    t.dtype = dtype;
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(
        1, std::min<int64_t>(cores, static_cast<int64_t>(t.tokenCount))));
    const uint64_t average = (t.tokenCount + t.blockNum - 1) / t.blockNum;
    // Align both scale (float32) and y (int8 row-major) core boundaries to
    // 64 bytes so scalar/short-tail stores from adjacent cores never overlap.
    const uint64_t yRows = 64 / DynamicQuantGcd(t.rowLength, 64);
    const uint64_t alignment = (16 / DynamicQuantGcd(16, yRows)) * yRows;
    t.blockLength = ((average + alignment - 1) / alignment) * alignment;
    return t;
}
