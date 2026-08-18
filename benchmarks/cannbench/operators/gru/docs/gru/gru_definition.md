# GRU definition

The interface is the task schema:

`gru(x, weight_ih[], weight_hh[], inputSize, hiddenSize, numLayers, bias, batchFirst, dropout, bidirectional, bias_ih[]?, bias_hh[]?, h0?) -> (y, hn)`.

PyTorch gate rows are ordered reset, update, new. For each layer and direction:

```text
r = sigmoid(W_ir x + b_ir + W_hr h + b_hr)
z = sigmoid(W_iz x + b_iz + W_hz h + b_hz)
n = tanh(W_in x + b_in + r * (W_hn h + b_hn))
h = (1-z) * n + z * h
```

Forward directions iterate `0..S-1`; reverse directions iterate `S-1..0` but
write results at the logical sequence position. A later layer consumes the
concatenated forward/reverse output. `batchFirst` changes only external layout.
Missing `h0` means zero. Missing bias tensors with `bias=false` means zero.
Dropout is inactive because the authoritative golden runs its GRU in eval mode.
Input and output support FP16, BF16, and FP32. Shapes, list ordering, odd feature
sizes, long sequences, bidirectionality, up to three layers, and explicit h0
come directly from the 20 task cases.
