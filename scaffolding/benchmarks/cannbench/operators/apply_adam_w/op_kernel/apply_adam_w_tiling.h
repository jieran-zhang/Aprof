#pragma once

#include <cstdint>

enum ApplyAdamWDType : uint32_t {
    APPLY_ADAM_W_FLOAT32 = 0,
    APPLY_ADAM_W_FLOAT16 = 1,
    APPLY_ADAM_W_BFLOAT16 = 2,
};

struct ApplyAdamWTilingData {
    uint64_t totalLength;
    uint64_t blockFormer;
    uint64_t blockTail;
    uint32_t blockNum;
    uint32_t ubFormer;
    uint32_t loopsFormer;
    uint32_t tailFormer;
    uint32_t loopsTail;
    uint32_t tailTail;
    uint32_t dtypeCode;
    float beta1;
    float beta2;
    float oneMinusBeta1;
    float oneMinusBeta2;
    float invBias1;
    float invBias2;
    float weightDecay;
    float epsilon;
    float signedLr;
    uint32_t quietNanBits;
    uint32_t positiveInfBits;
    uint32_t negativeInfBits;
};
