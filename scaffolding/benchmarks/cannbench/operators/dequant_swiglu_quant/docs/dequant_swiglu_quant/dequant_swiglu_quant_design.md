# Design

Vector cores split the token rows evenly. Each core loads one row directly from GM and converts both halves to float32 UB tensors. The int32 path applies both dequant scales on device. `AscendC::Exp` computes the sigmoid exponential; remaining SwiGLU arithmetic, optional `[1,H]` scale broadcast, row maximum, scale and exact round-to-even/clamp are also device-side. Only final int8 values and float32 scales are written to GM.

Two aligned float32 UB buffers of `H` elements are live (`8*aligned(H)` bytes total; at maximum H=4097 this is 32,832 bytes). There are no host-computed tensor values. Host work is limited to validation-independent file I/O, allocation, tiling, launch, and output copy. Tails are handled by scalar indexed access; the vector Exp count is the exact H.
