# Transpose design

The host validates shape/perm, computes row-major input strides and permuted output shape, then
launches up to the available vector-core count. Each core owns a contiguous output interval.
For each output linear index the kernel performs mixed-radix decomposition using output shape,
maps each coordinate through `perm`, and accumulates the source linear offset using input strides.

No UB workspace or arithmetic instruction is needed. Dispatch is by storage width (1/2/4/8 bytes),
so all supported dtypes, including BF16 and special floating values, are copied exactly. All indices,
strides and element counts use 64-bit integers for the largest original cases.
