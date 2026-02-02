"""Schema validation using JSON Schema and Pydantic."""

from __future__ import annotations

from typing import Any, Type

import jsonschema
from pydantic import BaseModel, Field, ValidationError

from datashield.core.result import ValidationResult, ValidationStatus
from datashield.validators.base import BaseValidator, ValidatorConfig


class SchemaValidatorConfig(ValidatorConfig):
    """Configuration for schema validation."""

    strict: bool = Field(True, description="Strict mode fails on extra fields")
    coerce_types: bool = Field(False, description="Attempt to coerce types")
    allow_none: bool = Field(False, description="Allow None/null values for optional fields")


class SchemaValidator(BaseValidator):
    """Validates data against JSON Schema or Pydantic models.

    Supports two modes:
    1. JSON Schema validation (dict schema)
    2. Pydantic model validation (model class)

    Example with JSON Schema:
        >>> schema = {
        ...     "type": "object",
        ...     "required": ["id", "content"],
        ...     "properties": {
        ...         "id": {"type": "integer"},
        ...         "content": {"type": "string"},
        ...     }
        ... }
        >>> validator = SchemaValidator(schema=schema)
        >>> result = validator.validate({"id": 1, "content": "Hello"}, result)

    Example with Pydantic:
        >>> from pydantic import BaseModel
        >>> class Document(BaseModel):
        ...     id: int
        ...     content: str
        >>> validator = SchemaValidator(model=Document)
        >>> result = validator.validate({"id": 1, "content": "Hello"}, result)
    """

    name = "schema"

    def __init__(
        self,
        schema: dict[str, Any] | None = None,
        model: Type[BaseModel] | None = None,
        config: SchemaValidatorConfig | dict[str, Any] | None = None,
    ):
        """Initialize the schema validator.

        Args:
            schema: JSON Schema dict for validation
            model: Pydantic model class for validation
            config: Validator configuration

        Raises:
            ValueError: If neither schema nor model is provided
        """
        if config is None:
            super().__init__(SchemaValidatorConfig())
        elif isinstance(config, dict):
            super().__init__(SchemaValidatorConfig(**config))
        else:
            super().__init__(config)

        if schema is None and model is None:
            raise ValueError("Either 'schema' or 'model' must be provided")

        self.schema = schema
        self.model = model
        self._json_schema_validator: jsonschema.Draft7Validator | None = None

        if schema:
            self._json_schema_validator = jsonschema.Draft7Validator(schema)

    def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate data against the schema.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        if self.model is not None:
            return self._validate_pydantic(data, result)
        elif self.schema is not None:
            return self._validate_json_schema(data, result)
        return result

    def _validate_pydantic(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate using Pydantic model.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        if self.model is None:
            return result

        try:
            # Validate and get the model instance
            validated = self.model.model_validate(data)
            result.data = validated.model_dump()
            result.metadata["validated_model"] = self.model.__name__
        except ValidationError as e:
            for error in e.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                result.add_message(
                    code=f"SCHEMA_{error['type'].upper()}",
                    message=error["msg"],
                    severity=ValidationStatus.FAILED,
                    validator=self.name,
                    field=field_path,
                    details={"error_type": error["type"], "input": error.get("input")},
                )
            result.status = ValidationStatus.FAILED

        return result

    def _validate_json_schema(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate using JSON Schema.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        if self._json_schema_validator is None:
            return result

        errors = list(self._json_schema_validator.iter_errors(data))

        if not errors:
            result.data = data
            return result

        for error in errors:
            # Build field path from error path
            field_path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else None

            result.add_message(
                code=f"SCHEMA_{error.validator.upper()}",
                message=error.message,
                severity=ValidationStatus.FAILED,
                validator=self.name,
                field=field_path,
                details={
                    "validator": error.validator,
                    "validator_value": str(error.validator_value)[:100],  # Truncate long values
                    "schema_path": list(error.schema_path),
                },
            )

        result.status = ValidationStatus.FAILED
        return result

    def __repr__(self) -> str:
        if self.model:
            return f"SchemaValidator(model={self.model.__name__})"
        return f"SchemaValidator(schema={bool(self.schema)})"
