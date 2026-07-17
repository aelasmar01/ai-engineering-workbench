from __future__ import annotations

import pytest

from workbench.evidence.redaction import redact_secrets


@pytest.mark.parametrize(
    ("secret", "replacement"),
    [
        ("AKIAIOSFODNN7EXAMPLE", "[REDACTED:aws-access-key-id]"),
        ("ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ", "[REDACTED:github-token]"),
        ("github_pat_abcdefghijklmnopqrstuvwxyz_123456", "[REDACTED:github-token]"),
        ("xoxb-1234567890-secret", "[REDACTED:slack-token]"),
        ("eyJabcdefghijk.eyJabcdefghijk.eyJabcdefghijk", "[REDACTED:jwt]"),
        (
            "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----",
            "[REDACTED:private-key-block]",
        ),
        ("Authorization: supersecrettoken", "[REDACTED:authorization-header]"),
        ("Bearer supersecrettoken", "[REDACTED:authorization-header]"),
        ("password = supersecrettoken", "password = [REDACTED:assignment-secret]"),
        ("api_key=supersecrettoken", "api_key=[REDACTED:assignment-secret]"),
        ("access-token: supersecrettoken", "access-token: [REDACTED:assignment-secret]"),
    ],
)
def test_redact_secrets_replaces_known_secret_patterns(secret: str, replacement: str) -> None:
    assert redact_secrets(f"value: {secret}") == f"value: {replacement}"


@pytest.mark.parametrize(
    "text",
    [
        "token = None",
        "password:",
        "0123456789abcdef0123456789abcdef01234567",
        "123e4567-e89b-12d3-a456-426614174000",
        "eyJ",
    ],
)
def test_redact_secrets_leaves_non_secrets_unredacted(text: str) -> None:
    assert redact_secrets(text) == text


def test_redact_secrets_handles_multiple_secret_types() -> None:
    text = "aws=AKIAIOSFODNN7EXAMPLE github=ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"

    redacted = redact_secrets(text)

    assert "[REDACTED:aws-access-key-id]" in redacted
    assert "[REDACTED:github-token]" in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ" not in redacted
