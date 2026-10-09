class AProfRuntimeError(Exception):
    """Base class for expected runtime failures."""


class ContractError(AProfRuntimeError, ValueError):
    """A serialized object did not satisfy its contract."""


class GateError(AProfRuntimeError):
    """A candidate gate request was invalid."""


class StoreError(AProfRuntimeError):
    """An append-only store invariant was violated."""


class GraphError(AProfRuntimeError):
    """A graph snapshot was invalid or could not be routed."""

