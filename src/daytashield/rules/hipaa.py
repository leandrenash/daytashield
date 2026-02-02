"""HIPAA compliance rules for healthcare data."""

from __future__ import annotations

import re
from typing import Any

from daytashield.rules.base import ComplianceRule, ComplianceViolation


class HIPAARules(ComplianceRule):
    """HIPAA compliance rules for Protected Health Information (PHI).

    Checks for the 18 HIPAA identifiers:
    1. Names
    2. Geographic data (addresses, zip codes)
    3. Dates (except year)
    4. Phone numbers
    5. Fax numbers
    6. Email addresses
    7. Social Security numbers
    8. Medical record numbers
    9. Health plan beneficiary numbers
    10. Account numbers
    11. Certificate/license numbers
    12. Vehicle identifiers
    13. Device identifiers
    14. Web URLs
    15. IP addresses
    16. Biometric identifiers
    17. Full-face photographs
    18. Any other unique identifying characteristic

    Example:
        >>> rules = HIPAARules()
        >>> violations = rules.check(data, text_content)
        >>> for v in violations:
        ...     print(f"HIPAA violation: {v.message}")
    """

    name = "hipaa"
    description = "HIPAA compliance rules for Protected Health Information"

    # HIPAA-specific patterns
    PATTERNS: list[dict[str, Any]] = [
        {
            "name": "mrn",
            "pattern": r"\b(?:MRN|Medical Record|Record #|Patient ID)[:\s#]*([A-Z0-9]{6,12})\b",
            "code": "HIPAA_MRN",
            "message": "Medical Record Number (MRN) detected",
            "category": "phi",
            "severity": "error",
            "recommendation": "Remove or encrypt MRN per HIPAA requirements",
        },
        {
            "name": "health_plan_id",
            "pattern": r"\b(?:Health Plan|Insurance|Plan ID|Member ID)[:\s#]*([A-Z0-9]{8,15})\b",
            "code": "HIPAA_HEALTH_PLAN",
            "message": "Health plan beneficiary number detected",
            "category": "phi",
            "severity": "error",
            "recommendation": "Remove or encrypt health plan identifiers",
        },
        {
            "name": "diagnosis_code",
            "pattern": r"\b(?:ICD-?10|ICD-?9|Diagnosis)[:\s]*([A-Z][0-9]{2}\.?[0-9A-Z]{0,4})\b",
            "code": "HIPAA_DIAGNOSIS",
            "message": "Diagnosis code detected (ICD)",
            "category": "clinical",
            "severity": "warning",
            "recommendation": "Ensure diagnosis codes are de-identified when required",
        },
        {
            "name": "prescription",
            "pattern": r"\b(?:Rx|Prescription|NDC)[:\s#]*([0-9]{10,11})\b",
            "code": "HIPAA_PRESCRIPTION",
            "message": "Prescription/NDC number detected",
            "category": "clinical",
            "severity": "warning",
            "recommendation": "Review if prescription details need de-identification",
        },
        {
            "name": "provider_npi",
            "pattern": r"\b(?:NPI|Provider ID)[:\s#]*([0-9]{10})\b",
            "code": "HIPAA_NPI",
            "message": "National Provider Identifier (NPI) detected",
            "category": "provider",
            "severity": "warning",
            "recommendation": "NPI may be included but verify context",
        },
        {
            "name": "dea_number",
            "pattern": r"\b(?:DEA)[:\s#]*([A-Z]{2}[0-9]{7})\b",
            "code": "HIPAA_DEA",
            "message": "DEA number detected",
            "category": "provider",
            "severity": "error",
            "recommendation": "DEA numbers should not be exposed",
        },
    ]

    # Keywords that suggest PHI context
    PHI_CONTEXT_KEYWORDS = [
        "patient",
        "diagnosis",
        "treatment",
        "prescription",
        "medical",
        "health",
        "hospital",
        "doctor",
        "physician",
        "nurse",
        "clinic",
        "symptom",
        "medication",
        "allergy",
        "procedure",
        "surgery",
        "lab result",
        "test result",
        "vital sign",
        "blood pressure",
        "heart rate",
        "temperature",
    ]

    def __init__(self, strict: bool = True):
        """Initialize HIPAA rules.

        Args:
            strict: If True, flag any data that appears to be in healthcare context
        """
        self.strict = strict
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
        """Check for HIPAA violations.

        Args:
            data: The original data structure
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of ComplianceViolation objects
        """
        violations: list[ComplianceViolation] = []

        # Check if data appears to be in healthcare context
        is_healthcare_context = self._detect_healthcare_context(text_content)

        # Check specific patterns
        for field_path, text in text_content:
            for pattern, config in self._compiled_patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    # Get the captured group (the actual identifier)
                    matched_value = match.group(1) if match.groups() else match.group(0)

                    violations.append(
                        ComplianceViolation(
                            code=config["code"],
                            message=config["message"],
                            severity=config["severity"],
                            category=config["category"],
                            field=field_path or None,
                            matched_value=self._redact(matched_value),
                            recommendation=config["recommendation"],
                        )
                    )

        # In strict mode, check for general PII in healthcare context
        if self.strict and is_healthcare_context:
            from daytashield.rules.pii import PIIDetector

            pii_detector = PIIDetector(
                patterns=["ssn", "email", "phone_us", "date_of_birth"],
                severity_overrides={
                    "ssn": "error",
                    "email": "error",  # Elevate to error in healthcare context
                    "phone_us": "error",
                    "date_of_birth": "error",
                },
            )
            pii_violations = pii_detector.check(data, text_content)

            # Add HIPAA context to PII violations
            for v in pii_violations:
                v.code = f"HIPAA_{v.code}"
                v.message = f"{v.message} (in healthcare context)"
                v.recommendation = (
                    f"HIPAA requires protection of this data. {v.recommendation}"
                )
                violations.append(v)

        return violations

    def _detect_healthcare_context(self, text_content: list[tuple[str, str]]) -> bool:
        """Detect if data appears to be in a healthcare context.

        Args:
            text_content: List of (field_path, text_value) tuples

        Returns:
            True if healthcare context is detected
        """
        all_text = " ".join(text for _, text in text_content).lower()

        keyword_count = sum(
            1 for keyword in self.PHI_CONTEXT_KEYWORDS if keyword in all_text
        )

        # Consider healthcare context if 2+ keywords found
        return keyword_count >= 2

    def _redact(self, value: str) -> str:
        """Redact a matched value for safe logging."""
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
