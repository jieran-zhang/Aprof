# conv_2d definition

For NCHW input `x`, OIHW filter `w`, and channel bias `b`:

`y[n,co,oh,ow] = b[co] + sum_ci,kh,kw x[n,ci,oh*sh+kh*dh-pt,ow*sw+kw*dw-pl] * w[co,ci,kh,kw]`, with out-of-range input coordinates treated as zero.

Pads are `[top,bottom,left,right]`; strides and dilations are two-element lists. Output spatial dimensions use the standard floor formula. Inputs and output share FP16, BF16, or FP32 dtype. Contraction accumulation is FP32 and the output cast occurs after bias. NaN and infinity propagation follows floating multiply/add semantics.

The original unmodified task reference calls `torch.nn.functional.conv2d` and remains recorded as a diagnostic. On this aarch64 host its default oneDNN `indirect_gemm:acl` BF16 result is not a valid mathematical reference for large-K cancellation (an audited case6 element is `0.010009765625` versus `8.0` from FP32 accumulation). BF16 primary correctness therefore converts inputs, weights, and bias to FP32, accumulates in FP32, and casts once to BF16. For device-selected low-magnitude outputs, the reference fixes the reduction order to `ci -> kh -> kw`, matching the definition rather than a private host-GEMM reduction tree.
