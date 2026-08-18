# engram_gate_fusion definition

For `keys, hidden_states: [B,L,HC,D]` and `value: [B,L,D]`, the operator
computes FP32 RMSNorms of keys and hidden states, their scaled dot-product,
and

`gate = sigmoid(sign(raw) * sqrt(max(abs(raw), 1e-6)))`.

It broadcasts `gate` over `value`, applies another FP32 RMSNorm, interprets
the result as `[B,HC*D,L]`, and performs bias-free causal dilated depthwise
cross-correlation with weights `[HC*D,1,K]`. The final output is
`value_gated + silu(conv)` converted to BF16.

The optional BF16 `conv_state` is `[B,HC*D,(K-1)*dilation]`. It precedes the
current normalized gated values in Decode mode. Without state, the same
prefix is zero. `conv_state_out` is the last state-length slice of that
concatenation, including zero prefix when a Prefill sequence is shorter than
the state length.

All activation inputs and outputs are BF16; norm and convolution weights are
FP32. `HC`, `D`, and `K` must agree with the attributes and linked tensor
shapes. `L=1` requires state. The original matrix covers HC 2/4/8, D
256/512/769/1024, K 4/8, dilation 1/3, Prefill and stateful Decode.
