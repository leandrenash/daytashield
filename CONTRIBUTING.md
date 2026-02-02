# Contributing to DataShield

Thank you for your interest in contributing to DataShield! This document provides guidelines and information for contributors.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and constructive in all interactions.

## Getting Started

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/datashield.git
   cd datashield
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=datashield --cov-report=html

# Run specific test file
pytest tests/test_validators/test_schema.py

# Run tests matching a pattern
pytest -k "test_fresh"
```

### Code Quality

```bash
# Run linting
ruff check src tests

# Run formatting
ruff format src tests

# Run type checking
mypy src
```

## How to Contribute

### Reporting Bugs

Before submitting a bug report:
1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - Python version
   - DataShield version
   - Operating system
   - Minimal reproducible example
   - Expected vs actual behavior

### Suggesting Features

1. Check existing issues and discussions
2. Use the feature request template
3. Explain the use case and benefits
4. Consider implementation complexity

### Pull Requests

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow the code style (enforced by ruff)
   - Add tests for new functionality
   - Update documentation if needed

3. **Run quality checks**:
   ```bash
   ruff check src tests
   ruff format src tests
   mypy src
   pytest
   ```

4. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add support for XML processing"
   ```
   
   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation
   - `test:` tests
   - `refactor:` code refactoring
   - `chore:` maintenance

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

### PR Review Process

1. Automated checks must pass
2. At least one maintainer review required
3. Address feedback constructively
4. Squash commits before merge

## Project Structure

```
datashield/
├── src/datashield/
│   ├── core/          # Core pipeline, router, audit
│   ├── validators/    # Schema, semantic, freshness, compliance
│   ├── processors/    # PDF, CSV, JSON processors
│   ├── integrations/  # LangChain, etc.
│   ├── rules/         # Compliance rule packs
│   └── cli/           # Command-line interface
├── tests/             # Test suite
├── examples/          # Example scripts
└── docs/              # Documentation
```

## Adding New Validators

1. Create a new file in `src/datashield/validators/`
2. Extend `BaseValidator`:
   ```python
   from datashield.validators.base import BaseValidator
   
   class MyValidator(BaseValidator):
       name = "my_validator"
       
       def validate(self, data, result):
           # Your validation logic
           return result
   ```
3. Add to `__init__.py`
4. Add tests in `tests/test_validators/`
5. Document in `docs/validators.md`

## Adding New Processors

1. Create a new file in `src/datashield/processors/`
2. Extend `BaseProcessor`:
   ```python
   from datashield.processors.base import BaseProcessor
   
   class MyProcessor(BaseProcessor):
       name = "my_processor"
       supported_extensions = [".xyz"]
       
       def process(self, source, result=None):
           # Your processing logic
           return result
   ```
3. Add to `__init__.py`
4. Add tests in `tests/test_processors/`
5. Document in `docs/processors.md`

## Adding Compliance Rules

1. Create a new file in `src/datashield/rules/`
2. Extend `ComplianceRule`:
   ```python
   from datashield.rules.base import ComplianceRule
   
   class MyRule(ComplianceRule):
       name = "my_rule"
       
       def check(self, data, text_content):
           violations = []
           # Your rule logic
           return violations
   ```
3. Add to `__init__.py`
4. Add tests in `tests/test_validators/test_compliance.py`

## Documentation

- Use docstrings for all public APIs
- Follow Google docstring style
- Update relevant docs in `docs/`
- Include examples where helpful

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create and push a tag: `git tag v0.2.0 && git push --tags`
4. GitHub Actions will:
   - Run tests
   - Build package
   - Publish to PyPI
   - Build and push Docker images
   - Create GitHub release

## Questions?

- Open a [Discussion](https://github.com/datashield/datashield/discussions)
- Join our [Discord](https://discord.gg/datashield)
- Email: team@datashield.dev

Thank you for contributing! 🛡️
