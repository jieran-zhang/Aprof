#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

enum NacreDType : uint32_t { NACRE_S16 = 0, NACRE_S32 = 1, NACRE_B16 = 2 };

struct NacrePlan {
    uint64_t extent;
    uint64_t laneExtent;
    uint32_t laneCount;
    uint32_t windowElements;
    uint32_t storageTag;
    float gain;
    float bias;
};

inline NacrePlan MakeNacrePlan(uint64_t n, uint32_t storageTag, int64_t cores,
                                      float base, float scale, float bias) {
    NacrePlan t{};
    t.extent = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.laneCount = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.laneExtent = (n + t.laneCount - 1) / t.laneCount;
    t.windowElements = 4096;
    t.storageTag = storageTag;
    t.gain = scale * (base > 0.0f ? std::log(base) : 1.0f);
    t.bias = bias * (base > 0.0f ? std::log(base) : 1.0f);
    return t;
}
