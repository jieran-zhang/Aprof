# Scatter troubleshooting

## [Phase 7] FP16 add accumulator and GM scalar write granularity

The large FP16 `add` case initially exposed two dav-2201 issues: unsupported scalar half conversion paths produced zeros, and scalar writes to a contiguous half buffer only preserved part of each 32-byte region. The final implementation uses a three-launch FP32 accumulator path, vector Cast plus DMA for half initialization/finalization, explicit launch synchronization, and a cache clean/invalidate after accumulator reduction.

This restored exact output for the 8192 x 8192 case with 33,554,432 updates and preserved exact results for the remaining overwrite, add, multiply, amin, and amax cases.
