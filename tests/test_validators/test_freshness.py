"""Tests for FreshnessValidator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from datashield import FreshnessValidator
from datashield.core.result import ValidationStatus, create_result


class TestFreshnessValidator:
    """Tests for FreshnessValidator."""

    def test_fresh_data_passes(self) -> None:
        """Fresh data should pass validation."""
        validator = FreshnessValidator(max_age="7d")
        now = datetime.now(timezone.utc)
        data = {
            "content": "Test",
            "timestamp": now.isoformat(),
        }
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED

    def test_stale_data_fails(self) -> None:
        """Stale data should fail validation."""
        validator = FreshnessValidator(max_age="1d")
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        data = {
            "content": "Test",
            "timestamp": old_time.isoformat(),
        }
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.FAILED
        assert any("stale" in m.message.lower() for m in result.errors)

    def test_near_stale_warns(self) -> None:
        """Data approaching staleness should warn."""
        validator = FreshnessValidator(max_age="10d")
        # 85% of max age (past 80% threshold)
        old_time = datetime.now(timezone.utc) - timedelta(days=8.5)
        data = {
            "content": "Test",
            "timestamp": old_time.isoformat(),
        }
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.WARNING

    def test_unix_timestamp(self) -> None:
        """Unix timestamps should be parsed correctly."""
        validator = FreshnessValidator(max_age="7d")
        now = datetime.now(timezone.utc).timestamp()
        data = {"timestamp": now}
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED

    def test_custom_timestamp_field(self) -> None:
        """Custom timestamp field should be used."""
        validator = FreshnessValidator(max_age="7d", timestamp_field="created_at")
        now = datetime.now(timezone.utc)
        data = {
            "created_at": now.isoformat(),
            "timestamp": "1970-01-01",  # This should be ignored
        }
        result = create_result()
        result = validator.validate(data, result)
        assert result.status == ValidationStatus.PASSED

    def test_missing_timestamp_warns(self) -> None:
        """Missing timestamp should warn, not fail."""
        validator = FreshnessValidator(max_age="7d")
        data = {"content": "No timestamp here"}
        result = create_result()
        result = validator.validate(data, result)
        assert len(result.messages) > 0
        assert any("no timestamp" in m.message.lower() for m in result.messages)


class TestFreshnessValidatorDurationParsing:
    """Tests for duration string parsing."""

    @pytest.mark.parametrize(
        "duration,expected_seconds",
        [
            ("30s", 30),
            ("30 seconds", 30),
            ("5m", 300),
            ("5 minutes", 300),
            ("2h", 7200),
            ("2 hours", 7200),
            ("7d", 604800),
            ("7 days", 604800),
            ("2w", 1209600),
            ("2 weeks", 1209600),
            ("1M", 2592000),  # 30 days
            ("1 month", 2592000),
            ("1y", 31536000),  # 365 days
            ("1 year", 31536000),
        ],
    )
    def test_duration_parsing(self, duration: str, expected_seconds: int) -> None:
        """Various duration formats should be parsed correctly."""
        validator = FreshnessValidator(max_age=duration)
        assert validator.max_age.total_seconds() == expected_seconds

    def test_invalid_duration_raises(self) -> None:
        """Invalid duration format should raise ValueError."""
        with pytest.raises(ValueError):
            FreshnessValidator(max_age="invalid")
