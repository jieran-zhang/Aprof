# Training run `run_20260901_022941`

## Setup

- branch: `feat/aprofgraph`
- base model: `deepseek-v4-flash`
- graph: `v0001`
- measurement: `contract_valid_placeholder_pairs_not_live_910b`

## DeepSeek proposal

```json
{
  "predicate_id": null,
  "transformation_id": null,
  "rationale": null,
  "model": "deepseek-v4-flash",
  "usage": {
    "prompt_tokens": 528,
    "completion_tokens": 500
  }
}
```

## Graph routes / gate

```json
[
  {
    "candidate_id": "c0001",
    "session_id": "run_20260901_022941-s1",
    "selected_edge_id": "edge.prior.tiny_copy.coalesce",
    "selected_transformation_id": "transformation.coalesce_contiguous_transfers",
    "verdict": "production_safe_gain",
    "policy_update_eligible": true,
    "episode_id": "episode-31c371ed-451f-4897-9d63-1e06baaccdd6"
  },
  {
    "candidate_id": "c0002",
    "session_id": "run_20260901_022941-s2",
    "selected_edge_id": "edge.prior.tiny_copy.coalesce",
    "selected_transformation_id": "transformation.coalesce_contiguous_transfers",
    "verdict": "production_safe_gain",
    "policy_update_eligible": true,
    "episode_id": "episode-f29dab1d-7753-4695-a1a3-8f5e67609126"
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

- `docs/training_runs/run_20260901_022941/episodes.sqlite`
- `docs/training_runs/run_20260901_022941/policy_p0001.json`
- `docs/training_runs/run_20260901_022941/deepseek_proposal.json`
