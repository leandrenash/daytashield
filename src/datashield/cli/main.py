"""DataShield command-line interface."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from datashield import __version__
from datashield.core.audit import AuditTrail
from datashield.core.pipeline import ValidationPipeline
from datashield.core.result import ValidationResult, ValidationStatus
from datashield.core.router import DataRouter, RouteAction
from datashield.processors.csv import CSVProcessor
from datashield.processors.json import JSONProcessor
from datashield.processors.pdf import PDFProcessor
from datashield.validators.compliance import ComplianceValidator
from datashield.validators.freshness import FreshnessValidator
from datashield.validators.schema import SchemaValidator

console = Console()


def get_status_style(status: ValidationStatus) -> str:
    """Get Rich style for a validation status."""
    styles = {
        ValidationStatus.PASSED: "bold green",
        ValidationStatus.WARNING: "bold yellow",
        ValidationStatus.FAILED: "bold red",
        ValidationStatus.ERROR: "bold red",
        ValidationStatus.SKIPPED: "dim",
    }
    return styles.get(status, "")


def format_duration(ms: float | None) -> str:
    """Format duration in human-readable form."""
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms:.1f}ms"
    return f"{ms / 1000:.2f}s"


@click.group()
@click.version_option(version=__version__, prog_name="datashield")
def cli() -> None:
    """DataShield: Validate multimodal data for AI systems.

    The missing validation layer between unstructured data and AI.
    """
    pass


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--schema",
    "-s",
    type=click.Path(exists=True),
    help="JSON Schema file for validation",
)
@click.option(
    "--rules",
    "-r",
    multiple=True,
    type=click.Choice(["hipaa", "gdpr", "pii"]),
    help="Compliance rules to apply",
)
@click.option(
    "--max-age",
    "-a",
    type=str,
    help="Maximum data age (e.g., 7d, 2w, 1M)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for results (JSON)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "summary"]),
    default="table",
    help="Output format",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    help="Stop on first validation failure",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress output except errors",
)
def validate(
    paths: tuple[str, ...],
    schema: str | None,
    rules: tuple[str, ...],
    max_age: str | None,
    output: str | None,
    output_format: str,
    fail_fast: bool,
    quiet: bool,
) -> None:
    """Validate files against schema and compliance rules.

    Examples:

        datashield validate invoice.pdf --schema invoice.json

        datashield validate ./data/ --rules hipaa --rules pii

        datashield validate report.csv --max-age 7d --output results.json
    """
    # Build pipeline
    pipeline = _build_pipeline(schema, rules, max_age, fail_fast)

    # Collect files to validate
    files = _collect_files(paths)

    if not files:
        console.print("[yellow]No files found to validate[/yellow]")
        return

    if not quiet:
        console.print(f"\n[bold]Validating {len(files)} file(s)...[/bold]\n")

    # Validate files
    results: list[tuple[Path, ValidationResult]] = []
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=quiet,
    ) as progress:
        task = progress.add_task("Validating...", total=len(files))

        for file_path in files:
            progress.update(task, description=f"Validating {file_path.name}...")
            result = pipeline.validate_file(file_path)
            results.append((file_path, result))
            progress.advance(task)

    total_time = time.time() - start_time

    # Output results
    if output_format == "json":
        _output_json(results, output)
    elif output_format == "summary":
        _output_summary(results, total_time, quiet)
    else:
        _output_table(results, total_time, quiet)

    # Write to file if specified
    if output:
        _write_output_file(results, output)
        if not quiet:
            console.print(f"\n[dim]Results written to {output}[/dim]")

    # Exit with error code if any failures
    failed_count = sum(1 for _, r in results if r.failed)
    if failed_count > 0:
        sys.exit(1)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--schema",
    "-s",
    type=click.Path(exists=True),
    help="JSON Schema file for validation",
)
@click.option(
    "--rules",
    "-r",
    multiple=True,
    type=click.Choice(["hipaa", "gdpr", "pii"]),
    help="Compliance rules to apply",
)
@click.option(
    "--pattern",
    "-p",
    default="*",
    help="File pattern to watch (e.g., *.pdf)",
)
@click.option(
    "--audit",
    type=click.Path(),
    help="Audit log file path",
)
def watch(
    directory: str,
    schema: str | None,
    rules: tuple[str, ...],
    pattern: str,
    audit: str | None,
) -> None:
    """Watch a directory for new files and validate them.

    Example:

        datashield watch ./incoming/ --rules hipaa --audit ./audit.jsonl
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        console.print(
            "[red]watchdog package required for watch mode.[/red]\n"
            "Install with: pip install watchdog"
        )
        sys.exit(1)

    pipeline = _build_pipeline(schema, rules, None, False)
    audit_trail = AuditTrail(audit) if audit else None
    router = DataRouter()

    console.print(f"\n[bold]Watching {directory} for {pattern} files...[/bold]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    class ValidationHandler(FileSystemEventHandler):
        def on_created(self, event: Any) -> None:
            if event.is_directory:
                return

            file_path = Path(event.src_path)
            if not file_path.match(pattern):
                return

            console.print(f"[cyan]New file: {file_path.name}[/cyan]")

            result = pipeline.validate_file(file_path)
            decision = router.route(result)

            status_style = get_status_style(result.status)
            console.print(
                f"  Status: [{status_style}]{result.status.value}[/{status_style}] "
                f"→ {decision.route.action.value}"
            )

            if result.messages:
                for msg in result.messages[:3]:
                    console.print(f"  • {msg}")

            if audit_trail:
                audit_trail.log(result)

    handler = ValidationHandler()
    observer = Observer()
    observer.schedule(handler, directory, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if audit_trail:
            audit_trail.flush()
        console.print("\n[dim]Stopped watching[/dim]")

    observer.join()


@cli.command()
@click.argument("audit_file", type=click.Path(exists=True))
@click.option(
    "--status",
    "-s",
    type=click.Choice(["passed", "warning", "failed", "error"]),
    help="Filter by status",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=20,
    help="Maximum entries to show",
)
@click.option(
    "--stats",
    is_flag=True,
    help="Show statistics only",
)
def audit(
    audit_file: str,
    status: str | None,
    limit: int,
    stats: bool,
) -> None:
    """Query the audit trail.

    Example:

        datashield audit ./audit.jsonl --status failed --limit 10
    """
    trail = AuditTrail(audit_file)

    if stats:
        audit_stats = trail.stats()

        table = Table(title="Audit Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Validations", str(audit_stats["total"]))
        table.add_row("Passed", str(audit_stats["by_status"]["passed"]))
        table.add_row("Warnings", str(audit_stats["by_status"]["warning"]))
        table.add_row("Failed", str(audit_stats["by_status"]["failed"]))
        table.add_row("Errors", str(audit_stats["by_status"]["error"]))
        table.add_row("Avg Duration", f"{audit_stats['avg_duration_ms']:.1f}ms")

        console.print(table)
        return

    # Query entries
    status_filter = ValidationStatus(status) if status else None
    entries = list(trail.query(status=status_filter, limit=limit))

    if not entries:
        console.print("[yellow]No entries found[/yellow]")
        return

    table = Table(title=f"Audit Log ({len(entries)} entries)")
    table.add_column("Time", style="dim")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Messages")
    table.add_column("Duration")

    for entry in entries:
        status_style = get_status_style(entry.status)
        table.add_row(
            entry.timestamp.strftime("%Y-%m-%d %H:%M"),
            entry.source_id or "-",
            f"[{status_style}]{entry.status.value}[/{status_style}]",
            str(entry.message_count),
            format_duration(entry.duration_ms),
        )

    console.print(table)


@cli.command()
def info() -> None:
    """Show DataShield configuration and status."""
    tree = Tree("[bold]DataShield[/bold]")

    # Version info
    version_branch = tree.add("[cyan]Version[/cyan]")
    version_branch.add(f"datashield: {__version__}")

    # Available validators
    validators_branch = tree.add("[cyan]Validators[/cyan]")
    validators_branch.add("SchemaValidator - JSON Schema / Pydantic validation")
    validators_branch.add("SemanticValidator - LLM-based semantic validation")
    validators_branch.add("FreshnessValidator - Timestamp/staleness checks")
    validators_branch.add("ComplianceValidator - HIPAA/GDPR/PII rules")

    # Available processors
    processors_branch = tree.add("[cyan]Processors[/cyan]")
    processors_branch.add("PDFProcessor - PDF text extraction")
    processors_branch.add("CSVProcessor - CSV/TSV parsing")
    processors_branch.add("JSONProcessor - JSON/JSONL parsing")

    # Compliance rules
    rules_branch = tree.add("[cyan]Compliance Rules[/cyan]")
    rules_branch.add("hipaa - HIPAA PHI detection")
    rules_branch.add("gdpr - GDPR data protection")
    rules_branch.add("pii - PII pattern detection")

    console.print(tree)


def _build_pipeline(
    schema: str | None,
    rules: tuple[str, ...],
    max_age: str | None,
    fail_fast: bool,
) -> ValidationPipeline:
    """Build validation pipeline from CLI options."""
    validators = []

    # Add schema validator
    if schema:
        schema_path = Path(schema)
        schema_data = json.loads(schema_path.read_text())
        validators.append(SchemaValidator(schema=schema_data))

    # Add freshness validator
    if max_age:
        validators.append(FreshnessValidator(max_age=max_age))

    # Add compliance validator
    if rules:
        validators.append(ComplianceValidator(rules=list(rules)))

    # Build pipeline with processors
    pipeline = ValidationPipeline(
        validators=validators,
        config={"fail_fast": fail_fast},
    )

    # Register processors
    pipeline.add_processor(".pdf", PDFProcessor())
    pipeline.add_processor(".csv", CSVProcessor())
    pipeline.add_processor(".tsv", CSVProcessor({"delimiter": "\t"}))
    pipeline.add_processor(".json", JSONProcessor())
    pipeline.add_processor(".jsonl", JSONProcessor())

    return pipeline


def _collect_files(paths: tuple[str, ...]) -> list[Path]:
    """Collect all files from paths (files and directories)."""
    files: list[Path] = []
    supported_extensions = {".pdf", ".csv", ".tsv", ".json", ".jsonl"}

    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for ext in supported_extensions:
                files.extend(path.rglob(f"*{ext}"))

    return sorted(set(files))


def _output_table(
    results: list[tuple[Path, ValidationResult]],
    total_time: float,
    quiet: bool,
) -> None:
    """Output results as a table."""
    if quiet:
        return

    table = Table(title="Validation Results")
    table.add_column("File", style="cyan")
    table.add_column("Status")
    table.add_column("Messages")
    table.add_column("Duration")

    for file_path, result in results:
        status_style = get_status_style(result.status)
        table.add_row(
            file_path.name,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            str(len(result.messages)),
            format_duration(result.duration_ms),
        )

    console.print(table)

    # Summary
    passed = sum(1 for _, r in results if r.status == ValidationStatus.PASSED)
    warnings = sum(1 for _, r in results if r.status == ValidationStatus.WARNING)
    failed = sum(1 for _, r in results if r.failed)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{passed} passed[/green], "
        f"[yellow]{warnings} warnings[/yellow], "
        f"[red]{failed} failed[/red] "
        f"[dim]({total_time:.2f}s)[/dim]"
    )


def _output_summary(
    results: list[tuple[Path, ValidationResult]],
    total_time: float,
    quiet: bool,
) -> None:
    """Output a brief summary."""
    passed = sum(1 for _, r in results if r.status == ValidationStatus.PASSED)
    warnings = sum(1 for _, r in results if r.status == ValidationStatus.WARNING)
    failed = sum(1 for _, r in results if r.failed)

    if not quiet:
        console.print(
            f"Validated {len(results)} files: "
            f"{passed} passed, {warnings} warnings, {failed} failed "
            f"({total_time:.2f}s)"
        )


def _output_json(
    results: list[tuple[Path, ValidationResult]],
    output: str | None,
) -> None:
    """Output results as JSON."""
    data = [
        {
            "file": str(file_path),
            "result": result.to_dict(),
        }
        for file_path, result in results
    ]

    if output:
        Path(output).write_text(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, default=str))


def _write_output_file(
    results: list[tuple[Path, ValidationResult]],
    output: str,
) -> None:
    """Write results to output file."""
    data = [
        {
            "file": str(file_path),
            "result": result.to_dict(),
        }
        for file_path, result in results
    ]
    Path(output).write_text(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    cli()
