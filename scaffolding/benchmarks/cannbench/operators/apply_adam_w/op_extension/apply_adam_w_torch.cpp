#include <cstdint>
#include "acl/acl.h"
#include "tiling/platform/platform_ascendc.h"
#include <torch/extension.h>
#include "torch_npu/csrc/core/npu/NPUStream.h"
#include "apply_adam_w_common.h"

extern "C" void apply_adam_w_kernel(uint32_t blockDim, void *l2Ctrl, aclrtStream stream,
    uint8_t *var, uint8_t *grad, uint8_t *m, uint8_t *v, uint8_t *y, uint8_t *tiling);

namespace ascend_kernel {
at::Tensor apply_adam_w_torch(const at::Tensor& var, const at::Tensor& grad,
    const at::Tensor& m, const at::Tensor& v, double lr, double beta1, double beta2,
    double weight_decay, double epsilon, int64_t step, bool maximize)
{
    TORCH_CHECK(var.is_privateuseone() && grad.is_privateuseone() && m.is_privateuseone() && v.is_privateuseone(),
                "all inputs must be NPU tensors");
    TORCH_CHECK(var.is_contiguous() && grad.is_contiguous() && m.is_contiguous() && v.is_contiguous(),
                "all inputs must be contiguous");
    TORCH_CHECK(var.sizes() == grad.sizes() && var.sizes() == m.sizes() && var.sizes() == v.sizes(),
                "all input shapes must match");
    TORCH_CHECK(var.scalar_type() == grad.scalar_type() && var.scalar_type() == m.scalar_type() && var.scalar_type() == v.scalar_type(),
                "all input dtypes must match");
    uint32_t dtype;
    if (var.scalar_type() == at::kFloat) dtype = APPLY_ADAM_W_FLOAT32;
    else if (var.scalar_type() == at::kHalf) dtype = APPLY_ADAM_W_FLOAT16;
    else if (var.scalar_type() == at::kBFloat16) dtype = APPLY_ADAM_W_BFLOAT16;
    else TORCH_CHECK(false, "only float32, float16 and bfloat16 are supported");
    TORCH_CHECK(var.numel() > 0, "empty tensors are not supported");
    int32_t device = -1; TORCH_CHECK(aclrtGetDevice(&device) == ACL_SUCCESS, "aclrtGetDevice failed");
    int64_t cores = 0, ub = 0;
    TORCH_CHECK(aclrtGetDeviceInfo(device, ACL_DEV_ATTR_VECTOR_CORE_NUM, &cores) == ACL_SUCCESS, "core query failed");
    TORCH_CHECK(aclrtGetDeviceInfo(device, ACL_DEV_ATTR_UBUF_PER_VECTOR_CORE, &ub) == ACL_SUCCESS, "UB query failed");
    if (ub <= 0) {
        uint64_t platformUb = 0;
        auto platform = platform_ascendc::PlatformAscendCManager::GetInstance();
        platform->GetCoreMemSize(platform_ascendc::CoreMemType::UB, platformUb);
        ub = static_cast<int64_t>(platformUb);
    }
    auto tiling = ComputeApplyAdamWTiling(var.numel(), dtype, cores, ub, lr, beta1, beta2,
        weight_decay, epsilon, step, maximize);
    auto y = at::empty_like(var);
    auto tilingTensor = at::empty({static_cast<int64_t>(sizeof(tiling))}, var.options().dtype(at::kByte));
    TORCH_CHECK(aclrtMemcpy(tilingTensor.mutable_data_ptr(), sizeof(tiling), &tiling, sizeof(tiling),
        ACL_MEMCPY_HOST_TO_DEVICE) == ACL_SUCCESS, "tiling H2D failed");
    auto stream = c10_npu::getCurrentNPUStream().stream(true);
    apply_adam_w_kernel(tiling.blockNum, nullptr, stream,
        reinterpret_cast<uint8_t*>(var.mutable_data_ptr()), reinterpret_cast<uint8_t*>(grad.mutable_data_ptr()),
        reinterpret_cast<uint8_t*>(m.mutable_data_ptr()), reinterpret_cast<uint8_t*>(v.mutable_data_ptr()),
        reinterpret_cast<uint8_t*>(y.mutable_data_ptr()), reinterpret_cast<uint8_t*>(tilingTensor.mutable_data_ptr()));
    return y;
}
}
