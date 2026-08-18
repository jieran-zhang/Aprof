# Mish definition

For every input element, `y = x * tanh(log(1 + exp(x)))`. Input and output
have identical shape and dtype. Supported dtypes are float16, float32, and
bfloat16. NaN propagates; positive infinity maps to positive infinity and
negative infinity produces NaN, matching `torch.nn.functional.mish`.
