"""Parser for .env file format with multiline and escape support."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Union

from .models import EnvEntry, EnvFile


def parse_env(content: str, path: Optional[str] = None) -> EnvFile:
    """Parses .env file content string into an EnvFile structure."""
    lines = content.splitlines()
    entries: List[EnvEntry] = []
    
    i = 0
    total_lines = len(lines)

    while i < total_lines:
        line_num = i + 1
        raw_line = lines[i]
        stripped = raw_line.strip()

        # Empty line
        if not stripped:
            entries.append(
                EnvEntry(
                    key="",
                    value="",
                    line_number=line_num,
                    raw_line=raw_line,
                    is_comment=False,
                )
            )
            i += 1
            continue

        # Comment line
        if stripped.startswith("#"):
            entries.append(
                EnvEntry(
                    key="",
                    value="",
                    line_number=line_num,
                    raw_line=raw_line,
                    is_comment=True,
                    inline_comment=stripped[1:].strip(),
                )
            )
            i += 1
            continue

        # Check for export prefix
        is_export = False
        work_line = stripped
        if work_line.startswith("export "):
            is_export = True
            work_line = work_line[7:].strip()

        if "=" not in work_line:
            # Malformed line without '='
            entries.append(
                EnvEntry(
                    key=work_line,
                    value="",
                    line_number=line_num,
                    raw_line=raw_line,
                    is_export=is_export,
                )
            )
            i += 1
            continue

        has_spaces = False
        raw_before_eq, raw_after_eq = work_line.split("=", 1)
        if raw_before_eq.endswith(" ") or raw_before_eq.endswith("\t") or raw_after_eq.startswith(" ") or raw_after_eq.startswith("\t"):
            has_spaces = True

        key = raw_before_eq.strip()
        val_str = raw_after_eq.lstrip()

        quote_char: Optional[str] = None
        inline_comment: Optional[str] = None
        parsed_val = ""
        unclosed_quote = False

        # Check for quoted string
        if val_str and val_str[0] in ('"', "'"):
            quote_char = val_str[0]
            accumulated = [val_str[1:]]
            closed = False
            
            # Check if quote is closed on same line or subsequent lines
            while not closed:
                current_text = accumulated[-1]
                idx = 0
                found_close = False
                while idx < len(current_text):
                    if current_text[idx] == "\\" and idx + 1 < len(current_text):
                        idx += 2
                        continue
                    if current_text[idx] == quote_char:
                        found_close = True
                        break
                    idx += 1

                if found_close:
                    closed = True
                    val_content = current_text[:idx]
                    rest = current_text[idx + 1:].strip()
                    accumulated[-1] = val_content
                    if rest.startswith("#"):
                        inline_comment = rest[1:].strip()
                else:
                    i += 1
                    if i < total_lines:
                        accumulated.append(lines[i])
                    else:
                        unclosed_quote = True
                        break

            parsed_val = "\n".join(accumulated)
            if quote_char == '"':
                parsed_val = parsed_val.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            elif quote_char == "'":
                parsed_val = parsed_val.replace("\\'", "'")

        else:
            # Unquoted value
            comment_match = re.search(r"(\s+#.*)$", val_str)
            if comment_match:
                parsed_val = val_str[: comment_match.start()].rstrip()
                inline_comment = comment_match.group(1).lstrip()[1:].strip()
            elif val_str.startswith("#"):
                parsed_val = ""
                inline_comment = val_str[1:].strip()
            else:
                parsed_val = val_str.rstrip()

        entries.append(
            EnvEntry(
                key=key,
                value=parsed_val,
                line_number=line_num,
                raw_line=raw_line,
                is_export=is_export,
                inline_comment=inline_comment,
                quote_char=quote_char,
                unclosed_quote=unclosed_quote,
                has_spaces_around_eq=has_spaces,
            )
        )
        i += 1

    return EnvFile(path=path, entries=entries, raw_lines=lines)


def parse_env_file(file_path: Union[str, Path]) -> EnvFile:
    """Reads and parses an env file from the given path."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    content = p.read_text(encoding="utf-8", errors="replace")
    return parse_env(content, path=str(p.resolve()))
