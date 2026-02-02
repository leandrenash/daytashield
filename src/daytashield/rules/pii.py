"""PII (Personally Identifiable Information) detection rules."""

from __future__ import annotations

import re
from typing import Any

from daytashield.rules.base import ComplianceRule, ComplianceViolation


class PIIDetector(ComplianceRule):
    """Detects personally identifiable information in data.

    Scans for common PII patterns including:
    - Social Security Numbers (SSN)
    - Credit card numbers
    - Email addresses
    - Phone numbers
    - IP addresses
    - Passport numbers
    - Driver's license numbers

    Example:
        >>> detector = PIIDetector()
        >>> violations = detector.check(data, [("email", "john@example.com")])
        >>> for v in violations:
        ...     print(f"{v.code}: {v.message}")
    """

    name = "pii"
    description = "Detects personally identifiable information"

    # PII patterns with their metadata
    PATTERNS: list[dict[str, Any]] = [
        {
            "name": "ssn",
            "pattern": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
            "code": "PII_SSN",
            "message": "Social Security Number detected",
            "category": "ssn",
            "severity": "error",
            "recommendation": "Remove or encrypt SSN before processing",
        },
        {
            "name": "credit_card",
            "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
            "code": "PII_CREDIT_CARD",
            "message": "Credit card number detected",
            "category": "financial",
            "severity": "error",
            "recommendation": "Remove or tokenize credit card numbers",
        },
        {
            "name": "email",
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "code": "PII_EMAIL",
            "message": "Email address detected",
            "category": "contact",
            "severity": "warning",
            "recommendation": "Consider if email is necessary or should be hashed",
        },
        {
            "name": "phone_us",
            "pattern": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
            "code": "PII_PHONE",
            "message": "Phone number detected",
            "category": "contact",
            "severity": "warning",
            "recommendation": "Consider if phone number is necessary",
        },
        {
            "name": "ip_address",
            "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            "code": "PII_IP_ADDRESS",
            "message": "IP address detected",
            "category": "technical",
            "severity": "warning",
            "recommendation": "Consider anonymizing IP addresses",
        },
        {
            "name": "passport_us",
            "pattern": r"\b[A-Z]{1,2}[0-9]{6,9}\b",
            "code": "PII_PASSPORT",
            "message": "Potential passport number detected",
            "category": "identity",
            "severity": "error",
            "recommendation": "Remove passport numbers from data",
        },
        {
            "name": "date_of_birth",
            "pattern": r"\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12][0-9]|3[01])[-/](?:19|20)\d{2}\b",
            "code": "PII_DOB",
            "message": "Date of birth detected",
            "category": "identity",
            "severity": "warning",
            "recommendation": "Consider if full DOB is necessary (year might suffice)",
        },
        {
            "name": "drivers_license",
            "pattern": r"\b[A-Z][0-9]{7,8}\b",
            "code": "PII_DRIVERS_LICENSE",
            "message": "Potential driver's license number detected",
            "category": "identity",
            "severity": "error",
            "recommendation": "Remove driver's license numbers",
        },
    ]

    def __init__(
        self,
        patterns: list[str] | None = None,
        severity_overrides: dict[str, str] | None = None,
    ):
        """Initialize the PII detector.

        Args:
            patterns: List of pattern names to enable (None = all)
            severity_overrides: Override severity for specific patterns
        """
        self.enabled_patterns = patterns
        self.severity_overrides = severity_overrides or {}
        self._compiled_patterns: list[tuple[re.Pattern[str], dict[str, Any]]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for pattern_config in self.PATTERNS:
            if self.enabled_patterns and pattern_config["name"] not in self.enabled_patterns:
                continue

            compiled = re.compile(pattern_config["pattern"], re.IGNORECASE)
            self._compiled_patterns.append((compiled, pattern_config))

    def check(
        self, data: Any, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check for PII in the text content.

        Args:
            data: The original data structure (unused for pattern matching)
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of ComplianceViolation objects
        """
        violations: list[ComplianceViolation] = []
        seen: set[tuple[str, str, str]] = set()  # Dedupe by (field, code, match)

        for field_path, text in text_content:
            for pattern, config in self._compiled_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    # Get the matched string
                    matched_str = match if isinstance(match, str) else match[0]

                    # Dedupe
                    key = (field_path, config["code"], matched_str)
                    if key in seen:
                        continue
                    seen.add(key)

                    # Get severity (with possible override)
                    severity = self.severity_overrides.get(
                        config["name"], config["severity"]
                    )

                    # Redact the matched value for logging
                    redacted = self._redact(matched_str, config["name"])

                    violations.append(
                        ComplianceViolation(
                            code=config["code"],
                            message=config["message"],
                            severity=severity,
                            category=config["category"],
                            field=field_path or None,
                            matched_value=redacted,
                            recommendation=config["recommendation"],
                        )
                    )

        return violations

    def _redact(self, value: str, pattern_name: str) -> str:
        """Redact a matched value for safe logging.

        Args:
            value: The matched value
            pattern_name: Name of the pattern that matched

        Returns:
            Redacted value
        """
        if len(value) <= 4:
            return "*" * len(value)

        if pattern_name in ("ssn", "credit_card", "phone_us"):
            # Show last 4 digits
            return "*" * (len(value) - 4) + value[-4:]
        elif pattern_name == "email":
            # Show first char and domain
            at_idx = value.find("@")
            if at_idx > 0:
                return value[0] + "*" * (at_idx - 1) + value[at_idx:]
            return "*" * len(value)
        else:
            # Generic: show first and last char
            return value[0] + "*" * (len(value) - 2) + value[-1]
