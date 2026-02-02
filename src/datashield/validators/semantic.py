"""Semantic validation using LLMs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import Field

from datashield.core.result import ValidationResult, ValidationStatus
from datashield.validators.base import BaseValidator, ValidatorConfig


class SemanticValidatorConfig(ValidatorConfig):
    """Configuration for semantic validation."""

    model: str = Field("gpt-4o-mini", description="LLM model to use")
    temperature: float = Field(0.0, description="LLM temperature (0 for deterministic)")
    max_tokens: int = Field(500, description="Maximum response tokens")
    cache_results: bool = Field(True, description="Cache validation results")
    timeout: int = Field(30, description="Request timeout in seconds")
    api_base: str | None = Field(None, description="Custom API base URL")


class SemanticValidator(BaseValidator):
    """Validates data semantically using LLMs.

    Uses language models to perform content-based validation that goes
    beyond schema checking. Useful for:
    - Checking if content is appropriate/relevant
    - Verifying factual consistency
    - Detecting anomalies or outliers
    - Domain-specific validation rules

    Example:
        >>> validator = SemanticValidator(
        ...     prompt="Check if this document is a valid invoice with required fields",
        ...     criteria=["has_invoice_number", "has_date", "has_line_items", "has_total"],
        ... )
        >>> result = validator.validate(document_data, result)

    The validator uses LiteLLM for provider-agnostic LLM access, supporting
    OpenAI, Anthropic, local models, and more.
    """

    name = "semantic"

    def __init__(
        self,
        prompt: str,
        criteria: list[str] | None = None,
        config: SemanticValidatorConfig | dict[str, Any] | None = None,
    ):
        """Initialize the semantic validator.

        Args:
            prompt: The validation prompt describing what to check
            criteria: List of specific criteria to evaluate
            config: Validator configuration
        """
        if config is None:
            super().__init__(SemanticValidatorConfig())
        elif isinstance(config, dict):
            super().__init__(SemanticValidatorConfig(**config))
        else:
            super().__init__(config)

        self.prompt = prompt
        self.criteria = criteria or []
        self._cache: dict[str, dict[str, Any]] = {}

    def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate data semantically using an LLM.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        config = self.config
        if not isinstance(config, SemanticValidatorConfig):
            config = SemanticValidatorConfig()

        # Generate cache key
        cache_key = self._get_cache_key(data)
        if config.cache_results and cache_key in self._cache:
            return self._apply_cached_result(result, self._cache[cache_key])

        # Build the validation prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(data)

        try:
            # Import litellm here to make it optional
            import litellm

            # Configure litellm
            if config.api_base:
                litellm.api_base = config.api_base

            # Make the LLM call
            response = litellm.completion(
                model=config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                response_format={"type": "json_object"},
            )

            # Parse the response
            response_text = response.choices[0].message.content
            validation_result = json.loads(response_text)

            # Cache the result
            if config.cache_results:
                self._cache[cache_key] = validation_result

            # Apply the result
            return self._apply_validation_result(result, validation_result)

        except ImportError:
            result.add_message(
                code="SEMANTIC_NO_LITELLM",
                message="litellm package not installed. Install with: pip install litellm",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR
            return result

        except json.JSONDecodeError as e:
            result.add_message(
                code="SEMANTIC_PARSE_ERROR",
                message=f"Failed to parse LLM response as JSON: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR
            return result

        except Exception as e:
            result.add_message(
                code="SEMANTIC_LLM_ERROR",
                message=f"LLM validation failed: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
                details={"error": str(e)},
            )
            result.status = ValidationStatus.ERROR
            return result

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM."""
        criteria_text = ""
        if self.criteria:
            criteria_list = "\n".join(f"- {c}" for c in self.criteria)
            criteria_text = f"\n\nSpecific criteria to evaluate:\n{criteria_list}"

        return f"""You are a data validation assistant. Your task is to validate data based on the given criteria and return a structured JSON response.

Validation task: {self.prompt}{criteria_text}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
    "valid": true/false,
    "confidence": 0.0-1.0,
    "issues": [
        {{
            "criterion": "criterion_name",
            "passed": true/false,
            "message": "explanation"
        }}
    ],
    "summary": "brief overall assessment"
}}"""

    def _build_user_prompt(self, data: Any) -> str:
        """Build the user prompt with the data to validate."""
        if isinstance(data, dict):
            data_str = json.dumps(data, indent=2, default=str)
        elif isinstance(data, str):
            data_str = data
        else:
            data_str = str(data)

        return f"""Please validate the following data:

```
{data_str[:10000]}
```

Return your validation result as JSON."""

    def _get_cache_key(self, data: Any) -> str:
        """Generate a cache key for the data."""
        data_str = json.dumps(data, sort_keys=True, default=str) if isinstance(data, dict) else str(data)
        content = f"{self.prompt}:{self.criteria}:{data_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _apply_validation_result(
        self, result: ValidationResult, validation: dict[str, Any]
    ) -> ValidationResult:
        """Apply the LLM validation result to the ValidationResult."""
        is_valid = validation.get("valid", False)
        confidence = validation.get("confidence", 0.0)
        issues = validation.get("issues", [])
        summary = validation.get("summary", "")

        # Add metadata
        result.metadata["semantic_confidence"] = confidence
        result.metadata["semantic_summary"] = summary

        # Process issues
        for issue in issues:
            if not issue.get("passed", True):
                severity = ValidationStatus.WARNING if confidence > 0.5 else ValidationStatus.FAILED
                result.add_message(
                    code="SEMANTIC_CRITERION_FAILED",
                    message=issue.get("message", "Criterion not met"),
                    severity=severity,
                    validator=self.name,
                    field=issue.get("criterion"),
                    details={"confidence": confidence},
                )

        # Update status
        if not is_valid:
            if confidence < 0.5:
                result.status = ValidationStatus.FAILED
            else:
                # High confidence but invalid = warning
                if result.status != ValidationStatus.FAILED:
                    result.status = ValidationStatus.WARNING

        return result

    def _apply_cached_result(
        self, result: ValidationResult, cached: dict[str, Any]
    ) -> ValidationResult:
        """Apply a cached validation result."""
        result.metadata["semantic_cached"] = True
        return self._apply_validation_result(result, cached)

    def clear_cache(self) -> None:
        """Clear the validation cache."""
        self._cache.clear()

    def __repr__(self) -> str:
        return f"SemanticValidator(prompt={self.prompt[:50]!r}..., criteria={len(self.criteria)})"
