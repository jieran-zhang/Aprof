# Training run `run_20260901_023025`

## Setup

- branch: `feat/aprofgraph`
- base model: `deepseek-v4-flash`
- graph: `v0001`
- measurement: `contract_valid_placeholder_pairs_not_live_910b`

## DeepSeek proposal

```json
{
  "predicate_id": "predicate.profile.gm_traffic_amplified",
  "transformation_id": "transformation.coalesce_contiguous_transfers",
  "rationale": "fallback_after_unparseable_model_output:We need answer JSON only. Need pick one predicate and transformation for Ascend C gelu-like kernel shape=[2048], suspected tiny tile / MTE setup overhead. Need rationale. Choose pr",
  "model": "deepseek-v4-flash",
  "usage": {
    "prompt_tokens": 402,
    "completion_tokens": 256
  }
}
```

## Graph routes / gate

```json
[
  {
    "candidate_id": "c0001",
    "session_id": "run_20260901_023025-s1",
    "selected_edge_id": "edge.prior.roundtrip.noop",
    "selected_transformation_id": "transformation.noop",
    "verdict": "static_rejected",
    "policy_update_eligible": false,
    "episode_id": "episode-74e582f5-e44d-4808-9c2b-05d4ee998d96"
  },
  {
    "candidate_id": "c0002",
    "session_id": "run_20260901_023025-s2",
    "selected_edge_id": "edge.prior.roundtrip.noop",
    "selected_transformation_id": "transformation.noop",
    "verdict": "static_rejected",
    "policy_update_eligible": false,
    "episode_id": "episode-94c0df85-d28f-427a-b26c-f12a9dffe699"
  }
]
```

## Training summary

```json
{
  "input_record_count": 2,
  "unique_valid_episode_count": 2,
  "training_episode_count": 0,
  "updated_edge_count": 0,
  "skip_reasons": {
    "policy_update_ineligible": 2
  }
}
```

## Edge updates (nonzero support/bias)

```json
[]
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

- `docs/training_runs/run_20260901_023025/episodes.sqlite`
- `docs/training_runs/run_20260901_023025/policy_p0001.json`
- `docs/training_runs/run_20260901_023025/deepseek_proposal.json`
