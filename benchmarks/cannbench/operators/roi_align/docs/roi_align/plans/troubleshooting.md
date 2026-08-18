# Troubleshooting

## [Phase 6] dav-2201 rejects float/unsigned casts

**现象：** The first kernel build rejected device-side casts between float and
`uint32_t`/`uint64_t`.
**根因：** dav-2201 AICore scalar conversion only accepts the signed integer form in
this compilation path.
**解决方案：** Use `int64_t` for coordinate/grid conversion and precompute float
pooled dimensions in host tiling.
**经验：** Coordinate kernels should use signed scalar indices around float casts.
**预防：** Avoid float/unsigned casts in dav-2201 device code.

## [Phase 7] FP16 golden rounds every operation

**现象：** FP32 case 3 was bit exact, while initial FP16 case 1 matched the FP32
reference cast to half but differed from torchvision by up to 0.0463.
**根因：** torchvision's FP16 CPU ROIAlign executes geometry, interpolation weights,
products, accumulation, and division with half rounding at each operation.
**解决方案：** Added software FP16 RNE and explicit rounding after every semantic
operation. Case 1 then became bit exact over 1,605,632 elements.
**经验：** Output-only casting does not reproduce dtype-native compound kernels.
**预防：** Compare dtype-native golden with FP32-then-cast before choosing arithmetic.

## [Phase 7] Adaptive-grid expression order

**现象：** Fixed-ratio FP16 became exact, but aligned adaptive case 4 differed.
**根因：** The golden evaluates `(sample + 0.5) * bin_size / grid`; computing
`(bin_size / grid) * (sample + 0.5)` changes half rounding for non-power-of-two grids.
**解决方案：** Matched the golden multiplication/division order exactly.
**经验：** Algebraically equivalent expressions are not FP16-equivalent.
**预防：** Preserve source expression order around every FP16 rounding point.
