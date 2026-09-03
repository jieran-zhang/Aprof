# Live trajectory run `run_20260901_123623`

- base model: `deepseek-v4-flash`
- operator: `gelu` case `2`
- measurement: live wall-clock pairs × 30
- selected transform: `transformation.coalesce_contiguous_transfers`
- verdict: `measurement_unstable`
- mean speedup: `1.0304`

## DeepSeek proposal

```json
{
  "predicate_id": "predicate.profile.mte_setup_dominated",
  "transformation_id": "transformation.coalesce_contiguous_transfers",
  "rationale": "fallback_after_unparseable_model_output:We need answer JSON. Need analyze. Need pick predicate and transformation. Operator gelu elementwise shape 2048x2048 float32 numel 4,194,304. baseline tile_elements=1024. That mean",
  "parameters": {
    "tile_elements": 4096
  },
  "model": "deepseek-v4-flash",
  "usage": {
    "prompt_tokens": 546,
    "completion_tokens": 384
  }
}
```

## Trajectory steps

```json
[
  {
    "phase": "baseline",
    "build_ok": true,
    "accuracy_ok": true,
    "tile_elements": 1024,
    "samples_ns_mean": 2359240194.3333335,
    "n_pairs": 30
  },
  {
    "phase": "candidate",
    "patch_info": {
      "transformation_id": "transformation.coalesce_contiguous_transfers",
      "applied": true,
      "tile_elements": 4096,
      "patch": "tileElements->4096"
    },
    "build_ok": true,
    "accuracy_ok": true,
    "samples_ns_mean": 2289592146.0,
    "n_pairs": 30
  }
]
```

## Gate / train

```json
{
  "routes": [
    {
      "candidate_id": "c0001",
      "session_id": "run_20260901_123623-s1",
      "selected_edge_id": "edge.prior.tiny_copy.coalesce",
      "selected_transformation_id": "transformation.coalesce_contiguous_transfers",
      "verdict": "measurement_unstable",
      "policy_update_eligible": true,
      "episode_id": "episode-4b7c6ec8-166c-4cb8-afd3-e10eebd5a481",
      "baseline_mean_ns": 2359240194.3333335,
      "candidate_mean_ns": 2289592146.0,
      "speedup_mean": 1.0304194126692001
    }
  ],
  "training_summary": {
    "input_record_count": 1,
    "unique_valid_episode_count": 1,
    "training_episode_count": 0,
    "updated_edge_count": 0,
    "skip_reasons": {
      "measurement_unstable": 1
    }
  },
  "edge_updates": []
}
```
