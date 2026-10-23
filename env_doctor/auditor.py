"""Secret auditor and security vulnerability scanner for .env files."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .models import Diagnostic, EnvEntry, EnvFile, SecretAuditResult, Severity
from .parser import parse_env, parse_env_file

SECRET_PATTERNS = [
    (
        "SEC001",
        "AWS Access Key ID",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        Severity.ERROR,
        "Store AWS credentials in AWS Secrets Manager or use IAM roles.",
    ),
    (
        "SEC002",
        "GitHub Personal Access Token",
        re.compile(r"\b(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b"),
        Severity.ERROR,
        "Revoke and rotate this GitHub token immediately; inject via environment secret.",
    ),
    (
        "SEC003",
        "Slack API Token",
        re.compile(r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*\b"),
        Severity.ERROR,
        "Rotate the Slack token and do not store in source-controlled .env files.",
    ),
    (
        "SEC004",
        "Stripe Live API Key",
        re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}\b"),
        Severity.ERROR,
        "Live Stripe key detected! Revoke immediately in the Stripe dashboard.",
    ),
    (
        "SEC005",
        "Google API Key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{30,45}\b"),
        Severity.ERROR,
        "Google API key found. Restrict API key permissions and remove from .env.",
    ),
    (
        "SEC006",
        "OpenAI or Anthropic API Key",
        re.compile(r"\b(sk-[a-zA-Z0-9]{32,}|sk-ant-[a-zA-Z0-9]{32,})\b"),
        Severity.ERROR,
        "AI provider API key detected. Inject via environment variable at runtime.",
    ),
    (
        "SEC007",
        "SendGrid API Key",
        re.compile(r"\bSG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}\b"),
        Severity.ERROR,
        "SendGrid key detected. Rotate token immediately.",
    ),
    (
        "SEC008",
        "Private Key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        Severity.ERROR,
        "Private key block detected. Move to a dedicated key vault or file.",
    ),
    (
        "SEC009",
        "JSON Web Token (JWT)",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        Severity.ERROR,
        "Hardcoded JWT token found. Issue tokens dynamically.",
    ),
    (
        "SEC010",
        "Database URI with Plaintext Password",
        re.compile(r"^[a-zA-Z0-9+.-]+://[^:\s@]+:([^@\s]+)@[^\s]+"),
        Severity.ERROR,
        "Database connection string contains embedded password. Use secret injection or credentials file.",
    ),
]

WEAK_PASSWORDS = {
    "password",
    "password123",
    "123456",
    "12345678",
    "admin",
    "root",
    "secret",
    "changeme",
    "default",
    "toor",
    "qwerty",
    "letmein",
    "test",
    "dev",
}

PLACEHOLDER_REGEX = re.compile(
    r"^(<.*>|\{.*\}|your[-_].*|changeme.*|todo|replace[-_]me|dummy|xxx|null|undefined)$",
    re.IGNORECASE,
)

SENSITIVE_KEY_PATTERN = re.compile(
    r"(SECRET|PASSWORD|PASSWD|PASS|TOKEN|API_KEY|AUTH|CREDENTIAL|PRIVATE_KEY|SIGNING_KEY)",
    re.IGNORECASE,
)


def calculate_shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    freqs: Dict[str, int] = {}
    for char in data:
        freqs[char] = freqs.get(char, 0) + 1
    for count in freqs.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_placeholder_value(val: str) -> bool:
    """Checks whether a value is a documented placeholder rather than a real secret."""
    cleaned = val.strip()
    if not cleaned:
        return True
    return bool(PLACEHOLDER_REGEX.match(cleaned))


def audit_secrets(
    env: Union[EnvFile, str],
    allow_placeholders: bool = True,
) -> SecretAuditResult:
    """Scans an EnvFile or string content for exposed secrets and weak credentials."""
    env_file = parse_env(env) if isinstance(env, str) else env
    findings: List[Diagnostic] = []

    for entry in env_file.entries:
        if entry.is_comment or not entry.key:
            continue

        val = entry.value.strip()
        if not val:
            continue

        if allow_placeholders and is_placeholder_value(val):
            continue

        # 1. Check known signature patterns
        matched_sig = False
        for code, label, pattern, severity, fix in SECRET_PATTERNS:
            if pattern.search(val):
                findings.append(
                    Diagnostic(
                        code=code,
                        message=f"Line {entry.line_number}: Exposed {label} detected in key '{entry.key}'.",
                        line=entry.line_number,
                        key=entry.key,
                        severity=severity,
                        suggested_fix=fix,
                    )
                )
                matched_sig = True
                break

        if matched_sig:
            continue

        # 2. Check weak / default passwords in sensitive keys
        if SENSITIVE_KEY_PATTERN.search(entry.key):
            lower_val = val.lower()
            if lower_val in WEAK_PASSWORDS:
                findings.append(
                    Diagnostic(
                        code="SEC011",
                        message=(
                            f"Line {entry.line_number}: Sensitive key '{entry.key}' has weak or default "
                            f"value '{val}'."
                        ),
                        line=entry.line_number,
                        key=entry.key,
                        severity=Severity.ERROR,
                        suggested_fix="Generate a strong, cryptographically secure secret.",
                    )
                )
                continue

            # 3. High entropy secret detection on sensitive keys
            if len(val) >= 24:
                entropy = calculate_shannon_entropy(val)
                # Hex secrets max entropy is ~4.0, base64 ~5.9
                threshold = 3.3 if re.fullmatch(r"[0-9a-fA-F]+", val) else 4.0
                if entropy >= threshold:
                    findings.append(
                        Diagnostic(
                            code="SEC012",
                            message=(
                                f"Line {entry.line_number}: Key '{entry.key}' appears to contain a high-entropy "
                                f"secret (entropy: {entropy:.2f})."
                            ),
                            line=entry.line_number,
                            key=entry.key,
                            severity=Severity.WARNING,
                            suggested_fix="Ensure this secret is not committed to git; use environment injection.",
                        )
                    )

    return SecretAuditResult(
        path=env_file.path or "content",
        findings=findings,
    )


def audit_env_file(
    file_path: Union[str, Path],
    allow_placeholders: bool = True,
) -> SecretAuditResult:
    """Audits secrets in an env file on disk."""
    env_file = parse_env_file(file_path)
    return audit_secrets(env_file, allow_placeholders=allow_placeholders)
