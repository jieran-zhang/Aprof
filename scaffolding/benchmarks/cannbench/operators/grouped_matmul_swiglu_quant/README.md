# grouped_matmul_swiglu_quant

Direct Ascend C implementation for the cann-bench level4 task. Build and run one original case with `./run.sh --case 12 --device 0`, or all cases with `./run.sh --all --device 0`. The implementation uses an AIC Cube grouped int8 matmul and an AIV fused dequant/SwiGLU/per-token quant kernel; it does not call ACLNN or compute results on the host.
