# Dilation2D definition

For NHWC input and per-channel `[KH,KW,C]` filter, each output is the maximum over filter positions
of a float16 input sample plus the corresponding float16 filter value. Stride and sampling rate apply
to spatial dimensions. SAME output uses ceil(input/stride) and inferred asymmetric padding; VALID uses
the effective dilated filter extent. Padding values are negative infinity.

FP16 addition occurs before maximum. NaN propagates through maximum, including the boundary case
`-inf + +inf` from padding and an infinite filter.
