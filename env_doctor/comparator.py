"""Drift comparator module between .env files and templates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import EnvDiffResult, EnvFile
from .parser import parse_env, parse_env_file

URL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/$.?#].[^\s]*$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def infer_type(val: str) -> Optional[str]:
    """Infers the high-level semantic type of a string value."""
    val = val.strip()
    if not val:
        return None

    lower = val.lower()
    if lower in ("true", "false", "yes", "no", "on", "off"):
        return "boolean"

    if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
        return "integer"

    try:
        float(val)
        if "." in val:
            return "float"
    except ValueError:
        pass

    if URL_PATTERN.match(val):
        return "url"

    if EMAIL_PATTERN.match(val):
        return "email"

    if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
        try:
            json.loads(val)
            return "json"
        except Exception:
            pass

    return "string"


def is_placeholder(val: str) -> bool:
    """Checks if a template value is a documentation placeholder."""
    v = val.strip().lower()
    if not v:
        return True
    if v.startswith("<") and v.endswith(">"):
        return True
    if v.startswith("your_") or v.startswith("your-") or v.startswith("changeme"):
        return True
    if v in ("todo", "replace_me", "xxx", "none", "null", "undefined", "example"):
        return True
    return False


def compare_envs(
    source: Union[EnvFile, str],
    target: Union[EnvFile, str],
    source_name: str = "template",
    target_name: str = "target",
) -> EnvDiffResult:
    """Compares target env file against source/template env file and returns drift diagnostics."""
    src_file = parse_env(source, path=source_name) if isinstance(source, str) else source
    tgt_file = parse_env(target, path=target_name) if isinstance(target, str) else target

    src_map = {e.key: e.value for e in src_file.entries if not e.is_comment and e.key}
    tgt_map = {e.key: e.value for e in tgt_file.entries if not e.is_comment and e.key}

    missing_keys: List[str] = []
    extra_keys: List[str] = []
    empty_keys: List[str] = []
    type_mismatches: List[Dict[str, Any]] = []

    # Check missing in target
    for key in src_map:
        if key not in tgt_map:
            missing_keys.append(key)

    # Check extra in target
    for key in tgt_map:
        if key not in src_map:
            extra_keys.append(key)

    # Check empty values in target where source was not empty / placeholder
    for key, tgt_val in tgt_map.items():
        if key in src_map:
            src_val = src_map[key]
            if tgt_val == "" and src_val != "" and not is_placeholder(src_val):
                empty_keys.append(key)

            # Check type mismatch
            # Only infer type if source isn't an obvious placeholder like '<port>'
            if src_val and not is_placeholder(src_val) and tgt_val:
                src_type = infer_type(src_val)
                tgt_type = infer_type(tgt_val)
                if src_type in ("boolean", "integer", "url", "json") and tgt_type != src_type:
                    # Special exception: if src_type is url and tgt has valid host/domain or vice versa
                    type_mismatches.append(
                        {
                            "key": key,
                            "expected_type": src_type,
                            "actual_type": tgt_type,
                            "source_value": src_val,
                            "target_value": tgt_val,
                        }
                    )

    return EnvDiffResult(
        source_path=src_file.path or source_name,
        target_path=tgt_file.path or target_name,
        missing_keys=missing_keys,
        extra_keys=extra_keys,
        empty_keys=empty_keys,
        type_mismatches=type_mismatches,
    )


def compare_env_files(
    source_path: Union[str, Path],
    target_path: Union[str, Path],
) -> EnvDiffResult:
    """Compares two env files on disk."""
    src = parse_env_file(source_path)
    tgt = parse_env_file(target_path)
    return compare_envs(src, tgt, source_name=str(source_path), target_name=str(target_path))
