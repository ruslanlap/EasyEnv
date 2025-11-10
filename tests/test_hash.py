"""Tests for hash stability."""

from easyenv.cache import CacheManager
from easyenv.spec import EnvSpec


def test_hash_stability():
    """Test that hash is stable for same spec."""
    spec = EnvSpec(python="3.12", packages=["requests==2.32.3"])

    cache_mgr = CacheManager()
    hash1 = cache_mgr.compute_hash(spec)
    hash2 = cache_mgr.compute_hash(spec)

    assert hash1 == hash2


def test_hash_normalization():
    """Test that normalized specs produce same hash."""
    spec1 = EnvSpec(
        python="3.12", packages=["requests==2.32.3", "numpy>=1.24.0"], extras=["dev", "test"]
    )
    spec2 = EnvSpec(
        python="3.12", packages=["numpy>=1.24.0", "requests==2.32.3"], extras=["test", "dev"]
    )

    cache_mgr = CacheManager()
    hash1 = cache_mgr.compute_hash(spec1)
    hash2 = cache_mgr.compute_hash(spec2)

    assert hash1 == hash2


def test_hash_different_python():
    """Test that different Python versions produce different hashes."""
    spec1 = EnvSpec(python="3.11", packages=["requests"])
    spec2 = EnvSpec(python="3.12", packages=["requests"])

    cache_mgr = CacheManager()
    hash1 = cache_mgr.compute_hash(spec1)
    hash2 = cache_mgr.compute_hash(spec2)

    assert hash1 != hash2


def test_hash_different_packages():
    """Test that different packages produce different hashes."""
    spec1 = EnvSpec(python="3.12", packages=["requests==2.32.3"])
    spec2 = EnvSpec(python="3.12", packages=["requests==2.31.0"])

    cache_mgr = CacheManager()
    hash1 = cache_mgr.compute_hash(spec1)
    hash2 = cache_mgr.compute_hash(spec2)

    assert hash1 != hash2


def test_hash_includes_extras():
    """Test that extras affect hash."""
    spec1 = EnvSpec(python="3.12", packages=["requests"], extras=["dev"])
    spec2 = EnvSpec(python="3.12", packages=["requests"], extras=["test"])

    cache_mgr = CacheManager()
    hash1 = cache_mgr.compute_hash(spec1)
    hash2 = cache_mgr.compute_hash(spec2)

    assert hash1 != hash2


def test_hash_deterministic_across_instances():
    """Test that hash is deterministic across cache manager instances."""
    spec = EnvSpec(python="3.12", packages=["requests==2.32.3"])

    cache_mgr1 = CacheManager()
    cache_mgr2 = CacheManager()

    hash1 = cache_mgr1.compute_hash(spec)
    hash2 = cache_mgr2.compute_hash(spec)

    assert hash1 == hash2
