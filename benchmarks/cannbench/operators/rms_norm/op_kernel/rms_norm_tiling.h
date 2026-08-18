#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

enum RmsNormDType : uint32_t { RMS_FLOAT16 = 0, RMS_FLOAT32 = 1, RMS_BFLOAT16 = 2 };

struct RmsNormTilingData {
    uint64_t rows;
    uint64_t rowsPerBlock;
    uint32_t hidden;
    uint32_t blockNum;
    uint32_t dtype;
    float epsilon;
    float invHidden;
};

inline RmsNormTilingData ComputeRmsNormTiling(uint64_t numel, uint32_t hidden,
                                               uint32_t dtype, float epsilon,
                                               int64_t cores) {
    if (hidden == 0 || hidden > 8192 || numel == 0 || numel % hidden != 0)
        throw std::invalid_argument("numel must be nonzero and divisible by hidden in [1,8192]");
    if (!(epsilon > 0.0f)) throw std::invalid_argument("epsilon must be positive");
    RmsNormTilingData t{};
    t.rows = numel / hidden; t.hidden = hidden; t.dtype = dtype; t.epsilon = epsilon;
    t.invHidden = 1.0f / static_cast<float>(hidden);
    t.blockNum = static_cast<uint32_t>(std::min<uint64_t>(t.rows, static_cast<uint64_t>(std::max<int64_t>(1, cores))));
    t.rowsPerBlock = (t.rows + t.blockNum - 1) / t.blockNum;
    return t;
}
