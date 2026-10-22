# Frozen blind fact grading protocol

Grade one masked answer against its case gold and the frozen source/API corpus. The grader must not see arm A/B, skill contents, repeat identity, sibling answers, prior scores, teacher material, or model self-reported confidence. Keep the answer byte-for-byte unchanged. Assign a neutral `answer_id`; preserve the arm mapping outside the grading input until all scores are locked.

Each case has three equally weighted dimensions: algorithm_strategy, execution, hardware. Each dimension has 10 available points; a case has 30 points. The six-case maximum is 180 for each complete suite repeat. Each fact has a stable `CUxx.*` ID and integer weight. Concrete facts, reasoning and evidence earn points; length, formatting, fluency, citation count and terminology imitation do not.

Use exactly one status per fact:

- `correct`: the answer explicitly supports the complete fact or a semantically equivalent statement; earn the full weight.
- `partial`: the answer supports an independently meaningful subset of the fact, omits the remaining subset, and does not contradict it; earn half the weight. Record the supported subset.
- `wrong`: the answer makes an explicit claim contradicting the fact/source/contract, including wrong units, wrong actual dispatch, or wrong physical memory; earn zero. Cite the conflicting answer span.
- `omitted`: the answer supplies no assessable claim about the fact; earn zero. Do not infer knowledge from generic background.
- `unsupported`: the answer substitutes an unverified assertion for the required fact, for example measured speed, a deterministic OOB output, a hardware crash, or portability claimed from a macro alone; earn zero. Record what evidence would be needed.

A short answer can earn full credit. A long generic explanation cannot earn a fact unless its content resolves the current implementation and workload. Source filename/line references are helpful for audit, but absence of a formal citation is not itself a deduction when a correct concrete explanation is present. Correct uncertainty statements may satisfy a gold fact explicitly about evidence boundaries; blanket uncertainty does not replace facts the source does establish.

A `critical_error` cap applies only to an explicit triggering claim. Omission does not trigger a cap. For each dimension, first sum fact credits and then apply the smallest triggered cap for that dimension. Do not subtract an additional penalty. Record the exact answer span and the critical ID. If no listed trigger applies, do not invent a new cap after seeing A/B results.

The gold's `acceptable_unknowns` bound what the task does not establish. In particular, a source-level invalid requested GM range or missing happens-before edge is not an observed hardware fault. Do not reward a claim of a measured failure for those static facts. Finite arithmetic examples do not require exact device transcendental or rounding bits.

Before accepting a score, verify that every fact appears exactly once; each status is justified by an answer span or an explicit omission; all triggered critical errors have a quoted span; and all dimensions remain in [0,10]. `helpers/score_answer.py` validates and aggregates the annotation; it does not judge natural language.

After all 24 answers are frozen and all masked scores are locked, unmask conditions. Report each case/arm/repeat's three dimension scores, total, wrong/omitted/unsupported counts, and explicit critical errors. Compare paired A/B cases within each independent repeat, then report means across all six cases and both repeats. Preserve individual results; do not replace them with only an overall average.

Infrastructure failures do not count as zero-quality answers: record them and rerun with the same settings and budgets. A completed answer truncated by the agreed model budget is graded only on its preserved content. Do not extend a B budget or selectively give feedback based on an interim score. Any invalidating correction to prompt/source/gold after the first evaluation call requires a new suite version and a fresh matched evaluation; spelling-only report changes must not change the frozen artifacts.
