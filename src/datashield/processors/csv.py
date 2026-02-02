"""CSV file processor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from pydantic import Field

from datashield.core.result import ValidationResult, ValidationStatus
from datashield.processors.base import BaseProcessor, ProcessedData, ProcessorConfig


class CSVProcessorConfig(ProcessorConfig):
    """Configuration for CSV processing."""

    delimiter: str = Field(",", description="Field delimiter")
    encoding: str = Field("utf-8", description="File encoding")
    has_header: bool = Field(True, description="First row is header")
    infer_types: bool = Field(True, description="Infer column data types")
    max_rows: int | None = Field(None, description="Maximum rows to process")
    skip_rows: int = Field(0, description="Rows to skip at start")
    null_values: list[str] = Field(
        default_factory=lambda: ["", "NA", "N/A", "null", "NULL", "None", "nan", "NaN"],
        description="Values to treat as null",
    )


class CSVProcessor(BaseProcessor):
    """Processes CSV files to extract structured data.

    Uses pandas for robust CSV parsing with:
    - Automatic type inference
    - Missing value detection
    - Schema extraction
    - Encoding detection

    Example:
        >>> processor = CSVProcessor()
        >>> result = processor.process("data.csv")
        >>> records = result.data.content  # List of dicts
        >>> schema = result.data.metadata["schema"]  # Inferred schema
    """

    name = "csv"
    supported_extensions = [".csv", ".tsv", ".txt"]
    supported_mime_types = ["text/csv", "text/tab-separated-values"]

    def __init__(self, config: CSVProcessorConfig | dict[str, Any] | None = None):
        """Initialize the CSV processor.

        Args:
            config: Processor configuration
        """
        if config is None:
            super().__init__(CSVProcessorConfig())
        elif isinstance(config, dict):
            super().__init__(CSVProcessorConfig(**config))
        else:
            super().__init__(config)

    def process(
        self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None
    ) -> ValidationResult:
        """Process a CSV file and extract records.

        Args:
            source: CSV file path, file object, or bytes
            result: Optional existing ValidationResult

        Returns:
            ValidationResult with ProcessedData containing records
        """
        # Create result if not provided
        if result is None:
            result, provenance = self._create_result(source)
        else:
            provenance = result.provenance

        config = self.config
        if not isinstance(config, CSVProcessorConfig):
            config = CSVProcessorConfig()

        try:
            import pandas as pd
        except ImportError:
            result.add_message(
                code="CSV_NO_PANDAS",
                message="pandas package not installed. Install with: pip install pandas",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR
            return result

        try:
            # Read raw bytes for checksum
            raw_bytes = self._read_source(source)

            # Compute checksum if configured
            if self.config.compute_checksum and provenance:
                provenance.checksum = self._compute_checksum(raw_bytes)

            # Determine delimiter for TSV
            delimiter = config.delimiter
            if isinstance(source, (str, Path)):
                if Path(source).suffix.lower() == ".tsv":
                    delimiter = "\t"

            # Read CSV with pandas
            import io

            df = pd.read_csv(
                io.BytesIO(raw_bytes),
                delimiter=delimiter,
                encoding=config.encoding,
                header=0 if config.has_header else None,
                nrows=config.max_rows,
                skiprows=config.skip_rows if config.skip_rows > 0 else None,
                na_values=config.null_values,
                low_memory=False,
            )

            # Extract schema information
            schema = self._infer_schema(df) if config.infer_types else {}

            # Get quality metrics
            quality_metrics = self._compute_quality_metrics(df)

            # Convert to records
            records = df.to_dict(orient="records")

            # Create processed data
            processed = ProcessedData(
                content=records,
                content_type="records",
                source_type="csv",
                metadata={
                    "schema": schema,
                    "columns": list(df.columns),
                    "quality": quality_metrics,
                },
                record_count=len(records),
                raw_size_bytes=len(raw_bytes),
            )

            result.data = processed

            # Add warnings for data quality issues
            if quality_metrics["null_percentage"] > 20:
                result.add_message(
                    code="CSV_HIGH_NULL_RATE",
                    message=f"High null rate: {quality_metrics['null_percentage']:.1f}% of values are null",
                    severity=ValidationStatus.WARNING,
                    validator=self.name,
                )
                if result.status == ValidationStatus.PASSED:
                    result.status = ValidationStatus.WARNING

            if quality_metrics["duplicate_rows"] > 0:
                result.add_message(
                    code="CSV_DUPLICATE_ROWS",
                    message=f"Found {quality_metrics['duplicate_rows']} duplicate rows",
                    severity=ValidationStatus.WARNING,
                    validator=self.name,
                )
                if result.status == ValidationStatus.PASSED:
                    result.status = ValidationStatus.WARNING

        except pd.errors.EmptyDataError:
            result.add_message(
                code="CSV_EMPTY",
                message="CSV file is empty",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR

        except pd.errors.ParserError as e:
            result.add_message(
                code="CSV_PARSE_ERROR",
                message=f"Failed to parse CSV: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR

        except Exception as e:
            result.add_message(
                code="CSV_PROCESSING_ERROR",
                message=f"Failed to process CSV: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
                details={"error": str(e)},
            )
            result.status = ValidationStatus.ERROR

        return result

    def _infer_schema(self, df: Any) -> dict[str, Any]:
        """Infer schema from DataFrame.

        Args:
            df: pandas DataFrame

        Returns:
            Schema dict with column types
        """
        schema: dict[str, Any] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {},
            },
        }

        type_mapping = {
            "int64": "integer",
            "int32": "integer",
            "float64": "number",
            "float32": "number",
            "bool": "boolean",
            "object": "string",
            "datetime64[ns]": "string",
            "category": "string",
        }

        for col in df.columns:
            dtype_str = str(df[col].dtype)
            json_type = type_mapping.get(dtype_str, "string")

            col_schema: dict[str, Any] = {"type": json_type}

            # Add nullable if column has nulls
            if df[col].isna().any():
                col_schema["nullable"] = True

            # Add enum for low-cardinality string columns
            if json_type == "string":
                unique_count = df[col].nunique()
                if unique_count <= 10 and unique_count > 0:
                    unique_values = df[col].dropna().unique().tolist()
                    col_schema["enum"] = [str(v) for v in unique_values]

            schema["items"]["properties"][str(col)] = col_schema

        return schema

    def _compute_quality_metrics(self, df: Any) -> dict[str, Any]:
        """Compute data quality metrics.

        Args:
            df: pandas DataFrame

        Returns:
            Dict of quality metrics
        """
        total_cells = df.size
        null_cells = df.isna().sum().sum()

        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "total_cells": total_cells,
            "null_cells": int(null_cells),
            "null_percentage": (null_cells / total_cells * 100) if total_cells > 0 else 0,
            "duplicate_rows": int(df.duplicated().sum()),
            "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        }
