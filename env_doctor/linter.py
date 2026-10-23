"""Linter module for .env files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from .models import Diagnostic, EnvEntry, EnvFile, Severity
from .parser import parse_env, parse_env_file

VALID_KEY_REGEX = re.compile(r"^[A-Z][A-Z0-9_]*$")
LOWERCASE_OR_DASH_KEY_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def lint_env(
    env: Union[EnvFile, str],
    rules: Optional[Dict[str, bool]] = None,
    strict: bool = False,
) -> List[Diagnostic]:
    """Lints an EnvFile or string content against production .env standards."""
    if isinstance(env, str):
        env_file = parse_env(env)
    else:
        env_file = env

    enabled_rules = {
        "ENV001": True,  # Duplicate keys
        "ENV002": True,  # Missing '=' delimiter / syntax error
        "ENV003": True,  # Spaces around '='
        "ENV004": True,  # Non-standard key naming (e.g., lowercase, dashes)
        "ENV005": True,  # Unquoted spaces or special characters
        "ENV006": True,  # Trailing whitespace
        "ENV007": True,  # Empty variable value
        "ENV008": True,  # Unclosed quotation mark
        "ENV009": True,  # Lowercase or unnecessary 'export' prefix
    }
    if rules:
        enabled_rules.update(rules)

    diagnostics: List[Diagnostic] = []
    seen_keys: Dict[str, EnvEntry] = {}

    for entry in env_file.entries:
        # Check trailing whitespace (ENV006)
        if enabled_rules.get("ENV006", True):
            if entry.raw_line.endswith(" ") or entry.raw_line.endswith("\t"):
                diagnostics.append(
                    Diagnostic(
                        code="ENV006",
                        message=f"Line {entry.line_number} has trailing whitespace.",
                        line=entry.line_number,
                        key=entry.key or None,
                        severity=Severity.WARNING,
                        suggested_fix=entry.raw_line.rstrip(),
                    )
                )

        if entry.is_comment or (not entry.key and not entry.raw_line.strip()):
            continue

        # Missing '=' syntax error (ENV002)
        if enabled_rules.get("ENV002", True):
            if "=" not in entry.raw_line:
                diagnostics.append(
                    Diagnostic(
                        code="ENV002",
                        message=f"Line {entry.line_number} is missing '=' delimiter: '{entry.raw_line.strip()}'.",
                        line=entry.line_number,
                        key=entry.key or None,
                        severity=Severity.ERROR,
                    )
                )
                continue

        # Unclosed quotation mark (ENV008)
        if enabled_rules.get("ENV008", True) and entry.unclosed_quote:
            diagnostics.append(
                Diagnostic(
                    code="ENV008",
                    message=f"Line {entry.line_number} has unclosed quote ({entry.quote_char}) for key '{entry.key}'.",
                    line=entry.line_number,
                    key=entry.key,
                    severity=Severity.ERROR,
                )
            )

        # Duplicate keys (ENV001)
        if enabled_rules.get("ENV001", True):
            if entry.key in seen_keys:
                prev_entry = seen_keys[entry.key]
                is_same_val = prev_entry.value == entry.value
                sev = Severity.WARNING if is_same_val else Severity.ERROR
                diagnostics.append(
                    Diagnostic(
                        code="ENV001",
                        message=(
                            f"Duplicate key '{entry.key}' on line {entry.line_number} "
                            f"(previously declared on line {prev_entry.line_number})."
                        ),
                        line=entry.line_number,
                        key=entry.key,
                        severity=sev,
                        suggested_fix=f"Remove duplicate declaration of '{entry.key}'",
                    )
                )
            else:
                seen_keys[entry.key] = entry

        # Spaces around '=' (ENV003)
        if enabled_rules.get("ENV003", True) and entry.has_spaces_around_eq:
            quote_wrapper = f'"{entry.value}"' if entry.quote_char == '"' else (f"'{entry.value}'" if entry.quote_char == "'" else entry.value)
            diagnostics.append(
                Diagnostic(
                    code="ENV003",
                    message=f"Line {entry.line_number} contains whitespace around '=' operator for key '{entry.key}'.",
                    line=entry.line_number,
                    key=entry.key,
                    severity=Severity.WARNING,
                    suggested_fix=f"{entry.key}={quote_wrapper}",
                )
            )

        # Non-standard key naming (ENV004)
        if enabled_rules.get("ENV004", True) and entry.key:
            if not VALID_KEY_REGEX.match(entry.key):
                clean_key = re.sub(r"[^A-Za-z0-9_]", "_", entry.key).upper()
                if clean_key and clean_key[0].isdigit():
                    clean_key = "_" + clean_key
                diagnostics.append(
                    Diagnostic(
                        code="ENV004",
                        message=(
                            f"Key '{entry.key}' does not follow standard uppercase SNAKE_CASE convention."
                        ),
                        line=entry.line_number,
                        key=entry.key,
                        severity=Severity.WARNING,
                        suggested_fix=clean_key,
                    )
                )

        # Unquoted spaces or special characters (ENV005)
        if enabled_rules.get("ENV005", True) and not entry.quote_char and entry.value:
            # Check for unquoted spaces or comments in value
            if any(ch in entry.value for ch in (" ", "\t", "#", ";")):
                safe_val = entry.value.replace('"', '\\"')
                diagnostics.append(
                    Diagnostic(
                        code="ENV005",
                        message=(
                            f"Value for '{entry.key}' contains spaces or special characters without quotes."
                        ),
                        line=entry.line_number,
                        key=entry.key,
                        severity=Severity.WARNING,
                        suggested_fix=f'{entry.key}="{safe_val}"',
                    )
                )

        # Empty variable value (ENV007)
        if enabled_rules.get("ENV007", True) and entry.key:
            if entry.value == "":
                diagnostics.append(
                    Diagnostic(
                        code="ENV007",
                        message=f"Key '{entry.key}' has empty value on line {entry.line_number}.",
                        line=entry.line_number,
                        key=entry.key,
                        severity=Severity.WARNING,
                    )
                )

        # Lowercase export prefix (ENV009)
        if enabled_rules.get("ENV009", True) and entry.is_export:
            diagnostics.append(
                Diagnostic(
                    code="ENV009",
                    message=f"Line {entry.line_number} uses bash 'export' prefix which may cause incompatibility with some dotenv parsers.",
                    line=entry.line_number,
                    key=entry.key,
                    severity=Severity.INFO,
                    suggested_fix=f"{entry.key}={entry.value}",
                )
            )

    if strict:
        for diag in diagnostics:
            if diag.severity == Severity.WARNING:
                diag.severity = Severity.ERROR

    return diagnostics


def lint_env_file(
    file_path: Union[str, Path],
    rules: Optional[Dict[str, bool]] = None,
    strict: bool = False,
) -> List[Diagnostic]:
    """Reads and lints an env file."""
    env_file = parse_env_file(file_path)
    return lint_env(env_file, rules=rules, strict=strict)
