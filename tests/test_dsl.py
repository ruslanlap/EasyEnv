"""Tests for DSL parsing."""

from pathlib import Path

import pytest

from easyenv.dsl import SpecParseError, export_yaml, parse_dsl, parse_spec, parse_yaml
from easyenv.spec import EnvSpec


def test_parse_dsl_basic():
    """Test basic DSL parsing."""
    spec = parse_dsl("py=3.12 pkgs:requests==2.32.3")
    assert spec.python == "3.12"
    assert "requests==2.32.3" in spec.packages


def test_parse_dsl_multiple_packages():
    """Test DSL with multiple packages."""
    spec = parse_dsl("py=3.11 pkgs:requests==2.32.3,numpy>=1.24.0,pandas~=2.0")
    assert spec.python == "3.11"
    assert len(spec.packages) == 3
    assert "requests==2.32.3" in spec.packages
    assert "numpy>=1.24.0" in spec.packages
    assert "pandas~=2.0" in spec.packages


def test_parse_dsl_with_extras():
    """Test DSL with extras."""
    spec = parse_dsl("py=3.12 pkgs:requests extras:dev,test")
    assert spec.python == "3.12"
    assert "dev" in spec.extras
    assert "test" in spec.extras


def test_parse_dsl_with_flags():
    """Test DSL with flags."""
    spec = parse_dsl("py=3.12 pkgs:requests flags:opt1=val1,opt2=val2")
    assert spec.flags["opt1"] == "val1"
    assert spec.flags["opt2"] == "val2"


def test_parse_dsl_order_insensitive():
    """Test that DSL parsing is order-insensitive."""
    spec1 = parse_dsl("py=3.12 pkgs:requests extras:dev")
    spec2 = parse_dsl("extras:dev pkgs:requests py=3.12")

    assert spec1.python == spec2.python
    assert set(spec1.packages) == set(spec2.packages)
    assert set(spec1.extras) == set(spec2.extras)


def test_parse_dsl_missing_python():
    """Test that DSL without python version fails."""
    with pytest.raises(SpecParseError, match=r"Python version.*required"):
        parse_dsl("pkgs:requests")


def test_parse_dsl_empty():
    """Test that empty DSL fails."""
    with pytest.raises(SpecParseError, match="Empty DSL string"):
        parse_dsl("")


def test_parse_dsl_unknown_component():
    """Test that unknown DSL components fail."""
    with pytest.raises(SpecParseError, match="Unknown DSL component"):
        parse_dsl("py=3.12 unknown:value")


def test_parse_yaml_basic(tmp_path):
    """Test basic YAML parsing."""
    yaml_content = """
python: "3.12"
packages:
  - "requests==2.32.3"
  - "numpy>=1.24.0"
"""
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(yaml_content)

    spec = parse_yaml(yaml_file)
    assert spec.python == "3.12"
    assert len(spec.packages) == 2


def test_parse_yaml_with_scripts(tmp_path):
    """Test YAML with scripts."""
    yaml_content = """
python: "3.12"
packages:
  - "requests"
scripts:
  post_install:
    - "python -c 'import requests'"
"""
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(yaml_content)

    spec = parse_yaml(yaml_file)
    assert "post_install" in spec.scripts
    assert len(spec.scripts["post_install"]) == 1


def test_parse_yaml_with_env(tmp_path):
    """Test YAML with environment variables."""
    yaml_content = """
python: "3.12"
packages:
  - "pandas"
env:
  PANDAS_IGNORE_WARNING: "1"
  DEBUG: "true"
"""
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(yaml_content)

    spec = parse_yaml(yaml_file)
    assert spec.env["PANDAS_IGNORE_WARNING"] == "1"
    assert spec.env["DEBUG"] == "true"


def test_parse_yaml_missing_python(tmp_path):
    """Test YAML without python version fails."""
    yaml_content = """
packages:
  - "requests"
"""
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(yaml_content)

    with pytest.raises(SpecParseError, match=r"Python version.*required"):
        parse_yaml(yaml_file)


def test_parse_yaml_not_found():
    """Test that missing YAML file fails."""
    with pytest.raises(SpecParseError, match="not found"):
        parse_yaml(Path("/nonexistent/file.yaml"))


def test_parse_spec_dsl():
    """Test parse_spec with DSL string."""
    spec = parse_spec("py=3.12 pkgs:requests")
    assert spec.python == "3.12"


def test_parse_spec_yaml(tmp_path):
    """Test parse_spec with YAML file."""
    yaml_content = """
python: "3.12"
packages:
  - "requests"
"""
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(yaml_content)

    spec = parse_spec(str(yaml_file))
    assert spec.python == "3.12"


def test_export_yaml(tmp_path):
    """Test exporting spec to YAML."""
    spec = EnvSpec(
        python="3.12",
        packages=["requests==2.32.3", "numpy>=1.24.0"],
        extras=["dev"],
        env={"DEBUG": "true"},
    )

    output_file = tmp_path / "output.yaml"
    export_yaml(spec, output_file)

    assert output_file.exists()

    # Re-parse to verify
    loaded_spec = parse_yaml(output_file)
    assert loaded_spec.python == "3.12"
    assert len(loaded_spec.packages) == 2


def test_spec_normalization():
    """Test that spec normalization is stable."""
    spec1 = parse_dsl("py=3.12 pkgs:numpy,requests extras:test,dev")
    spec2 = parse_dsl("py=3.12 pkgs:requests,numpy extras:dev,test")

    norm1 = spec1.normalize()
    norm2 = spec2.normalize()

    assert norm1.packages == norm2.packages
    assert norm1.extras == norm2.extras
