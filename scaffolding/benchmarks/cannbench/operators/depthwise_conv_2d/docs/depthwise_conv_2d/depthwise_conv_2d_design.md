# Design

The output linear index space is divided evenly across available vector
cores. Each core decodes one index to `(n,c,oh,ow)`, derives input coordinates
from runtime stride, padding, and dilation, and reads only that channel's input
plane and filter directly from global memory. All convolution products and
accumulation execute in the device kernel; the host only validates metadata,
copies the three raw inputs, launches the kernel, and copies the output back.

Float32 results are written directly to GM. Float16 and bfloat16 results are
accumulated into a 1024-element float UB tile and converted once with
`AscendC::Cast`; the byte-counted `DataCopyPad` supports non-32-byte tails.
The live UB footprint is 4096 bytes for float accumulators plus 2048 bytes for
converted output. No atomic operation or cross-core state is required.

This is deliberately a correctness-only direct-invoke path for dav-2201. Its
scalar GM access pattern avoids layout transformations and large temporary
buffers, and is not presented as a performance-optimized convolution.
