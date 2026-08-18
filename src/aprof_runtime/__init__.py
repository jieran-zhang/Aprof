"""AProf's small, machine-authoritative execution boundary."""

from .contracts import (
    CandidateDraft,
    CandidateEpisode,
    Context,
    GateConfig,
    GateEvidence,
    GateOutcome,
    GateRequest,
    GateStageStatus,
    GateVerdict,
    ProducerHashes,
    RouteCandidate,
    RouteDecision,
    SourceHashes,
)
from .gates import CandidateGate
from .policy import (
    EdgePolicyUpdate,
    PolicyCheckpoint,
    PolicyTrainingConfig,
    load_policy_checkpoint,
    train_fixed_graph_policy,
    write_policy_checkpoint,
)
from .store import EpisodeStore

__all__ = [
    "CandidateDraft",
    "CandidateEpisode",
    "CandidateGate",
    "Context",
    "EpisodeStore",
    "GateConfig",
    "GateEvidence",
    "GateOutcome",
    "GateRequest",
    "GateStageStatus",
    "GateVerdict",
    "ProducerHashes",
    "EdgePolicyUpdate",
    "PolicyCheckpoint",
    "PolicyTrainingConfig",
    "RouteCandidate",
    "RouteDecision",
    "SourceHashes",
    "load_policy_checkpoint",
    "train_fixed_graph_policy",
    "write_policy_checkpoint",
]

__version__ = "0.2.0"
