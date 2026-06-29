#ifndef REDUCE_SUM_TILING_H
#define REDUCE_SUM_TILING_H

#include <cstdint>

struct ReduceSumTilingData {
    uint32_t m;
    uint32_t n;
    uint32_t inputStrideN;
    uint32_t rowsPerCore;
    uint32_t perLoopN;
    uint32_t perLoopNAligned;
    uint32_t loopCount;
    uint32_t tailN;
};

#endif // REDUCE_SUM_TILING_H
