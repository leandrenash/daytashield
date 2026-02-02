"""Tests for JSONProcessor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from daytashield import JSONProcessor
from daytashield.core.result import ValidationStatus


class TestJSONProcessor:
    """Tests for JSONProcessor."""

    def test_process_json_file(self, temp_json_file: Path) -> None:
        """JSON files should be processed correctly."""
        processor = JSONProcessor()
        result = processor.process(temp_json_file)
        
        assert result.status == ValidationStatus.PASSED
        assert result.data is not None
        assert result.data.content_type in ("object", "array")
        assert result.data.source_type == "json"

    def test_process_json_bytes(self) -> None:
        """JSON bytes should be processed correctly."""
        processor = JSONProcessor()
        data = {"id": 1, "name": "Test"}
        result = processor.process(json.dumps(data).encode())
        
        assert result.status == ValidationStatus.PASSED
        assert result.data.content == data

    def test_process_jsonl_file(self, temp_jsonl_file: Path) -> None:
        """JSON Lines files should be processed correctly."""
        processor = JSONProcessor()
        result = processor.process(temp_jsonl_file)
        
        assert result.status == ValidationStatus.PASSED
        assert result.data.content_type == "records"
        assert result.data.metadata["is_jsonl"] is True
        assert len(result.data.content) == 3

    def test_invalid_json_fails(self) -> None:
        """Invalid JSON should fail."""
        processor = JSONProcessor()
        result = processor.process(b"not valid json")
        
        assert result.status == ValidationStatus.ERROR
        assert any("JSON" in m.code for m in result.messages)

    def test_structure_analysis(self) -> None:
        """Structure analysis should be performed."""
        processor = JSONProcessor()
        data = {
            "level1": {
                "level2": {
                    "level3": {"value": 1}
                }
            },
            "array": [1, 2, 3],
        }
        result = processor.process(json.dumps(data).encode())
        
        structure = result.data.metadata["structure"]
        assert structure["max_depth"] >= 3
        assert structure["total_keys"] > 0

    def test_flatten_option(self) -> None:
        """Flattening should work when enabled."""
        processor = JSONProcessor(config={"flatten": True})
        data = {"user": {"name": "Test", "address": {"city": "NYC"}}}
        result = processor.process(json.dumps(data).encode())
        
        content = result.data.content
        assert "user.name" in content
        assert "user.address.city" in content

    def test_deep_nesting_warning(self) -> None:
        """Deep nesting should produce a warning."""
        processor = JSONProcessor()
        
        # Create deeply nested structure
        data: dict = {"value": 1}
        for i in range(15):
            data = {"level": data}
        
        result = processor.process(json.dumps(data).encode())
        assert any("DEEP_NESTING" in m.code for m in result.messages)


class TestJSONProcessorProvenance:
    """Tests for JSONProcessor provenance tracking."""

    def test_provenance_from_file(self, temp_json_file: Path) -> None:
        """Provenance should be tracked for file sources."""
        processor = JSONProcessor()
        result = processor.process(temp_json_file)
        
        assert result.provenance is not None
        assert result.provenance.source_type == "file"
        assert result.provenance.source_path is not None
        assert result.provenance.checksum is not None

    def test_provenance_from_bytes(self) -> None:
        """Provenance should be tracked for byte sources."""
        processor = JSONProcessor()
        result = processor.process(b'{"test": 1}')
        
        assert result.provenance is not None
        assert result.provenance.source_type == "bytes"
        assert result.provenance.checksum is not None
