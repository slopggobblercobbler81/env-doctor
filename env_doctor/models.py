"""Data models for env-doctor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Diagnostic:
    code: str
    message: str
    line: Optional[int] = None
    key: Optional[str] = None
    severity: Severity = Severity.ERROR
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "key": self.key,
            "severity": self.severity.value,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class EnvEntry:
    key: str
    value: str
    line_number: int
    raw_line: str
    is_export: bool = False
    is_comment: bool = False
    inline_comment: Optional[str] = None
    quote_char: Optional[str] = None
    unclosed_quote: bool = False
    has_spaces_around_eq: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "line_number": self.line_number,
            "raw_line": self.raw_line,
            "is_export": self.is_export,
            "is_comment": self.is_comment,
            "inline_comment": self.inline_comment,
            "quote_char": self.quote_char,
            "unclosed_quote": self.unclosed_quote,
            "has_spaces_around_eq": self.has_spaces_around_eq,
        }


@dataclass
class EnvFile:
    path: Optional[str] = None
    entries: List[EnvEntry] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for entry in reversed(self.entries):
            if not entry.is_comment and entry.key == key:
                return entry.value
        return default

    def keys(self) -> List[str]:
        seen = set()
        result = []
        for entry in self.entries:
            if not entry.is_comment and entry.key and entry.key not in seen:
                seen.add(entry.key)
                result.append(entry.key)
        return result

    def items(self) -> List[tuple[str, str]]:
        seen = set()
        result = []
        for entry in self.entries:
            if not entry.is_comment and entry.key and entry.key not in seen:
                seen.add(entry.key)
                result.append((entry.key, entry.value))
        return result

    def __getitem__(self, key: str) -> str:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        return any(not e.is_comment and e.key == key for e in self.entries)

    def __len__(self) -> int:
        return len(self.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "keys_count": len(self.keys()),
            "entries": [e.to_dict() for e in self.entries if not e.is_comment and e.key],
        }


@dataclass
class EnvDiffResult:
    source_path: str
    target_path: str
    missing_keys: List[str] = field(default_factory=list)
    extra_keys: List[str] = field(default_factory=list)
    empty_keys: List[str] = field(default_factory=list)
    type_mismatches: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.missing_keys or self.extra_keys or self.empty_keys or self.type_mismatches)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "target_path": self.target_path,
            "has_drift": self.has_drift,
            "missing_keys": self.missing_keys,
            "extra_keys": self.extra_keys,
            "empty_keys": self.empty_keys,
            "type_mismatches": self.type_mismatches,
        }


@dataclass
class SecretAuditResult:
    path: str
    findings: List[Diagnostic] = field(default_factory=list)

    @property
    def has_vulnerabilities(self) -> bool:
        return any(f.severity == Severity.ERROR for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "has_vulnerabilities": self.has_vulnerabilities,
            "total_findings": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }
