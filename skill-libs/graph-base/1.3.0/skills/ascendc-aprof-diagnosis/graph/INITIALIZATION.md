# v0004 历史先验与逐项声明

旧learning只为v0003身份及排序历史保留；不是来源可信度、机制概率、收益或因果正确性。当前检索不按这些值沿SPA自动选择动作。

| ID | 类型 | 旧值 | 声明类别 | 审阅状态 |
| --- | --- | --- | --- | --- |
| [action.align_cache_policy](actions/action.align_cache_policy.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.amortize_partial_merge](actions/action.amortize_partial_merge.md) | action | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.balance_tail_assignment](actions/action.balance_tail_assignment.md) | action | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.batch_vector_api_calls](actions/action.batch_vector_api_calls.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.batch_writeback](actions/action.batch_writeback.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.coalesce_cast](actions/action.coalesce_cast.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.coalesce_contiguous_transfers](actions/action.coalesce_contiguous_transfers.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.decompose_tasks_dynamically](actions/action.decompose_tasks_dynamically.md) | action | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.dispatch_by_workload](actions/action.dispatch_by_workload.md) | action | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.fuse_kernel_chain](actions/action.fuse_kernel_chain.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.hoist_invariant_control](actions/action.hoist_invariant_control.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.keep_intermediate_onchip](actions/action.keep_intermediate_onchip.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.narrow_sync_scope](actions/action.narrow_sync_scope.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.pad_ub_layout](actions/action.pad_ub_layout.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.rebalance_mixed_stages](actions/action.rebalance_mixed_stages.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.reduce_memory_traffic](actions/action.reduce_memory_traffic.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.reorder_contiguous_access](actions/action.reorder_contiguous_access.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.restructure_broadcast](actions/action.restructure_broadcast.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.restructure_reduction](actions/action.restructure_reduction.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.retain_matrix_tiles](actions/action.retain_matrix_tiles.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.reuse_disjoint_onchip_buffers](actions/action.reuse_disjoint_onchip_buffers.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.reuse_input_tiles](actions/action.reuse_input_tiles.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.shorten_scalar_lifetimes](actions/action.shorten_scalar_lifetimes.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.size_workspace_by_shape](actions/action.size_workspace_by_shape.md) | action | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.software_pipeline_stages](actions/action.software_pipeline_stages.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.stagger_resource_access](actions/action.stagger_resource_access.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | gap |
| [action.vectorize_scalar_loop](actions/action.vectorize_scalar_loop.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [action.vectorize_tail](actions/action.vectorize_tail.md) | action | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.broadcast_strategy_mismatch](edges/edge.action.broadcast_strategy_mismatch.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.cache_policy_mismatch](edges/edge.action.cache_policy_mismatch.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.chunk_merge_overhead](edges/edge.action.chunk_merge_overhead.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.control_metadata_overhead](edges/edge.action.control_metadata_overhead.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.dynamic_shape_mismatch](edges/edge.action.dynamic_shape_mismatch.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.fragmented_writeback](edges/edge.action.fragmented_writeback.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.insufficient_input_reuse](edges/edge.action.insufficient_input_reuse.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.l1_l0_reuse_deficit](edges/edge.action.l1_l0_reuse_deficit.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.memory_bandwidth_saturation](edges/edge.action.memory_bandwidth_saturation.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.missing_kernel_fusion](edges/edge.action.missing_kernel_fusion.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.mixed_pipeline_imbalance](edges/edge.action.mixed_pipeline_imbalance.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.noncontiguous_access](edges/edge.action.noncontiguous_access.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.reduction_strategy_mismatch](edges/edge.action.reduction_strategy_mismatch.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.redundant_cast](edges/edge.action.redundant_cast.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.register_spill](edges/edge.action.register_spill.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.tail_slow_path](edges/edge.action.tail_slow_path.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.action.transfer_compute_contention](edges/edge.action.transfer_compute_contention.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | gap |
| [edge.action.workspace_overallocation](edges/edge.action.workspace_overallocation.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.mechanism.bank_contention](edges/edge.mechanism.bank_contention.md) | edge | `{"weight": 1}` | mechanism_inference, source_statement | gap |
| [edge.mechanism.capacity_pipeline](edges/edge.mechanism.capacity_pipeline.md) | edge | `{"weight": 1}` | mechanism_inference, source_statement | reviewed_with_limits |
| [edge.mechanism.sync_pipeline](edges/edge.mechanism.sync_pipeline.md) | edge | `{"weight": 1}` | mechanism_inference, source_statement | reviewed_with_limits |
| [edge.mechanism.tiny_bandwidth](edges/edge.mechanism.tiny_bandwidth.md) | edge | `{"weight": 1}` | mechanism_inference, source_statement | reviewed_with_limits |
| [edge.mechanism.underused_tail](edges/edge.mechanism.underused_tail.md) | edge | `{"weight": 1}` | code_fact, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.capacity.reuse](edges/edge.prior.capacity.reuse.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.conflict.pad](edges/edge.prior.conflict.pad.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.pipeline.software_pipeline](edges/edge.prior.pipeline.software_pipeline.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.roundtrip.keep_onchip](edges/edge.prior.roundtrip.keep_onchip.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.scalar.vectorize](edges/edge.prior.scalar.vectorize.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.sync.narrow](edges/edge.prior.sync.narrow.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.tail.balance](edges/edge.prior.tail.balance.md) | edge | `{"weight": 3}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.tiny_copy.coalesce](edges/edge.prior.tiny_copy.coalesce.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.underused.dynamic_tasks](edges/edge.prior.underused.dynamic_tasks.md) | edge | `{"weight": 3}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.prior.vector.batch](edges/edge.prior.vector.batch.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.refute.bandwidth.tiny_transfer](edges/edge.refute.bandwidth.tiny_transfer.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.refute.overlap.serial](edges/edge.refute.overlap.serial.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.refute.tiny.underused](edges/edge.refute.tiny.underused.md) | edge | `{"weight": 3}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.broadcast_strategy_mismatch.profile](edges/edge.support.broadcast_strategy_mismatch.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.broadcast_strategy_mismatch.source](edges/edge.support.broadcast_strategy_mismatch.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.cache_policy_mismatch.profile](edges/edge.support.cache_policy_mismatch.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.cache_policy_mismatch.source](edges/edge.support.cache_policy_mismatch.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.capacity.capacity](edges/edge.support.capacity.capacity.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.chunk_merge_overhead.profile](edges/edge.support.chunk_merge_overhead.profile.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.chunk_merge_overhead.source](edges/edge.support.chunk_merge_overhead.source.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.conflict.profile](edges/edge.support.conflict.profile.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.conflict.source](edges/edge.support.conflict.source.md) | edge | `{"weight": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.control_metadata_overhead.profile](edges/edge.support.control_metadata_overhead.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.control_metadata_overhead.source](edges/edge.support.control_metadata_overhead.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.dynamic_shape_mismatch.profile](edges/edge.support.dynamic_shape_mismatch.profile.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.dynamic_shape_mismatch.source](edges/edge.support.dynamic_shape_mismatch.source.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.fragmented_writeback.profile](edges/edge.support.fragmented_writeback.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.fragmented_writeback.source](edges/edge.support.fragmented_writeback.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.insufficient_input_reuse.profile](edges/edge.support.insufficient_input_reuse.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.insufficient_input_reuse.source](edges/edge.support.insufficient_input_reuse.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.l1_l0_reuse_deficit.profile](edges/edge.support.l1_l0_reuse_deficit.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.l1_l0_reuse_deficit.source](edges/edge.support.l1_l0_reuse_deficit.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.memory_bandwidth_saturation.profile](edges/edge.support.memory_bandwidth_saturation.profile.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.memory_bandwidth_saturation.source](edges/edge.support.memory_bandwidth_saturation.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.missing_kernel_fusion.profile](edges/edge.support.missing_kernel_fusion.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.missing_kernel_fusion.source](edges/edge.support.missing_kernel_fusion.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.mixed_pipeline_imbalance.profile](edges/edge.support.mixed_pipeline_imbalance.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.mixed_pipeline_imbalance.source](edges/edge.support.mixed_pipeline_imbalance.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.noncontiguous_access.profile](edges/edge.support.noncontiguous_access.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.noncontiguous_access.source](edges/edge.support.noncontiguous_access.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.overlap.pipeline](edges/edge.support.overlap.pipeline.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.reduction_strategy_mismatch.profile](edges/edge.support.reduction_strategy_mismatch.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.reduction_strategy_mismatch.source](edges/edge.support.reduction_strategy_mismatch.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.redundant_cast.profile](edges/edge.support.redundant_cast.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.redundant_cast.source](edges/edge.support.redundant_cast.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.register_spill.profile](edges/edge.support.register_spill.profile.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.register_spill.source](edges/edge.support.register_spill.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.roundtrip.profile](edges/edge.support.roundtrip.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.roundtrip.source](edges/edge.support.roundtrip.source.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.scalar.profile](edges/edge.support.scalar.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.scalar.source](edges/edge.support.scalar.source.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.serial.source](edges/edge.support.serial.source.md) | edge | `{"weight": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.sync.source](edges/edge.support.sync.source.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tail.profile](edges/edge.support.tail.profile.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tail.source](edges/edge.support.tail.source.md) | edge | `{"weight": 3}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tail_slow_path.profile](edges/edge.support.tail_slow_path.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tail_slow_path.source](edges/edge.support.tail_slow_path.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tasks.profile](edges/edge.support.tasks.profile.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tasks.source](edges/edge.support.tasks.source.md) | edge | `{"weight": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tiny_copy.profile](edges/edge.support.tiny_copy.profile.md) | edge | `{"weight": 3}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.tiny_copy.source](edges/edge.support.tiny_copy.source.md) | edge | `{"weight": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.transfer_compute_contention.profile](edges/edge.support.transfer_compute_contention.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | gap |
| [edge.support.transfer_compute_contention.source](edges/edge.support.transfer_compute_contention.source.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | gap |
| [edge.support.vector.profile](edges/edge.support.vector.profile.md) | edge | `{"weight": 2}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.workspace_overallocation.profile](edges/edge.support.workspace_overallocation.profile.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [edge.support.workspace_overallocation.source](edges/edge.support.workspace_overallocation.source.md) | edge | `{"weight": 2}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.broadcast_strategy_mismatch](problems/problem.broadcast_strategy_mismatch.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.cache_policy_mismatch](problems/problem.cache_policy_mismatch.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.chunk_merge_overhead](problems/problem.chunk_merge_overhead.md) | problem | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.control_metadata_overhead](problems/problem.control_metadata_overhead.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.core_tail_imbalance](problems/problem.core_tail_imbalance.md) | problem | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.dynamic_shape_mismatch](problems/problem.dynamic_shape_mismatch.md) | problem | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.excessive_sync_scope](problems/problem.excessive_sync_scope.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.fragmented_writeback](problems/problem.fragmented_writeback.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.insufficient_input_reuse](problems/problem.insufficient_input_reuse.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.l1_l0_reuse_deficit](problems/problem.l1_l0_reuse_deficit.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.memory_bandwidth_saturation](problems/problem.memory_bandwidth_saturation.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.missing_kernel_fusion](problems/problem.missing_kernel_fusion.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.mixed_pipeline_imbalance](problems/problem.mixed_pipeline_imbalance.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.noncontiguous_access](problems/problem.noncontiguous_access.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.onchip_capacity_pressure](problems/problem.onchip_capacity_pressure.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.pipeline_serialization](problems/problem.pipeline_serialization.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.reduction_strategy_mismatch](problems/problem.reduction_strategy_mismatch.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.redundant_cast](problems/problem.redundant_cast.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.redundant_gm_round_trip](problems/problem.redundant_gm_round_trip.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.register_spill](problems/problem.register_spill.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.scalar_control_hot_loop](problems/problem.scalar_control_hot_loop.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.tail_slow_path](problems/problem.tail_slow_path.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.tiny_transfer_setup_amplification](problems/problem.tiny_transfer_setup_amplification.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.transfer_compute_contention](problems/problem.transfer_compute_contention.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | gap |
| [problem.ub_bank_conflict](problems/problem.ub_bank_conflict.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.underused_task_parallelism](problems/problem.underused_task_parallelism.md) | problem | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.vector_api_fragmentation](problems/problem.vector_api_fragmentation.md) | problem | `{"bias": 0}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [problem.workspace_overallocation](problems/problem.workspace_overallocation.md) | problem | `{"bias": 0}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.broadcast_strategy_mismatch](symptoms/symptom.profile.broadcast_strategy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.cache_policy_mismatch](symptoms/symptom.profile.cache_policy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.chunk_merge_overhead](symptoms/symptom.profile.chunk_merge_overhead.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.control_metadata_overhead](symptoms/symptom.profile.control_metadata_overhead.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.dynamic_shape_mismatch](symptoms/symptom.profile.dynamic_shape_mismatch.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.fragmented_writeback](symptoms/symptom.profile.fragmented_writeback.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.gm_traffic_amplified](symptoms/symptom.profile.gm_traffic_amplified.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.insufficient_input_reuse](symptoms/symptom.profile.insufficient_input_reuse.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.l1_l0_reuse_deficit](symptoms/symptom.profile.l1_l0_reuse_deficit.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.memory_bandwidth_saturation](symptoms/symptom.profile.memory_bandwidth_saturation.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.missing_kernel_fusion](symptoms/symptom.profile.missing_kernel_fusion.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.mixed_pipeline_imbalance](symptoms/symptom.profile.mixed_pipeline_imbalance.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.mte_setup_dominated](symptoms/symptom.profile.mte_setup_dominated.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.noncontiguous_access](symptoms/symptom.profile.noncontiguous_access.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.overlap_low](symptoms/symptom.profile.overlap_low.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.per_core_time_imbalanced](symptoms/symptom.profile.per_core_time_imbalanced.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.reduction_strategy_mismatch](symptoms/symptom.profile.reduction_strategy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.redundant_cast](symptoms/symptom.profile.redundant_cast.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.register_spill](symptoms/symptom.profile.register_spill.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.scalar_hot](symptoms/symptom.profile.scalar_hot.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.steady_overlap](symptoms/symptom.profile.steady_overlap.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.tail_slow_path](symptoms/symptom.profile.tail_slow_path.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.tasks_below_available_cores](symptoms/symptom.profile.tasks_below_available_cores.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.transfer_compute_contention](symptoms/symptom.profile.transfer_compute_contention.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | gap |
| [symptom.profile.ub_conflict_high](symptoms/symptom.profile.ub_conflict_high.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.vector_granularity_low](symptoms/symptom.profile.vector_granularity_low.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.profile.workspace_overallocation](symptoms/symptom.profile.workspace_overallocation.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.broadcast_strategy_mismatch](symptoms/symptom.source.broadcast_strategy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.cache_policy_mismatch](symptoms/symptom.source.cache_policy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.chunk_merge_overhead](symptoms/symptom.source.chunk_merge_overhead.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.control_metadata_overhead](symptoms/symptom.source.control_metadata_overhead.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.dynamic_shape_mismatch](symptoms/symptom.source.dynamic_shape_mismatch.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.fixed_or_undersubscribed_tasking](symptoms/symptom.source.fixed_or_undersubscribed_tasking.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.fragmented_writeback](symptoms/symptom.source.fragmented_writeback.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.gm_intermediate_roundtrip](symptoms/symptom.source.gm_intermediate_roundtrip.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.inner_loop_copy](symptoms/symptom.source.inner_loop_copy.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.insufficient_input_reuse](symptoms/symptom.source.insufficient_input_reuse.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.l1_l0_reuse_deficit](symptoms/symptom.source.l1_l0_reuse_deficit.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.memory_bandwidth_saturation](symptoms/symptom.source.memory_bandwidth_saturation.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.missing_kernel_fusion](symptoms/symptom.source.missing_kernel_fusion.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.mixed_pipeline_imbalance](symptoms/symptom.source.mixed_pipeline_imbalance.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.noncontiguous_access](symptoms/symptom.source.noncontiguous_access.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.reduction_strategy_mismatch](symptoms/symptom.source.reduction_strategy_mismatch.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.redundant_cast](symptoms/symptom.source.redundant_cast.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.register_spill](symptoms/symptom.source.register_spill.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.scalar_element_loop](symptoms/symptom.source.scalar_element_loop.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.serial_queue_or_event_order](symptoms/symptom.source.serial_queue_or_event_order.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.sync_inside_tile_loop](symptoms/symptom.source.sync_inside_tile_loop.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.tail_concentrated](symptoms/symptom.source.tail_concentrated.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.tail_slow_path](symptoms/symptom.source.tail_slow_path.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.transfer_compute_contention](symptoms/symptom.source.transfer_compute_contention.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | gap |
| [symptom.source.ub_live_bytes_near_capacity](symptoms/symptom.source.ub_live_bytes_near_capacity.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.ub_stride_conflict_risk](symptoms/symptom.source.ub_stride_conflict_risk.md) | symptom | `{"gain": 1}` | legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.source.workspace_overallocation](symptoms/symptom.source.workspace_overallocation.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
| [symptom.workload.tiny_or_overhead_limited](symptoms/symptom.workload.tiny_or_overhead_limited.md) | symptom | `{"gain": 1}` | code_fact, legacy_seed, mechanism_inference, source_statement | reviewed_with_limits |
