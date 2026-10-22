#include <cstdio>
#include "../../public/case-01/source/op_kernel/exp_tiling.h"
#include "../../public/case-03/source/op_kernel/maximum_tiling.h"
#include "../../public/case-06/source/vector/op_kernel/nacre_plan.h"

static void shape(const uint64_t* p, unsigned n) {
    std::printf("[");
    for (unsigned i=0;i<n;i++) std::printf("%s%llu",i?",":"",(unsigned long long)p[i]);
    std::printf("]");
}
static void maximum(const char* name, const MaximumTilingData& t) {
    std::printf("\"%s\":{\"total\":%llu,\"blockLength\":%llu,\"blocks\":%u,\"tile\":%u,\"dtype\":%u,\"rank\":%u,\"sameShape\":%u,\"outShape\":",
                name,(unsigned long long)t.totalLength,(unsigned long long)t.blockLength,t.blockNum,t.tileElements,t.dtype,t.rank,t.sameShape);
    shape(t.outShape,t.rank); std::printf(",\"x1Stride\":");shape(t.x1Stride,t.rank);
    std::printf(",\"x2Stride\":");shape(t.x2Stride,t.rank);std::printf("}");
}
int main() {
    const auto e=ComputeExpTiling(25019,EXP_BFLOAT16,3,2.0f,0.5f,-1.0f);
    const auto v=MakeNacrePlan(25019,NACRE_B16,3,2.0f,0.5f,-1.0f);
    std::printf("{\"exp\":{\"total\":%llu,\"blockLength\":%llu,\"blocks\":%u,\"tile\":%u,\"dtype\":%u,\"multiplier\":%.9g,\"shift\":%.9g},",
                (unsigned long long)e.totalLength,(unsigned long long)e.blockLength,e.blockNum,e.tileElements,e.dtype,e.multiplier,e.shift);
    std::printf("\"renamed\":{\"total\":%llu,\"blockLength\":%llu,\"blocks\":%u,\"tile\":%u,\"dtype\":%u,\"multiplier\":%.9g,\"shift\":%.9g},",
                (unsigned long long)v.extent,(unsigned long long)v.laneExtent,v.laneCount,v.windowElements,v.storageTag,v.gain,v.bias);
    maximum("P",ComputeMaximumTiling({2,3},{2,1},MAX_FLOAT16,4));std::printf(",");
    maximum("Q",ComputeMaximumTiling({2,3},{2,1},MAX_FLOAT32,4));std::printf(",");
    maximum("R",ComputeMaximumTiling({2,3},{3},MAX_FLOAT16,4));std::printf("}\n");
}
