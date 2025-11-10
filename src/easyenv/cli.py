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
from easyenv.spec import CacheMetadata, EnvSpec
from easyenv.uv_integration import UVError, UVIntegration
from easyenv.welcome import show_welcome_if_needed

app = typer.Typer(
    name="easyenv",
    help="EasyEnv - Ephemeral, reproducible, cached development environments",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Main callback to show welcome screen on first run."""
    show_welcome_if_needed()
    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def get_config() -> EasyEnvConfig:
    """Load configuration."""
    return EasyEnvConfig.load()


def get_cache_manager(config: EasyEnvConfig | None = None) -> CacheManager:
    """Get cache manager instance."""
    if config is None:
        config = get_config()
    cache_dir = config.get_cache_dir() if config.cache_dir else None
    return CacheManager(cache_dir)


def resolve_runtime_flags(
    config: EasyEnvConfig, verbose_option: bool | None, offline_option: bool | None
) -> tuple[bool, bool]:
    """Resolve runtime flags by combining config defaults with CLI overrides."""

    verbose = config.verbose if verbose_option is None else verbose_option
    offline = config.offline if offline_option is None else offline_option
    return verbose, offline


def ensure_environment_ready(
    env_spec: EnvSpec,
    cache_mgr: CacheManager,
    *,
    verbose: bool,
    offline: bool,
) -> str:
    """Ensure an environment exists for the given spec and return its hash."""

    hash_key = cache_mgr.compute_hash(env_spec)

    if cache_mgr.env_exists(hash_key):
        if verbose:
            console.print(f"[green]Using cached environment:[/green] {hash_key}")
        cache_mgr.update_last_used(hash_key)
        return hash_key

    console.print(f"[yellow]Creating environment:[/yellow] {hash_key}")

    uv_ok, uv_msg = UVIntegration.check_uv_available()
    if not uv_ok:
        console.print(f"[red]Error:[/red] {uv_msg}")
        raise typer.Exit(1)

    py_ok, py_msg = UVIntegration.check_python_available(env_spec.python)
    if not py_ok:
        console.print(f"[red]Error:[/red] {py_msg}")
        raise typer.Exit(1)
    if verbose and py_msg:
        console.print(f"[cyan]Python interpreter:[/cyan] {py_msg}")

    env_path = cache_mgr.get_env_path(hash_key)
    UVIntegration.prepare_environment(env_path, env_spec, verbose=verbose, offline=offline)

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

    sbom_path = env_path / "bom.json"
    SBOMGenerator.generate_and_save(env_path, sbom_path)

    console.print(f"[green]Environment ready:[/green] {hash_key}")
    return hash_key


@app.command()
def run(
    spec: str = typer.Argument(
        ..., help="Spec string or YAML path. Example: 'py=3.11 pkgs:requests'"
    ),
    command: list[str] = typer.Argument(..., help="Command to run after '--'"),
    verbose: bool | None = typer.Option(
        None,
        "--verbose/--no-verbose",
        "-v",
        help="Verbose output",
        show_default=False,
    ),
    offline: bool | None = typer.Option(
        None,
        "--offline/--online",
        help="Offline mode",
        show_default=False,
    ),
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
    verbose_flag = False
    offline_flag = False
    try:
        config = get_config()
        verbose_flag, offline_flag = resolve_runtime_flags(config, verbose, offline)

        # Parse spec
        env_spec = parse_spec(spec, default_python=config.default_python)
        if verbose_flag:
            console.print(f"[cyan]Spec:[/cyan] {env_spec}")

        # Get cache manager
        cache_mgr = get_cache_manager(config)
        hash_key = ensure_environment_ready(
            env_spec,
            cache_mgr,
            verbose=verbose_flag,
            offline=offline_flag,
        )

        # Run command
        env_path = cache_mgr.get_env_path(hash_key)
        runner = EnvRunner(env_path, env_spec)

        if verbose_flag:
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
        if verbose_flag:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def prepare(
    spec: str = typer.Argument(
        ..., help="Spec string or YAML path. Example: 'py=3.11 pkgs:requests'"
    ),
    verbose: bool | None = typer.Option(
        None,
        "--verbose/--no-verbose",
        "-v",
        help="Verbose output",
        show_default=False,
    ),
    offline: bool | None = typer.Option(
        None,
        "--offline/--online",
        help="Offline mode",
        show_default=False,
    ),
) -> None:
    """Prepare environment without running command.

    [bold cyan]Examples:[/bold cyan]

      [green]# Pre-build environment with Python 3.11[/green]
      easyenv-cli prepare "py=3.11 pkgs:requests==2.32.3"

      [green]# Prepare from YAML[/green]
      easyenv-cli prepare env.yaml

    [yellow]Tip:[/yellow] Run 'easyenv-cli doctor' to check available Python versions.
    """
    verbose_flag = False
    offline_flag = False
    try:
        config = get_config()
        verbose_flag, offline_flag = resolve_runtime_flags(config, verbose, offline)
        env_spec = parse_spec(spec, default_python=config.default_python)
        cache_mgr = get_cache_manager(config)
        hash_key = ensure_environment_ready(
            env_spec,
            cache_mgr,
            verbose=verbose_flag,
            offline=offline_flag,
        )
        console.print(f"[green]Environment ready:[/green] {hash_key}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose_flag:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@app.command("list")
def list_envs(
    details: bool = typer.Option(
        False,
        "--details",
        help="Show full package/extras details for each environment",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON instead of a table",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Show only the most recent N environments",
    ),
) -> None:
    """List cached environments."""
    try:
        cache_mgr = get_cache_manager()
        envs = cache_mgr.list_environments()

        if limit is not None and limit > 0:
            envs = envs[:limit]

        if not envs:
            console.print("[yellow]No cached environments[/yellow]")
            return

        if json_output:
            payload = []
            for env in envs:
                data = env.to_dict()
                data["packages"] = env.spec.packages
                data["extras"] = env.spec.extras
                data["flags"] = env.spec.flags
                payload.append(data)
            console.print_json(data=payload)
            return

        table = Table(title="Cached Environments")
        table.add_column("Hash", style="cyan")
        table.add_column("Python", style="green")
        table.add_column("Packages", style="yellow")
        if details:
            table.add_column("Details", style="white")
        table.add_column("Size", style="magenta")
        table.add_column("Last Used", style="blue")

        for env in envs:
            size_mb = env.size_bytes / (1024 * 1024)
            last_used = env.last_used.split("T")[0] if "T" in env.last_used else env.last_used
            packages = env.spec.packages
            if packages:
                preview = ", ".join(packages[:3])
                if len(packages) > 3:
                    preview += f" … (+{len(packages) - 3})"
            else:
                preview = "—"

            row = [
                env.hash_key[:12],
                env.spec.python,
                preview,
            ]

            if details:
                detail_lines: list[str] = []
                if packages:
                    detail_lines.append(f"pkgs: {', '.join(packages)}")
                if env.spec.extras:
                    detail_lines.append(f"extras: {', '.join(env.spec.extras)}")
                if env.spec.flags:
                    flag_text = ", ".join(f"{k}={v}" for k, v in env.spec.flags.items())
                    detail_lines.append(f"flags: {flag_text}")
                if not detail_lines:
                    detail_lines.append("—")
                row.append("\n".join(detail_lines))

            row.extend([f"{size_mb:.1f} MB", last_used])
            table.add_row(*row)

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
    now: bool = typer.Option(False, "--now", help="Remove all cached environments immediately"),
) -> None:
    """Purge cached environments.

    Examples:
        easyenv-cli purge --older-than 30d --max-size 8GB --dry-run
        easyenv-cli purge --now  # Remove everything immediately
    """
    try:
        cache_mgr = get_cache_manager()

        # Handle --now flag
        if now:
            if dry_run:
                console.print("[yellow]Would remove ALL cached environments[/yellow]")
            else:
                console.print("[yellow]Removing ALL cached environments...[/yellow]")

            removed = cache_mgr.purge(
                older_than_days=0,  # Remove everything
                max_size_bytes=0,  # Remove everything
                dry_run=dry_run,
            )
        else:
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
            verbose_flag, offline_flag = resolve_runtime_flags(config, None, None)
            env_spec = parse_spec(spec_str, default_python=config.default_python)
            cache_mgr = get_cache_manager(config)
            hash_key = ensure_environment_ready(
                env_spec,
                cache_mgr,
                verbose=verbose_flag,
                offline=offline_flag,
            )
            env_path = cache_mgr.get_env_path(hash_key)
            runner = EnvRunner(env_path, env_spec)
            if verbose_flag:
                console.print(f"[cyan]Running:[/cyan] {' '.join(command)}")
            exit_code = runner.run_interactive(command)
            raise typer.Exit(exit_code)

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
        config = get_config()
        cache_mgr = get_cache_manager(config)
        lock_mgr = LockManager(cache_mgr)

        # Check if it's a hash
        if cache_mgr.env_exists(hash_or_spec):
            hash_key = hash_or_spec
        else:
            # Try parsing as spec
            env_spec = parse_spec(hash_or_spec, default_python=config.default_python)
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
    verbose: bool | None = typer.Option(
        None,
        "--verbose/--no-verbose",
        "-v",
        help="Verbose output",
        show_default=False,
    ),
    offline: bool | None = typer.Option(
        None,
        "--offline/--online",
        help="Offline mode",
        show_default=False,
    ),
) -> None:
    """Import lock file and create environment.

    Example:
        easyenv lock import ee.lock.json
    """
    verbose_flag = False
    offline_flag = False
    try:
        config = get_config()
        verbose_flag, offline_flag = resolve_runtime_flags(config, verbose, offline)
        cache_mgr = get_cache_manager(config)
        lock_mgr = LockManager(cache_mgr)

        lock_path = Path(lock_file)
        if not lock_path.exists():
            console.print(f"[red]Lock file not found:[/red] {lock_path}")
            raise typer.Exit(1)

        console.print("[yellow]Importing lock file...[/yellow]")
        hash_key = lock_mgr.import_lock(lock_path, verbose=verbose_flag, offline=offline_flag)
        console.print(f"[green]Environment created:[/green] {hash_key}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose_flag:
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
        console.print(
            "[yellow]  → Install UV: curl -LsSf https://astral.sh/uv/install.sh | sh[/yellow]"
        )

    # Check Python versions
    console.print("\n[bold]Python versions (for uv):[/bold]")
    available_versions = []
    for py_ver in ["3.11", "3.12", "3.13"]:
        py_ok, py_msg = UVIntegration.check_python_available(py_ver)
        if py_ok:
            # Check if it's actually usable by uv
            import subprocess

            try:
                result = subprocess.run(
                    ["uv", "python", "find", py_ver],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    console.print(f"[green]✓[/green] Python {py_ver}: Ready for use")
                    available_versions.append(py_ver)
                else:
                    console.print(f"[yellow]⚠[/yellow] Python {py_ver}: Found but not usable by uv")
                    console.print(f"[dim]   → Fix: easyenv-cli python install {py_ver}[/dim]")
                    console.print("[dim]   → Or use: py=3.11 in your specs[/dim]")
            except Exception:
                console.print(f"[yellow]○[/yellow] Python {py_ver}: {py_msg}")
                available_versions.append(py_ver)
        else:
            console.print(f"[yellow]○[/yellow] Python {py_ver}: Not found")

    if not available_versions:
        console.print("\n[red]⚠ No Python versions found![/red]")
        console.print("[yellow]Install Python using:[/yellow]")
        console.print("  • [cyan]easyenv-cli python install 3.11[/cyan]")
        console.print("  • [dim]uv python install 3.11[/dim]")
        console.print("  • [dim]System package manager (apt, brew, etc.)[/dim]")
    else:
        console.print(f"\n[green]✓ You can use Python: {', '.join(available_versions)}[/green]")

    # Check cache dir
    config = get_config()
    cache_dir = config.get_cache_dir()
    console.print("\n[bold]Cache:[/bold]")
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
        console.print("1. Install Python: [cyan]easyenv-cli python install 3.11[/cyan]")
        console.print("2. Run doctor again: [cyan]easyenv-cli doctor[/cyan]")
        console.print(
            "3. Try example: [cyan]easyenv-cli run 'py=3.11 pkgs:requests' -- python -c 'import requests; print(\"OK\")'[/cyan]"
        )


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


@app.command()
def welcome() -> None:
    """Show welcome screen with quick start guide."""
    from easyenv.welcome import show_welcome

    show_welcome()


@app.command()
def python(
    action: str = typer.Argument(..., help="Action: install, list, uninstall"),
    version: str | None = typer.Argument(None, help="Python version (e.g., 3.11, 3.12)"),
) -> None:
    """Manage Python versions using uv.

    [bold cyan]Examples:[/bold cyan]

      [green]# List available Python versions[/green]
      easyenv-cli python list

      [green]# Install Python 3.11[/green]
      easyenv-cli python install 3.11

      [green]# Install Python 3.12[/green]
      easyenv-cli python install 3.12

      [green]# Uninstall Python 3.12[/green]
      easyenv-cli python uninstall 3.12
    """
    import subprocess

    config = get_config()

    try:
        if action == "list":
            console.print("[cyan]Checking installed Python versions...[/cyan]\n")

            # Check with uv
            result = subprocess.run(
                ["uv", "python", "list"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                console.print(result.stdout)
            else:
                console.print("[yellow]Could not list Python versions[/yellow]")
                console.print(result.stderr)

            # Also show what doctor sees
            console.print("\n[cyan]Available for EasyEnv:[/cyan]")
            versions_to_check = [config.default_python, "3.11", "3.12", "3.13"]
            seen: set[str] = set()
            for py_ver in versions_to_check:
                if py_ver in seen:
                    continue
                seen.add(py_ver)
                py_ok, py_msg = UVIntegration.check_python_available(py_ver)
                if py_ok:
                    console.print(f"[green]✓[/green] Python {py_ver}: {py_msg}")
                else:
                    console.print(f"[yellow]○[/yellow] Python {py_ver}: Not found")

            console.print(f"\n[cyan]Default Python (config):[/cyan] {config.default_python}")

        elif action == "install":
            if not version:
                console.print("[red]Error:[/red] Version required for install")
                console.print("Example: easyenv-cli python install 3.11")
                raise typer.Exit(1)

            console.print(f"[cyan]Installing Python {version}...[/cyan]\n")

            result = subprocess.run(
                ["uv", "python", "install", version],
                check=False,
                capture_output=False,  # Show output in real-time
            )

            if result.returncode == 0:
                console.print(f"\n[green]✓ Python {version} installed successfully![/green]")
                console.print(f"You can now use: [cyan]py={version}[/cyan] in your specs")
                if version != config.default_python:
                    console.print(
                        "[dim]Tip: Set this as your default in the config file if desired (default_python).[/dim]"
                    )
            else:
                console.print(f"\n[red]Failed to install Python {version}[/red]")
                raise typer.Exit(1)

        elif action == "uninstall":
            if not version:
                console.print("[red]Error:[/red] Version required for uninstall")
                console.print("Example: easyenv-cli python uninstall 3.12")
                raise typer.Exit(1)

            console.print(f"[cyan]Uninstalling Python {version}...[/cyan]")

            result = subprocess.run(
                ["uv", "python", "uninstall", version],
                check=False,
            )

            if result.returncode == 0:
                console.print(f"[green]✓ Python {version} uninstalled[/green]")
            else:
                console.print(f"[red]Failed to uninstall Python {version}[/red]")
                raise typer.Exit(1)

        else:
            console.print(f"[red]Unknown action:[/red] {action}")
            console.print("Available actions: list, install, uninstall")
            raise typer.Exit(1)

    except FileNotFoundError:
        console.print("[red]Error:[/red] UV not found")
        console.print(
            "Install UV first: [cyan]curl -LsSf https://astral.sh/uv/install.sh | sh[/cyan]"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
