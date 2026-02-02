"""Immutable audit trail for validation operations."""

from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import orjson
from pydantic import BaseModel, Field

from daytashield.core.result import ValidationResult, ValidationStatus


class AuditEntry(BaseModel):
    """A single audit log entry."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the entry was created",
    )
    result_id: UUID = Field(..., description="ID of the validation result")
    status: ValidationStatus = Field(..., description="Validation status")
    validators_run: list[str] = Field(default_factory=list, description="Validators executed")
    message_count: int = Field(0, description="Number of validation messages")
    error_count: int = Field(0, description="Number of errors")
    warning_count: int = Field(0, description="Number of warnings")
    duration_ms: float | None = Field(None, description="Validation duration")
    source_id: str | None = Field(None, description="Source identifier")
    source_path: str | None = Field(None, description="Source file path")
    checksum: str | None = Field(None, description="Data checksum")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @classmethod
    def from_result(cls, result: ValidationResult, metadata: dict[str, Any] | None = None) -> AuditEntry:
        """Create an audit entry from a validation result.

        Args:
            result: The validation result to log
            metadata: Additional metadata to include

        Returns:
            New AuditEntry
        """
        return cls(
            result_id=result.id,
            status=result.status,
            validators_run=result.validators_run,
            message_count=len(result.messages),
            error_count=len(result.errors),
            warning_count=len(result.warnings),
            duration_ms=result.duration_ms,
            source_id=result.provenance.source_id if result.provenance else None,
            source_path=result.provenance.source_path if result.provenance else None,
            checksum=result.provenance.checksum if result.provenance else None,
            metadata=metadata or {},
        )

    def to_jsonl(self) -> bytes:
        """Serialize to JSON Lines format (single line)."""
        return orjson.dumps(self.model_dump(mode="json")) + b"\n"


class AuditTrailConfig(BaseModel):
    """Configuration for the audit trail."""

    path: Path = Field(
        default_factory=lambda: Path("./audit.jsonl"),
        description="Path to the audit log file",
    )
    compress: bool = Field(False, description="Use gzip compression")
    max_size_bytes: int = Field(100 * 1024 * 1024, description="Max file size before rotation")
    include_data: bool = Field(False, description="Include actual data in audit (careful!)")
    buffer_size: int = Field(100, description="Number of entries to buffer before flush")


class AuditTrail:
    """Immutable audit trail using JSON Lines format.

    The audit trail provides an append-only log of all validation operations.
    It uses JSON Lines format for easy querying and analysis.

    Example:
        >>> audit = AuditTrail(path="./validation_audit.jsonl")
        >>> result = pipeline.validate(data)
        >>> audit.log(result)
        >>> # Later, query the audit trail
        >>> for entry in audit.query(status=ValidationStatus.FAILED):
        ...     print(f"Failed: {entry.source_id} at {entry.timestamp}")

    Features:
    - Append-only (immutable)
    - JSON Lines format (one JSON object per line)
    - Optional gzip compression
    - File rotation support
    - Query by status, date range, source
    """

    def __init__(self, config: AuditTrailConfig | dict[str, Any] | Path | str | None = None):
        """Initialize the audit trail.

        Args:
            config: Configuration (AuditTrailConfig, dict, or path string)
        """
        if config is None:
            self.config = AuditTrailConfig()
        elif isinstance(config, (str, Path)):
            self.config = AuditTrailConfig(path=Path(config))
        elif isinstance(config, dict):
            self.config = AuditTrailConfig(**config)
        else:
            self.config = config

        self._buffer: list[AuditEntry] = []
        self._ensure_path()

    def _ensure_path(self) -> None:
        """Ensure the audit file directory exists."""
        self.config.path.parent.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self) -> Path:
        """Get the current audit file path."""
        if self.config.compress:
            return self.config.path.with_suffix(".jsonl.gz")
        return self.config.path

    def log(self, result: ValidationResult, metadata: dict[str, Any] | None = None) -> AuditEntry:
        """Log a validation result to the audit trail.

        Args:
            result: The validation result to log
            metadata: Additional metadata to include

        Returns:
            The created AuditEntry
        """
        entry = AuditEntry.from_result(result, metadata)
        self._buffer.append(entry)

        if len(self._buffer) >= self.config.buffer_size:
            self.flush()

        return entry

    def flush(self) -> int:
        """Flush buffered entries to disk.

        Returns:
            Number of entries flushed
        """
        if not self._buffer:
            return 0

        count = len(self._buffer)
        data = b"".join(entry.to_jsonl() for entry in self._buffer)

        file_path = self._get_file_path()

        if self.config.compress:
            with gzip.open(file_path, "ab") as f:
                f.write(data)
        else:
            with open(file_path, "ab") as f:
                f.write(data)

        self._buffer.clear()
        return count

    def log_batch(self, results: list[ValidationResult]) -> list[AuditEntry]:
        """Log multiple validation results.

        Args:
            results: List of validation results

        Returns:
            List of created AuditEntries
        """
        entries = [self.log(result) for result in results]
        self.flush()
        return entries

    def query(
        self,
        status: ValidationStatus | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> Iterator[AuditEntry]:
        """Query the audit trail.

        Args:
            status: Filter by validation status
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            source_id: Filter by source identifier
            limit: Maximum number of entries to return

        Yields:
            Matching AuditEntry objects
        """
        self.flush()  # Ensure all entries are on disk

        file_path = self._get_file_path()
        if not file_path.exists():
            return

        count = 0
        opener = gzip.open if self.config.compress else open

        with opener(file_path, "rb") as f:  # type: ignore[operator]
            for line in f:
                if not line.strip():
                    continue

                data = orjson.loads(line)
                entry = AuditEntry(**data)

                # Apply filters
                if status is not None and entry.status != status:
                    continue
                if start_time is not None and entry.timestamp < start_time:
                    continue
                if end_time is not None and entry.timestamp > end_time:
                    continue
                if source_id is not None and entry.source_id != source_id:
                    continue

                yield entry
                count += 1

                if limit is not None and count >= limit:
                    return

    def stats(self) -> dict[str, Any]:
        """Get statistics from the audit trail.

        Returns:
            Dict with count by status, total count, etc.
        """
        self.flush()

        stats: dict[str, Any] = {
            "total": 0,
            "by_status": {status.value: 0 for status in ValidationStatus},
            "avg_duration_ms": 0.0,
            "total_errors": 0,
            "total_warnings": 0,
        }

        durations: list[float] = []

        for entry in self.query():
            stats["total"] += 1
            stats["by_status"][entry.status.value] += 1
            stats["total_errors"] += entry.error_count
            stats["total_warnings"] += entry.warning_count
            if entry.duration_ms is not None:
                durations.append(entry.duration_ms)

        if durations:
            stats["avg_duration_ms"] = sum(durations) / len(durations)

        return stats

    def __enter__(self) -> AuditTrail:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.flush()

    def __repr__(self) -> str:
        return f"AuditTrail(path={self.config.path})"
