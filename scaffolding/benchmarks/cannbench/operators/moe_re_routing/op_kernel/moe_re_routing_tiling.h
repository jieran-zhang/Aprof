#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

enum MoeReRoutingDtype : uint32_t {
    MRR_FLOAT16 = 0, MRR_BFLOAT16 = 1, MRR_INT8 = 2,
    MRR_INT32 = 3, MRR_INT64 = 4
};

struct MoeReRoutingTilingData {
    uint64_t tokens;
    uint64_t hidden;
    uint32_t ranks;
    uint32_t experts;
    uint32_t tokenDtype;
    uint32_t countDtype;
    uint32_t hasScales;
    uint32_t blockNum;
    uint64_t tokensPerBlock;
};

inline MoeReRoutingTilingData ComputeMoeReRoutingTiling(
    uint64_t tokens, uint64_t hidden, uint32_t ranks, uint32_t experts,
    uint32_t tokenDtype, uint32_t countDtype, bool hasScales, int64_t cores) {
    if (!tokens || !hidden || !ranks || !experts)
        throw std::invalid_argument("all dimensions must be positive");
    if (hidden >= 16384) throw std::invalid_argument("hidden must be less than 16384");
    if (tokenDtype > MRR_INT8) throw std::invalid_argument("unsupported token dtype");
    if (countDtype != MRR_INT32 && countDtype != MRR_INT64)
        throw std::invalid_argument("count dtype must be int32 or int64");
    MoeReRoutingTilingData t{};
    t.tokens = tokens; t.hidden = hidden; t.ranks = ranks; t.experts = experts;
    t.tokenDtype = tokenDtype; t.countDtype = countDtype; t.hasScales = hasScales;
    t.blockNum = std::max<uint32_t>(1, std::min<uint64_t>(std::max<int64_t>(1, cores), tokens));
    t.tokensPerBlock = (tokens + t.blockNum - 1) / t.blockNum;
    return t;
}
