"""Pytest configuration and fixtures for DataShield tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from datashield import (
    ComplianceValidator,
    FreshnessValidator,
    SchemaValidator,
    ValidationPipeline,
)
from datashield.core.result import ValidationResult, ValidationStatus


@pytest.fixture
def sample_schema() -> dict[str, Any]:
    """Sample JSON schema for testing."""
    return {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 1},
            "email": {"type": "string"},
            "timestamp": {"type": "string"},
        },
    }


@pytest.fixture
def sample_valid_data() -> dict[str, Any]:
    """Sample data that passes schema validation."""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "timestamp": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_invalid_data() -> dict[str, Any]:
    """Sample data that fails schema validation."""
    return {
        "id": "not-an-integer",  # Wrong type
        "name": "",  # Too short
    }


@pytest.fixture
def sample_pii_data() -> dict[str, Any]:
    """Sample data containing PII."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "ssn": "123-45-6789",
        "notes": "Customer called from 192.168.1.100",
    }


@pytest.fixture
def sample_hipaa_data() -> dict[str, Any]:
    """Sample healthcare data with PHI."""
    return {
        "patient_name": "Jane Doe",
        "mrn": "MRN: 12345678",
        "diagnosis": "ICD-10: J06.9",
        "provider_npi": "NPI: 1234567890",
        "dob": "01/15/1985",
    }


@pytest.fixture
def schema_validator(sample_schema: dict[str, Any]) -> SchemaValidator:
    """SchemaValidator instance."""
    return SchemaValidator(schema=sample_schema)


@pytest.fixture
def freshness_validator() -> FreshnessValidator:
    """FreshnessValidator instance with 30 day max age."""
    return FreshnessValidator(max_age="30d")


@pytest.fixture
def compliance_validator() -> ComplianceValidator:
    """ComplianceValidator instance with PII rules."""
    return ComplianceValidator(rules=["pii"])


@pytest.fixture
def basic_pipeline(schema_validator: SchemaValidator) -> ValidationPipeline:
    """Basic ValidationPipeline with schema validation."""
    return ValidationPipeline([schema_validator])


@pytest.fixture
def full_pipeline(
    schema_validator: SchemaValidator,
    freshness_validator: FreshnessValidator,
    compliance_validator: ComplianceValidator,
) -> ValidationPipeline:
    """Full ValidationPipeline with all validators."""
    return ValidationPipeline([
        schema_validator,
        freshness_validator,
        compliance_validator,
    ])


@pytest.fixture
def temp_json_file(sample_valid_data: dict[str, Any]) -> Path:
    """Temporary JSON file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_valid_data, f)
        return Path(f.name)


@pytest.fixture
def temp_csv_file() -> Path:
    """Temporary CSV file for testing."""
    content = "id,name,email\n1,Alice,alice@example.com\n2,Bob,bob@example.com\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def temp_jsonl_file() -> Path:
    """Temporary JSON Lines file for testing."""
    lines = [
        '{"id": 1, "name": "Alice"}',
        '{"id": 2, "name": "Bob"}',
        '{"id": 3, "name": "Charlie"}',
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(lines))
        return Path(f.name)


@pytest.fixture
def passed_result() -> ValidationResult:
    """A passed ValidationResult."""
    result = ValidationResult(
        status=ValidationStatus.PASSED,
        data={"id": 1, "name": "Test"},
    )
    return result


@pytest.fixture
def failed_result() -> ValidationResult:
    """A failed ValidationResult with messages."""
    result = ValidationResult(
        status=ValidationStatus.FAILED,
        data={"id": "invalid"},
    )
    result.add_message(
        code="TEST_ERROR",
        message="Test error message",
        severity=ValidationStatus.FAILED,
        validator="test_validator",
        field="id",
    )
    return result
