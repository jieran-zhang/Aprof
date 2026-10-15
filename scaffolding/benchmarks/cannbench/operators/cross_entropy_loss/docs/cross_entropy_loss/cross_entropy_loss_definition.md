# CrossEntropyLoss definition
For channel-first logits `(N,C,...)` and hard labels `(N,...)`, each valid position is `max + log(sum(exp(x-max))) - x[target]`. Labels equal to ignore_index contribute zero and are excluded from mean count. Reduction is none, sum, or mean. Original 20 cases use int64 hard labels and float16/float32/bfloat16 logits.
