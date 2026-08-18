# Troubleshooting

## Direct TBuf reuse requires cross-pipeline synchronization

- Symptom: the first real-NPU case launched successfully, but `xOut` and scale
  contained blocks of zeros and non-finite garbage.
- Cause: barriers restricted to MTE2 or MTE3 did not establish the required
  MTE2-to-vector and vector-to-MTE3 dependency before a directly reused TBuf.
- Fix: use `PipeBarrier<PIPE_ALL>` at direct DMA/compute reuse boundaries.
- Prevention: prefer queues for overlapped DMA; when correctness-first code
  directly reuses TBuf storage, explicitly synchronize all participating pipes.

## Core output boundaries must share a 64-byte alignment

- Symptom: after fixing pipeline dependencies, xOut was exact but roughly half
  the scale rows were zero and y differed in the same rows.
- Cause: 13-row core partitions put adjacent cores' FP32 scalar scale stores in
  the same 64-byte cache line, allowing short-write overlap.
- Fix: align `rowsPerBlock` to the LCM of scale (16 rows), int8-y row, and
  two-byte-xOut row 64-byte alignment requirements.
- Prevention: derive a joint row boundary alignment for every GM output, not
  merely the largest tensor.

## Vector output needs a VECOUT queue dependency

- Symptom: xOut and scale became accurate, but sporadic quantized rows exactly
  duplicated the preceding row.
- Cause: a VECCALC TBuf used directly as the result of `AscendQuant` did not
  reliably hand off completion to the MTE3 copy.
- Fix: allocate y from a VECOUT TQue and use EnQue/DeQue before DataCopyPad.
- Prevention: use TQue event semantics for vector-produced GM outputs.

## Apply extreme-range quant scale before AscendQuant

- Symptom: case 11 had exact xOut and accurate scale, but expected moderate
  int8 values saturated to +/-127 when unscaled normalized values exceeded the
  FP16 finite range.
- Cause: `AscendQuant<float>` uses an internal FP16 conversion before its scale
  argument, so large finite FP32 y_norm overflowed too early.
- Fix: multiply y_norm by inverseScale in FP32 on device, then invoke
  AscendQuant with scale 1.0 while values are bounded near [-127,127].
- Prevention: pre-scale FP32 explicitly before conversion-based quantization
  whenever the unscaled domain can exceed 65504.
