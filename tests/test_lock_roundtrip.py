"""Tests for lock file export/import roundtrip."""

from pathlib import Path

import pytest

from easyenv.lock import LockError, LockFile
from easyenv.spec import EnvSpec


def test_lock_file_creation():
    """Test creating a lock file."""
    spec = EnvSpec(python="3.12", packages=["requests==2.32.3"])

    lock_file = LockFile(
        spec=spec,
        resolved_packages=["requests==2.32.3", "certifi==2023.7.22"],
        python_version="Python 3.12.0",
        uv_version="uv 0.1.0",
        platform_info="linux",
    )

    assert lock_file.spec.python == "3.12"
    assert len(lock_file.resolved_packages) == 2


def test_lock_file_export_import(tmp_path):
    """Test lock file export and import roundtrip."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests==2.32.3"],
        extras=["dev"],
        env={"DEBUG": "true"},
    )

    lock_file = LockFile(
        spec=spec,
        resolved_packages=["requests==2.32.3", "certifi==2023.7.22", "urllib3==2.0.4"],
        python_version="Python 3.12.0",
        uv_version="uv 0.1.0",
        platform_info="linux",
    )

    # Export
    lock_path = tmp_path / "test.lock.json"
    lock_file.export(lock_path)

    assert lock_path.exists()

    # Import
    loaded_lock = LockFile.load(lock_path)

    assert loaded_lock.spec.python == spec.python
    assert loaded_lock.spec.packages == spec.packages
    assert loaded_lock.spec.extras == spec.extras
    assert loaded_lock.spec.env == spec.env
    assert len(loaded_lock.resolved_packages) == 3
    assert loaded_lock.python_version == "Python 3.12.0"
    assert loaded_lock.uv_version == "uv 0.1.0"
    assert loaded_lock.platform_info == "linux"


def test_lock_file_to_dict():
    """Test lock file dictionary conversion."""
    spec = EnvSpec(python="3.12", packages=["requests"])

    lock_file = LockFile(
        spec=spec,
        resolved_packages=["requests==2.32.3"],
        python_version="Python 3.12.0",
        uv_version="uv 0.1.0",
        platform_info="linux",
    )

    data = lock_file.to_dict()

    assert data["version"] == "1.0"
    assert data["spec"]["python"] == "3.12"
    assert "resolved_packages" in data
    assert data["python_version"] == "Python 3.12.0"


def test_lock_file_from_dict():
    """Test creating lock file from dictionary."""
    data = {
        "version": "1.0",
        "created_at": "2024-01-01T00:00:00",
        "spec": {"python": "3.12", "packages": ["requests"]},
        "resolved_packages": ["requests==2.32.3"],
        "python_version": "Python 3.12.0",
        "uv_version": "uv 0.1.0",
        "platform": "linux",
    }

    lock_file = LockFile.from_dict(data)

    assert lock_file.spec.python == "3.12"
    assert lock_file.resolved_packages == ["requests==2.32.3"]


def test_lock_file_invalid_version():
    """Test that unsupported version raises error."""
    data = {
        "version": "999.0",
        "spec": {"python": "3.12"},
        "resolved_packages": [],
        "python_version": "Python 3.12.0",
        "uv_version": "uv 0.1.0",
        "platform": "linux",
    }

    with pytest.raises(LockError, match="Unsupported lock file version"):
        LockFile.from_dict(data)


def test_lock_file_missing_fields():
    """Test that missing required fields raise error."""
    data = {
        "version": "1.0",
        "spec": {"python": "3.12"},
        # Missing resolved_packages, python_version, etc.
    }

    with pytest.raises(LockError, match="Invalid lock file format"):
        LockFile.from_dict(data)


def test_lock_file_load_not_found():
    """Test loading non-existent lock file."""
    with pytest.raises(LockError, match="not found"):
        LockFile.load(Path("/nonexistent/lock.json"))


def test_lock_file_preserves_spec_details():
    """Test that lock file preserves all spec details."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests==2.32.3", "numpy>=1.24.0"],
        extras=["dev", "test"],
        flags={"opt1": "val1"},
        scripts={"post_install": ["echo hello"]},
        env={"VAR1": "value1", "VAR2": "value2"},
    )

    lock_file = LockFile(
        spec=spec,
        resolved_packages=["requests==2.32.3", "numpy==1.26.0"],
        python_version="Python 3.12.0",
        uv_version="uv 0.1.0",
        platform_info="linux",
    )

    # Export and reimport
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "test.lock.json"
        lock_file.export(lock_path)
        loaded = LockFile.load(lock_path)

    assert loaded.spec.python == spec.python
    assert set(loaded.spec.packages) == set(spec.packages)
    assert set(loaded.spec.extras) == set(spec.extras)
    assert loaded.spec.flags == spec.flags
    assert loaded.spec.scripts == spec.scripts
    assert loaded.spec.env == spec.env
