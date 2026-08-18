# NMS definition

Given legal `[x1,y1,x2,y2]` boxes and scores, repeatedly retain the highest-scoring remaining box and
suppress every remaining box whose IoU with it is not `<= iou_threshold`. IoU uses area union plus
`1e-6`, exactly as the source golden. Output is the retained original indices in descending score order.

The source `get_input` legalizes each coordinate pair and replaces tied scores with a deterministic
unique permutation; the case generator performs those same transformations. NaN IoU suppresses because
`~(iou <= threshold)` is true.
