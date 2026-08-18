# MaskedScale design

The host partitions the flattened input across available vector cores. Each core
streams 4096-element tiles through separate `x`, `mask`, and output queues.
Inputs are converted to FP32, multiplied, scaled, and converted to `x` dtype.
Integer masks use an int8/uint8-to-FP16-to-FP32 cast chain supported by
`dav-2201`. `DataCopyPad` handles every non-32-byte-aligned tail.
