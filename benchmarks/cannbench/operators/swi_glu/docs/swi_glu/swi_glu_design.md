# SwiGLU flash design

The row-major output is divided into contiguous ranges across available vector
cores. Let `segmentLength = (shape[dim] / 2) * product(shape[dim+1:])`.
For output index `o`, `group = o / segmentLength`, and the two source addresses
are `x0 = o + group * segmentLength` and `x1 = x0 + segmentLength`.

Each core advances in tiles of at most 4096 elements. A tile is clipped at a
segment boundary, so both DMA inputs and the output are contiguous even when
the split axis is not the last axis. The vector sequence is negate, Exp, add
one, divide, then multiply by the gate. Float16 and bfloat16 are cast to float32
in UB before the sequence and cast back afterward.

This is an accuracy-first flash implementation. No profiling or performance
optimization is part of this pass.
