"""Formatter and template generator for .env files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .models import EnvEntry, EnvFile
from .parser import parse_env, parse_env_file

SENSITIVE_KEYWORDS = [
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "KEY",
    "AUTH",
    "CREDENTIAL",
    "PRIVATE",
    "CERT",
]


def needs_quotes(val: str) -> bool:
    """Returns True if string value requires quotes in standard .env files."""
    if not val:
        return False
    if val.startswith(" ") or val.endswith(" ") or val.startswith("\t") or val.endswith("\t"):
        return True
    if any(c in val for c in ('"', "'", " ", "\t", "#", ";", "\n", "\r", "$")):
        return True
    return False


def format_value(val: str, quote_style: str = "quote_needed", original_quote: Optional[str] = None) -> str:
    """Formats a value according to quote_style ('quote_needed', 'always', 'preserve')."""
    if quote_style == "preserve" and original_quote:
        if original_quote == "'":
            escaped = val.replace("'", "\\'")
            return f"'{escaped}'"
        else:
            escaped = val.replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'

    if quote_style == "always":
        escaped = val.replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'

    # 'quote_needed'
    if needs_quotes(val):
        escaped = val.replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'

    return val


def format_env(
    content_or_file: Union[EnvFile, str],
    sort_keys: bool = False,
    quote_style: str = "quote_needed",
    ensure_trailing_newline: bool = True,
) -> str:
    """Formats .env content with consistent syntax, quotes, and spacing."""
    env = parse_env(content_or_file) if isinstance(content_or_file, str) else content_or_file

    if not sort_keys:
        formatted_lines: List[str] = []
        last_was_blank = False

        for entry in env.entries:
            if not entry.key and not entry.raw_line.strip():
                # Blank line
                if not last_was_blank:
                    formatted_lines.append("")
                    last_was_blank = True
                continue

            last_was_blank = False

            if entry.is_comment:
                comment_text = entry.inline_comment or ""
                formatted_lines.append(f"# {comment_text}".rstrip())
                continue

            prefix = "export " if entry.is_export else ""
            key = entry.key
            val_formatted = format_value(entry.value, quote_style=quote_style, original_quote=entry.quote_char)
            line = f"{prefix}{key}={val_formatted}"
            if entry.inline_comment:
                line = f"{line} # {entry.inline_comment}"
            formatted_lines.append(line)

        output = "\n".join(formatted_lines)
        if ensure_trailing_newline and output and not output.endswith("\n"):
            output += "\n"
        return output

    # If sort_keys is True:
    # Associate comments with following key where appropriate
    groups: List[Tuple[List[str], EnvEntry]] = []
    current_comments: List[str] = []

    for entry in env.entries:
        if not entry.key and not entry.raw_line.strip():
            continue
        if entry.is_comment:
            c = entry.inline_comment or ""
            current_comments.append(f"# {c}".rstrip())
            continue
        groups.append((current_comments, entry))
        current_comments = []

    groups.sort(key=lambda g: g[1].key.lower())

    out_lines: List[str] = []
    for comments, entry in groups:
        for c in comments:
            out_lines.append(c)
        prefix = "export " if entry.is_export else ""
        key = entry.key
        val_formatted = format_value(entry.value, quote_style=quote_style, original_quote=entry.quote_char)
        line = f"{prefix}{key}={val_formatted}"
        if entry.inline_comment:
            line = f"{line} # {entry.inline_comment}"
        out_lines.append(line)

    output = "\n".join(out_lines)
    if ensure_trailing_newline and output and not output.endswith("\n"):
        output += "\n"
    return output


def format_env_file(
    file_path: Union[str, Path],
    write: bool = False,
    sort_keys: bool = False,
    quote_style: str = "quote_needed",
) -> str:
    """Formats an env file on disk, optionally overwriting in-place."""
    p = Path(file_path)
    env = parse_env_file(p)
    formatted = format_env(env, sort_keys=sort_keys, quote_style=quote_style)
    if write:
        p.write_text(formatted, encoding="utf-8")
    return formatted


def generate_template(
    content_or_file: Union[EnvFile, str],
    placeholder_format: str = "<your-{name}>",
) -> str:
    """Generates a sanitized .env.example template from an existing .env file."""
    env = parse_env(content_or_file) if isinstance(content_or_file, str) else content_or_file
    lines: List[str] = []

    for entry in env.entries:
        if not entry.key and not entry.raw_line.strip():
            lines.append("")
            continue
        if entry.is_comment:
            c = entry.inline_comment or ""
            lines.append(f"# {c}".rstrip())
            continue

        key = entry.key
        is_sensitive = any(kw in key.upper() for kw in SENSITIVE_KEYWORDS)

        if is_sensitive:
            clean_name = key.lower().replace("_", "-")
            val = placeholder_format.format(name=clean_name)
        else:
            val = entry.value

        line = f"{key}={val}"
        if entry.inline_comment:
            line = f"{line} # {entry.inline_comment}"
        lines.append(line)

    res = "\n".join(lines)
    if not res.endswith("\n"):
        res += "\n"
    return res
