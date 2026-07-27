"""Minimal YAML subset loader for Skill-RL skill files (no PyYAML required).

Supports the indentation style used in skills/aprof/skill_library/v0/*.yaml:
mappings, lists, nested mappings, and simple scalars.
"""

from __future__ import annotations

from typing import Any


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "" or s == "null" or s == "~":
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def safe_load(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append(raw.rstrip())
    if not lines:
        return None
    value, _ = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines: list[str], idx: int, base_indent: int) -> tuple[Any, int]:
    if idx >= len(lines):
        return None, idx
    ind = _indent(lines[idx])
    if ind < base_indent:
        return None, idx
    # Sequence
    if lines[idx].lstrip().startswith("- "):
        return _parse_list(lines, idx, ind)
    return _parse_map(lines, idx, ind)


def _parse_list(lines: list[str], idx: int, list_indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while idx < len(lines):
        line = lines[idx]
        ind = _indent(line)
        if ind < list_indent:
            break
        if ind > list_indent:
            break
        if not line.lstrip().startswith("- "):
            break
        body = line.lstrip()[2:]
        idx += 1
        if body == "":
            # nested block
            val, idx = _parse_block(lines, idx, list_indent + 2)
            items.append(val)
            continue
        if ":" in body and not (body.startswith('"') or body.startswith("'")):
            # inline map start: key: value possibly followed by nested keys
            key, _, rest = body.partition(":")
            key = key.strip()
            rest = rest.strip()
            node: dict[str, Any] = {}
            if rest:
                node[key] = _parse_scalar(rest)
            else:
                nested, idx = _parse_block(lines, idx, list_indent + 2)
                node[key] = nested
            # consume following map keys at indent > list_indent
            while idx < len(lines):
                nline = lines[idx]
                nind = _indent(nline)
                if nind <= list_indent:
                    break
                if nline.lstrip().startswith("- "):
                    break
                if ":" not in nline:
                    break
                k, _, r = nline.lstrip().partition(":")
                k = k.strip()
                r = r.strip()
                idx += 1
                if r:
                    node[k] = _parse_scalar(r)
                else:
                    nested, idx = _parse_block(lines, idx, nind + 2)
                    node[k] = nested
            items.append(node)
        else:
            items.append(_parse_scalar(body))
    return items, idx


def _parse_map(lines: list[str], idx: int, map_indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while idx < len(lines):
        line = lines[idx]
        ind = _indent(line)
        if ind < map_indent:
            break
        if ind > map_indent:
            break
        if line.lstrip().startswith("- "):
            break
        if ":" not in line:
            break
        key, _, rest = line.lstrip().partition(":")
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            result[key] = _parse_scalar(rest)
        else:
            if idx < len(lines) and _indent(lines[idx]) > map_indent:
                nested, idx = _parse_block(lines, idx, map_indent + 2)
                result[key] = nested
            else:
                result[key] = None
    return result, idx


def safe_dump(data: Any, sort_keys: bool = False, allow_unicode: bool = True) -> str:
    """Dump a restricted subset back to YAML text."""

    def emit(obj: Any, indent: int = 0) -> list[str]:
        pad = " " * indent
        out: list[str] = []
        if isinstance(obj, dict):
            items = sorted(obj.items()) if sort_keys else list(obj.items())
            if not items:
                return [pad + "{}"]
            for k, v in items:
                if isinstance(v, (dict, list)):
                    out.append(f"{pad}{k}:")
                    out.extend(emit(v, indent + 2))
                else:
                    out.append(f"{pad}{k}: {_fmt(v)}")
        elif isinstance(obj, list):
            if not obj:
                return [pad + "[]"]
            for v in obj:
                if isinstance(v, dict):
                    keys = list(v.items())
                    if not keys:
                        out.append(f"{pad}- {{}}")
                        continue
                    first_k, first_v = keys[0]
                    if isinstance(first_v, (dict, list)):
                        out.append(f"{pad}- {first_k}:")
                        out.extend(emit(first_v, indent + 4))
                    else:
                        out.append(f"{pad}- {first_k}: {_fmt(first_v)}")
                    for nk, nv in keys[1:]:
                        if isinstance(nv, (dict, list)):
                            out.append(f"{pad}  {nk}:")
                            out.extend(emit(nv, indent + 4))
                        else:
                            out.append(f"{pad}  {nk}: {_fmt(nv)}")
                elif isinstance(v, list):
                    out.append(f"{pad}-")
                    out.extend(emit(v, indent + 2))
                else:
                    out.append(f"{pad}- {_fmt(v)}")
        else:
            out.append(pad + _fmt(obj))
        return out

    def _fmt(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        if any(ch in s for ch in [":", "#", "\n", '"']):
            return '"' + s.replace('"', '\\"') + '"'
        return s

    return "\n".join(emit(data)) + "\n"
