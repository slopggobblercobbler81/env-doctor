"""Tests for env-doctor formatter and template generator."""

import tempfile
from pathlib import Path
from env_doctor.formatter import format_env, format_env_file, generate_template, needs_quotes


def test_needs_quotes():
    assert needs_quotes("simple_value") is False
    assert needs_quotes("value with spaces") is True
    assert needs_quotes("has#hash") is True
    assert needs_quotes("newline\nvalue") is True
    assert needs_quotes('has"quote') is True


def test_format_env_clean_spacing():
    content = """FOO = bar
BAZ  =  qux
EMPTY=
"""
    formatted = format_env(content)
    assert formatted == "FOO=bar\nBAZ=qux\nEMPTY=\n"


def test_format_env_quotes_needed():
    content = """TITLE=My Great App
UNQUOTED_HASH=value#tag
CLEAN=simple
"""
    formatted = format_env(content, quote_style="quote_needed")
    assert 'TITLE="My Great App"' in formatted
    assert 'UNQUOTED_HASH="value#tag"' in formatted
    assert "CLEAN=simple" in formatted


def test_format_env_quote_always():
    content = "PORT=8080\nHOST=localhost\n"
    formatted = format_env(content, quote_style="always")
    assert 'PORT="8080"' in formatted
    assert 'HOST="localhost"' in formatted


def test_format_env_preserve_comments_and_blank_lines():
    content = """# App Configuration
PORT=8080 # default port

# Database settings
DB_NAME=mydb
"""
    formatted = format_env(content)
    assert "# App Configuration" in formatted
    assert "PORT=8080 # default port" in formatted
    assert "# Database settings" in formatted
    assert "DB_NAME=mydb" in formatted


def test_format_env_sort_keys():
    content = """# Z comment
ZEBRA=last
# A comment
ALPHA=first
MIDDLE=mid
"""
    formatted = format_env(content, sort_keys=True)
    lines = [line for line in formatted.strip().splitlines() if not line.startswith("#")]
    assert lines == ["ALPHA=first", "MIDDLE=mid", "ZEBRA=last"]


def test_format_file_on_disk():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("A = 1\nB = 2\n")
        f_path = f.name

    try:
        res = format_env_file(f_path, write=True)
        assert res == "A=1\nB=2\n"
        saved = Path(f_path).read_text(encoding="utf-8")
        assert saved == "A=1\nB=2\n"
    finally:
        Path(f_path).unlink()


def test_generate_template():
    content = """# App Settings
PORT=8080
API_KEY=sk-1234567890abcdef1234567890abcdef
DATABASE_PASSWORD=supersecret_pass
APP_SECRET=top_secret
DEBUG=false
"""
    tmpl = generate_template(content)
    assert "PORT=8080" in tmpl
    assert "DEBUG=false" in tmpl
    assert "API_KEY=<your-api-key>" in tmpl
    assert "DATABASE_PASSWORD=<your-database-password>" in tmpl
    assert "APP_SECRET=<your-app-secret>" in tmpl
    assert "supersecret_pass" not in tmpl
    assert "sk-1234567890abcdef" not in tmpl
