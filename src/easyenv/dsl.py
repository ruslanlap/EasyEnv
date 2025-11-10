"""DSL and YAML parser for EasyEnv specifications."""

from __future__ import annotations

from pathlib import Path

import yaml

from easyenv.spec import EnvSpec


class SpecParseError(Exception):
    """Error parsing specification."""


def parse_dsl(dsl_string: str) -> EnvSpec:
    """Parse DSL string into EnvSpec.

    DSL format: space-separated key-value pairs
    - py=<version>
    - pkgs:<pkg1>[==|~=]<ver>[,pkg2...]
    - extras:<label>[,label2...]
    - flags:<k=v>[,k=v...]

    Args:
        dsl_string: DSL specification string

    Returns:
        Parsed EnvSpec

    Raises:
        SpecParseError: If parsing fails
    """
    dsl_string = dsl_string.strip()
    if not dsl_string:
        raise SpecParseError("Empty DSL string")

    # Split by spaces (but respect quoted strings if any)
    parts = dsl_string.split()

    python_version: str | None = None
    packages: list[str] = []
    extras: list[str] = []
    flags: dict[str, str] = {}

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Match py=<version>
        if part.startswith("py="):
            python_version = part[3:]
            continue

        # Match pkgs:<pkg-list>
        if part.startswith("pkgs:"):
            pkg_list = part[5:]
            packages.extend(p.strip() for p in pkg_list.split(",") if p.strip())
            continue

        # Match extras:<label-list>
        if part.startswith("extras:"):
            extra_list = part[7:]
            extras.extend(e.strip() for e in extra_list.split(",") if e.strip())
            continue

        # Match flags:<k=v,k=v...>
        if part.startswith("flags:"):
            flag_list = part[6:]
            for flag_item in flag_list.split(","):
                if "=" in flag_item:
                    key, value = flag_item.split("=", 1)
                    flags[key.strip()] = value.strip()
            continue

        # Unknown part
        raise SpecParseError(f"Unknown DSL component: {part}")

    if python_version is None:
        raise SpecParseError("Python version (py=...) is required")

    return EnvSpec(python=python_version, packages=packages, extras=extras, flags=flags)


def parse_yaml(yaml_path: Path) -> EnvSpec:
    """Parse YAML file into EnvSpec.

    YAML format:
        python: "3.12"
        packages:
          - "requests==2.32.3"
          - "pendulum~=3.0"
        scripts:
          post_install:
            - "python -c 'import requests'"
        env:
          SOME_VAR: "value"

    Args:
        yaml_path: Path to YAML file

    Returns:
        Parsed EnvSpec

    Raises:
        SpecParseError: If parsing fails
    """
    if not yaml_path.exists():
        raise SpecParseError(f"YAML file not found: {yaml_path}")

    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SpecParseError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise SpecParseError("YAML must contain a dictionary")

    python_version = data.get("python")
    if not python_version:
        raise SpecParseError("Python version is required in YAML")

    packages = data.get("packages", [])
    if not isinstance(packages, list):
        raise SpecParseError("packages must be a list")

    extras = data.get("extras", [])
    if not isinstance(extras, list):
        extras = []

    flags = data.get("flags", {})
    if not isinstance(flags, dict):
        flags = {}

    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        scripts = {}

    env = data.get("env", {})
    if not isinstance(env, dict):
        env = {}

    return EnvSpec(
        python=str(python_version),
        packages=[str(p) for p in packages],
        extras=[str(e) for e in extras],
        flags={str(k): str(v) for k, v in flags.items()},
        scripts={str(k): [str(s) for s in v] for k, v in scripts.items()},
        env={str(k): str(v) for k, v in env.items()},
    )


def parse_spec(spec_or_path: str) -> EnvSpec:
    """Parse specification from DSL string or YAML file path.

    Args:
        spec_or_path: Either a DSL string or path to YAML file

    Returns:
        Parsed EnvSpec

    Raises:
        SpecParseError: If parsing fails
    """
    # Check if it's a file path
    potential_path = Path(spec_or_path)
    if potential_path.exists() and potential_path.is_file():
        # Assume YAML
        return parse_yaml(potential_path)

    # Try parsing as DSL
    return parse_dsl(spec_or_path)


def export_yaml(spec: EnvSpec, output_path: Path) -> None:
    """Export EnvSpec to YAML file.

    Args:
        spec: Environment specification
        output_path: Path to write YAML file
    """
    with open(output_path, "w") as f:
        yaml.safe_dump(spec.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)
