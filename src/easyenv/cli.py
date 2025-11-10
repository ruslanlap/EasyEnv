"""CLI interface for EasyEnv using Typer."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from easyenv import __version__
from easyenv.cache import CacheManager
from easyenv.config import EasyEnvConfig
from easyenv.dsl import SpecParseError, parse_spec
from easyenv.lock import LockManager
from easyenv.runner import EnvRunner
from easyenv.sbom import SBOMGenerator
from easyenv.spec import CacheMetadata
from easyenv.uv_integration import UVError, UVIntegration

app = typer.Typer(
    name="easyenv",
    help="EasyEnv - Ephemeral, reproducible, cached development environments",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def get_config() -> EasyEnvConfig:
    """Load configuration."""
    return EasyEnvConfig.load()


def get_cache_manager(config: EasyEnvConfig | None = None) -> CacheManager:
    """Get cache manager instance."""
    if config is None:
        config = get_config()
    cache_dir = config.get_cache_dir() if config.cache_dir else None
    return CacheManager(cache_dir)


@app.command()
def run(
    spec: str = typer.Argument(..., help="Spec string or YAML path. Example: 'py=3.11 pkgs:requests'"),
    command: list[str] = typer.Argument(..., help="Command to run after '--'"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    offline: bool = typer.Option(False, "--offline", help="Offline mode"),
) -> None:
    """Run command in ephemeral environment.

    [bold cyan]Examples:[/bold cyan]
    
      [green]# Run with Python 3.11 (if available)[/green]
      easyenv-cli run "py=3.11 pkgs:requests" -- python -c "import requests; print('OK')"
      
      [green]# Multiple packages[/green]
      easyenv-cli run "py=3.11 pkgs:requests,numpy" -- python script.py
      
      [green]# From YAML file[/green]
      easyenv-cli run env.yaml -- python app.py
    
    [yellow]Tip:[/yellow] Run 'easyenv-cli doctor' first to see available Python versions.
    """
    try:
        # Parse spec
        env_spec = parse_spec(spec)
        if verbose:
            console.print(f"[cyan]Spec:[/cyan] {env_spec}")

        # Get cache manager
        cache_mgr = get_cache_manager()
        hash_key = cache_mgr.compute_hash(env_spec)

        # Check if environment exists
        if cache_mgr.env_exists(hash_key):
            if verbose:
                console.print(f"[green]Using cached environment:[/green] {hash_key}")
            cache_mgr.update_last_used(hash_key)
        else:
            console.print(f"[yellow]Creating environment:[/yellow] {hash_key}")

            # Check UV
            uv_ok, uv_msg = UVIntegration.check_uv_available()
            if not uv_ok:
                console.print(f"[red]Error:[/red] {uv_msg}")
                raise typer.Exit(1)

            # Check Python
            py_ok, py_msg = UVIntegration.check_python_available(env_spec.python)
            if not py_ok:
                console.print(f"[red]Error:[/red] {py_msg}")
                raise typer.Exit(1)

            # Create environment
            env_path = cache_mgr.get_env_path(hash_key)
            UVIntegration.prepare_environment(env_path, env_spec, verbose=verbose, offline=offline)

            # Save metadata
            now = datetime.utcnow().isoformat()
            metadata = CacheMetadata(
                hash_key=hash_key,
                spec=env_spec,
                created_at=now,
                last_used=now,
                size_bytes=0,
                platform=__import__("platform").system().lower(),
                python_path=str(env_path / "bin" / "python"),
                python_version=UVIntegration.get_python_version(env_path),
                uv_version=uv_msg or "unknown",
                cache_path=str(env_path),
            )
            cache_mgr.save_metadata(metadata)
            cache_mgr.update_size(hash_key)

            # Generate SBOM
            sbom_path = env_path / "bom.json"
            SBOMGenerator.generate_and_save(env_path, sbom_path)

            console.print(f"[green]Environment ready:[/green] {hash_key}")

        # Run command
        env_path = cache_mgr.get_env_path(hash_key)
        runner = EnvRunner(env_path, env_spec)

        if verbose:
            console.print(f"[cyan]Running:[/cyan] {' '.join(command)}")

        exit_code = runner.run_interactive(command)
        # Exit with the command's exit code (0 = success, non-zero = error)
        sys.exit(exit_code)

    except SpecParseError as e:
        console.print(f"[red]Spec error:[/red] {e}")
        raise typer.Exit(1)
    except UVError as e:
        console.print(f"[red]UV error:[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def prepare(
    spec: str = typer.Argument(..., help="Spec string or YAML path. Example: 'py=3.11 pkgs:requests'"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    offline: bool = typer.Option(False, "--offline", help="Offline mode"),
) -> None:
    """Prepare environment without running command.

    [bold cyan]Examples:[/bold cyan]
    
      [green]# Pre-build environment with Python 3.11[/green]
      easyenv-cli prepare "py=3.11 pkgs:requests==2.32.3"
      
      [green]# Prepare from YAML[/green]
      easyenv-cli prepare env.yaml
    
    [yellow]Tip:[/yellow] Run 'easyenv-cli doctor' to check available Python versions.
    """
    try:
        env_spec = parse_spec(spec)
        cache_mgr = get_cache_manager()
        hash_key = cache_mgr.compute_hash(env_spec)

        if cache_mgr.env_exists(hash_key):
            console.print(f"[green]Environment already exists:[/green] {hash_key}")
            cache_mgr.update_last_used(hash_key)
            return

        console.print(f"[yellow]Creating environment:[/yellow] {hash_key}")

        # Check UV
        uv_ok, uv_msg = UVIntegration.check_uv_available()
        if not uv_ok:
            console.print(f"[red]Error:[/red] {uv_msg}")
            raise typer.Exit(1)

        # Create environment
        env_path = cache_mgr.get_env_path(hash_key)
        UVIntegration.prepare_environment(env_path, env_spec, verbose=verbose, offline=offline)

        # Save metadata
        now = datetime.utcnow().isoformat()
        metadata = CacheMetadata(
            hash_key=hash_key,
            spec=env_spec,
            created_at=now,
            last_used=now,
            size_bytes=0,
            platform=__import__("platform").system().lower(),
            python_path=str(env_path / "bin" / "python"),
            python_version=UVIntegration.get_python_version(env_path),
            uv_version=uv_msg or "unknown",
            cache_path=str(env_path),
        )
        cache_mgr.save_metadata(metadata)
        cache_mgr.update_size(hash_key)

        # Generate SBOM
        sbom_path = env_path / "bom.json"
        SBOMGenerator.generate_and_save(env_path, sbom_path)

        console.print(f"[green]Environment ready:[/green] {hash_key}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@app.command("list")
def list_envs() -> None:
    """List cached environments."""
    try:
        cache_mgr = get_cache_manager()
        envs = cache_mgr.list_environments()

        if not envs:
            console.print("[yellow]No cached environments[/yellow]")
            return

        table = Table(title="Cached Environments")
        table.add_column("Hash", style="cyan")
        table.add_column("Python", style="green")
        table.add_column("Packages", style="yellow")
        table.add_column("Size", style="magenta")
        table.add_column("Last Used", style="blue")

        for env in envs:
            size_mb = env.size_bytes / (1024 * 1024)
            pkg_count = len(env.spec.packages)
            last_used = env.last_used.split("T")[0]  # Just date

            table.add_row(
                env.hash_key[:12],
                env.spec.python,
                f"{pkg_count} packages",
                f"{size_mb:.1f} MB",
                last_used,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def du() -> None:
    """Show cache disk usage."""
    try:
        cache_mgr = get_cache_manager()
        stats = cache_mgr.get_stats()

        console.print(f"[cyan]Cache directory:[/cyan] {stats['cache_dir']}")
        console.print(f"[cyan]Total environments:[/cyan] {stats['total_environments']}")
        console.print(f"[cyan]Total size:[/cyan] {stats['total_size_gb']:.2f} GB")

        envs = cache_mgr.list_environments()
        if envs:
            console.print("\n[yellow]Per-environment breakdown:[/yellow]")
            for env in envs:
                size_mb = env.size_bytes / (1024 * 1024)
                console.print(f"  {env.hash_key[:12]}: {size_mb:.1f} MB ({env.spec.python})")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def purge(
    older_than: str | None = typer.Option(
        None, "--older-than", help="Remove envs older than (e.g., '30d')"
    ),
    max_size: str | None = typer.Option(
        None, "--max-size", help="Keep total size under (e.g., '8GB')"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed"),
) -> None:
    """Purge cached environments.

    Example:
        easyenv purge --older-than 30d --max-size 8GB --dry-run
    """
    try:
        cache_mgr = get_cache_manager()

        # Parse older_than
        older_than_days = None
        if older_than:
            if older_than.endswith("d"):
                older_than_days = int(older_than[:-1])
            else:
                console.print("[red]Error:[/red] Invalid older-than format (use '30d')")
                raise typer.Exit(1)

        # Parse max_size
        max_size_bytes = None
        if max_size:
            max_size = max_size.upper()
            if max_size.endswith("GB"):
                max_size_bytes = int(float(max_size[:-2]) * 1024 * 1024 * 1024)
            elif max_size.endswith("MB"):
                max_size_bytes = int(float(max_size[:-2]) * 1024 * 1024)
            else:
                console.print("[red]Error:[/red] Invalid max-size format (use '8GB')")
                raise typer.Exit(1)

        removed = cache_mgr.purge(
            older_than_days=older_than_days,
            max_size_bytes=max_size_bytes,
            dry_run=dry_run,
        )

        if not removed:
            console.print("[green]No environments to remove[/green]")
            return

        if dry_run:
            console.print(f"[yellow]Would remove {len(removed)} environments:[/yellow]")
        else:
            console.print(f"[green]Removed {len(removed)} environments:[/green]")

        for hash_key in removed:
            console.print(f"  - {hash_key[:12]}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def template(
    action: str = typer.Argument(..., help="Action: add, list, remove, use"),
    name: str | None = typer.Argument(None, help="Template name"),
    spec: str | None = typer.Argument(None, help="Spec for template"),
    command: list[str] | None = typer.Argument(None, help="Command to run"),
) -> None:
    """Manage templates.

    Examples:
        easyenv template add datasci "py=3.12 pkgs:numpy,pandas"
        easyenv template list
        easyenv template use datasci -- python script.py
    """
    try:
        config = get_config()

        if action == "add":
            if not name or not spec:
                console.print("[red]Error:[/red] Name and spec required for 'add'")
                raise typer.Exit(1)
            config.templates[name] = spec
            config.save()
            console.print(f"[green]Template added:[/green] {name}")

        elif action == "list":
            if not config.templates:
                console.print("[yellow]No templates defined[/yellow]")
                return
            console.print("[cyan]Templates:[/cyan]")
            for tpl_name, tpl_spec in config.templates.items():
                console.print(f"  {tpl_name}: {tpl_spec}")

        elif action == "remove":
            if not name:
                console.print("[red]Error:[/red] Name required for 'remove'")
                raise typer.Exit(1)
            if name in config.templates:
                del config.templates[name]
                config.save()
                console.print(f"[green]Template removed:[/green] {name}")
            else:
                console.print(f"[yellow]Template not found:[/yellow] {name}")

        elif action == "use":
            if not name or not command:
                console.print("[red]Error:[/red] Name and command required for 'use'")
                raise typer.Exit(1)
            if name not in config.templates:
                console.print(f"[red]Template not found:[/red] {name}")
                raise typer.Exit(1)

            # Call run with template spec
            spec_str = config.templates[name]
            run(spec=spec_str, command=command, verbose=False, offline=False)

        else:
            console.print(f"[red]Unknown action:[/red] {action}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


lock_app = typer.Typer(help="Lock file operations")
app.add_typer(lock_app, name="lock")


@lock_app.command("export")
def lock_export(
    hash_or_spec: str = typer.Argument(..., help="Environment hash or spec to export"),
    output: str = typer.Option("ee.lock.json", "--output", "-o", help="Output file"),
) -> None:
    """Export lock file for environment.

    Example:
        easyenv lock export abc123def456 -o my.lock.json
    """
    try:
        cache_mgr = get_cache_manager()
        lock_mgr = LockManager(cache_mgr)

        # Check if it's a hash
        if cache_mgr.env_exists(hash_or_spec):
            hash_key = hash_or_spec
        else:
            # Try parsing as spec
            env_spec = parse_spec(hash_or_spec)
            hash_key = cache_mgr.compute_hash(env_spec)

            if not cache_mgr.env_exists(hash_key):
                console.print("[red]Environment not found[/red]")
                raise typer.Exit(1)

        output_path = Path(output)
        lock_mgr.export_lock(hash_key, output_path)
        console.print(f"[green]Lock file exported:[/green] {output_path}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@lock_app.command("import")
def lock_import(
    lock_file: str = typer.Argument(..., help="Lock file to import"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    offline: bool = typer.Option(False, "--offline", help="Offline mode"),
) -> None:
    """Import lock file and create environment.

    Example:
        easyenv lock import ee.lock.json
    """
    try:
        cache_mgr = get_cache_manager()
        lock_mgr = LockManager(cache_mgr)

        lock_path = Path(lock_file)
        if not lock_path.exists():
            console.print(f"[red]Lock file not found:[/red] {lock_path}")
            raise typer.Exit(1)

        console.print("[yellow]Importing lock file...[/yellow]")
        hash_key = lock_mgr.import_lock(lock_path, verbose=verbose, offline=offline)
        console.print(f"[green]Environment created:[/green] {hash_key}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def doctor() -> None:
    """Diagnose EasyEnv setup and show available Python versions."""
    console.print("[bold cyan]EasyEnv Doctor[/bold cyan]\n")

    # Check UV
    uv_ok, uv_msg = UVIntegration.check_uv_available()
    if uv_ok:
        console.print(f"[green]✓[/green] UV: {uv_msg}")
    else:
        console.print(f"[red]✗[/red] UV: {uv_msg}")
        console.print("[yellow]  → Install UV: curl -LsSf https://astral.sh/uv/install.sh | sh[/yellow]")

    # Check Python versions
    console.print("\n[bold]Available Python versions:[/bold]")
    available_versions = []
    for py_ver in ["3.11", "3.12", "3.13"]:
        py_ok, py_msg = UVIntegration.check_python_available(py_ver)
        if py_ok:
            console.print(f"[green]✓[/green] Python {py_ver}: {py_msg}")
            available_versions.append(py_ver)
        else:
            console.print(f"[yellow]○[/yellow] Python {py_ver}: Not found")
    
    if not available_versions:
        console.print("\n[red]⚠ No Python versions found![/red]")
        console.print("[yellow]Install Python using one of these methods:[/yellow]")
        console.print("  • uv python install 3.11")
        console.print("  • System package manager (apt, brew, etc.)")
    else:
        console.print(f"\n[green]✓ You can use Python: {', '.join(available_versions)}[/green]")

    # Check cache dir
    config = get_config()
    cache_dir = config.get_cache_dir()
    console.print(f"\n[bold]Cache:[/bold]")
    if cache_dir.exists():
        console.print(f"[green]✓[/green] Cache dir: {cache_dir}")
    else:
        console.print(f"[yellow]○[/yellow] Cache dir: {cache_dir} (will be created)")

    # Check config
    config_path = (
        Path(__import__("platformdirs").user_config_dir("easyenv", "easyenv")) / "config.toml"
    )
    if config_path.exists():
        console.print(f"[green]✓[/green] Config: {config_path}")
    else:
        console.print("[yellow]○[/yellow] Config: Not found (using defaults)")

    console.print(f"\n[cyan]EasyEnv version:[/cyan] {__version__}")
    
    # Show quick start if no Python available
    if not available_versions:
        console.print("\n[bold yellow]Quick Start:[/bold yellow]")
        console.print("1. Install Python: [cyan]uv python install 3.11[/cyan]")
        console.print("2. Run doctor again: [cyan]easyenv-cli doctor[/cyan]")
        console.print("3. Try example: [cyan]easyenv-cli run 'py=3.11 pkgs:requests' -- python -c 'import requests; print(\"OK\")'[/cyan]")


@app.command()
def tui(
    enable: bool = typer.Option(True, help="Enable TUI (set to False to disable)"),
) -> None:
    """Launch TUI for cache browsing."""
    if not enable:
        console.print("[yellow]TUI is disabled[/yellow]")
        return

    try:
        from easyenv.tui import EasyEnvTUI

        tui_app = EasyEnvTUI()
        tui_app.run()
    except ImportError:
        console.print("[red]TUI not available:[/red] Install textual with 'pip install textual'")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]TUI error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"EasyEnv version {__version__}")


if __name__ == "__main__":
    app()
