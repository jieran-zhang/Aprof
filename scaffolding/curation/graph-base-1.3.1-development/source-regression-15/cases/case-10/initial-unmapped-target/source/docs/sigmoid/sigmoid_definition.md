# Sigmoid definition

For every input element, `y = 1 / (1 + exp(-x))`. Output shape and dtype equal
the input. Supported dtypes are float16, float32, and bfloat16; half formats use
FP32 internal calculation before conversion back to the requested dtype. The
reference is `torch.sigmoid(x)`. `sigmoid(-inf)=0`, `sigmoid(+inf)=1`, and NaN
propagates.
