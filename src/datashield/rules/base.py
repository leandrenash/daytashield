"""Base compliance rule abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ComplianceViolation(BaseModel):
    """A compliance violation detected by a rule."""

    code: str = Field(..., description="Machine-readable violation code")
    message: str = Field(..., description="Human-readable description")
    severity: str = Field("error", description="Severity: error, warning, info")
    category: str = Field(..., description="Violation category (e.g., PHI, PII)")
    field: str | None = Field(None, description="Field path where violation was found")
    matched_value: str | None = Field(None, description="The value that matched (redacted)")
    recommendation: str | None = Field(None, description="How to fix the violation")


class ComplianceRule(ABC):
    """Abstract base class for compliance rules.

    Compliance rules detect specific types of violations in data,
    such as exposed PII, missing consent, or regulatory violations.

    Example:
        >>> class MyRule(ComplianceRule):
        ...     name = "my_rule"
        ...     description = "Checks for custom violations"
        ...
        ...     def check(self, data, text_content):
        ...         violations = []
        ...         for field, text in text_content:
        ...             if "secret" in text.lower():
        ...                 violations.append(ComplianceViolation(
        ...                     code="SECRET_EXPOSED",
        ...                     message="Secret value detected",
        ...                     category="security",
        ...                     field=field,
        ...                 ))
        ...         return violations
    """

    name: str = "base_rule"
    description: str = "Base compliance rule"
    enabled: bool = True

    @abstractmethod
    def check(
        self, data: Any, text_content: list[tuple[str, str]]
    ) -> list[ComplianceViolation]:
        """Check data for compliance violations.

        Args:
            data: The original data structure
            text_content: List of (field_path, text_value) tuples

        Returns:
            List of ComplianceViolation objects
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
