"""Base validator abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datashield.core.result import ValidationResult


class ValidatorConfig(BaseModel):
    """Base configuration for all validators."""

    enabled: bool = Field(True, description="Whether this validator is enabled")
    fail_fast: bool = Field(False, description="Stop validation on first failure")
    severity_override: str | None = Field(
        None, description="Override default severity (warning, failed)"
    )

    model_config = {"extra": "allow"}


class BaseValidator(ABC):
    """Abstract base class for all DataShield validators.

    Validators are responsible for checking specific aspects of data quality.
    Each validator should focus on a single concern (schema, freshness, etc.).

    Example:
        >>> class MyValidator(BaseValidator):
        ...     name = "my_validator"
        ...
        ...     def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        ...         if not self._is_valid(data):
        ...             result.add_message(
        ...                 code="MY_001",
        ...                 message="Data failed custom validation",
        ...                 severity=ValidationStatus.FAILED,
        ...                 validator=self.name,
        ...             )
        ...         return result
    """

    name: str = "base_validator"

    def __init__(self, config: ValidatorConfig | dict[str, Any] | None = None):
        """Initialize the validator with optional configuration.

        Args:
            config: Validator configuration, either as ValidatorConfig or dict.
        """
        if config is None:
            self.config = ValidatorConfig()
        elif isinstance(config, dict):
            self.config = ValidatorConfig(**config)
        else:
            self.config = config

    @abstractmethod
    def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate the provided data and update the result.

        This is the main method that subclasses must implement. It should:
        1. Check the data against this validator's rules
        2. Add messages to the result for any issues found
        3. Optionally transform the data and update result.data
        4. Return the updated result

        Args:
            data: The data to validate (type depends on validator)
            result: The ValidationResult to update with findings

        Returns:
            The updated ValidationResult
        """
        pass

    def should_run(self, data: Any, result: ValidationResult) -> bool:
        """Check if this validator should run.

        Override this method to implement conditional validation logic.

        Args:
            data: The data to potentially validate
            result: The current validation result

        Returns:
            True if this validator should run, False otherwise
        """
        if not self.config.enabled:
            return False

        # Skip if previous validator failed and we're in fail-fast mode
        if self.config.fail_fast and result.failed:
            return False

        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
