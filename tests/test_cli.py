"""Tests for env-doctor CLI."""

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from env_doctor import __version__
from env_doctor.cli import main, resolve_env_files


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "env-doctor" in captured.out
    assert "lint" in captured.out
    assert "drift" in captured.out
    assert "audit" in captured.out
    assert "fmt" in captured.out


def test_cli_lint_clean(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("PORT=8080\nHOST=localhost\n")
        f_path = f.name

    try:
        ret = main(["lint", f_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "All checks passed cleanly" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_lint_errors(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("PORT=8080\nPORT=9000\nMALFORMED_NO_EQUALS\n")
        f_path = f.name

    try:
        ret = main(["lint", f_path])
        assert ret == 1
        captured = capsys.readouterr()
        assert "ENV001" in captured.out
        assert "ENV002" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_lint_json(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("A = 1\n")
        f_path = f.name

    try:
        ret = main(["lint", f_path, "--json"])
        assert ret == 0  # warning only
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_warnings"] == 1
        assert data["reports"][0]["diagnostics"][0]["code"] == "ENV003"
    finally:
        Path(f_path).unlink()


def test_cli_lint_fix(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("A = 1\nB = 2\n")
        f_path = f.name

    try:
        ret = main(["lint", f_path, "--fix"])
        assert ret == 0
        fixed = Path(f_path).read_text(encoding="utf-8")
        assert fixed == "A=1\nB=2\n"
    finally:
        Path(f_path).unlink()


def test_cli_lint_missing_file(capsys):
    ret = main(["lint", "definitely_non_existent.env"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_cli_drift_clean(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".example") as f1, \
         tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f2:
        f1.write("PORT=8080\nHOST=localhost\n")
        f2.write("PORT=3000\nHOST=127.0.0.1\n")
        f1_path, f2_path = f1.name, f2.name

    try:
        ret = main(["drift", f2_path, "-t", f1_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Perfect match" in captured.out
    finally:
        Path(f1_path).unlink()
        Path(f2_path).unlink()


def test_cli_drift_detected(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".example") as f1, \
         tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f2:
        f1.write("PORT=8080\nSECRET_KEY=xxx\n")
        f2.write("PORT=8080\nEXTRA_VAL=1\n")
        f1_path, f2_path = f1.name, f2.name

    try:
        ret = main(["drift", f2_path, "-t", f1_path])
        assert ret == 1
        captured = capsys.readouterr()
        assert "SECRET_KEY" in captured.out
        assert "EXTRA_VAL" in captured.out
    finally:
        Path(f1_path).unlink()
        Path(f2_path).unlink()


def test_cli_drift_json(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".example") as f1, \
         tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f2:
        f1.write("PORT=8080\nMISSING_ONE=1\n")
        f2.write("PORT=8080\n")
        f1_path, f2_path = f1.name, f2.name

    try:
        ret = main(["drift", f2_path, "-t", f1_path, "--json"])
        assert ret == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["drift_detected"] is True
        assert data["missing_keys"] == ["MISSING_ONE"]
    finally:
        Path(f1_path).unlink()
        Path(f2_path).unlink()


def test_cli_audit_clean(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("PORT=8080\nDEBUG=true\n")
        f_path = f.name

    try:
        ret = main(["audit", f_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "No secrets" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_audit_findings(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("AWS_KEY=AKIA1234567890ABCDEF\n")
        f_path = f.name

    try:
        ret = main(["audit", f_path])
        assert ret == 1
        captured = capsys.readouterr()
        assert "SEC001" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_audit_json(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz\n")
        f_path = f.name

    try:
        ret = main(["audit", f_path, "--json"])
        assert ret == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_vulnerabilities"] == 1
    finally:
        Path(f_path).unlink()


def test_cli_fmt_check_and_write(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("A = 1\nB = 2\n")
        f_path = f.name

    try:
        # Check should exit 1 because unformatted
        ret = main(["fmt", f_path, "--check"])
        assert ret == 1

        # Write should format it
        ret = main(["fmt", f_path, "-w"])
        assert ret == 0

        # Now check should pass
        ret = main(["fmt", f_path, "--check"])
        assert ret == 0
    finally:
        Path(f_path).unlink()


def test_cli_template_stdout(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("API_KEY=sk-1234567890abcdef1234567890abcdef\nPORT=8080\n")
        f_path = f.name

    try:
        ret = main(["template", f_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "API_KEY=<your-api-key>" in captured.out
        assert "PORT=8080" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_template_out_file():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f, \
         tempfile.NamedTemporaryFile("w", delete=False, suffix=".out") as out_f:
        f.write("DB_PASSWORD=secret123\n")
        f_path = f.name
        out_path = out_f.name

    try:
        ret = main(["template", f_path, "-o", out_path])
        assert ret == 0
        content = Path(out_path).read_text(encoding="utf-8")
        assert "DB_PASSWORD=<your-db-password>" in content
    finally:
        Path(f_path).unlink()
        Path(out_path).unlink()


def test_cli_main_no_args_displays_help(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "env-doctor" in captured.out


def test_cli_implicit_lint_on_file(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("VALID=1\n")
        f_path = f.name

    try:
        ret = main([f_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "All checks passed cleanly" in captured.out
    finally:
        Path(f_path).unlink()


def test_cli_drift_missing_template(capsys):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("PORT=8080\n")
        f_path = f.name

    try:
        ret = main(["drift", f_path, "-t", "non_existent_template.example"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "Error: No template file found" in captured.err
    finally:
        Path(f_path).unlink()


def test_cli_audit_missing_file(capsys):
    ret = main(["audit", "non_existent_audit.env"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_cli_fmt_missing_file(capsys):
    ret = main(["fmt", "non_existent_fmt.env"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_cli_template_missing_file(capsys):
    ret = main(["template", "non_existent_template.env"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err

