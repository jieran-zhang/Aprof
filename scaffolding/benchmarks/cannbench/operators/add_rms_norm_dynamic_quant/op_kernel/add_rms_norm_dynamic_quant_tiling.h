#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

enum AddRmsQuantDType : uint32_t { ADD_RMS_QUANT_FLOAT16 = 0, ADD_RMS_QUANT_BFLOAT16 = 1 };

struct AddRmsQuantTilingData {
    uint64_t rows;
    uint64_t rowsPerBlock;
    uint32_t hidden;
    uint32_t blockNum;
    uint32_t dtype;
    uint32_t tileElements;
    float epsilon;
    float invHidden;
};

inline uint64_t AddRmsQuantGcd(uint64_t a, uint64_t b) {
    while (b != 0) { const uint64_t r = a % b; a = b; b = r; }
    return a;
}
inline uint64_t AddRmsQuantLcm(uint64_t a, uint64_t b) {
    return a / AddRmsQuantGcd(a, b) * b;
}

inline AddRmsQuantTilingData ComputeAddRmsQuantTiling(uint64_t numel, uint32_t hidden,
                                                       uint32_t dtype, float epsilon,
                                                       int64_t cores) {
    if (hidden == 0 || hidden > 16384 || numel == 0 || numel % hidden != 0)
        throw std::invalid_argument("numel must be nonzero and divisible by hidden in [1,16384]");
    if (!(epsilon > 0.0f)) throw std::invalid_argument("epsilon must be positive");
    AddRmsQuantTilingData t{};
    t.rows = numel / hidden;
    t.hidden = hidden;
    t.dtype = dtype;
    t.epsilon = epsilon;
    t.invHidden = 1.0f / static_cast<float>(hidden);
    t.tileElements = 2048;
    t.blockNum = static_cast<uint32_t>(std::min<uint64_t>(
        t.rows, static_cast<uint64_t>(std::max<int64_t>(1, cores))));
    const uint64_t average = (t.rows + t.blockNum - 1) / t.blockNum;
    // Scalar/short GM writes are committed in cache-line units. Align core
    // row boundaries for float scale, int8 y and two-byte xOut simultaneously.
    const uint64_t yRows = 64 / AddRmsQuantGcd(hidden, 64);
    const uint64_t xOutRows = 64 / AddRmsQuantGcd(static_cast<uint64_t>(hidden) * 2, 64);
    const uint64_t alignment = AddRmsQuantLcm(16, AddRmsQuantLcm(yRows, xOutRows));
    t.rowsPerBlock = ((average + alignment - 1) / alignment) * alignment;
    return t;
}
