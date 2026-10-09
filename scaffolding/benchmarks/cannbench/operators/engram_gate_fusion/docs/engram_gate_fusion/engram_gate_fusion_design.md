# engram_gate_fusion design

The direct-invoke executable launches two ordered Ascend C AIV kernels on one
ACL stream. Stage 1 partitions complete `[B,L,HC]` rows. It directly reduces
BF16 activations with FP32 weights for the two RMSNorm denominators and gated
dot product, applies vector `Sqrt`/`Exp`, forms FP32 gated values, performs the
third RMSNorm, and writes two FP32 device workspaces. There is no host-side
tensor math.

Stage 2 partitions output elements. It reads normalized current values or the
optional BF16 history according to causal index
`l-(K-1-k)*dilation`, accumulates the FP32 depthwise convolution, applies SiLU,
adds the FP32 gated residual, and rounds once to BF16. It separately emits the
updated state from the same device workspace/history mapping.

UB use per Stage-1 core is 8,448 bytes (256-byte transcendental scratch plus
two 4,096-byte FP32 row buffers). Stage 2 uses 4,352 bytes (256-byte
transcendental scratch plus separate 2,048-byte BF16 output and state buffers).
Row partitions are rounded to eight rows, while BF16 output/state partitions
are rounded to 16 elements, preventing adjacent cores from sharing a 32-byte
GM write unit. Non-aligned D=769 rows and state length 9 are copied through
LocalTensor + `DataCopyPad`; this is required for deterministic device writes.

The FP32 gated and normalized workspaces are device-only intermediates. The
host only validates shapes/dtypes implied by the fixed CLI, allocates buffers,
copies declared inputs, launches both compiled kernels, and copies outputs.
No ACLNN call, CPU reference computation, simulator, or profiling path exists.
