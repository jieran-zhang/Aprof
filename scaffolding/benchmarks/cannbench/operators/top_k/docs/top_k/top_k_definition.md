# TopK definition

For every slice along `dim`, return the `k` largest values when `largest=true`, otherwise the `k`
smallest values, in sorted order. The value output preserves input dtype; indices are int64 positions
within the selected axis. Negative dimensions are normalized by rank. Equal-value index order is not
specified: indices are valid when gathering them from input reproduces the value output.

Supported original cases cover rank 1–5, k up to 2048, non-last axes, FP16/BF16/FP32 and signed or
unsigned integer inputs. PyTorch `torch.topk` is the reference.
