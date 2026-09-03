# Training run `run_20260901_023054`

## Setup

- branch: `feat/aprofgraph`
- base model: `deepseek-v4-flash`
- graph: `v0001`
- measurement: `contract_valid_placeholder_pairs_not_live_910b`

## DeepSeek proposal

```json
{
  "predicate_id": "predicate.profile.mte_setup_dominated",
  "transformation_id": "transformation.coalesce_contiguous_transfers",
  "rationale": "fallback_after_unparseable_model_output:We need to output a JSON object with keys: predicate_id, transformation_id, rationale, parameters. The user gave a scenario: \"Ascend C gelu-like kernel, shape=[2048], suspected tin",
  "model": "deepseek-v4-flash",
  "usage": {
    "prompt_tokens": 422,
    "completion_tokens": 256
  }
}
```

## Graph routes / gate

```json
[
  {
    "candidate_id": "c0001",
    "session_id": "run_20260901_023054-s1",
    "selected_edge_id": "edge.prior.tiny_copy.coalesce",
    "selected_transformation_id": "transformation.coalesce_contiguous_transfers",
    "verdict": "production_safe_gain",
    "policy_update_eligible": true,
    "episode_id": "episode-b1c584e9-d559-450a-86dd-3ec194b95a8a"
  },
  {
    "candidate_id": "c0002",
    "session_id": "run_20260901_023054-s2",
    "selected_edge_id": "edge.prior.tiny_copy.coalesce",
    "selected_transformation_id": "transformation.coalesce_contiguous_transfers",
    "verdict": "production_safe_gain",
    "policy_update_eligible": true,
    "episode_id": "episode-b6c7dc9d-1372-47c2-b809-293686eabc56"
  }
]
```

## Training summary

```json
{
  "input_record_count": 2,
  "unique_valid_episode_count": 2,
  "training_episode_count": 2,
  "updated_edge_count": 1,
  "skip_reasons": {}
}
```

## Edge updates (nonzero support/bias)

```json
[
  {
    "edge_id": "edge.prior.tiny_copy.coalesce",
    "source_id": "mechanism.tiny_transfer_setup_amplification",
    "target_id": "transformation.coalesce_contiguous_transfers",
    "prior_logit": 2.8,
    "bias": 0.06615043471078542,
    "effective_logit": 2.8661504347107853,
    "reliability": 0.3333333333333333,
    "support_count": 2,
    "weighted_support": 2.0,
    "positive_count": 2,
    "negative_count": 0
  }
]
```

## Hardware blocker for live traces

```json
{
  "ssh": "ok:longyihan@xeon6:2222",
  "npu_smi": "Ascend910 visible",
  "msprof": "not_on_PATH_for_this_account",
  "ascend_toolkit": "only /usr/local/Ascend/driver found in probe"
}
```

## Artifacts

- `docs/training_runs/run_20260901_023054/episodes.sqlite`
- `docs/training_runs/run_20260901_023054/policy_p0001.json`
- `docs/training_runs/run_20260901_023054/deepseek_proposal.json`
