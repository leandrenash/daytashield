"""Compliance validation for regulatory requirements."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from daytashield.core.result import ValidationResult, ValidationStatus
from daytashield.validators.base import BaseValidator, ValidatorConfig

if TYPE_CHECKING:
    from daytashield.rules.base import ComplianceRule


class ComplianceValidatorConfig(ValidatorConfig):
    """Configuration for compliance validation."""

    fail_on_warning: bool = Field(False, description="Treat warnings as failures")
    include_passed_rules: bool = Field(False, description="Include passed rules in messages")
    scan_nested: bool = Field(True, description="Scan nested objects and arrays")
    max_depth: int = Field(10, description="Maximum nesting depth to scan")


class ComplianceValidator(BaseValidator):
    """Validates data against compliance rules (HIPAA, GDPR, PII, etc.).

    Uses pluggable rule packs to check for compliance violations. Rules
    can detect sensitive data, check for required fields, validate
    consent flags, etc.

    Example:
        >>> from daytashield.rules import HIPAARules, GDPRRules
        >>> validator = ComplianceValidator(
        ...     rules=[HIPAARules(), GDPRRules()],
        ... )
        >>> result = validator.validate(patient_data, result)

    Built-in rule packs:
    - HIPAARules: Healthcare data compliance (PHI detection)
    - GDPRRules: EU data protection (consent, data subject rights)
    - PIIDetector: Personal information detection (SSN, emails, etc.)
    """

    name = "compliance"

    def __init__(
        self,
        rules: list[ComplianceRule] | list[str] | None = None,
        config: ComplianceValidatorConfig | dict[str, Any] | None = None,
    ):
        """Initialize the compliance validator.

        Args:
            rules: List of rule objects or rule names to load
            config: Validator configuration
        """
        if config is None:
            super().__init__(ComplianceValidatorConfig())
        elif isinstance(config, dict):
            super().__init__(ComplianceValidatorConfig(**config))
        else:
            super().__init__(config)

        self.rules: list[ComplianceRule] = []

        if rules:
            for rule in rules:
                if isinstance(rule, str):
                    self.rules.append(self._load_rule_by_name(rule))
                else:
                    self.rules.append(rule)

    def _load_rule_by_name(self, name: str) -> ComplianceRule:
        """Load a rule pack by name.

        Args:
            name: Rule name (hipaa, gdpr, pii)

        Returns:
            ComplianceRule instance

        Raises:
            ValueError: If rule name is unknown
        """
        name_lower = name.lower()

        if name_lower == "hipaa":
            from daytashield.rules.hipaa import HIPAARules
            return HIPAARules()
        elif name_lower == "gdpr":
            from daytashield.rules.gdpr import GDPRRules
            return GDPRRules()
        elif name_lower == "pii":
            from daytashield.rules.pii import PIIDetector
            return PIIDetector()
        else:
            raise ValueError(f"Unknown rule pack: {name}. Available: hipaa, gdpr, pii")

    def add_rule(self, rule: ComplianceRule | str) -> ComplianceValidator:
        """Add a rule to the validator.

        Args:
            rule: Rule object or rule name

        Returns:
            Self for method chaining
        """
        if isinstance(rule, str):
            self.rules.append(self._load_rule_by_name(rule))
        else:
            self.rules.append(rule)
        return self

    def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate data against all compliance rules.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        if not self.rules:
            result.add_message(
                code="COMPLIANCE_NO_RULES",
                message="No compliance rules configured",
                severity=ValidationStatus.WARNING,
                validator=self.name,
            )
            return result

        config = self.config
        if not isinstance(config, ComplianceValidatorConfig):
            config = ComplianceValidatorConfig()

        # Collect all text content to scan
        text_content = self._extract_text_content(data, config.max_depth if config.scan_nested else 1)

        # Run each rule
        total_violations = 0
        total_warnings = 0

        for rule in self.rules:
            violations = rule.check(data, text_content)

            for violation in violations:
                total_violations += 1 if violation.severity == "error" else 0
                total_warnings += 1 if violation.severity == "warning" else 0

                severity = (
                    ValidationStatus.FAILED
                    if violation.severity == "error"
                    else ValidationStatus.WARNING
                )

                result.add_message(
                    code=f"COMPLIANCE_{violation.code}",
                    message=violation.message,
                    severity=severity,
                    validator=self.name,
                    field=violation.field,
                    details={
                        "rule": rule.name,
                        "category": violation.category,
                        "matched_value": violation.matched_value[:50] if violation.matched_value else None,
                        "recommendation": violation.recommendation,
                    },
                )

        # Update result metadata
        result.metadata["compliance_rules_run"] = [r.name for r in self.rules]
        result.metadata["compliance_violations"] = total_violations
        result.metadata["compliance_warnings"] = total_warnings

        # Update status
        if total_violations > 0:
            result.status = ValidationStatus.FAILED
        elif total_warnings > 0:
            if config.fail_on_warning:
                result.status = ValidationStatus.FAILED
            elif result.status == ValidationStatus.PASSED:
                result.status = ValidationStatus.WARNING

        return result

    def _extract_text_content(self, data: Any, max_depth: int, current_depth: int = 0) -> list[tuple[str, str]]:
        """Extract all text content from data for scanning.

        Args:
            data: Data to extract from
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth

        Returns:
            List of (field_path, text_value) tuples
        """
        if current_depth >= max_depth:
            return []

        results: list[tuple[str, str]] = []

        if isinstance(data, str):
            results.append(("", data))
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    results.append((key, value))
                else:
                    nested = self._extract_text_content(value, max_depth, current_depth + 1)
                    results.extend((f"{key}.{path}" if path else key, text) for path, text in nested)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                nested = self._extract_text_content(item, max_depth, current_depth + 1)
                results.extend((f"[{i}].{path}" if path else f"[{i}]", text) for path, text in nested)

        return results

    def __repr__(self) -> str:
        rule_names = [r.name for r in self.rules]
        return f"ComplianceValidator(rules={rule_names})"
