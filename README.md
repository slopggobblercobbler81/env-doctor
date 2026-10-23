# env-doctor 🩺

[![CI](https://github.com/slopggobblercobbler81/env-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/env-doctor/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

> **Production-grade `.env` file linter, template drift detector, secret vulnerability scanner, and formatter.**

`env-doctor` ensures your environment variable files are syntactically sound, synchronized with deployment templates, free of leaked secrets and default passwords, and formatted to standard POSIX conventions.

---

## ⚡ Features

- 🔍 **Strict `.env` Linter**: Catches duplicate keys, missing `=` signs, unwanted whitespace around operators, lowercase / non-standard keys, unquoted special characters, trailing whitespace, and unclosed quotes.
- 📐 **Template Drift Detection**: Compares local `.env` files against `.env.example` or `.env.template` to flag missing required keys, undocumented extra keys, empty configurations, and semantic type mismatches.
- 🛡️ **Secret & Credential Scanner**: Scans for leaked AWS keys, GitHub tokens, Slack tokens, Stripe live keys, Google API keys, OpenAI keys, private keys, JWT tokens, plaintext database connection passwords, and weak default passwords.
- 🎨 **Deterministic Formatter**: Automatically fixes formatting, normalizes quoting, cleans up whitespace, and optionally sorts variables alphabetically while preserving code comments.
- 📋 **Sanitized Template Generator**: Instantly generate clean `.env.example` templates from existing `.env` files with automatic placeholder substitution for sensitive keys.
- 🚀 **Zero External Dependencies**: Pure Python standard library implementation. Lightning fast and portable across Linux, macOS, and Windows.

---

## 📦 Installation

```bash
pip install env-doctor
```

Or install in development mode:

```bash
git clone https://github.com/slopggobblercobbler81/env-doctor.git
cd env-doctor
pip install -e .
```

---

## 🚀 Quick Start

### 1. Lint Environment Files

Check `.env` files for syntax errors and convention violations:

```bash
# Lint default .env
env-doctor lint

# Lint multiple files or glob patterns
env-doctor lint .env .env.staging .env.production

# Escalate warnings to errors (ideal for CI)
env-doctor lint --strict

# Automatically fix fixable issues (spacing, quotes, whitespace)
env-doctor lint --fix

# Output results in machine-readable JSON
env-doctor lint --json
```

### 2. Detect Drift Against Templates

Ensure local and production environments match your template specifications:

```bash
# Compare .env against .env.example
env-doctor drift

# Specify custom template and target
env-doctor drift .env.production --template .env.template

# Treat undocumented extra keys as fatal errors
env-doctor drift --fail-on-extra
```

### 3. Scan for Leaked Secrets and Weak Credentials

Audit your environment files to prevent accidental credential commits:

```bash
# Scan default .env
env-doctor audit

# Scan specific files
env-doctor audit .env*

# Strict mode: treat weak/default passwords as fatal errors
env-doctor audit --strict
```

### 4. Format Environment Files

Normalize spacing and quoting:

```bash
# Check formatting without modifying files (exits with 1 if unformatted)
env-doctor fmt --check

# Format files in-place
env-doctor fmt --write

# Sort variables alphabetically
env-doctor fmt --write --sort

# Standardize quoting style ('needed', 'always', or 'preserve')
env-doctor fmt --write --quote always
```

### 5. Generate Sanitized `.env.example`

Generate a template from an existing environment file:

```bash
# Print template to stdout
env-doctor template .env

# Write directly to .env.example
env-doctor template .env --out .env.example
```

---

## 📋 Diagnostic Rule Reference

### Linter Rules

| Code | Severity | Description |
|---|---|---|
| `ENV001` | ERROR / WARN | Duplicate key declaration |
| `ENV002` | ERROR | Missing `=` delimiter (syntax error) |
| `ENV003` | WARNING | Whitespace surrounding `=` delimiter |
| `ENV004` | WARNING | Non-standard variable naming (not uppercase SNAKE_CASE) |
| `ENV005` | WARNING | Unquoted value containing spaces, `#`, or special characters |
| `ENV006` | WARNING | Trailing whitespace at end of line |
| `ENV007` | WARNING | Empty variable value |
| `ENV008` | ERROR | Unclosed quotation mark |
| `ENV009` | INFO | Bash `export` prefix present |

### Security Auditor Rules

| Code | Severity | Description |
|---|---|---|
| `SEC001` | ERROR | Exposed AWS Access Key ID (`AKIA...`) |
| `SEC002` | ERROR | Exposed GitHub Personal Access Token (`ghp_...`) |
| `SEC003` | ERROR | Exposed Slack API Token (`xoxb-...`) |
| `SEC004` | ERROR | Exposed Stripe Live Secret Key (`sk_live_...`) |
| `SEC005` | ERROR | Exposed Google API Key (`AIza...`) |
| `SEC006` | ERROR | Exposed OpenAI or Anthropic API Key (`sk-...`) |
| `SEC007` | ERROR | Exposed SendGrid API Key (`SG...`) |
| `SEC008` | ERROR | Exposed Private Key (`-----BEGIN ... PRIVATE KEY-----`) |
| `SEC009` | ERROR | Hardcoded JSON Web Token (JWT) |
| `SEC010` | ERROR | Database connection URL with embedded plaintext credentials |
| `SEC011` | ERROR | Insecure or default password (`password`, `admin`, `123456`, etc.) |
| `SEC012` | WARNING | High-entropy secret detected in sensitive variable |

---

## 🐍 Python Library API

`env-doctor` can also be used as a Python library within your deployment scripts or CI pipelines:

```python
from env_doctor import lint_env, compare_envs, audit_secrets, format_env

# 1. Linting
diagnostics = lint_env("PORT = 8080\\nAPI_KEY=xyz\\n")
for diag in diagnostics:
    print(f"[{diag.code}] {diag.message}")

# 2. Drift Detection
drift = compare_envs(
    source="PORT=8080\\nDATABASE_URL=postgres://...\\n",
    target="PORT=8080\\n",
)
if drift.has_drift:
    print(f"Missing keys: {drift.missing_keys}")

# 3. Secret Audit
audit = audit_secrets("AWS_KEY=AKIAIOSFODNN7EXAMPLE\\n")
if audit.has_vulnerabilities:
    print(f"Found {len(audit.findings)} security issues!")

# 4. Formatting
formatted = format_env("A = 1\\nB = 2\\n", sort_keys=True)
print(formatted)
```

---

## ⚙️ GitHub Actions CI Example

```yaml
name: Lint Environment Files

on: [push, pull_request]

jobs:
  env-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install env-doctor
      - name: Verify .env.example
        run: env-doctor lint .env.example --strict
      - name: Security Scan
        run: env-doctor audit .env.example
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
