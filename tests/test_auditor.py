"""Tests for env-doctor secret and vulnerability auditor."""

import tempfile
from pathlib import Path
from env_doctor.auditor import audit_secrets, audit_env_file, calculate_shannon_entropy
from env_doctor.models import Severity


def test_calculate_shannon_entropy():
    assert calculate_shannon_entropy("") == 0.0
    assert calculate_shannon_entropy("aaaaa") == 0.0
    # Higher entropy for random strings
    high_ent = calculate_shannon_entropy("4nF8#kL9@zP2!mX5$qW1")
    assert high_ent > 3.5


def test_audit_clean_env():
    content = """PORT=8080
LOG_LEVEL=info
DATABASE_HOST=localhost
"""
    result = audit_secrets(content)
    assert not result.has_vulnerabilities
    assert len(result.findings) == 0


def test_audit_aws_key():
    content = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC001" for f in result.findings)


def test_audit_github_token():
    mock_token = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
    content = f"GITHUB_TOKEN={mock_token}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC002" for f in result.findings)


def test_audit_slack_token():
    mock_token = "xoxb-" + "123456789012-1234567890123-456789abcdef"
    content = f"SLACK_BOT_TOKEN={mock_token}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC003" for f in result.findings)


def test_audit_stripe_live_key():
    mock_key = "sk" + "_live_" + "1234567890abcdefghijklmnop"
    content = f"STRIPE_KEY={mock_key}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC004" for f in result.findings)


def test_audit_google_api_key():
    mock_key = "AIzaSy" + "D-1234567890abcdefghijklmnopqrst"
    content = f"GOOGLE_MAPS_KEY={mock_key}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC005" for f in result.findings)


def test_audit_openai_key():
    mock_key = "sk-" + "1234567890abcdef1234567890abcdef123456"
    content = f"OPENAI_API_KEY={mock_key}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC006" for f in result.findings)


def test_audit_sendgrid_key():
    mock_key = "SG." + "1234567890123456789012.1234567890123456789012345678901234567890123"
    content = f"SENDGRID_API_KEY={mock_key}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC007" for f in result.findings)


def test_audit_private_key():
    content = "SSH_KEY=\"-----BEGIN RSA PRIVATE KEY-----\\nMIIEowIBAAKCAQEA...\\n-----END RSA PRIVATE KEY-----\"\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC008" for f in result.findings)


def test_audit_jwt_token():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    content = f"AUTH_TOKEN={token}\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC009" for f in result.findings)


def test_audit_db_url_with_credentials():
    content = "DATABASE_URL=postgres://root:secretpass123@db.prod.internal:5432/myapp\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    assert any(f.code == "SEC010" for f in result.findings)


def test_audit_weak_default_passwords():
    content = "APP_SECRET=password\nDB_PASSWORD=123456\nADMIN_TOKEN=admin\n"
    result = audit_secrets(content)
    assert result.has_vulnerabilities
    sec011 = [f for f in result.findings if f.code == "SEC011"]
    assert len(sec011) == 3


def test_audit_allow_placeholders():
    content = "API_KEY=<your-api-key-here>\nSECRET_TOKEN=your_secret_token\nDB_PASS=changeme\n"
    # By default, placeholders are allowed
    res_allowed = audit_secrets(content, allow_placeholders=True)
    assert not res_allowed.has_vulnerabilities

    # When disallowed, changeme is flagged
    res_disallowed = audit_secrets(content, allow_placeholders=False)
    assert res_disallowed.has_vulnerabilities


def test_audit_high_entropy_secret():
    content = "SESSION_SECRET=a8f8e02d8471b65e903bc02fe34d19a27b\n"
    result = audit_secrets(content)
    sec012 = [f for f in result.findings if f.code == "SEC012"]
    assert len(sec012) == 1
    assert sec012[0].severity == Severity.WARNING


def test_audit_file_on_disk():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("AWS_KEY=AKIA1234567890ABCDEF\n")
        f_path = f.name

    try:
        res = audit_env_file(f_path)
        assert res.has_vulnerabilities
        assert len(res.findings) == 1
    finally:
        Path(f_path).unlink()
