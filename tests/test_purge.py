"""Tests for cache purge policies."""

from datetime import datetime, timedelta

import pytest

from easyenv.cache import CacheManager
from easyenv.spec import CacheMetadata, EnvSpec


@pytest.fixture
def cache_manager(tmp_path):
    """Create cache manager with temp directory."""
    return CacheManager(cache_dir=tmp_path / "cache")


def create_mock_env(
    cache_mgr: CacheManager,
    python: str,
    packages: list[str],
    size_mb: float,
    days_ago: int,
) -> str:
    """Create mock environment metadata."""
    spec = EnvSpec(python=python, packages=packages)
    hash_key = cache_mgr.compute_hash(spec)

    env_path = cache_mgr.get_env_path(hash_key)
    env_path.mkdir(parents=True)
    (env_path / "bin").mkdir()

    last_used = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()

    metadata = CacheMetadata(
        hash_key=hash_key,
        spec=spec,
        created_at=datetime.utcnow().isoformat(),
        last_used=last_used,
        size_bytes=int(size_mb * 1024 * 1024),
        platform="linux",
        python_path=str(env_path / "bin" / "python"),
        python_version="Python 3.12.0",
        uv_version="uv 0.1.0",
        cache_path=str(env_path),
    )

    cache_mgr.save_metadata(metadata)
    return hash_key


def test_purge_older_than(cache_manager):
    """Test purging by age."""
    # Create old and new environments
    old_hash = create_mock_env(cache_manager, "3.11", ["requests"], size_mb=10, days_ago=40)
    new_hash = create_mock_env(cache_manager, "3.12", ["numpy"], size_mb=20, days_ago=10)

    # Purge environments older than 30 days
    removed = cache_manager.purge(older_than_days=30)

    assert old_hash in removed
    assert new_hash not in removed
    assert not cache_manager.env_exists(old_hash)
    assert cache_manager.env_exists(new_hash)


def test_purge_max_size(cache_manager):
    """Test purging by size (LRU)."""
    # Create multiple environments
    hash1 = create_mock_env(cache_manager, "3.11", ["requests"], size_mb=10, days_ago=30)
    hash2 = create_mock_env(cache_manager, "3.12", ["numpy"], size_mb=20, days_ago=20)
    hash3 = create_mock_env(cache_manager, "3.12", ["pandas"], size_mb=30, days_ago=10)

    # Total: 60MB, limit to 40MB (should remove oldest first)
    max_size_bytes = 40 * 1024 * 1024
    removed = cache_manager.purge(max_size_bytes=max_size_bytes)

    # Oldest (hash1) should be removed
    assert hash1 in removed
    # Newer ones should remain
    assert hash2 not in removed or hash3 not in removed


def test_purge_dry_run(cache_manager):
    """Test purge dry run mode."""
    hash1 = create_mock_env(cache_manager, "3.11", ["requests"], size_mb=10, days_ago=40)

    # Dry run should return what would be removed but not actually remove
    removed = cache_manager.purge(older_than_days=30, dry_run=True)

    assert hash1 in removed
    # Environment should still exist
    assert cache_manager.env_exists(hash1)


def test_purge_combined_policies(cache_manager):
    """Test purge with both age and size policies."""
    # Old and small - should be removed by age
    _hash1 = create_mock_env(cache_manager, "3.11", ["requests"], size_mb=10, days_ago=40)
    # Recent but large - may be removed by size
    _hash2 = create_mock_env(cache_manager, "3.12", ["numpy"], size_mb=50, days_ago=20)

    # Remove by age (>30 days) OR to stay under 40MB
    max_size_bytes = 40 * 1024 * 1024
    removed = cache_manager.purge(older_than_days=30, max_size_bytes=max_size_bytes)

    # At least one should be removed
    assert len(removed) >= 1


def test_purge_empty_cache(cache_manager):
    """Test purge on empty cache."""
    removed = cache_manager.purge(older_than_days=30)
    assert removed == []


def test_purge_no_matching_policies(cache_manager):
    """Test purge when no environments match policies."""
    hash1 = create_mock_env(cache_manager, "3.12", ["requests"], size_mb=10, days_ago=5)

    removed = cache_manager.purge(older_than_days=30)
    assert hash1 not in removed
    assert cache_manager.env_exists(hash1)
