# Conv3DBackpropFilter definition

For `x[N,Cin,D,H,W]` and upstream gradient `g[N,Cout,Do,Ho,Wo]`, the output is
`dw[Cout,Cin/groups,Kd,Kh,Kw]`:

```text
dw[co,ci,kd,kh,kw] = sum(n,od,oh,ow)
  x[n, group(co)*CinGroup+ci,
    od*sd+kd*dd-padFront,
    oh*sh+kh*dh-padTop,
    ow*sw+kw*dw-padLeft]
  * g[n,co,od,oh,ow]
```

Terms whose input spatial coordinate is outside the tensor are omitted. `group(co) = co / (Cout/groups)`. Output spatial dimensions use both sides of each six-element pad list; indexing subtracts the front/top/left pad, matching the authoritative torch golden. The output shape is exactly `filter_size`.

Both inputs have the same FP16 or BF16 dtype and output has that dtype. Products are accumulated in FP32 by the Cube path and converted once at the output. For BF16, inputs are explicitly widened before Cube because this is both reproducible and consistent with the mathematical contraction. `groups`, non-aligned channels, stride, dilation, 1/3/5 kernels, zero, NaN and Inf are covered by the original cases.

The primary oracle is `conv3d_weight(x.float(), grad.float(), ...).to(input_dtype)`. The native-dtype torch call remains a diagnostic because the aarch64 CPU FP16 convolution backend can materially disagree with the mathematical contraction under cancellation; this is documented in troubleshooting. For ill-conditioned outputs only, the verifier also computes `sum_abs_products` and the exact valid term count `K`. Two FP32 reduction orders may differ by at most `2*gamma_K*sum_abs_products`, where `gamma_K=K*eps/(1-K*eps)`. Relative error is waived only when both the oracle magnitude and device-oracle difference lie inside that per-output bound.
