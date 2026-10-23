"""Command line interface for env-doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .auditor import audit_env_file
from .comparator import compare_env_files
from .formatter import format_env_file, generate_template
from .linter import lint_env_file
from .models import Severity


def configure_streams() -> None:
    """Configures streams for cross-platform UTF-8 handling."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def get_symbol(unicode_sym: str, ascii_fallback: str) -> str:
    """Returns unicode symbol if stdout encoding supports it, else ascii fallback."""
    try:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        unicode_sym.encode(encoding)
        return unicode_sym
    except Exception:
        return ascii_fallback


ICON_OK = get_symbol("✓", "[OK]")
ICON_FAIL = get_symbol("✗", "[FAIL]")
ICON_WARN = get_symbol("⚠", "[WARN]")
ICON_BULLET = get_symbol("•", "*")


def resolve_env_files(paths: Optional[List[str]]) -> List[Path]:
    """Resolves target .env files from CLI args or discovers local .env files."""
    if paths:
        resolved = []
        for p in paths:
            path_obj = Path(p)
            if path_obj.is_file():
                resolved.append(path_obj)
            elif any(c in p for c in ("*", "?", "[")):
                matched = list(Path(".").glob(p))
                resolved.extend([m for m in matched if m.is_file()])
            else:
                resolved.append(path_obj)
        return resolved

    # Auto-discovery
    default_env = Path(".env")
    if default_env.is_file():
        return [default_env]

    # Look for .env.* files excluding templates
    candidates = []
    for f in Path(".").glob(".env*"):
        if f.is_file() and not f.name.endswith((".example", ".sample", ".template", ".bak")):
            candidates.append(f)

    if candidates:
        return candidates

    return [default_env]


def create_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for env-doctor."""
    parser = argparse.ArgumentParser(
        prog="env-doctor",
        description="Production-grade .env file linter, template drift detector, secret scanner, and formatter.",
    )
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: lint
    lint_p = subparsers.add_parser("lint", help="Lint .env files for syntax, formatting, and standard rules.")
    lint_p.add_argument("files", nargs="*", help="File path(s) or glob pattern to lint (default: .env)")
    lint_p.add_argument("--strict", action="store_true", help="Escalate warnings to errors.")
    lint_p.add_argument("--fix", action="store_true", help="Automatically format and fix issues in-place.")
    lint_p.add_argument("--json", action="store_true", help="Output diagnostics in JSON format.")

    # Command: drift / compare
    drift_p = subparsers.add_parser(
        "drift",
        aliases=["compare"],
        help="Detect drift between target .env and template (.env.example).",
    )
    drift_p.add_argument("target", nargs="?", default=".env", help="Target .env file to evaluate (default: .env)")
    drift_p.add_argument(
        "-t",
        "--template",
        default=None,
        help="Template file to compare against (default: .env.example or .env.template)",
    )
    drift_p.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Treat undocumented extra keys in target as fatal errors.",
    )
    drift_p.add_argument("--json", action="store_true", help="Output drift report in JSON format.")

    # Command: audit / scan
    audit_p = subparsers.add_parser(
        "audit",
        aliases=["scan"],
        help="Scan .env files for leaked secrets, API keys, and insecure default passwords.",
    )
    audit_p.add_argument("files", nargs="*", help="File path(s) to scan (default: .env)")
    audit_p.add_argument("--strict", action="store_true", help="Treat weak passwords as errors.")
    audit_p.add_argument(
        "--no-placeholders",
        action="store_true",
        help="Flag placeholder values (<your-key>, etc.) as issues.",
    )
    audit_p.add_argument("--json", action="store_true", help="Output audit report in JSON format.")

    # Command: fmt / format
    fmt_p = subparsers.add_parser("fmt", aliases=["format"], help="Format .env files with consistent spacing and quotes.")
    fmt_p.add_argument("files", nargs="*", help="File path(s) to format (default: .env)")
    fmt_p.add_argument("-w", "--write", action="store_true", help="Write formatted output directly to files.")
    fmt_p.add_argument("--check", action="store_true", help="Check formatting without writing; exit with 1 if unformatted.")
    fmt_p.add_argument("--sort", action="store_true", help="Sort keys alphabetically while preserving comments.")
    fmt_p.add_argument(
        "--quote",
        choices=["needed", "always", "preserve"],
        default="needed",
        help="Quoting style: 'needed' (default), 'always', or 'preserve'.",
    )

    # Command: template / gen-template
    tmpl_p = subparsers.add_parser(
        "template",
        aliases=["gen-template"],
        help="Generate a sanitized .env.example template from an existing .env file.",
    )
    tmpl_p.add_argument("file", nargs="?", default=".env", help="Source .env file (default: .env)")
    tmpl_p.add_argument("-o", "--out", default=None, help="Output template file path (default: stdout)")

    return parser


def handle_lint(args: argparse.Namespace) -> int:
    """Handles the 'lint' command."""
    files = resolve_env_files(args.files)
    total_errors = 0
    total_warnings = 0
    all_reports = []

    for file_path in files:
        if not file_path.is_file():
            print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
            total_errors += 1
            continue

        if args.fix:
            format_env_file(file_path, write=True)

        diags = lint_env_file(file_path, strict=args.strict)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        warnings = [d for d in diags if d.severity == Severity.WARNING]

        total_errors += len(errors)
        total_warnings += len(warnings)

        all_reports.append({
            "path": str(file_path),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "diagnostics": [d.to_dict() for d in diags],
        })

        if not args.json:
            if not diags:
                print(f"{ICON_OK} {file_path}: All checks passed cleanly.")
            else:
                status = f"{ICON_FAIL}" if errors else f"{ICON_WARN}"
                print(f"{status} {file_path} ({len(errors)} error(s), {len(warnings)} warning(s)):")
                for d in diags:
                    icon = ICON_FAIL if d.severity == Severity.ERROR else (ICON_WARN if d.severity == Severity.WARNING else ICON_BULLET)
                    line_info = f"L{d.line}: " if d.line else ""
                    print(f"  {icon} [{d.code}] {line_info}{d.message}")
                    if d.suggested_fix:
                        print(f"    Suggested fix: {d.suggested_fix}")

    if args.json:
        print(json.dumps({
            "total_files": len(files),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "reports": all_reports,
        }, indent=2))

    return 0 if total_errors == 0 else 1


def handle_drift(args: argparse.Namespace) -> int:
    """Handles the 'drift' command."""
    target_path = Path(args.target)
    if not target_path.is_file():
        print(f"Error: Target file '{target_path}' not found.", file=sys.stderr)
        return 1

    template_path = None
    if args.template:
        template_path = Path(args.template)
    else:
        for candidate in [".env.example", ".env.template", ".env.sample"]:
            cp = Path(candidate)
            if cp.is_file():
                template_path = cp
                break

    if not template_path or not template_path.is_file():
        print(
            "Error: No template file found. Specify one with --template / -t (e.g. .env.example).",
            file=sys.stderr,
        )
        return 1

    result = compare_env_files(template_path, target_path)
    has_drift = bool(result.missing_keys or (args.fail_on_extra and result.extra_keys) or result.type_mismatches)

    if args.json:
        data = result.to_dict()
        data["fail_on_extra"] = args.fail_on_extra
        data["drift_detected"] = has_drift
        print(json.dumps(data, indent=2))
        return 0 if not has_drift else 1

    print(f"Comparing target '{target_path}' against template '{template_path}'...\n")

    if not result.has_drift:
        print(f"{ICON_OK} Perfect match! No drift detected between '{target_path}' and '{template_path}'.")
        return 0

    if result.missing_keys:
        print(f"{ICON_FAIL} Missing {len(result.missing_keys)} required key(s) declared in template:")
        for k in result.missing_keys:
            print(f"  {ICON_FAIL} {k}")

    if result.empty_keys:
        print(f"{ICON_WARN} {len(result.empty_keys)} key(s) are empty in target:")
        for k in result.empty_keys:
            print(f"  {ICON_WARN} {k}")

    if result.type_mismatches:
        print(f"{ICON_FAIL} {len(result.type_mismatches)} type mismatch(es):")
        for m in result.type_mismatches:
            print(f"  {ICON_FAIL} {m['key']}: expected {m['expected_type']}, got {m['actual_type']} ('{m['target_value']}')")

    if result.extra_keys:
        icon = ICON_FAIL if args.fail_on_extra else ICON_WARN
        print(f"{icon} {len(result.extra_keys)} undocumented extra key(s) not in template:")
        for k in result.extra_keys:
            print(f"  {icon} {k}")

    return 0 if not has_drift else 1


def handle_audit(args: argparse.Namespace) -> int:
    """Handles the 'audit' command."""
    files = resolve_env_files(args.files)
    allow_placeholders = not args.no_placeholders
    total_findings = 0
    total_vulnerabilities = 0
    all_reports = []

    for file_path in files:
        if not file_path.is_file():
            print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
            total_vulnerabilities += 1
            continue

        result = audit_env_file(file_path, allow_placeholders=allow_placeholders)
        vulnerabilities = [f for f in result.findings if f.severity == Severity.ERROR or args.strict]
        total_findings += len(result.findings)
        total_vulnerabilities += len(vulnerabilities)

        all_reports.append(result.to_dict())

        if not args.json:
            if not result.findings:
                print(f"{ICON_OK} {file_path}: No secrets, credentials, or weak passwords detected.")
            else:
                status = ICON_FAIL if vulnerabilities else ICON_WARN
                print(f"{status} {file_path}: Found {len(result.findings)} security finding(s):")
                for f in result.findings:
                    icon = ICON_FAIL if f.severity == Severity.ERROR else ICON_WARN
                    line_info = f"L{f.line}: " if f.line else ""
                    print(f"  {icon} [{f.code}] {line_info}{f.message}")
                    if f.suggested_fix:
                        print(f"    Remediation: {f.suggested_fix}")

    if args.json:
        print(json.dumps({
            "total_files": len(files),
            "total_findings": total_findings,
            "total_vulnerabilities": total_vulnerabilities,
            "reports": all_reports,
        }, indent=2))

    return 0 if total_vulnerabilities == 0 else 1


def handle_fmt(args: argparse.Namespace) -> int:
    """Handles the 'fmt' command."""
    files = resolve_env_files(args.files)
    quote_style = f"quote_{args.quote}" if args.quote == "needed" else args.quote
    unformatted_count = 0

    for file_path in files:
        if not file_path.is_file():
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            return 1

        original_content = file_path.read_text(encoding="utf-8", errors="replace")
        formatted_content = format_env_file(
            file_path,
            write=args.write,
            sort_keys=args.sort,
            quote_style=quote_style,
        )

        needs_change = original_content != formatted_content
        if needs_change:
            unformatted_count += 1
            if args.check:
                print(f"{ICON_FAIL} {file_path} needs formatting.")
            elif args.write:
                print(f"{ICON_OK} Formatted and saved {file_path}.")
            else:
                print(formatted_content)
        else:
            if args.check or args.write:
                print(f"{ICON_OK} {file_path} is already cleanly formatted.")

    if args.check and unformatted_count > 0:
        return 1

    return 0


def handle_template(args: argparse.Namespace) -> int:
    """Handles the 'template' command."""
    src_path = Path(args.file)
    if not src_path.is_file():
        print(f"Error: Source file '{src_path}' not found.", file=sys.stderr)
        return 1

    template_str = generate_template(src_path.read_text(encoding="utf-8", errors="replace"))

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(template_str, encoding="utf-8")
        print(f"{ICON_OK} Generated sanitized template at '{out_path}'.")
    else:
        sys.stdout.write(template_str)

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for env-doctor CLI."""
    configure_streams()
    parser = create_parser()

    # If no arguments provided, display help or default to linting if .env exists
    args_list = sys.argv[1:] if argv is None else argv
    if not args_list:
        if Path(".env").is_file():
            args_list = ["lint"]
        else:
            parser.print_help()
            return 0

    # If first argument looks like a flag or file instead of a command, default to lint
    valid_commands = {"lint", "drift", "compare", "audit", "scan", "fmt", "format", "template", "gen-template"}
    first_arg = args_list[0]
    if first_arg not in valid_commands and not first_arg.startswith(("-h", "--help", "-v", "--version")):
        args_list = ["lint"] + args_list

    args = parser.parse_args(args_list)

    if args.command == "lint":
        return handle_lint(args)
    elif args.command in ("drift", "compare"):
        return handle_drift(args)
    elif args.command in ("audit", "scan"):
        return handle_audit(args)
    elif args.command in ("fmt", "format"):
        return handle_fmt(args)
    elif args.command in ("template", "gen-template"):
        return handle_template(args)

    return 0
