# Gelu flash design

The tensor is flattened and split over available vector cores. Each core loops
over 1024-element tiles. DMA uses `DataCopyPad` for arbitrary tails. Input is
promoted to FP32 in UB, either the erf or tanh formula is evaluated, and the
result is converted back to the source dtype. The tanh formula uses an
algebraically equivalent stable logistic evaluation to avoid cancellation for
large negative inputs, with explicit FP32 probability-grid rounding matching
the PyTorch vector golden. UB live storage per tile is two raw I/O queues,
three FP32 vectors, a mask, and five FP32 vectors reserved for Erfc.

The exact mode uses the equivalent `0.5*x*erfc(-x/sqrt(2))` form. This avoids
the negative-tail cancellation in `1+erf(x/sqrt(2))`; the shared Erfc workspace
contains five FP32 vectors.

This is intentionally a correctness-first flash implementation. No profiling
or performance tuning is part of this pass.

The official cases constrain shape, dtype, mode, and value range but do not
provide fixed input tensors. Float32 tanh cases therefore use deterministic
stratified anchors covering both range endpoints, the nonlinear center, and
saturation regions. Other finite ranges use deterministic seeded uniform data.
