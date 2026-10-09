#pragma once
#include <cstdint>
#include <stdexcept>
struct NmsTilingData{uint32_t n;float iouThreshold;};
inline NmsTilingData ComputeNmsTiling(uint64_t n,float threshold){if(n<1||n>8192)throw std::invalid_argument("N must be in [1,8192]");if(!(threshold>0.0f&&threshold<1.0f))throw std::invalid_argument("threshold must be in (0,1)");return{static_cast<uint32_t>(n),threshold};}
