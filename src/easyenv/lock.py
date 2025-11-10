"""Lock file management for reproducible environments."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from easyenv.cache import CacheManager
from easyenv.spec import EnvSpec
from easyenv.uv_integration import UVIntegration


class LockError(Exception):
    """Error during lock operations."""


class LockFile:
    """Represents a lock file for reproducible environments."""

    def __init__(
        self,
        spec: EnvSpec,
        resolved_packages: list[str],
        python_version: str,
        uv_version: str,
        platform_info: str,
        created_at: str | None = None,
    ) -> None:
        """Initialize lock file.

        Args:
            spec: Environment specification
            resolved_packages: List of resolved package specs with versions
            python_version: Full Python version string
            uv_version: UV version string
            platform_info: Platform identifier
            created_at: ISO timestamp (defaults to now)
        """
        self.spec = spec
        self.resolved_packages = resolved_packages
        self.python_version = python_version
        self.uv_version = uv_version
        self.platform_info = platform_info
        self.created_at = created_at or datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation
        """
        return {
            "version": "1.0",
            "created_at": self.created_at,
            "spec": self.spec.to_dict(),
            "resolved_packages": self.resolved_packages,
            "python_version": self.python_version,
            "uv_version": self.uv_version,
            "platform": self.platform_info,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LockFile:
        """Create from dictionary representation.

        Args:
            data: Dictionary data

        Returns:
            LockFile instance

        Raises:
            LockError: If data is invalid
        """
        version = data.get("version")
        if version != "1.0":
            raise LockError(f"Unsupported lock file version: {version}")

        try:
            spec = EnvSpec(**data["spec"])
            return cls(
                spec=spec,
                resolved_packages=data["resolved_packages"],
                python_version=data["python_version"],
                uv_version=data["uv_version"],
                platform_info=data["platform"],
                created_at=data.get("created_at"),
            )
        except (KeyError, TypeError) as e:
            raise LockError(f"Invalid lock file format: {e}") from e

    def export(self, path: Path) -> None:
        """Export lock file to path.

        Args:
            path: Path to write lock file
        """
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> LockFile:
        """Load lock file from path.

        Args:
            path: Path to lock file

        Returns:
            LockFile instance

        Raises:
            LockError: If loading fails
        """
        if not path.exists():
            raise LockError(f"Lock file not found: {path}")

        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise LockError(f"Invalid JSON in lock file: {e}") from e


class LockManager:
    """Manages lock file creation and restoration."""

    def __init__(self, cache_manager: CacheManager) -> None:
        """Initialize lock manager.

        Args:
            cache_manager: Cache manager instance
        """
        self.cache_manager = cache_manager

    def create_lock_from_env(self, env_path: Path, spec: EnvSpec) -> LockFile:
        """Create lock file from existing environment.

        Args:
            env_path: Path to environment
            spec: Environment specification

        Returns:
            LockFile instance

        Raises:
            LockError: If lock creation fails
        """
        # Freeze packages
        try:
            resolved_packages = UVIntegration.freeze_packages(env_path)
        except Exception as e:
            raise LockError(f"Failed to freeze packages: {e}") from e

        # Get Python version
        try:
            python_version = UVIntegration.get_python_version(env_path)
        except Exception as e:
            raise LockError(f"Failed to get Python version: {e}") from e

        # Get UV version
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            uv_version = result.stdout.strip()
        except Exception as e:
            raise LockError(f"Failed to get UV version: {e}") from e

        # Get platform info
        platform_info = platform.system().lower()

        return LockFile(
            spec=spec,
            resolved_packages=resolved_packages,
            python_version=python_version,
            uv_version=uv_version,
            platform_info=platform_info,
        )

    def export_lock(self, hash_key: str, output_path: Path) -> None:
        """Export lock file for cached environment.

        Args:
            hash_key: Environment hash key
            output_path: Path to write lock file

        Raises:
            LockError: If export fails
        """
        # Load metadata
        metadata = self.cache_manager.load_metadata(hash_key)
        if not metadata:
            raise LockError(f"Environment not found: {hash_key}")

        env_path = self.cache_manager.get_env_path(hash_key)
        if not env_path.exists():
            raise LockError(f"Environment path not found: {env_path}")

        # Create lock file
        lock_file = self.create_lock_from_env(env_path, metadata.spec)

        # Export
        lock_file.export(output_path)

    def import_lock(self, lock_path: Path, verbose: bool = False, offline: bool = False) -> str:
        """Import lock file and create environment.

        Args:
            lock_path: Path to lock file
            verbose: Enable verbose output
            offline: Offline mode

        Returns:
            Hash key of created environment

        Raises:
            LockError: If import fails
        """
        # Load lock file
        lock_file = LockFile.load(lock_path)

        # Check if environment already exists
        hash_key = self.cache_manager.compute_hash(lock_file.spec)
        if self.cache_manager.env_exists(hash_key):
            if verbose:
                print(f"Environment already exists: {hash_key}")
            return hash_key

        # Create environment
        env_path = self.cache_manager.get_env_path(hash_key)

        try:
            # Use resolved packages from lock file
            spec_with_resolved = EnvSpec(
                python=lock_file.spec.python,
                packages=lock_file.resolved_packages,  # Use frozen packages
                extras=lock_file.spec.extras,
                flags=lock_file.spec.flags,
                scripts=lock_file.spec.scripts,
                env=lock_file.spec.env,
            )

            UVIntegration.prepare_environment(
                env_path, spec_with_resolved, verbose=verbose, offline=offline
            )

            # Create metadata
            from easyenv.spec import CacheMetadata

            now = datetime.utcnow().isoformat()
            metadata = CacheMetadata(
                hash_key=hash_key,
                spec=lock_file.spec,  # Store original spec
                created_at=now,
                last_used=now,
                size_bytes=0,
                platform=lock_file.platform_info,
                python_path=str(env_path / "bin" / "python"),
                python_version=lock_file.python_version,
                uv_version=lock_file.uv_version,
                cache_path=str(env_path),
            )

            self.cache_manager.save_metadata(metadata)
            self.cache_manager.update_size(hash_key)

            return hash_key

        except Exception as e:
            # Clean up on failure
            import shutil

            if env_path.exists():
                shutil.rmtree(env_path)
            raise LockError(f"Failed to import lock file: {e}") from e
