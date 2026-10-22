# add_rms_norm_dynamic_quant

Standalone Ascend C direct-invocation benchmark for the authoritative level-3
`AddRmsNormDynamicQuant` task. It fuses FP32 residual addition, RMSNorm and
per-token symmetric int8 dynamic quantization on Ascend910 (`dav-2201`).

```bash
ASCEND_RT_VISIBLE_DEVICES=3 ASCEND_DEVICE_ID=3 ./run.sh --all --device 0
```

Physical device 3 is mapped to logical device 0 by `ASCEND_RT_VISIBLE_DEVICES`.
The original 20 cases are generated from `scripts/cases.py`; per-case evidence
is written under `build/cases`, and `results.json` is the aggregate record.
