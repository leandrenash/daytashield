# Processors Guide

DaytaShield processors extract content and metadata from various file formats.

## PDFProcessor

Extracts text and metadata from PDF documents using pdfplumber.

### Basic Usage

```python
from daytashield import PDFProcessor, ValidationPipeline

processor = PDFProcessor()
pipeline = ValidationPipeline([...])
pipeline.add_processor(".pdf", processor)

result = pipeline.validate_file("document.pdf")

# Access extracted content
content = result.data.content      # Extracted text
metadata = result.data.metadata    # PDF metadata
page_count = result.data.page_count
```

### Configuration

```python
from daytashield.processors.pdf import PDFProcessor, PDFProcessorConfig

processor = PDFProcessor(config=PDFProcessorConfig(
    extract_images=False,   # Don't extract embedded images
    extract_tables=True,    # Extract tables
    ocr_fallback=False,     # Use OCR if text extraction fails
    max_pages=100,          # Limit pages processed
    password="secret",      # PDF password if encrypted
))
```

### Extracted Metadata

```python
result = processor.process("document.pdf")
metadata = result.data.metadata

# Available fields:
metadata["title"]       # Document title
metadata["author"]      # Author name
metadata["created_at"]  # Creation date
metadata["modified_at"] # Last modified date
metadata["page_count"]  # Number of pages
metadata["tables"]      # Extracted tables (if enabled)
```

### OCR Fallback

For scanned PDFs, enable OCR:

```bash
pip install daytashield[ocr]
```

```python
processor = PDFProcessor(config={"ocr_fallback": True})
```

Requires `pytesseract` and `pdf2image` with Tesseract installed.

## CSVProcessor

Parses CSV and TSV files into structured records using pandas.

### Basic Usage

```python
from daytashield import CSVProcessor, ValidationPipeline

processor = CSVProcessor()
pipeline = ValidationPipeline([...])
pipeline.add_processor(".csv", processor)

result = pipeline.validate_file("data.csv")

# Access records
records = result.data.content      # List of dicts
schema = result.data.metadata["schema"]  # Inferred schema
quality = result.data.metadata["quality"]  # Quality metrics
```

### Configuration

```python
from daytashield.processors.csv import CSVProcessor, CSVProcessorConfig

processor = CSVProcessor(config=CSVProcessorConfig(
    delimiter=",",          # Field delimiter
    encoding="utf-8",       # File encoding
    has_header=True,        # First row is header
    infer_types=True,       # Infer column types
    max_rows=10000,         # Limit rows processed
    skip_rows=0,            # Skip rows at start
    null_values=["", "NA", "null"],  # Values to treat as null
))
```

### TSV Files

```python
# Automatic delimiter detection for .tsv files
pipeline.add_processor(".tsv", CSVProcessor())

# Or explicit configuration
processor = CSVProcessor(config={"delimiter": "\t"})
```

### Quality Metrics

```python
result = processor.process("data.csv")
quality = result.data.metadata["quality"]

quality["row_count"]        # Number of rows
quality["column_count"]     # Number of columns
quality["null_cells"]       # Count of null values
quality["null_percentage"]  # Percentage of null values
quality["duplicate_rows"]   # Number of duplicate rows
```

### Inferred Schema

```python
schema = result.data.metadata["schema"]
# JSON Schema format with inferred types:
# {
#   "type": "array",
#   "items": {
#     "type": "object",
#     "properties": {
#       "id": {"type": "integer"},
#       "name": {"type": "string"},
#       "status": {"type": "string", "enum": ["active", "inactive"]}
#     }
#   }
# }
```

## JSONProcessor

Handles JSON and JSON Lines files using orjson for speed.

### Basic Usage

```python
from daytashield import JSONProcessor, ValidationPipeline

processor = JSONProcessor()
pipeline = ValidationPipeline([...])
pipeline.add_processor(".json", processor)
pipeline.add_processor(".jsonl", processor)

result = pipeline.validate_file("data.json")
content = result.data.content  # Parsed JSON
```

### Configuration

```python
from daytashield.processors.json import JSONProcessor, JSONProcessorConfig

processor = JSONProcessor(config=JSONProcessorConfig(
    encoding="utf-8",           # File encoding
    max_depth=100,              # Maximum nesting depth
    flatten=False,              # Flatten nested structures
    flatten_separator=".",      # Key separator when flattening
))
```

### JSON Lines

JSON Lines files (`.jsonl`, `.ndjson`) are automatically detected:

```python
result = processor.process("events.jsonl")
records = result.data.content  # List of parsed objects
```

### Flattening

Convert nested structures to flat dictionaries:

```python
processor = JSONProcessor(config={"flatten": True})

# Input: {"user": {"name": "John", "address": {"city": "NYC"}}}
# Output: {"user.name": "John", "user.address.city": "NYC"}
```

### Structure Analysis

```python
result = processor.process("data.json")
structure = result.data.metadata["structure"]

structure["type"]           # "object" or "array"
structure["max_depth"]      # Maximum nesting depth
structure["total_keys"]     # Total number of keys
structure["array_count"]    # Number of arrays
structure["max_array_length"]  # Longest array
```

## Direct Processing

Process files directly without a pipeline:

```python
from daytashield import PDFProcessor

processor = PDFProcessor()
result = processor.process("document.pdf")

if result.passed:
    print(result.data.content)
else:
    for error in result.errors:
        print(error.message)
```

## Custom Processors

Create custom processors for other formats:

```python
from daytashield.processors.base import BaseProcessor, ProcessedData

class XMLProcessor(BaseProcessor):
    name = "xml"
    supported_extensions = [".xml"]
    
    def process(self, source, result=None):
        if result is None:
            result, provenance = self._create_result(source)
        
        # Read and parse
        raw_bytes = self._read_source(source)
        content = self._parse_xml(raw_bytes)
        
        # Create processed data
        result.data = ProcessedData(
            content=content,
            content_type="structured",
            source_type="xml",
            metadata={"root_element": "..."},
        )
        
        return result
```

## File Type Detection

Processors are selected by file extension:

```python
pipeline = ValidationPipeline([...])
pipeline.add_processor(".pdf", PDFProcessor())
pipeline.add_processor(".csv", CSVProcessor())
pipeline.add_processor(".json", JSONProcessor())

# Automatically selects correct processor
result = pipeline.validate_file("report.pdf")  # Uses PDFProcessor
result = pipeline.validate_file("data.csv")    # Uses CSVProcessor
```

Disable auto-detection:

```python
pipeline = ValidationPipeline(
    validators=[...],
    config={"auto_detect_processor": False}
)
```
