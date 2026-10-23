"""env-doctor: Production-grade .env file linter, drift detector, secret scanner, and formatter."""

from .models import Diagnostic, EnvEntry, EnvFile, Severity
from .parser import parse_env, parse_env_file
from .linter import lint_env, lint_env_file
from .comparator import compare_envs, compare_env_files, EnvDiffResult
from .auditor import audit_secrets, audit_env_file, SecretAuditResult
from .formatter import format_env, format_env_file, generate_template

__version__ = "1.0.0"

__all__ = [
    "Diagnostic",
    "EnvEntry",
    "EnvFile",
    "Severity",
    "parse_env",
    "parse_env_file",
    "lint_env",
    "lint_env_file",
    "compare_envs",
    "compare_env_files",
    "EnvDiffResult",
    "audit_secrets",
    "audit_env_file",
    "SecretAuditResult",
    "format_env",
    "format_env_file",
    "generate_template",
    "__version__",
]
