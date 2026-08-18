# GRU Ascend C design

The host reads tensors only, allocates device memory, creates Cube tilings, and
launches kernels. It never computes gates or hidden states and calls no ACLNN
operator.

- `gru_canonical` converts batch-first input to canonical `(S,B,I)` device data.
- FP16/BF16 gate products use `MatmulImpl` with ND A and transposed ND B and
  FP32 C: `(B,K) @ (3H,K)^T`. FP32 uses a self-compiled scalar AIC matmul.
- Separate device tiling buffers are retained for input and recurrent matmuls,
  so asynchronous launches cannot observe overwritten tiling metadata.
- `gru_update` is an AIV kernel. It constructs reset/update/new preactivations
  in FP32 UB tensors, applies vector `Exp`, `Reciprocal`, and `Tanh`, writes the
  recurrent hidden tensor, logical sequence output, and final `hn`.
- One recurrent hidden state is reused per direction. Two sequence buffers
  ping-pong across layers. Direction transitions synchronize before reusing
  hidden/tiling storage.
- AIV kernels guard `GetSubBlockIdx()!=0`, preventing parent/subcore duplicate
  writes on dav-2201.

Maximum update UB use is three `B*H` FP32 tensors. The largest original case has
`B*H=4096`, using 48 KiB for these tensors. Gate matrices remain in GM.
Correctness is prioritized; no profiling or performance tuning was requested.
