# Dilation2D design

The host computes output shape and SAME padding only. Device cores own cache-line-aligned contiguous
output ranges. For every output linear index, the kernel decodes `[batch,oy,ox,channel]`, visits every
filter coordinate, computes signed input coordinates, substitutes FP16 negative infinity when outside
the image, performs FP16 addition, and applies NaN-propagating maximum. Input/filter/output remain in GM;
no host-side output calculation or precomputation occurs. Window size is at most 25 in original cases.
