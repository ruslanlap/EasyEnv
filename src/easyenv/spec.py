"""Specification models for EasyEnv environments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class EnvSpec(BaseModel):
    """Environment specification model.

    Attributes:
        python: Python version (e.g., "3.12", "3.11")
        packages: List of package specifications (e.g., "requests==2.32.3")
        extras: Optional extra labels for grouping
        flags: Optional key-value flags for future use
        scripts: Optional scripts to run after install
        env: Optional environment variables to set
    """

    python: str = Field(..., description="Python version")
    packages: list[str] = Field(default_factory=list, description="Package specifications")
    extras: list[str] = Field(default_factory=list, description="Extra labels")
    flags: dict[str, str] = Field(default_factory=dict, description="Optional flags")
    scripts: dict[str, list[str]] = Field(default_factory=dict, description="Scripts to run")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")

    @field_validator("python")
    @classmethod
    def validate_python_version(cls, v: str) -> str:
        """Validate Python version format."""
        # Accept formats like "3.12", "3.11.5", "3.10"
        parts = v.split(".")
        if len(parts) < 2 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Invalid Python version format: {v}")
        return v

    @field_validator("packages")
    @classmethod
    def validate_packages(cls, v: list[str]) -> list[str]:
        """Validate package specifications."""
        for pkg in v:
            if not pkg.strip():
                raise ValueError("Empty package specification")
        return v

    def normalize(self) -> EnvSpec:
        """Normalize spec for consistent hashing.

        Returns:
            Normalized copy of the spec
        """
        return EnvSpec(
            python=self.python,
            packages=sorted(set(pkg.strip() for pkg in self.packages)),
            extras=sorted(set(self.extras)),
            flags=dict(sorted(self.flags.items())),
            scripts=dict(sorted(self.scripts.items())),
            env=dict(sorted(self.env.items())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return self.model_dump(exclude_none=True, exclude_defaults=True)

    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to YAML-compatible dictionary."""
        result: dict[str, Any] = {"python": self.python}
        if self.packages:
            result["packages"] = self.packages
        if self.extras:
            result["extras"] = self.extras
        if self.flags:
            result["flags"] = self.flags
        if self.scripts:
            result["scripts"] = self.scripts
        if self.env:
            result["env"] = self.env
        return result

    def __str__(self) -> str:
        """String representation (DSL-like)."""
        parts = [f"py={self.python}"]
        if self.packages:
            parts.append(f"pkgs:{','.join(self.packages)}")
        if self.extras:
            parts.append(f"extras:{','.join(self.extras)}")
        if self.flags:
            flag_str = ",".join(f"{k}={v}" for k, v in sorted(self.flags.items()))
            parts.append(f"flags:{flag_str}")
        return " ".join(parts)


class CacheMetadata(BaseModel):
    """Metadata for cached environment.

    Attributes:
        hash_key: Unique hash identifying this environment
        spec: Environment specification
        created_at: ISO timestamp when created
        last_used: ISO timestamp when last used
        size_bytes: Total size in bytes
        platform: Platform identifier (e.g., "linux", "darwin")
        python_path: Path to Python interpreter used
        python_version: Full Python version string
        uv_version: UV version string
        cache_path: Path to cache directory
    """

    hash_key: str
    spec: EnvSpec
    created_at: str
    last_used: str
    size_bytes: int = 0
    platform: str
    python_path: str
    python_version: str
    uv_version: str
    cache_path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return self.model_dump()
