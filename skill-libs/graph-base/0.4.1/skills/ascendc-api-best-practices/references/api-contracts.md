# API, memory and synchronization contracts

Read exact declarations and target guards in the installed CANN SDK. API signatures, maximum repeat counts, stride units and support sets vary by overload; examples below describe checks rather than an invented universal ABI.

## Copy, alignment and tails

Keep logical valid elements separate from aligned local allocation. Compute source/destination byte ranges for each core and tile before DataCopy. Check whether each stride/block-length field is in bytes, elements or data blocks for that overload. DataCopyPad can legalize some non-aligned transfers but does not authorize out-of-bounds GM access. Copy only valid GM elements and use explicit supported local padding/masks. Reject integer overflow in offsets or total byte products.

For strided/broadcast data, preserve per-axis mapping and validate the final partial block. A source or destination base being aligned does not imply every row is aligned. For NDDMA validate dimensions, strides, padding and target support against the chosen SDK.

## Queue and pipeline lifetime

AllocTensor/EnQue/DeQue/FreeTensor must form a valid lifetime for every path, including zero work, last tile and early exit. Reuse a queue slot only after the final consumer completes. TBuf scratch cannot alias a live producer or consumer merely because variable names differ. Count all live queue slots and temporary tensors in capacity.

For SetFlag/WaitFlag and cross-core flags, record producer pipe, consumer pipe, event identifier and iteration. Do not reuse an event while an earlier iteration still owns it. Every barrier participant must reach the barrier; work-skipping paths cannot omit required participants. A change from paired flags to another synchronization API requires target-specific evidence, not a generic architecture claim.

## Vector, Cast and reductions

Check masks, strides and API repeat limits per overload; where the declaration limits repeatTime to 255, split the operation legally instead of overflowing the field. Counter/normal mask modes have different lifetime and API requirements. Preserve masks across calls according to the SDK contract.

Changing Cast rounding, intermediate dtype, accumulation order, subnormal handling or approximation mode can change semantics. Validate special values and error thresholds from the existing operator checker. Reduce-with-index must preserve ties and index width; use actual aligned length only when padding values are neutral for that operation.

## Cube, matrix and host launch

Check platform/dtype support, transpose/layout, base tiles, accumulation type and API scratch before MatMul/GMM. MX/FP8 scale packing is part of the input contract; new target support does not permit lowering the user's dtype. MrgSort proposals and indices likewise follow the installed SDK layout.

Host and kernel must agree on argument order, uint64 tiling key representation, tiling structure alignment/size, workspace bytes and blockDim. Test the true compiled entry rather than a Python selector alone. In direct-launch projects, registration macros do not magically inject a tiling key; explicitly route the launcher or pass a key argument.

Device code must use target-supported language/library facilities. Do not introduce host-only std APIs, dynamic allocation or unsupported overloads into device functions. Build errors are typed evidence and require a repaired child candidate.
