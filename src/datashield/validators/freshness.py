"""Freshness validation for temporal data checks."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import parser as date_parser
from pydantic import Field

from datashield.core.result import ValidationResult, ValidationStatus
from datashield.validators.base import BaseValidator, ValidatorConfig


class FreshnessValidatorConfig(ValidatorConfig):
    """Configuration for freshness validation."""

    timestamp_fields: list[str] = Field(
        default_factory=lambda: ["timestamp", "created_at", "updated_at", "date", "datetime"],
        description="Field names to check for timestamps",
    )
    date_formats: list[str] = Field(
        default_factory=lambda: [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ],
        description="Date formats to try when parsing",
    )
    warn_threshold_ratio: float = Field(
        0.8, description="Ratio of max_age at which to warn (0.8 = 80%)"
    )


class FreshnessValidator(BaseValidator):
    """Validates data freshness based on timestamps.

    Checks that data is not stale by examining timestamp fields and
    comparing them against configurable age thresholds.

    Example:
        >>> validator = FreshnessValidator(max_age="7d")
        >>> result = validator.validate(
        ...     {"content": "Hello", "timestamp": "2024-01-15"},
        ...     result
        ... )

    Supported time units:
    - s, sec, second, seconds
    - m, min, minute, minutes
    - h, hr, hour, hours
    - d, day, days
    - w, week, weeks
    - M, month, months (30 days)
    - y, year, years (365 days)
    """

    name = "freshness"

    # Regex for parsing duration strings like "7d", "2 weeks", "30 minutes"
    # Note: M for months is case-sensitive, all others are case-insensitive
    DURATION_PATTERN = re.compile(
        r"^\s*(\d+)\s*(s|sec|seconds?|m|min|minutes?|"
        r"h|hr|hours?|d|days?|w|weeks?|M|months?|"
        r"y|years?)\s*$",
        re.IGNORECASE,
    )

    # Mapping of unit aliases to timedelta kwargs
    UNIT_MAPPING = {
        "s": "seconds",
        "sec": "seconds",
        "second": "seconds",
        "seconds": "seconds",
        "m": "minutes",
        "min": "minutes",
        "minute": "minutes",
        "minutes": "minutes",
        "h": "hours",
        "hr": "hours",
        "hour": "hours",
        "hours": "hours",
        "d": "days",
        "day": "days",
        "days": "days",
        "w": "weeks",
        "week": "weeks",
        "weeks": "weeks",
        "M": "months",  # Case-sensitive - uppercase M only
        "month": "months",
        "months": "months",
        "y": "years",
        "year": "years",
        "years": "years",
    }

    def __init__(
        self,
        max_age: str | timedelta,
        timestamp_field: str | None = None,
        config: FreshnessValidatorConfig | dict[str, Any] | None = None,
    ):
        """Initialize the freshness validator.

        Args:
            max_age: Maximum allowed age (e.g., "7d", "2 weeks", timedelta)
            timestamp_field: Specific field to check (overrides config)
            config: Validator configuration
        """
        if config is None:
            super().__init__(FreshnessValidatorConfig())
        elif isinstance(config, dict):
            super().__init__(FreshnessValidatorConfig(**config))
        else:
            super().__init__(config)

        self.max_age = self._parse_duration(max_age) if isinstance(max_age, str) else max_age
        self.timestamp_field = timestamp_field

    def _parse_duration(self, duration_str: str) -> timedelta:
        """Parse a duration string into a timedelta.

        Args:
            duration_str: Duration string like "7d", "2 weeks", "30m"

        Returns:
            timedelta representing the duration

        Raises:
            ValueError: If the duration string is invalid
        """
        match = self.DURATION_PATTERN.match(duration_str)
        if not match:
            raise ValueError(
                f"Invalid duration format: {duration_str}. "
                "Use formats like '7d', '2 weeks', '30 minutes'"
            )

        value = int(match.group(1))
        unit_raw = match.group(2)
        # Preserve uppercase M for months, lowercase everything else
        unit = unit_raw if unit_raw == "M" else unit_raw.lower()
        unit_name = self.UNIT_MAPPING.get(unit, unit)

        # Handle months and years specially
        if unit_name == "months":
            return timedelta(days=value * 30)
        elif unit_name == "years":
            return timedelta(days=value * 365)
        else:
            return timedelta(**{unit_name: value})

    def validate(self, data: Any, result: ValidationResult) -> ValidationResult:
        """Validate data freshness.

        Args:
            data: The data to validate
            result: The ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        if not isinstance(data, dict):
            result.add_message(
                code="FRESHNESS_NOT_DICT",
                message="Freshness validation requires dict data with timestamp fields",
                severity=ValidationStatus.WARNING,
                validator=self.name,
            )
            return result

        # Find timestamp field
        timestamp_value = self._find_timestamp(data)
        if timestamp_value is None:
            result.add_message(
                code="FRESHNESS_NO_TIMESTAMP",
                message="No timestamp field found in data",
                severity=ValidationStatus.WARNING,
                validator=self.name,
                details={"searched_fields": self._get_timestamp_fields()},
            )
            return result

        # Parse the timestamp
        parsed_time = self._parse_timestamp(timestamp_value)
        if parsed_time is None:
            result.add_message(
                code="FRESHNESS_PARSE_ERROR",
                message=f"Could not parse timestamp value: {timestamp_value}",
                severity=ValidationStatus.WARNING,
                validator=self.name,
            )
            return result

        # Calculate age
        now = datetime.now(timezone.utc)
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)

        age = now - parsed_time
        max_age_seconds = self.max_age.total_seconds()
        age_seconds = age.total_seconds()

        # Check freshness
        config = self.config
        if not isinstance(config, FreshnessValidatorConfig):
            config = FreshnessValidatorConfig()

        result.metadata["data_age_seconds"] = age_seconds
        result.metadata["max_age_seconds"] = max_age_seconds
        result.metadata["timestamp_value"] = str(timestamp_value)

        if age_seconds > max_age_seconds:
            result.add_message(
                code="FRESHNESS_STALE",
                message=f"Data is stale: age is {self._format_duration(age)}, max allowed is {self._format_duration(self.max_age)}",
                severity=ValidationStatus.FAILED,
                validator=self.name,
                details={
                    "age_seconds": age_seconds,
                    "max_age_seconds": max_age_seconds,
                    "timestamp": str(parsed_time),
                },
            )
            result.status = ValidationStatus.FAILED
        elif age_seconds > max_age_seconds * config.warn_threshold_ratio:
            result.add_message(
                code="FRESHNESS_NEAR_STALE",
                message=f"Data is approaching staleness: age is {self._format_duration(age)} "
                f"({age_seconds / max_age_seconds * 100:.0f}% of max)",
                severity=ValidationStatus.WARNING,
                validator=self.name,
            )
            if result.status == ValidationStatus.PASSED:
                result.status = ValidationStatus.WARNING

        return result

    def _get_timestamp_fields(self) -> list[str]:
        """Get the list of timestamp fields to check."""
        if self.timestamp_field:
            return [self.timestamp_field]
        config = self.config
        if isinstance(config, FreshnessValidatorConfig):
            return config.timestamp_fields
        return FreshnessValidatorConfig().timestamp_fields

    def _find_timestamp(self, data: dict[str, Any]) -> Any:
        """Find a timestamp value in the data.

        Args:
            data: Dict to search

        Returns:
            Timestamp value or None
        """
        fields_to_check = self._get_timestamp_fields()

        for field in fields_to_check:
            if field in data:
                return data[field]
            # Check nested fields (e.g., "metadata.timestamp")
            if "." in field:
                value = self._get_nested_value(data, field)
                if value is not None:
                    return value

        return None

    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse a timestamp value into a datetime.

        Args:
            value: The value to parse

        Returns:
            datetime or None if parsing fails
        """
        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            # Assume Unix timestamp
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (ValueError, OSError):
                return None

        if isinstance(value, str):
            # Try dateutil parser (handles most formats)
            try:
                return date_parser.parse(value)
            except (ValueError, TypeError):
                pass

            # Try configured formats
            config = self.config
            if isinstance(config, FreshnessValidatorConfig):
                for fmt in config.date_formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue

        return None

    def _format_duration(self, td: timedelta) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(td.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"

    def __repr__(self) -> str:
        return f"FreshnessValidator(max_age={self._format_duration(self.max_age)})"
