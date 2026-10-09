# MaskedScale definition

For equal-shaped tensors, `y = (x * mask * scale).to(x.dtype)`. `x` and output
support float16, bfloat16, and float32. `mask` independently supports int8,
uint8, float16, bfloat16, and float32. Arbitrary ranks are flattened without
changing element order. NaN and infinity follow PyTorch/IEEE propagation.
