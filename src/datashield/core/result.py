"""Validation result types and data structures."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Status of a validation operation."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ValidationMessage(BaseModel):
    """A single validation message with context."""

    code: str = Field(..., description="Machine-readable error/warning code")
    message: str = Field(..., description="Human-readable description")
    severity: ValidationStatus = Field(..., description="Severity level")
    field: str | None = Field(None, description="Field path that triggered the message")
    validator: str = Field(..., description="Name of the validator that produced this message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    def __str__(self) -> str:
        field_str = f" [{self.field}]" if self.field else ""
        return f"[{self.severity.value.upper()}] {self.validator}{field_str}: {self.message}"


class Provenance(BaseModel):
    """Tracks the origin and processing history of data."""

    source_id: str = Field(..., description="Unique identifier for the data source")
    source_type: str = Field(..., description="Type of source (file, api, stream)")
    source_path: str | None = Field(None, description="Path or URL of the source")
    checksum: str | None = Field(None, description="SHA-256 hash of the original data")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the data was processed",
    )
    processor_chain: list[str] = Field(
        default_factory=list, description="List of processors applied"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional source metadata")


class ValidationResult(BaseModel):
    """Complete result of a validation operation."""

    id: UUID = Field(default_factory=uuid4, description="Unique result identifier")
    status: ValidationStatus = Field(..., description="Overall validation status")
    messages: list[ValidationMessage] = Field(
        default_factory=list, description="All validation messages"
    )
    data: Any = Field(None, description="The validated/transformed data")
    original_data: Any = Field(None, description="The original input data")
    provenance: Provenance | None = Field(None, description="Data provenance information")
    validators_run: list[str] = Field(
        default_factory=list, description="Names of validators that were executed"
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation started",
    )
    completed_at: datetime | None = Field(None, description="When validation completed")
    duration_ms: float | None = Field(None, description="Total validation time in milliseconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional result metadata")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def passed(self) -> bool:
        """Check if validation passed (no failures or errors)."""
        return self.status in (ValidationStatus.PASSED, ValidationStatus.WARNING)

    @property
    def failed(self) -> bool:
        """Check if validation failed."""
        return self.status in (ValidationStatus.FAILED, ValidationStatus.ERROR)

    @property
    def errors(self) -> list[ValidationMessage]:
        """Get all error-level messages."""
        return [m for m in self.messages if m.severity == ValidationStatus.FAILED]

    @property
    def warnings(self) -> list[ValidationMessage]:
        """Get all warning-level messages."""
        return [m for m in self.messages if m.severity == ValidationStatus.WARNING]

    def add_message(
        self,
        code: str,
        message: str,
        severity: ValidationStatus,
        validator: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add a validation message to the result."""
        self.messages.append(
            ValidationMessage(
                code=code,
                message=message,
                severity=severity,
                field=field,
                validator=validator,
                details=details or {},
            )
        )

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge another result into this one, combining messages and updating status."""
        # Combine messages
        self.messages.extend(other.messages)

        # Update validators run
        self.validators_run.extend(other.validators_run)

        # Update status to the most severe
        status_priority = {
            ValidationStatus.ERROR: 4,
            ValidationStatus.FAILED: 3,
            ValidationStatus.WARNING: 2,
            ValidationStatus.PASSED: 1,
            ValidationStatus.SKIPPED: 0,
        }

        if status_priority[other.status] > status_priority[self.status]:
            self.status = other.status

        # Use the latest data
        if other.data is not None:
            self.data = other.data

        # Merge metadata
        self.metadata.update(other.metadata)

        return self

    def complete(self) -> ValidationResult:
        """Mark the validation as complete and calculate duration."""
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization."""
        return self.model_dump(mode="json")

    def __str__(self) -> str:
        status_str = self.status.value.upper()
        msg_count = len(self.messages)
        duration_str = f" ({self.duration_ms:.1f}ms)" if self.duration_ms else ""
        return f"ValidationResult[{status_str}] - {msg_count} message(s){duration_str}"

    def __repr__(self) -> str:
        return (
            f"ValidationResult(id={self.id}, status={self.status.value}, "
            f"messages={len(self.messages)}, validators={self.validators_run})"
        )


def create_result(
    status: ValidationStatus = ValidationStatus.PASSED,
    data: Any = None,
    provenance: Provenance | None = None,
) -> ValidationResult:
    """Factory function to create a new validation result."""
    return ValidationResult(
        status=status,
        data=data,
        original_data=data,
        provenance=provenance,
    )
