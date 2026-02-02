"""Tests for CSVProcessor."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from daytashield import CSVProcessor
from daytashield.core.result import ValidationStatus


class TestCSVProcessor:
    """Tests for CSVProcessor."""

    def test_process_csv_file(self, temp_csv_file: Path) -> None:
        """CSV files should be processed correctly."""
        processor = CSVProcessor()
        result = processor.process(temp_csv_file)
        
        assert result.status == ValidationStatus.PASSED
        assert result.data is not None
        assert result.data.content_type == "records"
        assert result.data.source_type == "csv"
        assert len(result.data.content) == 2  # Two data rows

    def test_process_csv_bytes(self) -> None:
        """CSV bytes should be processed correctly."""
        processor = CSVProcessor()
        csv_bytes = b"id,name\n1,Alice\n2,Bob"
        result = processor.process(csv_bytes)
        
        assert result.status == ValidationStatus.PASSED
        assert len(result.data.content) == 2
        assert result.data.content[0]["name"] == "Alice"

    def test_schema_inference(self, temp_csv_file: Path) -> None:
        """Schema should be inferred from CSV."""
        processor = CSVProcessor()
        result = processor.process(temp_csv_file)
        
        schema = result.data.metadata.get("schema")
        assert schema is not None
        assert "properties" in schema["items"]
        assert "id" in schema["items"]["properties"]

    def test_quality_metrics(self, temp_csv_file: Path) -> None:
        """Quality metrics should be computed."""
        processor = CSVProcessor()
        result = processor.process(temp_csv_file)
        
        quality = result.data.metadata.get("quality")
        assert quality is not None
        assert quality["row_count"] == 2
        assert quality["column_count"] == 3

    def test_high_null_rate_warning(self) -> None:
        """High null rate should produce a warning."""
        processor = CSVProcessor()
        # Create CSV with many null values
        csv_bytes = b"a,b,c,d,e\n1,,,,,\n2,,,,,\n3,,,,,"
        result = processor.process(csv_bytes)
        
        assert any("NULL" in m.code for m in result.messages)

    def test_duplicate_rows_warning(self) -> None:
        """Duplicate rows should produce a warning."""
        processor = CSVProcessor()
        csv_bytes = b"id,name\n1,Alice\n1,Alice\n1,Alice"
        result = processor.process(csv_bytes)
        
        assert any("DUPLICATE" in m.code for m in result.messages)

    def test_tsv_auto_detection(self) -> None:
        """TSV files should auto-detect tab delimiter."""
        processor = CSVProcessor()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
            f.write("id\tname\n1\tAlice\n2\tBob")
            tsv_path = Path(f.name)
        
        try:
            result = processor.process(tsv_path)
            assert result.status == ValidationStatus.PASSED
            assert len(result.data.content) == 2
        finally:
            tsv_path.unlink()

    def test_empty_csv_fails(self) -> None:
        """Empty CSV should fail."""
        processor = CSVProcessor()
        result = processor.process(b"")
        
        assert result.status == ValidationStatus.ERROR
        assert any("EMPTY" in m.code for m in result.messages)


class TestCSVProcessorConfig:
    """Tests for CSVProcessor configuration."""

    def test_custom_delimiter(self) -> None:
        """Custom delimiter should be used."""
        processor = CSVProcessor(config={"delimiter": ";"})
        csv_bytes = b"id;name\n1;Alice\n2;Bob"
        result = processor.process(csv_bytes)
        
        assert result.status == ValidationStatus.PASSED
        assert len(result.data.content) == 2

    def test_max_rows(self) -> None:
        """max_rows should limit processing."""
        processor = CSVProcessor(config={"max_rows": 1})
        csv_bytes = b"id,name\n1,Alice\n2,Bob\n3,Charlie"
        result = processor.process(csv_bytes)
        
        assert len(result.data.content) == 1

    def test_skip_rows(self) -> None:
        """skip_rows should skip initial rows."""
        processor = CSVProcessor(config={"skip_rows": 1})
        csv_bytes = b"# comment line\nid,name\n1,Alice"
        result = processor.process(csv_bytes)
        
        assert result.status == ValidationStatus.PASSED
