"""Configuration management for EasyEnv."""

from __future__ import annotations

from pathlib import Path

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel, Field


class EasyEnvConfig(BaseModel):
    """EasyEnv configuration.

    Attributes:
        cache_dir: Custom cache directory path
        default_python: Default Python version
        purge_older_than_days: Default purge age policy
        purge_max_size_gb: Default purge size policy in GB
        verbose: Enable verbose output by default
        offline: Enable offline mode by default
    """

    cache_dir: str | None = None
    default_python: str = "3.12"
    purge_older_than_days: int | None = None
    purge_max_size_gb: float | None = None
    verbose: bool = False
    offline: bool = False
    templates: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> EasyEnvConfig:
        """Load configuration from file.

        Args:
            config_path: Optional custom config path

        Returns:
            Configuration instance
        """
        if config_path is None:
            config_dir = Path(user_config_dir("easyenv", "easyenv"))
            config_path = config_dir / "config.toml"

        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                # Support both YAML and TOML (just use YAML parser for simplicity)
                data = yaml.safe_load(f) or {}
            return cls(**data)
        except Exception:
            # If config is invalid, return defaults
            return cls()

    def save(self, config_path: Path | None = None) -> None:
        """Save configuration to file.

        Args:
            config_path: Optional custom config path
        """
        if config_path is None:
            config_dir = Path(user_config_dir("easyenv", "easyenv"))
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.toml"

        with open(config_path, "w") as f:
            yaml.safe_dump(self.model_dump(exclude_none=True), f, default_flow_style=False)

    def get_cache_dir(self) -> Path:
        """Get cache directory path.

        Returns:
            Cache directory path
        """
        if self.cache_dir:
            return Path(self.cache_dir)
        from platformdirs import user_cache_dir

        return Path(user_cache_dir("easyenv", "easyenv"))
