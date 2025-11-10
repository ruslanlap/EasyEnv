"""Welcome screen for first-time users."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def show_welcome() -> None:
    """Show welcome message for first-time users."""
    # ASCII art banner
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  ████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗ █████╗ ██╗     ║
║  ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗██║     ║
║     ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║███████║██║     ║
║     ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██╔══██║██║     ║
║     ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██║  ██║███████╗║
║     ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝║
║                                                              ║
║                     [bold green]CLI v0.1.3[/bold green]                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    console.print(banner)
    
    welcome_text = Text()
    welcome_text.append("Welcome to ", style="bold cyan")
    welcome_text.append("EasyEnv CLI", style="bold green")
    welcome_text.append("! 🚀\n\n", style="bold cyan")

    welcome_text.append("Ephemeral, reproducible, cached development environments.\n\n", style="dim")

    welcome_text.append("Quick Start:\n", style="bold yellow")
    welcome_text.append("1. Check your setup:  ", style="white")
    welcome_text.append("easyenv-cli doctor\n", style="cyan")

    welcome_text.append("2. Install Python:     ", style="white")
    welcome_text.append("easyenv-cli python install 3.11\n", style="cyan")

    welcome_text.append("3. Try an example:     ", style="white")
    welcome_text.append("easyenv-cli run 'py=3.11 pkgs:requests' -- python -c 'import requests; print(\"✓\")'\n\n", style="cyan")

    welcome_text.append("Documentation:\n", style="bold yellow")
    welcome_text.append("• Quick Start: ", style="white")
    welcome_text.append("QUICKSTART.md\n", style="cyan")
    welcome_text.append("• Full Guide:  ", style="white")
    welcome_text.append("https://github.com/ruslanlap/EasyEnv\n\n", style="cyan")

    welcome_text.append("Get Help:\n", style="bold yellow")
    welcome_text.append("• Command help:   ", style="white")
    welcome_text.append("easyenv-cli --help\n", style="cyan")
    welcome_text.append("• Specific help:  ", style="white")
    welcome_text.append("easyenv-cli COMMAND --help\n", style="cyan")
    welcome_text.append("• Browse cache:   ", style="white")
    welcome_text.append("easyenv-cli tui\n", style="cyan")

    panel = Panel(
        welcome_text,
        title="[bold green]EasyEnv CLI[/bold green]",
        border_style="green",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print()


def mark_welcomed() -> None:
    """Mark that welcome screen has been shown."""
    from platformdirs import user_config_dir

    config_dir = Path(user_config_dir("easyenv", "easyenv"))
    config_dir.mkdir(parents=True, exist_ok=True)
    welcome_file = config_dir / ".welcomed"
    welcome_file.touch()


def should_show_welcome() -> bool:
    """Check if welcome screen should be shown."""
    from platformdirs import user_config_dir

    config_dir = Path(user_config_dir("easyenv", "easyenv"))
    welcome_file = config_dir / ".welcomed"
    return not welcome_file.exists()


def show_welcome_if_needed() -> None:
    """Show welcome screen if this is first run."""
    if should_show_welcome():
        show_welcome()
        mark_welcomed()
