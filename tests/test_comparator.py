"""Tests for env-doctor drift comparator."""

import tempfile
from pathlib import Path
from env_doctor.comparator import compare_envs, compare_env_files, infer_type


def test_infer_type():
    assert infer_type("true") == "boolean"
    assert infer_type("False") == "boolean"
    assert infer_type("1234") == "integer"
    assert infer_type("-42") == "integer"
    assert infer_type("3.1415") == "float"
    assert infer_type("https://api.example.com") == "url"
    assert infer_type("dev@example.org") == "email"
    assert infer_type('{"key": "val"}') == "json"
    assert infer_type("plain_string_value") == "string"


def test_compare_clean_match():
    template = """
PORT=8080
HOST=localhost
DATABASE_URL=postgres://localhost/db
"""
    target = """
PORT=3000
HOST=127.0.0.1
DATABASE_URL=postgres://prod/db
"""
    diff = compare_envs(template, target)
    assert not diff.has_drift
    assert diff.missing_keys == []
    assert diff.extra_keys == []
    assert diff.empty_keys == []
    assert diff.type_mismatches == []


def test_compare_missing_keys():
    template = """
PORT=8000
API_KEY=<your-key>
NEW_SETTING=true
"""
    target = """
PORT=8000
"""
    diff = compare_envs(template, target)
    assert diff.has_drift
    assert "API_KEY" in diff.missing_keys
    assert "NEW_SETTING" in diff.missing_keys


def test_compare_extra_keys():
    template = """
PORT=8000
"""
    target = """
PORT=8000
OBSOLETE_KEY=legacy
"""
    diff = compare_envs(template, target)
    assert diff.has_drift
    assert diff.extra_keys == ["OBSOLETE_KEY"]


def test_compare_empty_keys():
    template = """
PORT=8000
DATABASE_URL=postgres://user:pass@host/db
"""
    target = """
PORT=8000
DATABASE_URL=
"""
    diff = compare_envs(template, target)
    assert diff.has_drift
    assert "DATABASE_URL" in diff.empty_keys


def test_compare_type_mismatches():
    template = """
PORT=8000
ENABLE_FEATURE=true
"""
    target = """
PORT=invalid_port_string
ENABLE_FEATURE=not_a_bool
"""
    diff = compare_envs(template, target)
    assert diff.has_drift
    assert len(diff.type_mismatches) == 2
    keys = [m["key"] for m in diff.type_mismatches]
    assert "PORT" in keys
    assert "ENABLE_FEATURE" in keys


def test_compare_files_on_disk():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".example") as f1, \
         tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f2:
        f1.write("PORT=8000\nSECRET=xyz\n")
        f2.write("PORT=8000\n")
        f1_path, f2_path = f1.name, f2.name

    try:
        diff = compare_env_files(f1_path, f2_path)
        assert diff.missing_keys == ["SECRET"]
        assert diff.to_dict()["has_drift"] is True
    finally:
        Path(f1_path).unlink()
        Path(f2_path).unlink()
