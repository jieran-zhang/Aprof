# GCD001 integer boundary reclassification

The original GCD001 feedback remains an open infrastructure block. Its five
native boundary processes completed and dispatched as declared, but the CPU
guard reported numeric mismatches. The reviewed original golden computes
int16 inputs in int32 and narrows the result. For the frozen input
`gcd(-32768, 0)`, its exact int16 output is `-32768`; the retained candidate
output is `0`.

`level2_failure_classification.py` now recognizes only this candidate, the
reviewed guard/case/golden hashes, the registered build and dispatch plan, all
five successful native execution records, and the exact first-case input,
reference, and output bytes. It executes no task code or hardware. A changed
byte or missing record returns an infrastructure block. The proof attributes
the retained mismatch, not the instruction that caused it. As with older
numeric guard evidence, the output bytes were not independently presealed at
execution time.

After freezing the updated engineering, use `level2_feedback_recovery.py`
with `--operator gcd --candidate gcd001 --blocked-observation
gcd001-feedback-01 --recovery-id reclassification-01`. Inspect first, then
apply. This appends a new closed observation while keeping the old blocked
feedback and all measured costs. It neither reruns GCD001 nor adds an attempt.
