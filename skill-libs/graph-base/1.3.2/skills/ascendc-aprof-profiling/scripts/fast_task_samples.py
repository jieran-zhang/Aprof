"""复用 runtime 的完整调用解析器，避免采集和回放使用不同规则。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime/src"))
from aprof_runtime.unified_task_samples import complete_calls

__all__ = ["complete_calls"]
