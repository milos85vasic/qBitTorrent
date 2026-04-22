import logging
import re

_SENSITIVE_PATTERN = re.compile(
    r"(PASSWORD|COOKIE|TOKEN|SECRET|API_KEY)\s*[=:]\s*\S+",
    re.IGNORECASE,
)


class CredentialScrubber(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SENSITIVE_PATTERN.sub(
            lambda m: f"{m.group(1)}{m.group(0)[len(m.group(1))]}***",
            record.msg if isinstance(record.msg, str) else str(record.msg),
        )
        return True
