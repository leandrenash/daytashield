"""Tests for SchemaValidator."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from daytashield import SchemaValidator
from daytashield.core.result import ValidationResult, ValidationStatus, create_result


class TestSchemaValidatorJSONSchema:
    """Tests for JSON Schema validation."""

    def test_valid_data_passes(
        self,
        schema_validator: SchemaValidator,
        sample_valid_data: dict[str, Any],
    ) -> None:
        """Valid data should pass validation."""
        result = create_result()
        result = schema_validator.validate(sample_valid_data, result)
        assert result.status == ValidationStatus.PASSED
        assert len(result.errors) == 0

    def test_invalid_type_fails(
        self,
        schema_validator: SchemaValidator,
        sample_invalid_data: dict[str, Any],
    ) -> None:
        """Invalid type should fail validation."""
        result = create_result()
        result = schema_validator.validate(sample_invalid_data, result)
        assert result.status == ValidationStatus.FAILED
        assert len(result.errors) > 0

    def test_missing_required_field_fails(
        self,
        schema_validator: SchemaValidator,
    ) -> None:
        """Missing required field should fail validation."""
        data = {"id": 1}  # Missing 'name'
        result = create_result()
        result = schema_validator.validate(data, result)
        assert result.status == ValidationStatus.FAILED
        assert any("name" in str(m) for m in result.errors)

    def test_extra_fields_allowed_by_default(
        self,
        sample_schema: dict[str, Any],
    ) -> None:
        """Extra fields should be allowed by default."""
        validator = SchemaValidator(schema=sample_schema)
        data = {"id": 1, "name": "Test", "extra_field": "value"}
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED


class TestSchemaValidatorPydantic:
    """Tests for Pydantic model validation."""

    def test_pydantic_model_validation(self) -> None:
        """Pydantic model validation should work."""
        class UserModel(BaseModel):
            id: int
            name: str

        validator = SchemaValidator(model=UserModel)
        data = {"id": 1, "name": "Test"}
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED

    def test_pydantic_invalid_data_fails(self) -> None:
        """Invalid data should fail Pydantic validation."""
        class UserModel(BaseModel):
            id: int
            name: str

        validator = SchemaValidator(model=UserModel)
        data = {"id": "not-an-int", "name": "Test"}
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.FAILED

    def test_pydantic_type_coercion(self) -> None:
        """Pydantic should coerce compatible types."""
        class UserModel(BaseModel):
            id: int
            name: str

        validator = SchemaValidator(model=UserModel)
        data = {"id": "123", "name": "Test"}  # String that can be int
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED
        assert result.data["id"] == 123


class TestSchemaValidatorConfig:
    """Tests for SchemaValidator configuration."""

    def test_no_schema_or_model_raises(self) -> None:
        """Creating validator without schema or model should raise."""
        with pytest.raises(ValueError):
            SchemaValidator()

    def test_validator_repr(self, schema_validator: SchemaValidator) -> None:
        """Validator repr should be informative."""
        repr_str = repr(schema_validator)
        assert "SchemaValidator" in repr_str
