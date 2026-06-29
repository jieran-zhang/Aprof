from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    source: str
    path: Path
    op: str = ""
    variant: str = ""
    injected_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkManifest:
    name: str
    description: str
    cases: list[BenchmarkCase]
    source_repo: str = ""
    adapter: str = "local"
