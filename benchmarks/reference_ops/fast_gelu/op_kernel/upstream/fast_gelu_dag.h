/**
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

#ifndef CANN_CUSTOM_OPS_FAST_GELU_DAG_H
#define CANN_CUSTOM_OPS_FAST_GELU_DAG_H
#include "atvoss/util/dag.h"
#include "atvoss/util/vec.h"
#include "atvoss/util/placeholder.h"

namespace FastGeluDag {
using namespace Ops::Base;

template <class T, bool highPrecisionDiv>
struct FastGeluCustom : public Vec::ElemwiseUnaryOP<T, T> {
    __aicore__ inline FastGeluCustom(LocalTensor<T>& dst, LocalTensor<T>& src, uint32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t dtypeSize = sizeof(T);
        uint32_t VL = AscendC::VECTOR_REG_WIDTH / dtypeSize;
        uint16_t loopNum = CeilDivision(count, VL);
        uint32_t vlSize = VL;
        T value1 = -1.702;
        T value2 = 1.0;

        __VEC_SCOPE__
        {
            __ubuf__ T* srcAddr = (__ubuf__ T*)src.GetPhyAddr();
            __ubuf__ T* dstAddr = (__ubuf__ T*)dst.GetPhyAddr();

            AscendC::MicroAPI::RegTensor<T, AscendC::MicroAPI::RegTraitNumOne> x;
            AscendC::MicroAPI::RegTensor<T, AscendC::MicroAPI::RegTraitNumOne> denominator;
            AscendC::MicroAPI::RegTensor<T, AscendC::MicroAPI::RegTraitNumOne> result;
            static constexpr AscendC::MicroAPI::DivSpecificMode mode = {
                AscendC::MicroAPI::MaskMergeMode::ZEROING, highPrecisionDiv};
            AscendC::MicroAPI::MaskReg mask;

            for (uint16_t loopIdx = 0; loopIdx < loopNum; loopIdx++) {
                mask = AscendC::MicroAPI::UpdateMask<T, AscendC::MicroAPI::RegTraitNumOne>(count);
                AscendC::MicroAPI::DataCopy(x, (__ubuf__ T*)(srcAddr + loopIdx * vlSize));
                AscendC::MicroAPI::Muls(denominator, x, value1, mask);
                AscendC::MicroAPI::Exp(denominator, denominator, mask);
                AscendC::MicroAPI::Adds(denominator, denominator, value2, mask);
                // result = x / (Exp(-1.702 * x) + 1)
                AscendC::MicroAPI::Div<T, &mode>(result, x, denominator, mask);
                // OpCopyOut
                AscendC::MicroAPI::DataCopy((__ubuf__ T*)(dstAddr + loopIdx * vlSize), result, mask);
            }
        }
#endif
    }
};

template <typename T>
struct FastGeluNoCast {
    // 通过Compute构造计算图
    using OpCopyIn = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;
    using OpFastGelu = Bind<FastGeluCustom<float, true>, OpCopyIn>;

    using OpCopyOut = Bind<Vec::CopyOut<T>, Placeholder::Out0<T>, OpFastGelu>;
    // 指定输出节点
    using Outputs = Elems<OpCopyOut>; // 设置输出
    using OpDag = DAGSch<Outputs>;
};

template <typename T>
struct FastGeluNeedCast {
    // 通过Compute构造计算图
    using OpCopyIn = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>; // x
    using CastIn = Bind<Vec::Cast<float, T, 0>, OpCopyIn>;
    using OpFastGelu = Bind<FastGeluCustom<float, false>, CastIn>;

    using CastOut = Bind<Vec::Cast<T, float, 1>, OpFastGelu>;
    using OpCopyOut = Bind<Vec::CopyOut<T>, Placeholder::Out0<T>, CastOut>;
    // 指定输出节点
    using Outputs = Elems<OpCopyOut>; // 设置输出
    using OpDag = DAGSch<Outputs>;
};

};     // namespace FastGeluDag
#endif // CANN_CUSTOM_OPS_FAST_GELU_DAG_H
