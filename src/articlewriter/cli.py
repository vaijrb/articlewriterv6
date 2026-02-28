"""
CLI entry point using Typer. Run with: python -m articlewriter.cli [command]
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from articlewriter.orchestrator import ArticleWriterPipeline
from articlewriter.exceptions import ArticleWriterError

app = typer.Typer(help="Journal Article Writer - automated scholarly article generation")
console = Console()


@app.command()
def run(
    config: Path = typer.Option(None, "--config", "-c", help="Path to YAML config"),
    skip_trends: bool = typer.Option(False, "--skip-trends", help="Skip trend detection"),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Skip PDF generation"),
    title: str | None = typer.Option(None, "--title", "-t", help="Article title"),
):
    """Run the full pipeline and produce article.docx, PDF, bib, and reports."""
    try:
        pipeline = ArticleWriterPipeline(config_path=str(config) if config else None)
        paths = pipeline.run_full(
            article_title=title,
            write_pdf=not no_pdf,
            skip_trends=skip_trends,
        )
        table = Table(title="Output files")
        table.add_column("Output", style="cyan")
        table.add_column("Path", style="green")
        for name, path in paths.items():
            table.add_row(name, str(path))
        console.print(table)
    except ArticleWriterError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def trends(
    config: Path = typer.Option(None, "--config", "-c"),
):
    """Run only trend detection and print ranked topics."""
    try:
        pipeline = ArticleWriterPipeline(config_path=str(config) if config else None)
        result = pipeline.run_trend_detection()
        console.print(f"[bold]Domain:[/bold] {result.domain}")
        console.print(f"[bold]Topics (top 10):[/bold]")
        for t in result.topics[:10]:
            console.print(f"  - {t.label} (score={t.score}, papers={t.paper_count})")
    except ArticleWriterError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
