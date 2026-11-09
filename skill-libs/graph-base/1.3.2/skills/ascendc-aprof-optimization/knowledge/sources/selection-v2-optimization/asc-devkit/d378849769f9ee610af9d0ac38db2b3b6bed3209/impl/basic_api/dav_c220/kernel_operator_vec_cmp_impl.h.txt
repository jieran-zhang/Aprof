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
 * \file kernel_operator_vec_cmp_impl.h
 * \brief
 */
#if !defined(__ASCENDC_INCLUDE_INTERNAL_HEADERS__)
#pragma message( \
    "impl/basic_api/dav_c220/kernel_operator_vec_cmp_impl.h is an internal header file and must not be used directly. Functions or variables defined in this file may be removed in the future. Please use \"#include \"basic_api/kernel_vec_intf.h\"\" and use public functions or variables defined in interface headers files.")
#define __ASCENDC_INCLUDE_INTERNAL_HEADERS__
#define __UNDEF_ASCENDC_INCLUDE_INTERNAL_HEADERS_KERNEL_OPERATOR_VEC_CMP_IMPL_H__
#endif
#ifndef ASCENDC_MODULE_OPERATOR_VEC_CMP_IMPL_H
#define ASCENDC_MODULE_OPERATOR_VEC_CMP_IMPL_H
#include "../../../include/basic_api/kernel_common.h"
#include "../kernel_utils.h"
#include "../../../include/basic_api/kernel_struct_binary.h"
#include "../../../include/basic_api/kernel_struct_unary.h"

namespace AscendC {
/* ***************************************************************************************
 * ************************************** Compare ****************************************
 * ************************************************************************************** */
template <typename T>
__aicore__ inline void VcmpvIntrinsicsImpl(
    __ubuf__ uint8_t* dst, __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, uint8_t repeatTime,
    const BinaryRepeatParams& repeatParams)
{
    switch (cmpMode) {
        case CMPMODE::LT: {
            vcmpv_lt(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::GT: {
            vcmpv_gt(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::EQ: {
            vcmpv_eq(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::LE: {
            vcmpv_le(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::GE: {
            vcmpv_ge(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::NE: {
            vcmpv_ne(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride,
                repeatParams.src1BlkStride, repeatParams.dstRepStride, repeatParams.src0RepStride,
                repeatParams.src1RepStride);
            break;
        }
        default:
            ASCENDC_DEBUG_ASSERT(
                (false), KERNEL_LOG_INTERNAL(
                             KERNEL_ERROR,
                             "Failed to check cmpMode value in Compare, "
                             "supported values are CMPMODE::LT / GT / EQ / LE / GE / NE, current value is %d.\n",
                             static_cast<int32_t>(cmpMode)));
            break;
    }
}

template <typename T>
__aicore__ inline void VcmpIntrinsicsImpl(
    __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const BinaryRepeatParams& repeatParams)
{
    switch (cmpMode) {
        case CMPMODE::LT: {
            vcmp_lt(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::GT: {
            vcmp_gt(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::EQ: {
            vcmp_eq(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::LE: {
            vcmp_le(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::GE: {
            vcmp_ge(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        case CMPMODE::NE: {
            vcmp_ne(
                src0, src1, 1, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
                repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
            break;
        }
        default:
            ASCENDC_DEBUG_ASSERT(
                (false), KERNEL_LOG_INTERNAL(
                             KERNEL_ERROR,
                             "Failed to check cmpMode value in Compare, "
                             "supported values are CMPMODE::LT / GT / EQ / LE / GE / NE, current value is %d.\n",
                             static_cast<int32_t>(cmpMode)));
            break;
    }
}

__aicore__ inline void VcmpvIntrinsicsImpl(
    __ubuf__ uint8_t* dst, __ubuf__ int32_t* src0, __ubuf__ int32_t* src1, CMPMODE cmpMode, uint8_t repeatTime,
    const BinaryRepeatParams& repeatParams)
{
    // int32_t only support CMPMODE::EQ
    vcmpv_eq(
        dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.src0BlkStride, repeatParams.src1BlkStride,
        repeatParams.dstRepStride, repeatParams.src0RepStride, repeatParams.src1RepStride);
}

template <typename T, typename U>
__aicore__ inline void CompareCompute(
    __ubuf__ U* dst, __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint32_t count)
{
    if ASCEND_IS_AIV {
        struct BinaryRepeatParams repeatParams;
        uint32_t sumRepeat = count * sizeof(T) / ONE_REPEAT_BYTE_SIZE;
        constexpr uint32_t repeatNormal = 252;
        uint32_t repeatRound = sumRepeat / repeatNormal;
        uint32_t repeatTail = sumRepeat % repeatNormal;
        uint32_t srcOffset = repeatNormal * ONE_REPEAT_BYTE_SIZE / sizeof(T);
        uint32_t dstOffset = srcOffset / ONE_BYTE_BIT_SIZE;

        for (uint32_t i = 0; i < repeatRound; ++i) {
            VcmpvImpl(
                reinterpret_cast<__ubuf__ uint8_t*>(dst) + i * dstOffset, src0 + i * srcOffset, src1 + i * srcOffset,
                cmpMode, MASK_PLACEHOLDER, repeatNormal, repeatParams);
        }
        VcmpvImpl(
            reinterpret_cast<__ubuf__ uint8_t*>(dst) + repeatRound * dstOffset, src0 + repeatRound * srcOffset,
            src1 + repeatRound * srcOffset, cmpMode, MASK_PLACEHOLDER, repeatTail, repeatParams);
    }
}

template <typename T, typename U>
__aicore__ inline void CheckVcmpvDtype(CMPMODE cmpMode)
{
#if defined(ASCENDC_DEBUG) || defined(ASCENDC_CPU_DEBUG)
    ASCENDC_DEBUG_ASSERT(
        (SupportType<U, int8_t, uint8_t>()),
        KERNEL_LOG_INTERNAL(
            KERNEL_ERROR, "Failed to check "
                          "dtype U in Compare, current api support dtype combination is int8_t / uint8_t.\n"));
    if (cmpMode == CMPMODE::EQ) {
        ASCENDC_DEBUG_ASSERT(
            (SupportType<T, half, float, int32_t>()),
            KERNEL_LOG_INTERNAL(
                KERNEL_ERROR,
                "Failed to "
                "check dtype T in Compare when cmpMode is CMPMODE::EQ, current api support dtype combination is half / "
                "float / int32_t.\n"));
    } else {
        ASCENDC_DEBUG_ASSERT(
            (SupportType<T, half, float>()), KERNEL_LOG_INTERNAL(
                                                 KERNEL_ERROR, "Failed to check dtype "
                                                               "T in Compare when cmpMode is not CMPMODE::EQ, current "
                                                               "api support dtype combination is half / float.\n"));
    }
#endif
}

template <typename T>
__aicore__ inline void CheckVcmpDtype()
{
    ASCENDC_DEBUG_ASSERT(
        (SupportType<T, half, float>()),
        KERNEL_LOG_INTERNAL(
            KERNEL_ERROR, "Failed to check dtype T "
                          "in Compare, current api support dtype combination is src: half / float.\n"));
}

template <typename T, typename U>
__aicore__ inline void CheckVcmpvsDtype(CMPMODE cmpMode)
{
#if defined(ASCENDC_DEBUG) || defined(ASCENDC_CPU_DEBUG)
    ASCENDC_DEBUG_ASSERT(
        (SupportType<U, uint8_t>()),
        KERNEL_LOG_INTERNAL(
            KERNEL_ERROR, "Failed to check dtype U in "
                          "Compares / CompareScalar, current api support dtype combination is uint8_t.\n"));
    if (cmpMode == CMPMODE::EQ) {
        ASCENDC_DEBUG_ASSERT(
            (SupportType<T, half, float, int32_t>()),
            KERNEL_LOG_INTERNAL(
                KERNEL_ERROR,
                "Failed to "
                "check dtype T in Compares / CompareScalar when cmpMode is CMPMODE::EQ, current api support dtype "
                "combination is half / float / int32_t.\n"));
    } else {
        ASCENDC_DEBUG_ASSERT(
            (SupportType<T, half, float>()), KERNEL_LOG_INTERNAL(
                                                 KERNEL_ERROR, "Failed to check dtype "
                                                               "T in Compares / CompareScalar when cmpMode is not "
                                                               "CMPMODE::EQ, current api support dtype combination is "
                                                               "half / float.\n"));
    }
#endif
}

// Compare::Level 0 - mask bit mode
template <typename T, typename U, bool isSetMask = true>
__aicore__ inline void VcmpvImpl(
    __ubuf__ U* dst, __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint64_t mask[], uint8_t repeatTime,
    const BinaryRepeatParams& repeatParams)
{
    (void)(mask);
    if ASCEND_IS_AIV {
        CheckVcmpvDtype<T, U>(cmpMode);
        VcmpvIntrinsicsImpl(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, repeatTime, repeatParams);
    }
}

template <typename T, bool isSetMask = true>
__aicore__ inline void VcmpImpl(
    __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint64_t mask[], const BinaryRepeatParams& repeatParams)
{
    if ASCEND_IS_AIV {
        CheckVcmpDtype<T>();
        AscendCUtils::SetMask<T, isSetMask>(mask[1], mask[0]);
        VcmpIntrinsicsImpl(src0, src1, cmpMode, repeatParams);
    }
}

// Compare::Level 0 - mask count mode
template <typename T, typename U, bool isSetMask = true>
__aicore__ inline void VcmpvImpl(
    __ubuf__ U* dst, __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint64_t mask, uint8_t repeatTime,
    const BinaryRepeatParams& repeatParams)
{
    (void)(mask);
    if ASCEND_IS_AIV {
        CheckVcmpvDtype<T, U>(cmpMode);
        VcmpvIntrinsicsImpl(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, repeatTime, repeatParams);
    }
}

template <typename T, bool isSetMask = true>
__aicore__ inline void VcmpImpl(
    __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint64_t mask, const BinaryRepeatParams& repeatParams)
{
    if ASCEND_IS_AIV {
        CheckVcmpDtype<T>();
        AscendCUtils::SetMask<T, isSetMask>(mask);
        VcmpIntrinsicsImpl(src0, src1, cmpMode, repeatParams);
    }
}

// Compare::Level 2
template <typename T, typename U>
__aicore__ inline void VcmpvImpl(
    __ubuf__ U* dst, __ubuf__ T* src0, __ubuf__ T* src1, CMPMODE cmpMode, const uint32_t count)
{
    if ASCEND_IS_AIV {
        CheckVcmpvDtype<T, U>(cmpMode);
        CompareCompute(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, count);
    }
}

/* ***************************************************************************************
 * *********************************** CompareScalar *************************************
 * ************************************************************************************** */
template <typename T>
__aicore__ inline void VcmpvsIntrinsicsImpl(
    __ubuf__ uint8_t* dst, __ubuf__ T* src0, T src1, CMPMODE cmpMode, uint8_t repeatTime,
    const UnaryRepeatParams& repeatParams)
{
    switch (cmpMode) {
        case CMPMODE::LT: {
            vcmpvs_lt(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        case CMPMODE::GT: {
            vcmpvs_gt(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        case CMPMODE::EQ: {
            vcmpvs_eq(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        case CMPMODE::LE: {
            vcmpvs_le(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        case CMPMODE::GE: {
            vcmpvs_ge(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        case CMPMODE::NE: {
            vcmpvs_ne(
                dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
                static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
            break;
        }
        default:
            ASCENDC_DEBUG_ASSERT(
                (false), KERNEL_LOG_INTERNAL(
                             KERNEL_ERROR,
                             "Failed to check cmpMode value in "
                             "Compares / CompareScalar, supported values are CMPMODE::LT / GT / EQ / LE / GE / NE, "
                             "current value is "
                             "%d.\n",
                             static_cast<int32_t>(cmpMode)));
            break;
    }
}

__aicore__ inline void VcmpvsIntrinsicsImpl(
    __ubuf__ uint8_t* dst, __ubuf__ int32_t* src0, int32_t src1, CMPMODE cmpMode, uint8_t repeatTime,
    const UnaryRepeatParams& repeatParams)
{
    // int32_t only support CMPMODE::EQ
    vcmpvs_eq(
        dst, src0, src1, repeatTime, repeatParams.dstBlkStride, repeatParams.srcBlkStride,
        static_cast<uint16_t>(repeatParams.dstRepStride), static_cast<uint16_t>(repeatParams.srcRepStride));
}

template <typename T, typename U>
__aicore__ inline void CompareScalarCompute(
    __ubuf__ U* dst, __ubuf__ T* src0, T src1, CMPMODE cmpMode, const uint32_t count)
{
    if ASCEND_IS_AIV {
        struct UnaryRepeatParams repeatParams;
        uint32_t sumRepeat = count * sizeof(T) / ONE_REPEAT_BYTE_SIZE;
        constexpr uint32_t repeatNormal = 252;
        uint32_t repeatRound = sumRepeat / repeatNormal;
        uint32_t repeatTail = sumRepeat % repeatNormal;
        uint32_t srcOffset = repeatNormal * ONE_REPEAT_BYTE_SIZE / sizeof(T);
        uint32_t dstOffset = srcOffset / ONE_BYTE_BIT_SIZE;
        for (uint32_t i = 0; i < repeatRound; ++i) {
            VcmpvsImpl(
                reinterpret_cast<__ubuf__ uint8_t*>(dst) + i * dstOffset, src0 + i * srcOffset, src1, cmpMode,
                MASK_PLACEHOLDER, repeatNormal, repeatParams);
        }
        VcmpvsImpl(
            reinterpret_cast<__ubuf__ uint8_t*>(dst) + repeatRound * dstOffset, src0 + repeatRound * srcOffset, src1,
            cmpMode, MASK_PLACEHOLDER, repeatTail, repeatParams);
    }
}

// CompareScalar::Level 0 - mask bit mode
template <typename T, typename U, bool isSetMask = true>
__aicore__ inline void VcmpvsImpl(
    __ubuf__ U* dst, __ubuf__ T* src0, T src1, CMPMODE cmpMode, const uint64_t mask[], uint8_t repeatTime,
    const UnaryRepeatParams& repeatParams)
{
    (void)(mask);
    if ASCEND_IS_AIV {
        CheckVcmpvsDtype<T, U>(cmpMode);
        VcmpvsIntrinsicsImpl(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, repeatTime, repeatParams);
    }
}

// CompareScalar::Level 0 - mask count mode
template <typename T, typename U, bool isSetMask = true>
__aicore__ inline void VcmpvsImpl(
    __ubuf__ U* dst, __ubuf__ T* src0, T src1, CMPMODE cmpMode, const uint64_t mask, uint8_t repeatTime,
    const UnaryRepeatParams& repeatParams)
{
    (void)(mask);
    if ASCEND_IS_AIV {
        CheckVcmpvsDtype<T, U>(cmpMode);
        VcmpvsIntrinsicsImpl(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, repeatTime, repeatParams);
    }
}

// CompareScalar::Level 2
template <typename T, typename U>
__aicore__ inline void VcmpvsImpl(__ubuf__ U* dst, __ubuf__ T* src0, T src1, CMPMODE cmpMode, const uint32_t count)
{
    if ASCEND_IS_AIV {
        CheckVcmpvsDtype<T, U>(cmpMode);
        CompareScalarCompute(reinterpret_cast<__ubuf__ uint8_t*>(dst), src0, src1, cmpMode, count);
    }
}

template <typename T>
__aicore__ inline void GetCmpMaskImpl(__ubuf__ T* dst)
{
    get_cmpmask(dst);
}

template <typename T>
__aicore__ inline void SetCmpMaskImpl(__ubuf__ T* src)
{
    set_cmpmask(src);
}
} // namespace AscendC
#endif // ASCENDC_MODULE_OPERATOR_VEC_CMP_IMPL_H
#if defined(__UNDEF_ASCENDC_INCLUDE_INTERNAL_HEADERS_KERNEL_OPERATOR_VEC_CMP_IMPL_H__)
#undef __ASCENDC_INCLUDE_INTERNAL_HEADERS__
#undef __UNDEF_ASCENDC_INCLUDE_INTERNAL_HEADERS_KERNEL_OPERATOR_VEC_CMP_IMPL_H__
#endif
