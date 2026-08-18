#include <torch/extension.h>
#include <torch/library.h>
#include "ops.h"

namespace {
TORCH_LIBRARY_FRAGMENT(npu, m) {
    m.def("apply_adam_w(Tensor var, Tensor grad, Tensor m, Tensor v, float lr, float beta1, float beta2, "
          "float weight_decay, float epsilon=1e-8, int step=1, bool maximize=False) -> Tensor");
}
TORCH_LIBRARY_IMPL(npu, PrivateUse1, m) {
    m.impl("apply_adam_w", TORCH_FN(ascend_kernel::apply_adam_w_torch));
}
at::Tensor apply_adam_w_meta(const at::Tensor& var, const at::Tensor&, const at::Tensor&, const at::Tensor&,
    double, double, double, double, double, int64_t, bool) { return at::empty_like(var); }
TORCH_LIBRARY_IMPL(npu, Meta, m) { m.impl("apply_adam_w", &apply_adam_w_meta); }
}
