#ifndef FAST_GELU_TILING_H
#define FAST_GELU_TILING_H

#include <cstdint>

constexpr uint32_t TILE_LENGTH = 4096;
constexpr float FAST_GELU_ATTR = -1.702f;

struct FastGeluTilingData {
    uint32_t totalLength;
    uint32_t numPerCore;
    uint32_t tailNumLastCore;
    uint32_t blockNum;
};

#endif // FAST_GELU_TILING_H
