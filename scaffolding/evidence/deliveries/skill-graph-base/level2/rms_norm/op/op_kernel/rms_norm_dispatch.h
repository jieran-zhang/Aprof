#pragma once
#include "rms_norm_tiling.h"
inline uint64_t SelectRmsNormTilingKey(const RmsNormTilingData& t) {
    if (t.hidden == 2) return 12;
    if (t.hidden >= 1 && t.hidden <= 128) return 10;
    if (t.hidden > 128 && t.hidden <= 8192) return 11;
    return 0;
}
