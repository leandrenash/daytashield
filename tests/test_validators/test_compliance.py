"""Tests for ComplianceValidator and rules."""

from __future__ import annotations

from typing import Any

import pytest

from datashield import ComplianceValidator
from datashield.core.result import ValidationStatus, create_result
from datashield.rules import GDPRRules, HIPAARules, PIIDetector


class TestPIIDetector:
    """Tests for PIIDetector."""

    def test_detects_ssn(self) -> None:
        """SSN patterns should be detected."""
        detector = PIIDetector()
        text_content = [("ssn", "My SSN is 123-45-6789")]
        violations = detector.check({}, text_content)
        assert len(violations) > 0
        assert any(v.code == "PII_SSN" for v in violations)

    def test_detects_email(self) -> None:
        """Email patterns should be detected."""
        detector = PIIDetector()
        text_content = [("email", "Contact me at john@example.com")]
        violations = detector.check({}, text_content)
        assert len(violations) > 0
        assert any(v.code == "PII_EMAIL" for v in violations)

    def test_detects_phone(self) -> None:
        """Phone patterns should be detected."""
        detector = PIIDetector()
        text_content = [("phone", "Call me at (555) 123-4567")]
        violations = detector.check({}, text_content)
        assert len(violations) > 0
        assert any(v.code == "PII_PHONE" for v in violations)

    def test_detects_credit_card(self) -> None:
        """Credit card patterns should be detected."""
        detector = PIIDetector()
        text_content = [("cc", "Card: 4532015112830366")]
        violations = detector.check({}, text_content)
        assert len(violations) > 0
        assert any(v.code == "PII_CREDIT_CARD" for v in violations)

    def test_detects_ip_address(self) -> None:
        """IP address patterns should be detected."""
        detector = PIIDetector()
        text_content = [("notes", "User IP: 192.168.1.100")]
        violations = detector.check({}, text_content)
        assert len(violations) > 0
        assert any(v.code == "PII_IP_ADDRESS" for v in violations)

    def test_filtered_patterns(self) -> None:
        """Only specified patterns should be checked."""
        detector = PIIDetector(patterns=["ssn"])
        text_content = [
            ("ssn", "123-45-6789"),
            ("email", "test@example.com"),
        ]
        violations = detector.check({}, text_content)
        assert all(v.code == "PII_SSN" for v in violations)

    def test_severity_override(self) -> None:
        """Severity can be overridden."""
        detector = PIIDetector(severity_overrides={"email": "info"})
        text_content = [("email", "test@example.com")]
        violations = detector.check({}, text_content)
        assert violations[0].severity == "info"


class TestHIPAARules:
    """Tests for HIPAARules."""

    def test_detects_mrn(self) -> None:
        """Medical Record Numbers should be detected."""
        rules = HIPAARules()
        text_content = [("mrn", "MRN: 12345678")]
        violations = rules.check({}, text_content)
        assert any(v.code == "HIPAA_MRN" for v in violations)

    def test_detects_diagnosis_code(self) -> None:
        """ICD codes should be detected."""
        rules = HIPAARules()
        text_content = [("diagnosis", "ICD-10: J06.9")]
        violations = rules.check({}, text_content)
        assert any(v.code == "HIPAA_DIAGNOSIS" for v in violations)

    def test_detects_npi(self) -> None:
        """NPI numbers should be detected."""
        rules = HIPAARules()
        text_content = [("provider", "NPI: 1234567890")]
        violations = rules.check({}, text_content)
        assert any(v.code == "HIPAA_NPI" for v in violations)

    def test_strict_mode_includes_pii(self) -> None:
        """Strict mode should also check PII in healthcare context."""
        rules = HIPAARules(strict=True)
        text_content = [
            ("patient", "Patient John Doe"),
            ("ssn", "SSN: 123-45-6789"),
            ("notes", "Diagnosis: flu"),
        ]
        violations = rules.check({}, text_content)
        # Should find both HIPAA-specific and PII violations
        assert len(violations) > 0


class TestGDPRRules:
    """Tests for GDPRRules."""

    def test_detects_special_category_data(self) -> None:
        """Special category data (Article 9) should be detected."""
        rules = GDPRRules(check_special_categories=True)
        text_content = [
            ("beliefs", "political opinion: conservative"),
            ("health", "health data: diabetic"),
        ]
        violations = rules.check({}, text_content)
        assert any("SPECIAL_CATEGORY" in v.code for v in violations)

    def test_checks_consent(self) -> None:
        """Missing consent indicator should be flagged."""
        rules = GDPRRules(check_consent=True)
        data = {"email": "test@example.com"}  # No consent field
        text_content = [("email", "test@example.com")]
        violations = rules.check(data, text_content)
        assert any(v.code == "GDPR_NO_CONSENT" for v in violations)

    def test_consent_present_no_violation(self) -> None:
        """Present consent indicator should not be flagged."""
        rules = GDPRRules(check_consent=True)
        data = {"email": "test@example.com", "consent": True}
        text_content = [("email", "test@example.com")]
        violations = rules.check(data, text_content)
        assert not any(v.code == "GDPR_NO_CONSENT" for v in violations)


class TestComplianceValidator:
    """Tests for ComplianceValidator."""

    def test_loads_rules_by_name(self) -> None:
        """Rules can be loaded by name."""
        validator = ComplianceValidator(rules=["hipaa", "gdpr", "pii"])
        assert len(validator.rules) == 3

    def test_unknown_rule_raises(self) -> None:
        """Unknown rule name should raise ValueError."""
        with pytest.raises(ValueError):
            ComplianceValidator(rules=["unknown_rule"])

    def test_validation_pipeline(
        self,
        sample_pii_data: dict[str, Any],
    ) -> None:
        """ComplianceValidator should work in pipeline."""
        validator = ComplianceValidator(rules=["pii"])
        result = create_result()
        result = validator.validate(sample_pii_data, result)
        assert result.status in (ValidationStatus.FAILED, ValidationStatus.WARNING)
        assert len(result.messages) > 0

    def test_no_rules_warns(self) -> None:
        """No rules configured should produce a warning."""
        validator = ComplianceValidator()
        result = create_result()
        result = validator.validate({"data": "test"}, result)
        assert any("no compliance rules" in m.message.lower() for m in result.messages)
