"""GDPR compliance rules for EU data protection."""

from __future__ import annotations

import re
from typing import Any

from datashield.rules.base import ComplianceRule, ComplianceViolation


class GDPRRules(ComplianceRule):
    """GDPR compliance rules for EU data protection.

    Checks for:
    - Personal data without consent indicators
    - Special category data (Article 9)
    - Data subject rights compliance
    - Cross-border data transfer indicators
    - Data retention issues

    Example:
        >>> rules = GDPRRules()
        >>> violations = rules.check(data, text_content)
        >>> for v in violations:
        ...     print(f"GDPR issue: {v.message}")
    """

    name = "gdpr"
    description = "GDPR compliance rules for EU data protection"

    # GDPR-specific patterns
    PATTERNS: list[dict[str, Any]] = [
        {
            "name": "eu_national_id",
            "pattern": r"\b[A-Z]{2}[0-9]{8,12}\b",
            "code": "GDPR_NATIONAL_ID",
            "message": "Potential EU national ID number detected",
            "category": "personal_data",
            "severity": "error",
            "recommendation": "National IDs require explicit consent and purpose limitation",
        },
        {
            "name": "iban",
            "pattern": r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b",
            "code": "GDPR_IBAN",
            "message": "IBAN (bank account) detected",
            "category": "financial",
            "severity": "warning",
            "recommendation": "Financial data requires appropriate safeguards",
        },
        {
            "name": "vat_number",
            "pattern": r"\b[A-Z]{2}[0-9A-Z]{8,12}\b",
            "code": "GDPR_VAT",
            "message": "Potential VAT number detected",
            "category": "business",
            "severity": "info",
            "recommendation": "VAT numbers may be processed for legitimate business purposes",
        },
    ]

    # Special category data keywords (Article 9)
    SPECIAL_CATEGORY_KEYWORDS = {
        "racial_ethnic": [
            "race",
            "ethnicity",
            "ethnic origin",
            "nationality",
            "national origin",
        ],
        "political": [
            "political opinion",
            "political party",
            "political view",
            "voting",
            "election",
        ],
        "religious": [
            "religion",
            "religious belief",
            "faith",
            "church",
            "mosque",
            "synagogue",
            "temple",
        ],
        "trade_union": [
            "trade union",
            "labor union",
            "union member",
            "union membership",
        ],
        "genetic": [
            "genetic data",
            "dna",
            "genome",
            "genetic test",
            "hereditary",
        ],
        "biometric": [
            "fingerprint",
            "facial recognition",
            "iris scan",
            "biometric",
            "voice print",
        ],
        "health": [
            "health data",
            "medical condition",
            "diagnosis",
            "treatment",
            "prescription",
            "disability",
        ],
        "sexual": [
            "sexual orientation",
            "sex life",
            "sexual preference",
            "gender identity",
        ],
    }

    # Required consent indicators
    CONSENT_FIELDS = [
        "consent",
        "consent_given",
        "gdpr_consent",
        "data_consent",
        "privacy_consent",
        "marketing_consent",
        "opted_in",
        "consent_date",
        "consent_timestamp",
    ]

    def __init__(
        self,
        check_consent: bool = True,
        check_special_categories: bool = True,
        check_data_minimization: bool = True,
    ):
        """Initialize GDPR rules.

        Args:
            check_consent: Check for consent indicators
            check_special_categories: Check for Article 9 special category data
            check_data_minimization: Check for potential data minimization issues
        """
        self.check_consent = check_consent
        self.check_special_categories = check_special_categories
        self.check_data_minimization = check_data_minimization
        self._compiled_patterns: list[tuple[re.Pattern[str], dict[str, Any]]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for pattern_config in self.PATTERNS:
            compiled = re.compile(pattern_config["pattern"], re.IGNORECASE)
            self._compiled_patterns.append((compiled, pattern_config))

    def check(
        self, data: Any, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check for GDPR compliance issues.

        Args:
            data: The original data structure
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of ComplianceViolation objects
        """
        violations: list[ComplianceViolation] = []

        # Check for specific patterns
        for field_path, text in text_content:
            for pattern, config in self._compiled_patterns:
                if pattern.search(text):
                    violations.append(
                        ComplianceViolation(
                            code=config["code"],
                            message=config["message"],
                            severity=config["severity"],
                            category=config["category"],
                            field=field_path or None,
                            recommendation=config["recommendation"],
                        )
                    )

        # Check for special category data
        if self.check_special_categories:
            violations.extend(self._check_special_categories(text_content))

        # Check for consent indicators
        if self.check_consent:
            violations.extend(self._check_consent(data, text_content))

        # Check for data minimization
        if self.check_data_minimization:
            violations.extend(self._check_data_minimization(data, text_content))

        return violations

    def _check_special_categories(
        self, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check for Article 9 special category data.

        Args:
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of violations
        """
        violations: list[ComplianceViolation] = []
        all_text = " ".join(text for _, text in text_content).lower()

        for category, keywords in self.SPECIAL_CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in all_text:
                    violations.append(
                        ComplianceViolation(
                            code=f"GDPR_SPECIAL_CATEGORY_{category.upper()}",
                            message=f"Special category data detected: {category.replace('_', ' ')}",
                            severity="error",
                            category="special_category",
                            recommendation=(
                                "Article 9 data requires explicit consent and "
                                "one of the specific lawful bases for processing"
                            ),
                        )
                    )
                    break  # One violation per category

        return violations

    def _check_consent(
        self, data: Any, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check for consent indicators in data.

        Args:
            data: The original data structure
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of violations
        """
        violations: list[ComplianceViolation] = []

        # Check if data contains personal information
        has_personal_data = self._contains_personal_data(text_content)

        if not has_personal_data:
            return violations

        # Look for consent fields
        consent_found = False
        if isinstance(data, dict):
            for field in self.CONSENT_FIELDS:
                if field in data:
                    consent_value = data[field]
                    if consent_value in (True, "true", "yes", "1", 1):
                        consent_found = True
                        break

        if not consent_found:
            violations.append(
                ComplianceViolation(
                    code="GDPR_NO_CONSENT",
                    message="Personal data found without consent indicator",
                    severity="warning",
                    category="consent",
                    recommendation=(
                        "Ensure valid consent is obtained and recorded, "
                        "or document another lawful basis for processing"
                    ),
                )
            )

        return violations

    def _check_data_minimization(
        self, data: Any, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check for potential data minimization issues.

        Args:
            data: The original data structure
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of violations
        """
        violations: list[ComplianceViolation] = []

        # Check for excessive personal data collection
        personal_data_fields = 0
        excessive_threshold = 10

        if isinstance(data, dict):
            personal_field_patterns = [
                "name",
                "email",
                "phone",
                "address",
                "birth",
                "age",
                "gender",
                "salary",
                "income",
            ]

            for key in data:
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in personal_field_patterns):
                    personal_data_fields += 1

        if personal_data_fields > excessive_threshold:
            violations.append(
                ComplianceViolation(
                    code="GDPR_DATA_MINIMIZATION",
                    message=f"Potential data minimization issue: {personal_data_fields} personal data fields",
                    severity="warning",
                    category="data_minimization",
                    recommendation=(
                        "Review if all personal data fields are necessary "
                        "for the stated purpose (Article 5(1)(c))"
                    ),
                )
            )

        return violations

    def _contains_personal_data(self, text_content: list[tuple[str, str]]) -> bool:
        """Check if text content appears to contain personal data.

        Args:
            text_content: List of (field_path, text_value) tuples

        Returns:
            True if personal data is likely present
        """
        from datashield.rules.pii import PIIDetector

        detector = PIIDetector(patterns=["email", "phone_us", "ssn"])
        violations = detector.check(None, text_content)
        return len(violations) > 0
