"""Tests for EnvSpec model."""

import pytest
from pydantic import ValidationError

from easyenv.spec import EnvSpec


def test_envspec_basic():
    """Test basic EnvSpec creation."""
    spec = EnvSpec(python="3.12", packages=["requests==2.32.3"])

    assert spec.python == "3.12"
    assert len(spec.packages) == 1
    assert spec.packages[0] == "requests==2.32.3"


def test_envspec_with_extras():
    """Test EnvSpec with extras."""
    spec = EnvSpec(python="3.12", packages=["requests"], extras=["dev", "test"])

    assert len(spec.extras) == 2
    assert "dev" in spec.extras


def test_envspec_with_flags():
    """Test EnvSpec with flags."""
    spec = EnvSpec(python="3.12", packages=["requests"], flags={"opt1": "val1", "opt2": "val2"})

    assert spec.flags["opt1"] == "val1"
    assert spec.flags["opt2"] == "val2"


def test_envspec_with_scripts():
    """Test EnvSpec with scripts."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests"],
        scripts={"post_install": ["echo hello", "python -c 'print(1)'"]},
    )

    assert "post_install" in spec.scripts
    assert len(spec.scripts["post_install"]) == 2


def test_envspec_with_env():
    """Test EnvSpec with environment variables."""
    spec = EnvSpec(python="3.12", packages=["pandas"], env={"DEBUG": "true", "VAR1": "value1"})

    assert spec.env["DEBUG"] == "true"
    assert spec.env["VAR1"] == "value1"


def test_envspec_defaults():
    """Test EnvSpec defaults."""
    spec = EnvSpec(python="3.12")

    assert spec.packages == []
    assert spec.extras == []
    assert spec.flags == {}
    assert spec.scripts == {}
    assert spec.env == {}


def test_envspec_python_validation():
    """Test Python version validation."""
    # Valid versions
    EnvSpec(python="3.12")
    EnvSpec(python="3.11")
    EnvSpec(python="3.11.5")

    # Invalid versions
    with pytest.raises(ValidationError):
        EnvSpec(python="invalid")

    with pytest.raises(ValidationError):
        EnvSpec(python="3")


def test_envspec_normalize():
    """Test spec normalization."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests", "numpy", "pandas"],
        extras=["test", "dev"],
    )

    normalized = spec.normalize()

    # Packages should be sorted
    assert normalized.packages == ["numpy", "pandas", "requests"]
    # Extras should be sorted
    assert normalized.extras == ["dev", "test"]


def test_envspec_normalize_deduplicates():
    """Test that normalization removes duplicates."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests", "requests", "numpy"],
        extras=["dev", "dev", "test"],
    )

    normalized = spec.normalize()

    assert len(normalized.packages) == 2
    assert len(normalized.extras) == 2


def test_envspec_to_dict():
    """Test converting spec to dict."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests"],
        extras=["dev"],
        flags={"opt": "val"},
        env={"VAR": "value"},
    )

    data = spec.to_dict()

    assert data["python"] == "3.12"
    assert "packages" in data
    assert "extras" in data
    assert "flags" in data
    assert "env" in data


def test_envspec_to_yaml_dict():
    """Test converting spec to YAML-compatible dict."""
    spec = EnvSpec(python="3.12", packages=["requests"])

    data = spec.to_yaml_dict()

    assert data["python"] == "3.12"
    assert "packages" in data


def test_envspec_str():
    """Test string representation."""
    spec = EnvSpec(python="3.12", packages=["requests==2.32.3", "numpy"])

    spec_str = str(spec)

    assert "py=3.12" in spec_str
    assert "pkgs:" in spec_str


def test_envspec_complex():
    """Test complex spec with all fields."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests==2.32.3", "numpy>=1.24.0"],
        extras=["dev", "test"],
        flags={"opt1": "val1", "opt2": "val2"},
        scripts={
            "post_install": ["echo hello"],
            "pre_test": ["pytest --version"],
        },
        env={"DEBUG": "true", "LOG_LEVEL": "info"},
    )

    assert spec.python == "3.12"
    assert len(spec.packages) == 2
    assert len(spec.extras) == 2
    assert len(spec.flags) == 2
    assert len(spec.scripts) == 2
    assert len(spec.env) == 2

    # Test normalization preserves all fields
    normalized = spec.normalize()
    assert len(normalized.packages) == 2
    assert len(normalized.extras) == 2
    assert len(normalized.flags) == 2
