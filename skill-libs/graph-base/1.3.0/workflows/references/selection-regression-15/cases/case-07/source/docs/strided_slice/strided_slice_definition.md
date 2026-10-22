# StridedSlice definition

## Source and interface

Source: `third_party/cann-bench/tasks/level3/strided_slice`.

The operator returns a materialized tensor containing the values selected by a
TensorFlow-style multidimensional strided slice. Inputs are `x`, `begin`, `end`,
`strides`, `begin_mask`, `end_mask`, `ellipsis_mask`, `shrink_axis_mask`, and
`new_axis_mask`. Output dtype equals input dtype.

## Semantics

For every normal input dimension `d`, the selected coordinates are
`begin[d], begin[d] + stride[d], ...` before the exclusive end. Negative begin/end
values are adjusted by the dimension size exactly as in the supplied Python golden.

- `begin_mask`: replace begin with the first coordinate for the stride direction.
- `end_mask`: replace end with the exclusive boundary for the stride direction.
- `shrink_axis_mask`: select one coordinate and omit that dimension from output.
- `new_axis_mask`: insert an output dimension of size one without consuming input.
- `ellipsis_mask`: consume the number of full input dimensions implied by the
  remaining parameters; at most one ellipsis bit is allowed.

The official golden adjusts an explicit `end=-1` to `dim-1` before constructing
the Python slice. This is distinct from spelling `x[:-1]` directly and is mirrored
by both the host tiling and verifier.

## Dtypes and edge cases

The benchmark cases cover `float16`, `bfloat16`, `float32`, `int32`, and `int64`.
The kernel performs a storage-width copy and therefore preserves every bit without
floating-point arithmetic. Input ranks 1 through 4 are exercised; the metadata
format supports ranks up to 8. A zero stride, multiple ellipses, invalid shrink
coordinate, or zero-sized output is rejected by this direct-invoke runner.

## Reference pseudocode

```text
parse parameters into output_shape, source_base, source_step[]
for output_linear in [0, product(output_shape)):
    rem = output_linear
    source = source_base
    for axis from last output axis to first:
        coord = rem % output_shape[axis]
        rem //= output_shape[axis]
        source += coord * source_step[axis]
    output[output_linear] = input[source]
```

There is no iterative floating-point accumulation and hence no accumulation-error
risk.
