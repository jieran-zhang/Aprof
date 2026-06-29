class AProfError(Exception):
    """Base error for AProf."""


class BenchmarkNotFoundError(AProfError):
    """Raised when a benchmark case or manifest entry is missing."""


class MetricContractError(AProfError):
    """Raised when metric or architecture contracts are invalid."""
