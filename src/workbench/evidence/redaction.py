from __future__ import annotations

import re

PatternEntry = tuple[str, re.Pattern[str]]


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


SECRET_PATTERNS: list[PatternEntry] = [
    ("aws-access-key-id", _compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", _compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-token", _compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("slack-token", _compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", _compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    (
        "private-key-block",
        _compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    ("authorization-header", _compile(r"(?i)\b(authorization|bearer)\b[:= ]+\S{8,}")),
    (
        "assignment-secret",
        _compile(
            r"(?i)\b(?P<key>password|passwd|secret|api[_-]?key|access[_-]?token)"
            r"(?P<separator>\s*[=:]\s*)"
            r"(?P<value>\S{8,})"
        ),
    ),
]


def redact_secrets(text: str) -> str:
    redacted = text
    for name, pattern in SECRET_PATTERNS:
        if name == "assignment-secret":
            redacted = pattern.sub(_redact_assignment_secret, redacted)
        else:
            redacted = pattern.sub(f"[REDACTED:{name}]", redacted)
    return redacted


def _redact_assignment_secret(match: re.Match[str]) -> str:
    return f"{match.group('key')}{match.group('separator')}[REDACTED:assignment-secret]"
