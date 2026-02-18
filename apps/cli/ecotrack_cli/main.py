"""EcoTrack CLI entry point using Click."""
from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="ecotrack")
def cli() -> None:
    """EcoTrack — AI-for-Earth environmental intelligence platform CLI."""
    pass


@cli.group()
def data() -> None:
    """Data ingestion and pipeline management commands."""
    pass


@data.command()
@click.option("--source", required=True, help="Data source identifier")
@click.option("--bbox", default=None, help="Bounding box (min_lon,min_lat,max_lon,max_lat)")
def ingest(source: str, bbox: str | None) -> None:
    """Ingest data from an external source."""
    console.print(f"[bold green]Ingesting data from:[/] {source}")
    if bbox:
        console.print(f"[dim]Bounding box: {bbox}[/]")
    # TODO: Implement data ingestion trigger
    console.print("[yellow]Not yet implemented.[/]")


@data.command()
def status() -> None:
    """Check status of data pipelines."""
    console.print("[bold]Pipeline Status[/]")
    # TODO: Implement pipeline status check
    console.print("[yellow]Not yet implemented.[/]")


@cli.group()
def model() -> None:
    """ML model training and management commands."""
    pass


@model.command()
@click.option("--name", required=True, help="Model name")
@click.option("--dataset", required=True, help="Training dataset ID")
def train(name: str, dataset: str) -> None:
    """Train a model."""
    console.print(f"[bold green]Training model:[/] {name} on dataset {dataset}")
    # TODO: Implement model training trigger
    console.print("[yellow]Not yet implemented.[/]")


@model.command(name="list")
def list_models() -> None:
    """List registered models."""
    console.print("[bold]Registered Models[/]")
    # TODO: Implement MLflow registry query
    console.print("[yellow]Not yet implemented.[/]")


@cli.group()
def serve() -> None:
    """Service management commands."""
    pass


@serve.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def api(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI server."""
    console.print(f"[bold green]Starting API server on {host}:{port}[/]")
    import uvicorn

    uvicorn.run(
        "ecotrack_api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@serve.command()
@click.option("--queues", default="data,ml", help="Comma-separated queue names")
def worker(queues: str) -> None:
    """Start a Celery worker."""
    console.print(f"[bold green]Starting worker for queues: {queues}[/]")
    # TODO: Implement Celery worker startup
    console.print("[yellow]Not yet implemented.[/]")


@cli.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.command()
def show() -> None:
    """Show current configuration."""
    from ecotrack.config import get_config

    cfg = get_config()
    console.print("[bold]Current Configuration[/]")
    console.print(f"  Environment: {cfg.env}")
    console.print(f"  Debug: {cfg.debug}")
    console.print(f"  Log Level: {cfg.log_level}")
    console.print(f"  API: {cfg.api_host}:{cfg.api_port}")
    console.print(f"  Database: {cfg.db.host}:{cfg.db.port}/{cfg.db.name}")
    console.print(f"  Redis: {cfg.redis.host}:{cfg.redis.port}")


@config.command()
def validate() -> None:
    """Validate configuration and connectivity."""
    console.print("[bold]Validating configuration...[/]")
    # TODO: Implement connectivity checks
    console.print("[yellow]Not yet implemented.[/]")


if __name__ == "__main__":
    cli()
