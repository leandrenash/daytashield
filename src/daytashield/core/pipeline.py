"""Validation pipeline orchestrator."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from pydantic import BaseModel, Field

from daytashield.core.result import ValidationResult, ValidationStatus, create_result

if TYPE_CHECKING:
    from daytashield.processors.base import BaseProcessor
    from daytashield.validators.base import BaseValidator


class PipelineConfig(BaseModel):
    """Configuration for the validation pipeline."""

    fail_fast: bool = Field(False, description="Stop on first validation failure")
    parallel: bool = Field(False, description="Run validators in parallel (async)")
    include_original_data: bool = Field(True, description="Include original data in result")
    auto_detect_processor: bool = Field(True, description="Auto-detect processor by file extension")

    model_config = {"extra": "allow"}


class ValidationPipeline:
    """Orchestrates validation across multiple validators.

    The pipeline chains validators together, passing data and results through
    each validator in sequence. It handles processor selection, result
    aggregation, and provides hooks for auditing.

    Example:
        >>> from daytashield import ValidationPipeline, SchemaValidator, FreshnessValidator
        >>> pipeline = ValidationPipeline([
        ...     SchemaValidator(schema={"type": "object"}),
        ...     FreshnessValidator(max_age="7d"),
        ... ])
        >>> result = pipeline.validate({"id": 1, "timestamp": "2024-01-01"})
        >>> print(result.status)
        ValidationStatus.PASSED

    Attributes:
        validators: List of validators to run
        processors: Dict mapping extensions to processors
        config: Pipeline configuration
    """

    def __init__(
        self,
        validators: list[BaseValidator] | None = None,
        processors: dict[str, BaseProcessor] | None = None,
        config: PipelineConfig | dict[str, Any] | None = None,
    ):
        """Initialize the validation pipeline.

        Args:
            validators: List of validators to apply (in order)
            processors: Dict mapping file extensions to processors
            config: Pipeline configuration
        """
        self.validators: list[BaseValidator] = validators or []
        self.processors: dict[str, BaseProcessor] = processors or {}
        
        if config is None:
            self.config = PipelineConfig()
        elif isinstance(config, dict):
            self.config = PipelineConfig(**config)
        else:
            self.config = config

    def add_validator(self, validator: BaseValidator) -> ValidationPipeline:
        """Add a validator to the pipeline.

        Args:
            validator: The validator to add

        Returns:
            Self for method chaining
        """
        self.validators.append(validator)
        return self

    def add_processor(self, extension: str, processor: BaseProcessor) -> ValidationPipeline:
        """Register a processor for a file extension.

        Args:
            extension: File extension (e.g., ".pdf")
            processor: The processor to use

        Returns:
            Self for method chaining
        """
        self.processors[extension.lower()] = processor
        return self

    def validate(
        self,
        data: Any,
        source: str | Path | BinaryIO | bytes | None = None,
        result: ValidationResult | None = None,
    ) -> ValidationResult:
        """Run all validators on the data.

        This is the main entry point for validation. It:
        1. Creates or uses an existing result
        2. Processes the source if provided (file → structured data)
        3. Runs each validator in sequence
        4. Returns the aggregated result

        Args:
            data: The data to validate (dict, list, or ProcessedData)
            source: Optional original source (file path, bytes, etc.)
            result: Optional existing result to continue

        Returns:
            ValidationResult with all validation findings
        """
        start_time = time.perf_counter()

        # Create or use existing result
        if result is None:
            result = create_result(status=ValidationStatus.PASSED, data=data)
            if self.config.include_original_data:
                result.original_data = data

        # Process source if provided
        if source is not None:
            result = self._process_source(source, result)
            if result.failed:
                return result.complete()
            # Use processed data for validation
            if result.data is not None:
                data = result.data

        # Run validators
        for validator in self.validators:
            if not validator.should_run(data, result):
                continue

            try:
                result = validator.validate(data, result)
                result.validators_run.append(validator.name)

                # Check for fail-fast
                if self.config.fail_fast and result.failed:
                    break

            except Exception as e:
                result.add_message(
                    code="PIPELINE_ERROR",
                    message=f"Validator {validator.name} raised an exception: {e}",
                    severity=ValidationStatus.ERROR,
                    validator="pipeline",
                    details={"exception": str(e), "validator": validator.name},
                )
                result.status = ValidationStatus.ERROR
                if self.config.fail_fast:
                    break

        # Calculate duration
        end_time = time.perf_counter()
        result.duration_ms = (end_time - start_time) * 1000
        result.completed_at = datetime.now(timezone.utc)

        return result

    def validate_file(self, path: str | Path) -> ValidationResult:
        """Validate a file, auto-detecting the processor.

        Convenience method that reads a file, selects the appropriate
        processor based on extension, and runs validation.

        Args:
            path: Path to the file to validate

        Returns:
            ValidationResult with all validation findings
        """
        path = Path(path) if isinstance(path, str) else path

        if not path.exists():
            result = create_result(status=ValidationStatus.ERROR)
            result.add_message(
                code="FILE_NOT_FOUND",
                message=f"File not found: {path}",
                severity=ValidationStatus.ERROR,
                validator="pipeline",
            )
            return result.complete()

        return self.validate(data=None, source=path)

    def _process_source(
        self, source: str | Path | BinaryIO | bytes, result: ValidationResult
    ) -> ValidationResult:
        """Process a source using the appropriate processor.

        Args:
            source: The data source
            result: The current result

        Returns:
            Updated result with processed data
        """
        if not self.config.auto_detect_processor:
            return result

        # Determine file extension
        extension: str | None = None
        if isinstance(source, (str, Path)):
            extension = Path(source).suffix.lower()
        elif hasattr(source, "name") and source.name:
            extension = Path(source.name).suffix.lower()

        if extension and extension in self.processors:
            processor = self.processors[extension]
            try:
                result = processor.process(source, result)
                if result.provenance:
                    result.provenance.processor_chain.append(processor.name)
            except Exception as e:
                result.add_message(
                    code="PROCESSOR_ERROR",
                    message=f"Processor {processor.name} failed: {e}",
                    severity=ValidationStatus.ERROR,
                    validator="pipeline",
                    details={"exception": str(e), "processor": processor.name},
                )
                result.status = ValidationStatus.ERROR

        return result

    def __repr__(self) -> str:
        validator_names = [v.name for v in self.validators]
        return f"ValidationPipeline(validators={validator_names})"
