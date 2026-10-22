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
 * \file squared_relu_tiling.cpp
 * \brief squaredRelu_tiling source file
 */
#include "squared_relu_tiling.h"
#include <vector>
#include "register/op_impl_registry.h"
#include "register/tilingdata_base.h"
#include "op_host/tiling_base.h"
#include "op_host/tiling_templates_registry.h"
#include "log/log.h"

namespace optiling {

constexpr int32_t MAX_ELEMENT_NUM_EACH_CORE = 24 * 1024;

constexpr uint64_t TILING_KEY_HALF = 1;
constexpr uint64_t TILING_KEY_FLOAT = 2;
constexpr uint64_t TILING_KEY_BFLOAT16 = 3;

const static int32_t SIZE_16 = 16;
const static int32_t LENGTH_1024 = 1024;

class SquaredReluTiling {
public:
    explicit SquaredReluTiling(gert::TilingContext* context) : tilingContext(context){};
    ge::graphStatus RunBigKernelTiling();

private:
    ge::DataType dataType = ge::DT_UNDEFINED;
    gert::TilingContext* tilingContext = nullptr;
    gert::Shape inputShape;
    SquaredReluTilingData tilingData;

    int64_t inputShapeSize = 0;

    const int32_t workspaceSize_ = SIZE_16 * LENGTH_1024 * LENGTH_1024;

    inline int64_t CeilA2B(const int64_t a, const int64_t b)
    {
        if (b != 0) {
            return (a + b - 1) / b;
        } else {
            return a;
        }
    }

    int32_t GetNeedCoreNum(const int32_t coreNumPlatform)
    {
        int64_t needCoreNum = CeilA2B(inputShapeSize, MAX_ELEMENT_NUM_EACH_CORE);
        if (needCoreNum == 0) {
            needCoreNum = 1;
        }
        if (needCoreNum >= coreNumPlatform) {
            return coreNumPlatform;
        } else {
            return needCoreNum;
        }
    }
};

ge::graphStatus SquaredReluTiling::RunBigKernelTiling()
{
    // 获取输入矩阵
    auto srcTensor = tilingContext->GetInputTensor(0);
    if (srcTensor == nullptr) {
        return ge::GRAPH_FAILED;
    }

    // 获取数据类型
    auto temp = tilingContext->GetInputDesc(0);
    if (temp == nullptr) {
        return ge::GRAPH_FAILED;
    }
    dataType = tilingContext->GetInputDesc(0)->GetDataType();

    uint64_t tilingKey = 0;
    if (dataType == ge::DT_FLOAT16) {
        tilingKey = TILING_KEY_HALF;
    } else if (dataType == ge::DT_FLOAT) {
        tilingKey = TILING_KEY_FLOAT;
    } else if (dataType == ge::DT_BF16) {
        tilingKey = TILING_KEY_BFLOAT16;
    } else {
        return ge::GRAPH_FAILED;
    }
    tilingContext->SetTilingKey(tilingKey);

    // 获取输入的shape
    auto srcShape = tilingContext->GetInputShape(0);
    inputShape = srcShape->GetOriginShape();
    inputShapeSize = inputShape.GetShapeSize();

    auto platformInfo = platform_ascendc::PlatformAscendC(tilingContext->GetPlatformInfo());
    uint32_t needCoreNum = GetNeedCoreNum(platformInfo.GetCoreNumAiv());

    size_t* currentWorkspace = tilingContext->GetWorkspaceSizes(1);
    currentWorkspace[0] = workspaceSize_;

    tilingData.set_elementNum(inputShapeSize);
    tilingData.set_needCoreNum(needCoreNum);

    tilingData.SaveToBuffer(tilingContext->GetRawTilingData()->GetData(),
                            tilingContext->GetRawTilingData()->GetCapacity());
    tilingContext->GetRawTilingData()->SetDataSize(tilingData.GetDataSize());

    tilingContext->SetBlockDim(needCoreNum);
    return ge::GRAPH_SUCCESS;
}

static ge::graphStatus TilingPrepare4SquaredReluTiling([[maybe_unused]] gert::TilingParseContext* context)
{
    return ge::GRAPH_SUCCESS;
}

static ge::graphStatus TilingSquaredReluTiling(gert::TilingContext* context)
{
    SquaredReluTiling tilingObject(context);
    return tilingObject.RunBigKernelTiling();
}

IMPL_OP_OPTILING(SquaredRelu)
    .Tiling(TilingSquaredReluTiling)
    .TilingParse<SquaredReluCompileInfo>(TilingPrepare4SquaredReluTiling);
} // namespace optiling