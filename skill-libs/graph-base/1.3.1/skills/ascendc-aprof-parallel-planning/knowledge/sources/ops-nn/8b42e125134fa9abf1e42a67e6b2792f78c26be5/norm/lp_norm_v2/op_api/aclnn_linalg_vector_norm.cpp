/**
 * Copyright (c) 2025-2026 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

#include <bitset>
#include <climits>
#include <cmath>
#include "level0/zero_op.h"
#include "norm/common/op_api/lp_norm_reduce_v2.h"
#include "norm/common/op_api/lp_norm_update_v2.h"
#include "lp_norm_v2.h"
#include "aclnn_kernels/cast.h"
#include "aclnn_kernels/contiguous.h"
#include "op_api/op_api_def_nn.h"
#include "aclnn/aclnn_base.h"
#include "opdev/common_types.h"
#include "opdev/op_dfx.h"
#include "opdev/op_executor.h"
#include "opdev/tensor_view_utils.h"
#include "opdev/make_op_executor.h"
#include "op_api/level2_base_caculation_nn.h"
#include "op_api/aclnn_util.h"
#include "aclnn_linalg_vector_norm.h"

using namespace op;
#ifdef __cplusplus

extern "C" {
#endif

constexpr size_t MAX_MASK_LEN = 64;
constexpr float INT_MAX_F = static_cast<float>(INT_MAX);
constexpr float INT_MIN_F = static_cast<float>(INT_MIN);

static const std::initializer_list<op::DataType> DTYPE_SUPPORT_LIST_910 = {op::DataType::DT_FLOAT,
                                                                           op::DataType::DT_FLOAT16};

static const std::initializer_list<op::DataType> DTYPE_SUPPORT_LIST_910B_C = {
    op::DataType::DT_FLOAT, op::DataType::DT_FLOAT16, op::DataType::DT_BF16};

static const std::initializer_list<op::DataType> DTYPE_SUPPORT_LIST_FLOAT = {op::DataType::DT_FLOAT};

static const std::initializer_list<op::DataType> DTYPE_SUPPORT_LIST_FLOAT16 = {op::DataType::DT_FLOAT,
                                                                               op::DataType::DT_FLOAT16};

static const std::initializer_list<op::DataType> DTYPE_SUPPORT_LIST_BF16 = {op::DataType::DT_FLOAT,
                                                                            op::DataType::DT_BF16};

static inline bool CheckNotNull(const aclTensor* self, const aclScalar* ord, const aclIntArray* dims,
                                const aclTensor* out)
{
    OP_CHECK_NULL(self, return false);
    OP_CHECK_NULL(ord, return false);
    OP_CHECK_NULL(dims, return false);
    OP_CHECK_NULL(out, return false);

    return true;
}

static inline bool IsSocVersionSupportBf16()
{
    auto curArch = GetCurrentPlatformInfo().GetCurNpuArch();
    return curArch == NpuArch::DAV_2201 || Ops::NN::AclnnUtil::IsRegbase(curArch);
}

static inline bool CheckDtypeConvertValid(const aclTensor* self, const op::DataType dtype, const aclTensor* out)
{
    const std::initializer_list<DataType> DTYPE_SUPPORT_LIST = DTYPE_SUPPORT_LIST_910B_C;

    OP_CHECK_DTYPE_NOT_SUPPORT(self, DTYPE_SUPPORT_LIST, return false);
    OP_CHECK_DTYPE_NOT_SUPPORT(out, DTYPE_SUPPORT_LIST, return false);
    OP_CHECK(CheckType(dtype, DTYPE_SUPPORT_LIST),
             OP_LOGE(ACLNN_ERR_PARAM_INVALID, "dtype %s not in dtype support list [%s].",
                     op::ToString(dtype).GetString(), op::ToString(DTYPE_SUPPORT_LIST).GetString()),
             return false);
    // 校验self的数据类型是否可转换为dtype
    op::DataType selfDtype = self->GetDataType();
    std::initializer_list<op::DataType> DTYPE_CONVERT_LIST;
    if (selfDtype == op::DataType::DT_FLOAT) {
        DTYPE_CONVERT_LIST = DTYPE_SUPPORT_LIST_FLOAT;
    }
    if (selfDtype == op::DataType::DT_FLOAT16) {
        DTYPE_CONVERT_LIST = DTYPE_SUPPORT_LIST_FLOAT16;
    }
    if (selfDtype == op::DataType::DT_BF16) {
        DTYPE_CONVERT_LIST = DTYPE_SUPPORT_LIST_BF16;
    }
    OP_CHECK(CheckType(dtype, DTYPE_CONVERT_LIST),
             OP_LOGE(ACLNN_ERR_PARAM_INVALID, "For self with dtype %s, dtype should be %s, but got %s.",
                     op::ToString(selfDtype).GetString(), op::ToString(DTYPE_CONVERT_LIST).GetString(),
                     op::ToString(dtype).GetString()),
             return false);
    return true;
}

static inline bool CheckDtypeValid(const aclTensor* self, const op::DataType dtype, const aclTensor* out)
{
    OP_CHECK_DTYPE_NOT_MATCH(out, dtype, return false);
    if (IsComplexType(self->GetDataType()) || IsComplexType(out->GetDataType())) {
        OP_LOGE(ACLNN_ERR_PARAM_INVALID, "The operator does not support the complex number type.");
        return false;
    }

    if (Ops::NN::AclnnUtil::IsRegbase()) {
        return CheckDtypeConvertValid(self, dtype, out);
    }
    return true;
}

static inline bool CheckDimsValue(const aclTensor* self, const aclIntArray* dims)
{
    int64_t tmpDim = static_cast<int64_t>(self->GetViewShape().GetDimNum());
    if (tmpDim == 0) {
        tmpDim = 1;
    }
    auto dimsData = dims->GetData();
    vector<int64_t> dimsVector(dimsData, dimsData + dims->Size());

    auto it = std::find_if(dimsVector.cbegin(), dimsVector.cend(),
                           [tmpDim](int dim) { return dim < -tmpDim || dim >= tmpDim; });
    OP_CHECK(it == dimsVector.cend(),
             OP_LOGE(ACLNN_ERR_PARAM_INVALID,
                     "Dimension out of range (expected to be in range of [-%ld, %ld],"
                     "but got %ld)",
                     tmpDim, tmpDim - 1, *it),
             return false);

    std::set<int64_t> dimSet;
    for (uint64_t i = 0; i < dims->Size(); i++) {
        int64_t dim = dimsVector[i];
        dim = (dim < 0) ? (dim + tmpDim) : dim;
        OP_CHECK(dimSet.find(dim) == dimSet.end(),
                 OP_LOGE(ACLNN_ERR_PARAM_INVALID, "dim %ld appears multiple times in the list of dims", dim),
                 return false);
        dimSet.insert(dim);
    }

    return true;
}

static inline bool CheckPromoteType(const aclTensor* self, const aclTensor* out)
{
    // 检查self和out能否做数据类型推导
    op::DataType promoteType = op::PromoteType(self->GetDataType(), out->GetDataType());
    if (promoteType == DataType::DT_UNDEFINED) {
        OP_LOGE(ACLNN_ERR_PARAM_INVALID, "Input dtype %s and output dtype %s can not promote dtype.",
                op::ToString(self->GetDataType()).GetString(), op::ToString(out->GetDataType()).GetString());
        return false;
    }
    if (Ops::NN::AclnnUtil::IsRegbase()) {
        // 检查推导后的数据类型是否能转换为输出的数据类型
        OP_CHECK_RESULT_DTYPE_CAST_FAILED(promoteType, out->GetDataType(), return false);
    }

    return true;
}

static inline bool CheckShape(const aclTensor* self, const aclTensor* out, const aclIntArray* dims, bool keepDims)
{
    // 检查self/out的shape是否超过最大维度限制
    OP_CHECK_MAX_DIM(self, MAX_SUPPORT_DIMS_NUMS, return false);
    OP_CHECK_MAX_DIM(out, MAX_SUPPORT_DIMS_NUMS, return false);

    // 是否满足由self，dim，keepDim推导得到的shape
    op::Shape expectShape;
    ExpectShapeInferWithDimMask(self->GetViewShape(), dims, keepDims, expectShape);
    OP_CHECK_SHAPE_NOT_EQUAL_WITH_EXPECTED_SIZE(out, expectShape, return false);
    return true;
}

static bool IsFloatEqual(float a, float b, float epsilon = 1e-6f) { return std::fabs(a - b) < epsilon; }

static float CalculateOrdValue(const aclScalar* ord)
{
    float ordVal = ord->ToFloat();
    if ((std::isinf(ordVal) && ordVal > 0) || IsFloatEqual(ordVal, INT_MAX_F)) {
        return INT_MAX_F;
    } else if ((std::isinf(ordVal) && ordVal < 0) || IsFloatEqual(ordVal, INT_MIN_F)) {
        return INT_MIN_F;
    } else {
        return static_cast<float>(ordVal);
    }
}

static inline bool CheckOrdValue(const aclScalar* ord)
{
    // 950上支持所有float取值
    if (Ops::NN::AclnnUtil::IsRegbase()) {
        return true;
    }
    const std::vector<float> attrPSupportValue = {0.0, 1.0, 2.0, 3.0, INT_MAX_F, INT_MIN_F};
    float pValue = CalculateOrdValue(ord);
    auto it = std::find(attrPSupportValue.cbegin(), attrPSupportValue.cend(), pValue);
    std::stringstream sStream;
    std::for_each(attrPSupportValue.cbegin(), attrPSupportValue.cend(), [&](float value) { sStream << value << ", "; });
    OP_CHECK(it != attrPSupportValue.cend(),
             OP_LOGE(ACLNN_ERR_PARAM_INVALID, "ord must one of [inf, -inf, %s], but find %f.", sStream.str().c_str(),
                     pValue),
             return false);
    return true;
}

struct InputParams {
    const aclTensor* self;
    const aclScalar* ord;
    const aclIntArray* dims;
    const aclDataType dtype;
    const aclTensor* out;
    bool keepDims;
};

static aclnnStatus CheckParams(InputParams& inputParams)
{
    CHECK_RET(CheckNotNull(inputParams.self, inputParams.ord, inputParams.dims, inputParams.out),
              ACLNN_ERR_PARAM_NULLPTR);
    CHECK_RET(CheckDtypeValid(inputParams.self, op::ToOpDataType(inputParams.dtype), inputParams.out),
              ACLNN_ERR_PARAM_INVALID);
    CHECK_RET(CheckPromoteType(inputParams.self, inputParams.out), ACLNN_ERR_PARAM_INVALID);
    CHECK_RET(CheckDimsValue(inputParams.self, inputParams.dims), ACLNN_ERR_PARAM_INVALID);
    CHECK_RET(CheckShape(inputParams.self, inputParams.out, inputParams.dims, inputParams.keepDims),
              ACLNN_ERR_PARAM_INVALID);

    return ACLNN_SUCCESS;
}

namespace {
static aclnnStatus aclnnLinalgVectorA5(const aclTensor* selfContiguous, InputParams& inputParams,
                                       aclOpExecutor* executor)
{
    auto epsilon = static_cast<float>(0);
    auto normOut = l0op::LpNormV2(selfContiguous, inputParams.out, inputParams.ord->ToFloat(), inputParams.dims,
                                  inputParams.keepDims, epsilon, executor);
    CHECK_RET(normOut != nullptr, ACLNN_ERR_INNER_NULLPTR);

    auto viewCopyResult = l0op::ViewCopy(normOut, inputParams.out, executor);
    CHECK_RET(viewCopyResult != nullptr, ACLNN_ERR_INNER_NULLPTR);
    return ACLNN_SUCCESS;
}

static aclnnStatus aclnnLinalgVectorA3(const aclTensor* selfContiguous, InputParams& inputParams,
                                       aclOpExecutor* executor)
{
    auto epsilon = static_cast<float>(0);

    const aclTensor* normOut;
    bool isPromoteValid = CheckDtypeConvertValid(inputParams.self, op::ToOpDataType(inputParams.dtype),
                                                 inputParams.out);
    if (isPromoteValid) {
        normOut = l0op::LpNormV2(selfContiguous, inputParams.out, CalculateOrdValue(inputParams.ord), inputParams.dims,
                                 inputParams.keepDims, epsilon, executor);
        CHECK_RET(normOut != nullptr, ACLNN_ERR_INNER_NULLPTR);
    } else if (!isPromoteValid) {
        auto selfContiguousCast = l0op::Cast(selfContiguous, op::DataType::DT_FLOAT, executor);
        CHECK_RET(selfContiguousCast != nullptr, ACLNN_ERR_INNER_NULLPTR);

        normOut = l0op::LpNormV2(selfContiguousCast, selfContiguousCast, CalculateOrdValue(inputParams.ord),
                                 inputParams.dims, inputParams.keepDims, epsilon, executor);
        CHECK_RET(normOut != nullptr, ACLNN_ERR_INNER_NULLPTR);

        normOut = l0op::Cast(normOut, inputParams.out->GetDataType(), executor);
        CHECK_RET(normOut != nullptr, ACLNN_ERR_INNER_NULLPTR);
    }

    auto viewCopyResult = l0op::ViewCopy(normOut, inputParams.out, executor);
    CHECK_RET(viewCopyResult != nullptr, ACLNN_ERR_INNER_NULLPTR);
    return ACLNN_SUCCESS;
}

static aclnnStatus HandleOutNotEmpty(aclTensor* out, aclOpExecutor* executor)
{
    aclTensor* output;
    if (!CheckType(out->GetDataType(), DTYPE_SUPPORT_LIST_910B_C)) {
        output = executor->AllocTensor(out->GetViewShape(), op::DataType::DT_FLOAT);
    } else {
        output = executor->AllocTensor(out->GetViewShape(), out->GetDataType());
    }
    auto zeroOut = l0op::ZerosLike(output, executor);
    CHECK_RET(zeroOut != nullptr, ACLNN_ERR_INNER_NULLPTR);
    if (!CheckType(out->GetDataType(), DTYPE_SUPPORT_LIST_910B_C)) {
        zeroOut = l0op::Cast(zeroOut, out->GetDataType(), executor);
        CHECK_RET(zeroOut != nullptr, ACLNN_ERR_INNER_NULLPTR);
    }
    auto viewCopyOut = l0op::ViewCopy(zeroOut, out, executor);
    CHECK_RET(viewCopyOut != nullptr, ACLNN_ERR_INNER_NULLPTR);
    return ACLNN_SUCCESS;
}

} // namespace

aclnnStatus aclnnLinalgVectorNormGetWorkspaceSize(const aclTensor* self, const aclScalar* ord, const aclIntArray* dims,
                                                  bool keepDims, const aclDataType dtype, aclTensor* out,
                                                  uint64_t* workspaceSize, aclOpExecutor** executor)
{
    OP_CHECK_COMM_INPUT(workspaceSize, executor);

    L2_DFX_PHASE_1(aclnnLinalgVectorNorm, DFX_IN(self, ord, dims, keepDims, dtype), DFX_OUT(out));

    auto uniqueExecutor = CREATE_EXECUTOR();
    CHECK_RET(uniqueExecutor.get() != nullptr, ACLNN_ERR_INNER_CREATE_EXECUTOR);

    InputParams inputParams{self, ord, dims, dtype, out, keepDims};
    auto ret = CheckParams(inputParams);
    CHECK_RET(ret == ACLNN_SUCCESS, ret);

    if (self->IsEmpty() || out->IsEmpty()) {
        *workspaceSize = static_cast<uint64_t>(0);
        if (!out->IsEmpty()) {
            ret = HandleOutNotEmpty(out, uniqueExecutor.get());
            CHECK_RET(ret == ACLNN_SUCCESS, ret);
            *workspaceSize = uniqueExecutor->GetWorkspaceSize();
        }
        uniqueExecutor.ReleaseTo(executor);
        return ACLNN_SUCCESS;
    }

    float p = Ops::NN::AclnnUtil::IsRegbase() ? ord->ToFloat() : CalculateOrdValue(ord);
    auto epsilon = static_cast<float>(0);
    auto selfContiguous = l0op::Contiguous(self, uniqueExecutor.get());
    CHECK_RET(selfContiguous != nullptr, ACLNN_ERR_INNER_NULLPTR);

    // On Ascend910B or later chips: self (-> cast) -> LpNormV2 -> out
    if (Ops::NN::AclnnUtil::IsRegbase()) {
        aclnnLinalgVectorA5(selfContiguous, inputParams, uniqueExecutor.get());
    } else if (IsSocVersionSupportBf16()) {
        aclnnLinalgVectorA3(selfContiguous, inputParams, uniqueExecutor.get());
    } else {
        // on Ascend910A and Ascend310P chips: self -> fp32Self -> LpNormReduceV2 -> LpNormUpdateV2 -> Cast
        auto selfContiguousCast = l0op::Cast(selfContiguous, op::DataType::DT_FLOAT, uniqueExecutor.get());
        CHECK_RET(selfContiguousCast != nullptr, ACLNN_ERR_INNER_NULLPTR);

        auto reduceOut = l0op::LpNormReduceV2(selfContiguousCast, p, dims, keepDims, epsilon, uniqueExecutor.get());
        CHECK_RET(reduceOut != nullptr, ACLNN_ERR_INNER_NULLPTR);

        auto updateOut = l0op::LpNormUpdateV2(reduceOut, p, epsilon, uniqueExecutor.get());
        CHECK_RET(updateOut != nullptr, ACLNN_ERR_INNER_NULLPTR);

        auto castOut = l0op::Cast(updateOut, out->GetDataType(), uniqueExecutor.get());
        CHECK_RET(castOut != nullptr, ACLNN_ERR_INNER_NULLPTR);

        auto linalgViewCopyResult = l0op::ViewCopy(castOut, out, uniqueExecutor.get());
        CHECK_RET(linalgViewCopyResult != nullptr, ACLNN_ERR_INNER_NULLPTR);
    }

    *workspaceSize = uniqueExecutor->GetWorkspaceSize();
    uniqueExecutor.ReleaseTo(executor);
    return ACLNN_SUCCESS;
}

aclnnStatus aclnnLinalgVectorNorm(void* workspace, uint64_t workspaceSize, aclOpExecutor* executor, aclrtStream stream)
{
    L2_DFX_PHASE_2(aclnnLinalgVectorNorm);
    return CommonOpExecutorRun(workspace, workspaceSize, executor, stream);
}

#ifdef __cplusplus
}
#endif
