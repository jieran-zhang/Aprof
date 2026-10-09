#pragma once
#include <torch/extension.h>

namespace ascend_kernel {
at::Tensor apply_adam_w_torch(const at::Tensor& var, const at::Tensor& grad,
    const at::Tensor& m, const at::Tensor& v, double lr, double beta1, double beta2,
    double weight_decay, double epsilon, int64_t step, bool maximize);
}
