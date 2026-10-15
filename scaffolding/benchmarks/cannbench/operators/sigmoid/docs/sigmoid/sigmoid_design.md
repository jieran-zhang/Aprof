# Sigmoid design

The host flattens arbitrary-rank tensors and partitions elements over available
vector cores. Each core streams 4096-element tiles through one input and one
output queue. FP16/BF16 tiles are cast to FP32, evaluated with
`AscendC::Sigmoid`, then cast back; FP32 is evaluated directly.

UB live storage is two raw queue buffers (`2*sizeof(T)` bytes per element), plus
two FP32 buffers for half dtypes (`8` bytes per element), while the remaining UB
is available to the high-level Sigmoid API stack buffer. Thus the explicit peak
is 12 bytes/element for FP32-intermediate half paths. GM tails use byte-counted
`DataCopyPad`, including non-32-byte-aligned official shapes; there is no UB to
UB copy path.
