# Definition

For input `x[N,C,D,H,W]` and output size `(OD,OH,OW)`, each output is the
arithmetic mean over the adaptive window

`[floor(od*D/OD), ceil((od+1)*D/OD))` and likewise for H and W.

The output shape is `[N,C,OD,OH,OW]` and its dtype equals the input dtype.
The supported input types are float16, float32, and bfloat16. All window sums
accumulate in float32, followed by one conversion to the output dtype. NaN and
Inf propagate according to IEEE floating-point arithmetic. Both downsampling
and the overlapping-window behavior for output dimensions larger than input
dimensions are supported.
