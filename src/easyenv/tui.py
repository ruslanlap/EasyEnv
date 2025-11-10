"""Textual TUI for EasyEnv cache browsing."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static

from easyenv.cache import CacheManager


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

    def action_refresh(self) -> None:
        """Refresh environment list."""
        self.load_environments()
        info = self.query_one("#info", Static)
        info.update("Refreshed")

    def action_details(self) -> None:
        """Show details for selected environment."""
        table = self.query_one("#env_table", DataTable)
        if not table.cursor_row:
            return

        # Get the selected row key
        row_key = None
        if table.cursor_row is not None:
            # Get the row key directly from the table
            row_keys = list(table.rows.keys())
            if table.cursor_row < len(row_keys):
                row_key = row_keys[table.cursor_row]
        if row_key is None:
            return

        hash_key = str(row_key)
        metadata = self.cache_mgr.load_metadata(hash_key)

        if metadata:
            info = self.query_one("#info", Static)
            details = f"""
Hash: {metadata.hash_key}
Python: {metadata.python_version}
Platform: {metadata.platform}
Created: {metadata.created_at}
Last Used: {metadata.last_used}
Size: {metadata.size_bytes / (1024 * 1024):.1f} MB
Path: {metadata.cache_path}

Packages: {", ".join(metadata.spec.packages[:5])}
{"..." if len(metadata.spec.packages) > 5 else ""}
            """.strip()
            info.update(details)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        self.action_details()


if __name__ == "__main__":
    app = EasyEnvTUI()
    app.run()
