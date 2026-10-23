"""Tests for env-doctor linter."""

import tempfile
from pathlib import Path
from env_doctor.linter import lint_env, lint_env_file
from env_doctor.models import Severity


def test_lint_clean_env():
    content = """# Clean env
APP_ENV=production
PORT=8080
DATABASE_URL="postgres://localhost:5432/db"
"""
    diags = lint_env(content)
    assert len(diags) == 0


def test_lint_duplicate_keys():
    content = """PORT=8080
PORT=9000
"""
    diags = lint_env(content)
    dup = [d for d in diags if d.code == "ENV001"]
    assert len(dup) == 1
    assert dup[0].severity == Severity.ERROR
    assert "previously declared" in dup[0].message


def test_lint_duplicate_identical_keys():
    content = """PORT=8080
PORT=8080
"""
    diags = lint_env(content)
    dup = [d for d in diags if d.code == "ENV001"]
    assert len(dup) == 1
    assert dup[0].severity == Severity.WARNING


def test_lint_syntax_missing_equals():
    content = """VALID=1
INVALID_NO_EQUALS
ANOTHER=2
"""
    diags = lint_env(content)
    err = [d for d in diags if d.code == "ENV002"]
    assert len(err) == 1
    assert err[0].severity == Severity.ERROR


def test_lint_spaces_around_equals():
    content = "FOO = bar\nBAZ= qux\nCORRECT=1"
    diags = lint_env(content)
    spaces = [d for d in diags if d.code == "ENV003"]
    assert len(spaces) == 2
    assert spaces[0].suggested_fix == "FOO=bar"
    assert spaces[1].suggested_fix == "BAZ=qux"


def test_lint_non_standard_key_naming():
    content = """app_port=8080
api-key=123
123_INVALID=true
VALID_KEY_1=ok
"""
    diags = lint_env(content)
    names = [d for d in diags if d.code == "ENV004"]
    assert len(names) == 3
    keys = [d.key for d in names]
    assert "app_port" in keys
    assert "api-key" in keys
    assert "123_INVALID" in keys


def test_lint_unquoted_spaces():
    content = """TITLE=My Awesome Application
TAGS=alpha beta gamma
SAFE="quoted title"
"""
    diags = lint_env(content)
    unquoted = [d for d in diags if d.code == "ENV005"]
    assert len(unquoted) == 2
    assert unquoted[0].suggested_fix == 'TITLE="My Awesome Application"'


def test_lint_trailing_whitespace():
    content = "KEY1=val1   \nKEY2=val2\t\nKEY3=val3\n"
    diags = lint_env(content)
    trailing = [d for d in diags if d.code == "ENV006"]
    assert len(trailing) == 2


def test_lint_empty_value():
    content = "EMPTY_KEY=\nNOT_EMPTY=123"
    diags = lint_env(content)
    empty = [d for d in diags if d.code == "ENV007"]
    assert len(empty) == 1
    assert empty[0].key == "EMPTY_KEY"


def test_lint_unclosed_quotes():
    content = 'UNCLOSED="hello world'
    diags = lint_env(content)
    unclosed = [d for d in diags if d.code == "ENV008"]
    assert len(unclosed) == 1
    assert unclosed[0].severity == Severity.ERROR


def test_lint_export_prefix():
    content = "export API_TOKEN=xyz"
    diags = lint_env(content)
    exp = [d for d in diags if d.code == "ENV009"]
    assert len(exp) == 1
    assert exp[0].severity == Severity.INFO


def test_lint_strict_mode():
    content = "EMPTY_KEY=\nexport FOO=bar"
    diags = lint_env(content, strict=True)
    # In strict mode, warnings become errors
    empty_diag = [d for d in diags if d.code == "ENV007"][0]
    assert empty_diag.severity == Severity.ERROR


def test_lint_disabled_rule():
    content = "EMPTY_KEY=\nFOO = bar"
    diags = lint_env(content, rules={"ENV007": False})
    codes = [d.code for d in diags]
    assert "ENV007" not in codes
    assert "ENV003" in codes


def test_lint_file_on_disk():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("A = 1\n")
        f_path = f.name

    try:
        diags = lint_env_file(f_path)
        assert len(diags) == 1
        assert diags[0].code == "ENV003"
    finally:
        Path(f_path).unlink()
