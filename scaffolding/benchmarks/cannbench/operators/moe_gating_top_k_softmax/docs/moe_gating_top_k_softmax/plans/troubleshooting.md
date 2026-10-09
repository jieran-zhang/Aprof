# Troubleshooting

## dav-2201 compile count type

- Symptom: `AscendC::Exp` rejected a `uint64_t` count loaded directly from GM tiling.
- Cause: the API requires a const `int32_t&`, and the GM-qualified value cannot bind to it.
- Fix: validate dimensions in host tiling, then materialize local `int32_t` expert and TopK counts.
- Prevention: pass local API-native count values to vector APIs rather than GM struct members.

## Expert/value validation precision

- Symptom: FP32 case 15 initially failed only `expert_value_gather_match`, despite MERE `1.74e-8`, MARE `1.79e-7`, and valid indices.
- Cause: the first verifier required bitwise equality between CPU softmax values and device softmax values for the gather association check.
- Fix: retain the association check but apply the task's dtype-specific MERE/MARE limits, matching the authoritative precision contract.
- Prevention: use exact checks for integer contracts and documented numerical thresholds for floating-point device computations.
