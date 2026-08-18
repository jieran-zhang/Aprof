# Exp design

The host flattens arbitrary-rank tensors and partitions their elements over the
available vector cores. Each core streams 4096-element tiles through one input
and one output queue. FP16/BF16 tiles are cast to FP32, transformed with
`Muls -> Adds -> Exp`, and cast back; FP32 is transformed directly. Tail DMA
uses `DataCopyPad`, so non-32-byte-aligned official cases are supported.
