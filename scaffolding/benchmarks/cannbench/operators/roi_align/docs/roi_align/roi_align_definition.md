# ROIAlign definition

Source: `third_party/cann-bench/tasks/level3/roi_align`.

For every ROI `(batch, x0, y0, x1, y1)`, coordinates are multiplied by
`spatial_scale` and shifted by `-0.5` when `aligned=true`. The ROI is divided into
`outputHeight × outputWidth` bins. Each bin averages bilinear samples from the NCHW
feature map. A positive `sampling_ratio` fixes both grid dimensions; zero selects
`ceil(roi_size / pooled_size)` independently for each ROI.

Output shape is `[num_rois, C, outputHeight, outputWidth]` and dtype matches the
feature input. The official cases cover float16/float32, fixed and adaptive sampling,
aligned and unaligned coordinates, irregular channel/spatial dimensions, NaN, Inf,
zero, and large finite values. Boxes are regenerated exactly as the task's
`get_input`: legal integer batch indices and nondegenerate in-bounds coordinates.

The torchvision CPU golden performs all operations in the input dtype. Therefore
the FP16 path rounds geometry, weights, products, accumulation, and final division
at every scalar operation; FP32 retains FP32 throughout.
