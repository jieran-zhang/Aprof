# softmax definition

For every slice along normalized `dim`, softmax returns
`exp(x - max(x)) / sum(exp(x - max(x)))` in the input dtype and shape. Negative
dimensions are supported. FP16, FP32, and BF16 inputs are supported. NaN, any
positive infinity, or an all-negative-infinity slice produces NaN across that
slice; negative infinity alongside finite values produces zero at that site.
