"""Textual TUI for EasyEnv cache browsing."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static

from easyenv.cache import CacheManager
from easyenv.lock import LockManager
from easyenv.runner import EnvRunner


class EasyEnvTUI(App[None]):
    """TUI application for browsing EasyEnv cache."""

    CSS = """
    Screen {
        background: $surface;
    }

    DataTable {
        height: 1fr;
    }

    #info {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("d", "details", "Details"),
        ("enter", "launch", "Launch Shell"),
        ("p", "purge", "Remove"),
        ("e", "export_lock", "Export Lock"),
    ]

    def __init__(self) -> None:
        """Initialize TUI."""
        super().__init__()
        self.cache_mgr = CacheManager()
        self.selected_hash: str | None = None

    def compose(self) -> ComposeResult:
        """Compose TUI layout."""
        yield Header()
        yield Container(
            DataTable(id="env_table"),
            Static("Select an environment to view details", id="info"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Set up the application on mount."""
        table = self.query_one("#env_table", DataTable)
        table.add_columns("Hash", "Python", "Packages", "Size (MB)", "Last Used")
        table.cursor_type = "row"
        self.load_environments()

    def load_environments(self) -> None:
        """Load environments into table."""
        table = self.query_one("#env_table", DataTable)
        table.clear()

        envs = self.cache_mgr.list_environments()
        for env in envs:
            size_mb = env.size_bytes / (1024 * 1024)
            pkg_count = len(env.spec.packages)
            last_used = env.last_used.split("T")[0]

            table.add_row(
                env.hash_key[:12],
                env.spec.python,
                str(pkg_count),
                f"{size_mb:.1f}",
                last_used,
                key=env.hash_key,
            )

    def _selected_hash(self) -> str | None:
        """Return the hash of the currently selected environment."""
        table = self.query_one("#env_table", DataTable)
        if table.cursor_row is None:
            return None
        row_keys = list(table.rows.keys())
        if table.cursor_row < len(row_keys):
            return str(row_keys[table.cursor_row])
        return None

    def _selected_metadata(self):
        """Return metadata for the selected environment, if available."""
        hash_key = self._selected_hash()
        if not hash_key:
            return None
        metadata = self.cache_mgr.load_metadata(hash_key)
        if metadata is None:
            info = self.query_one("#info", Static)
            info.update("No metadata found for selection")
        return metadata

    def action_refresh(self) -> None:
        """Refresh environment list."""
        self.load_environments()
        info = self.query_one("#info", Static)
        info.update("Refreshed")

    def action_details(self) -> None:
        """Show details for selected environment."""
        metadata = self._selected_metadata()
        if not metadata:
            return

        info = self.query_one("#info", Static)
        packages_preview = ", ".join(metadata.spec.packages[:8])
        if len(metadata.spec.packages) > 8:
            packages_preview += " …"
        details = f"""
Hash: {metadata.hash_key}
Python: {metadata.python_version}
Platform: {metadata.platform}
Created: {metadata.created_at}
Last Used: {metadata.last_used}
Size: {metadata.size_bytes / (1024 * 1024):.1f} MB
Path: {metadata.cache_path}

Packages: {packages_preview or "—"}
Extras: {", ".join(metadata.spec.extras) or "—"}
Flags: {", ".join(f"{k}={v}" for k, v in metadata.spec.flags.items()) or "—"}
        """.strip()
        info.update(details)

    def action_launch(self) -> None:
        """Launch an interactive shell inside the selected environment."""
        metadata = self._selected_metadata()
        if not metadata:
            return

        shell = os.environ.get("SHELL") or ("cmd" if sys.platform.startswith("win") else "bash")
        info = self.query_one("#info", Static)
        info.update(f"Opening {shell} in {metadata.hash_key[:12]}…")

        runner = EnvRunner(Path(metadata.cache_path), metadata.spec)
        with self.app.suspend():
            exit_code = runner.run_interactive([shell])

        info.update(f"Shell exited with code {exit_code}")
        self.cache_mgr.update_last_used(metadata.hash_key)

    def action_purge(self) -> None:
        """Remove the selected environment from cache."""
        metadata = self._selected_metadata()
        if not metadata:
            return

        self.cache_mgr.remove_env(metadata.hash_key)
        self.load_environments()
        info = self.query_one("#info", Static)
        info.update(f"Removed {metadata.hash_key[:12]}")

    def action_export_lock(self) -> None:
        """Export lock file for the selected environment to the current directory."""
        metadata = self._selected_metadata()
        if not metadata:
            return

        lock_mgr = LockManager(self.cache_mgr)
        output = Path.cwd() / f"easyenv-{metadata.hash_key[:12]}.lock.json"
        lock_mgr.export_lock(metadata.hash_key, output)
        info = self.query_one("#info", Static)
        info.update(f"Lock exported to {output}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        self.action_details()


if __name__ == "__main__":
    app = EasyEnvTUI()
    app.run()
