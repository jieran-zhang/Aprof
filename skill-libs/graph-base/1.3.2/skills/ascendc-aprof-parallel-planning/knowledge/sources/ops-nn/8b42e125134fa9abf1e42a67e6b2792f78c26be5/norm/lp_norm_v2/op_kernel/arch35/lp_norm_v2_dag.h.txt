/**
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

/*!
 * \file lp_norm_v2_dag.h
 * \brief lp_norm_v2 dag
 */

#ifndef LP_NORM_V2_DAG_H
#define LP_NORM_V2_DAG_H

#include "atvoss/util/elems.h"
#include "atvoss/util/dag.h"
#include "atvoss/util/vec.h"
#include "atvoss/util/placeholder.h"
#include "atvoss/reduce/reduce_operator.h"

using namespace Ops::Base;

namespace LpNormV2 {

constexpr uint32_t TEMPLATE_P0 = 0;      // 0.0
constexpr uint32_t TEMPLATE_P1 = 1;      // 1.0
constexpr uint32_t TEMPLATE_P2 = 2;      // 2.0
constexpr uint32_t TEMPLATE_P3 = 3;      // 3.0
constexpr uint32_t TEMPLATE_P_NINF = 4;  // -inf
constexpr uint32_t TEMPLATE_P_INF = 5;   // inf
constexpr uint32_t TEMPLATE_P_OTHER = 6; // other

constexpr int CAST_MODE_NONE = 0;
constexpr int CAST_MODE_RINT = 1;
constexpr int COMPARE_MODE_EQ = 2;
constexpr int SEL_MODE_TENSOR_SCALAR = 1;

constexpr int VAR_INDEX_1 = 1;
constexpr int VAR_INDEX_2 = 2;

using namespace AscendC;

#ifdef __CCE_AICORE__
namespace Regbase {

using AscendC::Reg::RegTensor;

constexpr Reg::CastTrait CAST_16_TO_32 = {Reg::RegLayout::ZERO, Reg::SatMode::UNKNOWN, Reg::MaskMergeMode::ZEROING,
                                          RoundMode::UNKNOWN};
constexpr Reg::CastTrait CAST_32_TO_16 = {Reg::RegLayout::ZERO, Reg::SatMode::NO_SAT, Reg::MaskMergeMode::ZEROING,
                                          RoundMode::CAST_RINT};

constexpr uint32_t VREG_BYTES = Ops::Base::GetVRegSize();

template <typename T, typename U>
__aicore__ inline void CalcCastNonZeroVF(__ubuf__ U* dst, __ubuf__ T* src, uint32_t totalLen, uint32_t oneRepeat,
                                         uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regZero;
        RegTensor<U> regOne;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;
        Reg::MaskReg pregIsZero;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            if constexpr (IsSameType<T, U>::value) {
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            } else {
                RegTensor<T> regPacked;
                RegTensor<T> regWide;
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regPacked, src, (int32_t)oneRepeat);
                Reg::UnPack((RegTensor<int32_t>&)regWide, (RegTensor<int16_t>&)regPacked);
                Reg::Cast<U, T, CAST_16_TO_32>(regIn, regWide, pregUp);
            }
            Reg::Compares<U, CMPMODE::EQ>(pregIsZero, regIn, (U)0, pregUp);
            Reg::Duplicate(regZero, (U)0, pregUp);
            Reg::Duplicate(regOne, (U)1, pregUp);

            Reg::Select<U>(regOut, regZero, regOne, pregIsZero);

            Reg::StoreAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
        }
    }
}

// 融合 DAG 节点 Cast0 + Abs0: y = |x|
template <typename T, typename U>
__aicore__ inline void CalcCastAbsVF(__ubuf__ U* dst, __ubuf__ T* src, uint32_t totalLen, uint32_t oneRepeat,
                                     uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            if constexpr (IsSameType<T, U>::value) {
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            } else {
                RegTensor<T> regPacked;
                RegTensor<T> regWide;
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regPacked, src, (int32_t)oneRepeat);
                Reg::UnPack((RegTensor<int32_t>&)regWide, (RegTensor<int16_t>&)regPacked);
                Reg::Cast<U, T, CAST_16_TO_32>(regIn, regWide, pregUp);
            }
            Reg::Abs(regOut, regIn, pregUp);

            Reg::StoreAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
        }
    }
}

// 融合 DAG 节点 Cast0 + Mul0（p == 2）: y = x * x
template <typename T, typename U>
__aicore__ inline void CalcCastSquareVF(__ubuf__ U* dst, __ubuf__ T* src, uint32_t totalLen, uint32_t oneRepeat,
                                        uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            if constexpr (IsSameType<T, U>::value) {
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            } else {
                RegTensor<T> regPacked;
                RegTensor<T> regWide;
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regPacked, src, (int32_t)oneRepeat);
                Reg::UnPack((RegTensor<int32_t>&)regWide, (RegTensor<int16_t>&)regPacked);
                Reg::Cast<U, T, CAST_16_TO_32>(regIn, regWide, pregUp);
            }
            Reg::Mul(regOut, regIn, regIn, pregUp);

            Reg::StoreAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
        }
    }
}

// 融合 DAG 节点 Cast0 + Abs0 + Mul0 + Mul1（p == 3）: y = |x| * |x| * |x|
template <typename T, typename U>
__aicore__ inline void CalcCastCubeVF(__ubuf__ U* dst, __ubuf__ T* src, uint32_t totalLen, uint32_t oneRepeat,
                                      uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regAbs;
        RegTensor<U> regSquare;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            if constexpr (IsSameType<T, U>::value) {
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            } else {
                RegTensor<T> regPacked;
                RegTensor<T> regWide;
                Reg::LoadAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(regPacked, src, (int32_t)oneRepeat);
                Reg::UnPack((RegTensor<int32_t>&)regWide, (RegTensor<int16_t>&)regPacked);
                Reg::Cast<U, T, CAST_16_TO_32>(regIn, regWide, pregUp);
            }
            Reg::Abs(regAbs, regIn, pregUp);
            Reg::Mul(regSquare, regAbs, regAbs, pregUp);
            Reg::Mul(regOut, regSquare, regAbs, pregUp);

            Reg::StoreAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
        }
    }
}

// 融合 DAG 节点 OpMaxs + Cast1: y = cast(max(x, eps))
template <typename T, typename U>
__aicore__ inline void CalcMaxsCastVF(__ubuf__ T* dst, __ubuf__ U* src, U epsilon, uint32_t totalLen,
                                      uint32_t oneRepeat, uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            Reg::LoadAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            Reg::Maxs(regOut, regIn, epsilon, pregUp);

            if constexpr (IsSameType<T, U>::value) {
                Reg::StoreAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
            } else {
                RegTensor<T> regNarrow;
                RegTensor<T> regPacked;
                Reg::MaskReg pregNarrow;
                Reg::Cast<T, U, CAST_32_TO_16>(regNarrow, regOut, pregUp);
                Reg::Pack((RegTensor<uint16_t>&)regPacked, (RegTensor<uint32_t>&)regNarrow);
                Reg::Pack(pregNarrow, pregUp);
                Reg::StoreAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regPacked, (int32_t)oneRepeat, pregNarrow);
            }
        }
    }
}

// 融合 DAG 节点 Sqrt0 + OpMaxs + Cast1（p == 2）: y = cast(max(sqrt(x), eps))
template <typename T, typename U>
__aicore__ inline void CalcSqrtMaxsCastVF(__ubuf__ T* dst, __ubuf__ U* src, U epsilon, uint32_t totalLen,
                                          uint32_t oneRepeat, uint16_t repeatTimes)
{
    __VEC_SCOPE__
    {
        RegTensor<U> regIn;
        RegTensor<U> regSqrt;
        RegTensor<U> regOut;
        Reg::MaskReg pregUp;

        for (uint16_t loop = 0; loop < repeatTimes; loop++) {
            pregUp = Reg::UpdateMask<U>(totalLen);

            Reg::LoadAlign<U, Reg::PostLiteral::POST_MODE_UPDATE>(regIn, src, (int32_t)oneRepeat);
            Reg::Sqrt(regSqrt, regIn, pregUp);
            Reg::Maxs(regOut, regSqrt, epsilon, pregUp);

            if constexpr (IsSameType<T, U>::value) {
                Reg::StoreAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regOut, (int32_t)oneRepeat, pregUp);
            } else {
                RegTensor<T> regNarrow;
                RegTensor<T> regPacked;
                Reg::MaskReg pregNarrow;
                Reg::Cast<T, U, CAST_32_TO_16>(regNarrow, regOut, pregUp);
                Reg::Pack((RegTensor<uint16_t>&)regPacked, (RegTensor<uint32_t>&)regNarrow);
                Reg::Pack(pregNarrow, pregUp);
                Reg::StoreAlign<T, Reg::PostLiteral::POST_MODE_UPDATE>(dst, regPacked, (int32_t)oneRepeat, pregNarrow);
            }
        }
    }
}

} // namespace Regbase
#endif // __CCE_AICORE__

// p == 0: sum(x != 0) 的前置链
template <typename T, typename CalcT>
struct LpNormV2NonZeroOp : public Ops::Base::Vec::ElemwiseUnaryOP<CalcT, T> {
    __aicore__ inline LpNormV2NonZeroOp(Ops::Base::LocalTensor<CalcT>& dst, Ops::Base::LocalTensor<T>& src,
                                        int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcCastNonZeroVF<T, CalcT>((__ubuf__ CalcT*)dst.GetPhyAddr(), (__ubuf__ T*)src.GetPhyAddr(), totalLen,
                                             oneRepeat, repeatTimes);
#endif
    }
};

// p == 1 / p == inf / p == -inf / p == other: 前置链 y = |x|
template <typename T, typename CalcT>
struct LpNormV2CastAbsOp : public Ops::Base::Vec::ElemwiseUnaryOP<CalcT, T> {
    __aicore__ inline LpNormV2CastAbsOp(Ops::Base::LocalTensor<CalcT>& dst, Ops::Base::LocalTensor<T>& src,
                                        int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcCastAbsVF<T, CalcT>((__ubuf__ CalcT*)dst.GetPhyAddr(), (__ubuf__ T*)src.GetPhyAddr(), totalLen,
                                         oneRepeat, repeatTimes);
#endif
    }
};

// p == 2: 前置链 y = x * x
template <typename T, typename CalcT>
struct LpNormV2CastSquareOp : public Ops::Base::Vec::ElemwiseUnaryOP<CalcT, T> {
    __aicore__ inline LpNormV2CastSquareOp(Ops::Base::LocalTensor<CalcT>& dst, Ops::Base::LocalTensor<T>& src,
                                           int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcCastSquareVF<T, CalcT>((__ubuf__ CalcT*)dst.GetPhyAddr(), (__ubuf__ T*)src.GetPhyAddr(), totalLen,
                                            oneRepeat, repeatTimes);
#endif
    }
};

// p == 3: 前置链 y = |x|^3
template <typename T, typename CalcT>
struct LpNormV2CastCubeOp : public Ops::Base::Vec::ElemwiseUnaryOP<CalcT, T> {
    __aicore__ inline LpNormV2CastCubeOp(Ops::Base::LocalTensor<CalcT>& dst, Ops::Base::LocalTensor<T>& src,
                                         int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcCastCubeVF<T, CalcT>((__ubuf__ CalcT*)dst.GetPhyAddr(), (__ubuf__ T*)src.GetPhyAddr(), totalLen,
                                          oneRepeat, repeatTimes);
#endif
    }
};

// 所有模板共用的后置链 y = cast(max(x, eps))
// 输入 1 个 LocalTensor<CalcT> + 1 个标量（Placeholder:Var<CalcT, 0>）
template <typename OutT, typename CalcT>
struct LpNormV2MaxsCastOp : public Ops::Base::Vec::ElemwiseBinaryOP<OutT, CalcT, CalcT> {
    __aicore__ inline LpNormV2MaxsCastOp(Ops::Base::LocalTensor<OutT>& dst, Ops::Base::LocalTensor<CalcT>& src,
                                         CalcT& epsilon, int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcMaxsCastVF<OutT, CalcT>((__ubuf__ OutT*)dst.GetPhyAddr(), (__ubuf__ CalcT*)src.GetPhyAddr(),
                                             epsilon, totalLen, oneRepeat, repeatTimes);
#endif
    }
};

// p == 2: 后置链 y = cast(max(sqrt(x), eps))
template <typename OutT, typename CalcT>
struct LpNormV2SqrtMaxsCastOp : public Ops::Base::Vec::ElemwiseBinaryOP<OutT, CalcT, CalcT> {
    __aicore__ inline LpNormV2SqrtMaxsCastOp(Ops::Base::LocalTensor<OutT>& dst, Ops::Base::LocalTensor<CalcT>& src,
                                             CalcT& epsilon, int32_t count)
    {
#ifdef __CCE_AICORE__
        uint32_t oneRepeat = Regbase::VREG_BYTES / sizeof(CalcT);
        uint32_t totalLen = static_cast<uint32_t>(count);
        uint16_t repeatTimes = (uint16_t)((totalLen + oneRepeat - 1) / oneRepeat);

        Regbase::CalcSqrtMaxsCastVF<OutT, CalcT>((__ubuf__ OutT*)dst.GetPhyAddr(), (__ubuf__ CalcT*)src.GetPhyAddr(),
                                                 epsilon, totalLen, oneRepeat, repeatTimes);
#endif
    }
};

// sum(x!=0)
template <typename T, typename PromoteT, typename OutT>
struct LpNormV2P0Dag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + OpMask + DupZero + OpSel 融合为 1 个节点
    using OpNonZero = Bind<LpNormV2NonZeroOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceSumOp<PromoteT>, OpNonZero>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// sum(abs(x))
template <typename T, typename PromoteT, typename OutT>
struct LpNormV2P1Dag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Abs0 融合为 1 个节点
    using OpAbs = Bind<LpNormV2CastAbsOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceSumOp<PromoteT>, OpAbs>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// sqrt(sum(x*x))
template <typename T, typename PromoteT, typename OutT>
struct LpNormV2P2Dag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Mul0 融合为 1 个节点
    using OpSquare = Bind<LpNormV2CastSquareOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceSumOp<PromoteT>, OpSquare>;

    // Sqrt0 + OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2SqrtMaxsCastOp<OutT, PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// sum(abs(x)^3)^(1/3)
template <typename T, typename PromoteT, typename OutT>
struct LpNormV2P3Dag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Abs0 + Mul0 + Mul1 融合为 1 个节点
    using OpCube = Bind<LpNormV2CastCubeOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceSumOp<PromoteT>, OpCube>;
    using Pow1 = Bind<Vec::Power<PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, VAR_INDEX_1>>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, Pow1, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// inf: max(abs(x))
template <typename T, typename PromoteT = T, typename OutT = T>
struct LpNormV2PInfDag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Abs0 融合为 1 个节点（fp16 场景 T == PromoteT，节点内部退化为纯 Abs）
    using OpAbs = Bind<LpNormV2CastAbsOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceMaxOp<PromoteT>, OpAbs>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// -inf: min(abs(x))
template <typename T, typename PromoteT = T, typename OutT = T>
struct LpNormV2PNInfDag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Abs0 融合为 1 个节点（fp16 场景 T == PromoteT，节点内部退化为纯 Abs）
    using OpAbs = Bind<LpNormV2CastAbsOp<T, PromoteT>, OpCopyIn0>;
    using ReduceOp0 = Bind<Vec::ReduceMinOp<PromoteT>, OpAbs>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

// sum(abs(x)^p)^(1/p)
template <typename T, typename PromoteT, typename OutT>
struct LpNormV2POtherDag {
    using OpCopyIn0 = Bind<Vec::CopyIn<T>, Placeholder::In0<T>>;

    // Cast0 + Abs0 融合为 1 个节点
    using OpAbs = Bind<LpNormV2CastAbsOp<T, PromoteT>, OpCopyIn0>;
    using Pow0 = Bind<Vec::Power<PromoteT>, OpAbs, Placeholder::Var<PromoteT, VAR_INDEX_1>>;
    using ReduceOp0 = Bind<Vec::ReduceSumOp<PromoteT>, Pow0>;
    using Pow1 = Bind<Vec::Power<PromoteT>, ReduceOp0, Placeholder::Var<PromoteT, VAR_INDEX_2>>;

    // OpMaxs + Cast1 融合为 1 个节点: epsilon 通过 tiling 参数传递
    using OpMaxs = Bind<LpNormV2MaxsCastOp<OutT, PromoteT>, Pow1, Placeholder::Var<PromoteT, 0>>;

    using OpCopyOut = Bind<Vec::CopyOut<OutT>, Placeholder::Out0<OutT>, OpMaxs>;
    using Outputs = Elems<OpCopyOut>;
    using MemCfg = MemOptCfg<MemLevel::LEVEL_2>;
    using OpDag = DAGSch<Outputs, void, MemCfg>;
};

} // namespace LpNormV2

#endif
