"""Tests for env-doctor parser."""

import tempfile
from pathlib import Path
import pytest
from env_doctor.parser import parse_env, parse_env_file


def test_parse_simple_key_values():
    content = "KEY1=value1\nKEY2=value2\n"
    env = parse_env(content)
    assert len(env) == 2
    assert env.get("KEY1") == "value1"
    assert env.get("KEY2") == "value2"
    assert env["KEY1"] == "value1"
    assert "KEY1" in env
    assert "MISSING" not in env


def test_parse_comments_and_blank_lines():
    content = """# Header comment
KEY1=val1

# Inline block
KEY2=val2
"""
    env = parse_env(content)
    assert len(env) == 2
    assert env.get("KEY1") == "val1"
    assert env.get("KEY2") == "val2"
    comments = [e for e in env.entries if e.is_comment]
    assert len(comments) == 2
    assert comments[0].inline_comment == "Header comment"


def test_parse_quoted_strings():
    content = '''
DOUBLE="hello world"
SINGLE='single quoted'
ESCAPED="line1\\nline2\\t\\"quoted\\""
ESCAPED_SINGLE='it\\'s fine'
'''
    env = parse_env(content)
    assert env.get("DOUBLE") == "hello world"
    assert env.get("SINGLE") == "single quoted"
    assert env.get("ESCAPED") == 'line1\nline2\t"quoted"'
    assert env.get("ESCAPED_SINGLE") == "it's fine"


def test_parse_inline_comments():
    content = """
PORT=8080 # Server port
URL="https://example.com" # Production URL
HASH_IN_VAL=http://localhost:3000/#fragment
"""
    env = parse_env(content)
    assert env.get("PORT") == "8080"
    port_entry = [e for e in env.entries if e.key == "PORT"][0]
    assert port_entry.inline_comment == "Server port"

    url_entry = [e for e in env.entries if e.key == "URL"][0]
    assert url_entry.inline_comment == "Production URL"

    assert env.get("HASH_IN_VAL") == "http://localhost:3000/#fragment"


def test_parse_export_prefix():
    content = "export DATABASE_URL=postgres://localhost/db\nexport API_KEY=abc\n"
    env = parse_env(content)
    assert env.get("DATABASE_URL") == "postgres://localhost/db"
    assert env.get("API_KEY") == "abc"
    for e in env.entries:
        if e.key:
            assert e.is_export is True


def test_parse_spaces_around_equals():
    content = "FOO = bar\nBAZ= qux\nABC =xyz\n"
    env = parse_env(content)
    assert env.get("FOO") == "bar"
    assert env.get("BAZ") == "qux"
    assert env.get("ABC") == "xyz"
    for e in env.entries:
        if e.key:
            assert e.has_spaces_around_eq is True


def test_parse_multiline_double_quotes():
    content = '''MULTILINE="first line
second line
third line"
AFTER=123
'''
    env = parse_env(content)
    assert env.get("MULTILINE") == "first line\nsecond line\nthird line"
    assert env.get("AFTER") == "123"


def test_parse_unclosed_quotes():
    content = 'BROKEN="unclosed string without end\nNEXT=1'
    env = parse_env(content)
    entry = [e for e in env.entries if e.key == "BROKEN"][0]
    assert entry.unclosed_quote is True


def test_parse_file_on_disk():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("DISK_KEY=disk_value\n")
        f_path = f.name

    try:
        env = parse_env_file(f_path)
        assert env.get("DISK_KEY") == "disk_value"
        assert env.path is not None
        assert env.items() == [("DISK_KEY", "disk_value")]
    finally:
        Path(f_path).unlink()


def test_parse_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_env_file("non_existent_file_xyz.env")


def test_parse_malformed_line_no_equals():
    content = "JUST_A_WORD_NO_EQUALS\nVALID=1"
    env = parse_env(content)
    entry = [e for e in env.entries if e.key == "JUST_A_WORD_NO_EQUALS"][0]
    assert entry.value == ""
