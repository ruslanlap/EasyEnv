"""Cache management for EasyEnv environments."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir

from easyenv.spec import CacheMetadata, EnvSpec


class CacheManager:
    """Manages environment cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize cache manager.

        Args:
            cache_dir: Optional custom cache directory
        """
        if cache_dir is None:
            cache_dir = Path(user_cache_dir("easyenv", "easyenv"))
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Index database
        self.index_db = self.cache_dir / "index.db"
        self._init_index()

    def _init_index(self) -> None:
        """Initialize SQLite index database."""
        conn = sqlite3.connect(self.index_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS environments (
                hash_key TEXT PRIMARY KEY,
                spec_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                platform TEXT NOT NULL,
                python_path TEXT NOT NULL,
                python_version TEXT NOT NULL,
                uv_version TEXT NOT NULL,
                cache_path TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def compute_hash(self, spec: EnvSpec) -> str:
        """Compute stable hash for environment specification.

        Includes:
        - Normalized spec
        - Platform
        - Python version (major.minor)
        - UV version

        Args:
            spec: Environment specification

        Returns:
            Hash key string
        """
        normalized = spec.normalize()

        # Get platform info
        plat = platform.system().lower()

        # Get Python version (just major.minor for cross-patch compatibility)
        py_parts = spec.python.split(".")
        py_version = f"{py_parts[0]}.{py_parts[1]}"

        # Get UV version (if available)
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            uv_version = result.stdout.strip().split()[1] if result.stdout else "unknown"
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            IndexError,
            subprocess.TimeoutExpired,
        ):
            uv_version = "unknown"

        # Create hash input
        hash_input = {
            "spec": normalized.to_dict(),
            "platform": plat,
            "python": py_version,
            "uv": uv_version,
        }

        hash_str = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_str.encode()).hexdigest()[:16]

    def get_env_path(self, hash_key: str) -> Path:
        """Get path to environment cache directory.

        Args:
            hash_key: Environment hash key

        Returns:
            Path to environment directory
        """
        return self.cache_dir / hash_key

    def env_exists(self, hash_key: str) -> bool:
        """Check if environment exists in cache.

        Args:
            hash_key: Environment hash key

        Returns:
            True if environment exists
        """
        env_path = self.get_env_path(hash_key)
        return env_path.exists() and (env_path / "bin").exists()

    def save_metadata(self, metadata: CacheMetadata) -> None:
        """Save environment metadata to index.

        Args:
            metadata: Cache metadata
        """
        # Save to file
        meta_path = self.get_env_path(metadata.hash_key) / "meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Save to index
        conn = sqlite3.connect(self.index_db)
        conn.execute(
            """
            INSERT OR REPLACE INTO environments
            (hash_key, spec_json, created_at, last_used, size_bytes,
             platform, python_path, python_version, uv_version, cache_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.hash_key,
                json.dumps(metadata.spec.to_dict()),
                metadata.created_at,
                metadata.last_used,
                metadata.size_bytes,
                metadata.platform,
                metadata.python_path,
                metadata.python_version,
                metadata.uv_version,
                metadata.cache_path,
            ),
        )
        conn.commit()
        conn.close()

    def load_metadata(self, hash_key: str) -> CacheMetadata | None:
        """Load environment metadata from index.

        Args:
            hash_key: Environment hash key

        Returns:
            Cache metadata or None if not found
        """
        conn = sqlite3.connect(self.index_db)
        cursor = conn.execute("SELECT * FROM environments WHERE hash_key = ?", (hash_key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        spec_dict = json.loads(row[1])
        return CacheMetadata(
            hash_key=row[0],
            spec=EnvSpec(**spec_dict),
            created_at=row[2],
            last_used=row[3],
            size_bytes=row[4],
            platform=row[5],
            python_path=row[6],
            python_version=row[7],
            uv_version=row[8],
            cache_path=row[9],
        )

    def update_last_used(self, hash_key: str) -> None:
        """Update last used timestamp for environment.

        Args:
            hash_key: Environment hash key
        """
        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.index_db)
        conn.execute(
            "UPDATE environments SET last_used = ? WHERE hash_key = ?",
            (now, hash_key),
        )
        conn.commit()
        conn.close()

        # Also update file
        metadata = self.load_metadata(hash_key)
        if metadata:
            metadata.last_used = now
            meta_path = self.get_env_path(hash_key) / "meta.json"
            with open(meta_path, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2)

    def compute_size(self, path: Path) -> int:
        """Compute total size of directory in bytes.

        Args:
            path: Directory path

        Returns:
            Total size in bytes
        """
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        except (OSError, PermissionError):
            pass
        return total

    def update_size(self, hash_key: str) -> None:
        """Update size for environment.

        Args:
            hash_key: Environment hash key
        """
        env_path = self.get_env_path(hash_key)
        size = self.compute_size(env_path)

        conn = sqlite3.connect(self.index_db)
        conn.execute(
            "UPDATE environments SET size_bytes = ? WHERE hash_key = ?",
            (size, hash_key),
        )
        conn.commit()
        conn.close()

    def list_environments(self) -> list[CacheMetadata]:
        """List all cached environments.

        Returns:
            List of cache metadata
        """
        conn = sqlite3.connect(self.index_db)
        cursor = conn.execute("SELECT hash_key FROM environments ORDER BY last_used DESC")
        hash_keys = [row[0] for row in cursor.fetchall()]
        conn.close()

        envs = []
        for hash_key in hash_keys:
            metadata = self.load_metadata(hash_key)
            if metadata:
                envs.append(metadata)
        return envs

    def get_total_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size in bytes
        """
        conn = sqlite3.connect(self.index_db)
        cursor = conn.execute("SELECT SUM(size_bytes) FROM environments")
        total = cursor.fetchone()[0] or 0
        conn.close()
        return total

    def purge(
        self,
        older_than_days: int | None = None,
        max_size_bytes: int | None = None,
        dry_run: bool = False,
    ) -> list[str]:
        """Purge cached environments based on policies.

        Args:
            older_than_days: Remove environments not used in N days
            max_size_bytes: Keep total cache size under N bytes (remove oldest first)
            dry_run: If True, only return what would be removed

        Returns:
            List of removed hash keys
        """
        removed: list[str] = []
        envs = self.list_environments()

        # Filter by age
        if older_than_days is not None:
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            for metadata in envs:
                last_used = datetime.fromisoformat(metadata.last_used)
                if last_used < cutoff:
                    removed.append(metadata.hash_key)

        # Filter by size (LRU)
        if max_size_bytes is not None:
            # Sort by last_used (oldest first)
            envs_by_age = sorted(envs, key=lambda m: m.last_used)
            current_size = sum(m.size_bytes for m in envs)

            for metadata in envs_by_age:
                if current_size <= max_size_bytes:
                    break
                if metadata.hash_key not in removed:
                    removed.append(metadata.hash_key)
                    current_size -= metadata.size_bytes

        # Remove duplicates and actually delete
        removed = list(dict.fromkeys(removed))

        if not dry_run:
            for hash_key in removed:
                self.remove_env(hash_key)

        return removed

    def remove_env(self, hash_key: str) -> None:
        """Remove environment from cache.

        Args:
            hash_key: Environment hash key
        """
        env_path = self.get_env_path(hash_key)
        if env_path.exists():
            shutil.rmtree(env_path)

        conn = sqlite3.connect(self.index_db)
        conn.execute("DELETE FROM environments WHERE hash_key = ?", (hash_key,))
        conn.commit()
        conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        envs = self.list_environments()
        total_size = sum(m.size_bytes for m in envs)

        return {
            "total_environments": len(envs),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_size_gb": total_size / (1024 * 1024 * 1024),
            "cache_dir": str(self.cache_dir),
        }
