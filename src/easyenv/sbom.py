"""Software Bill of Materials (SBOM) generation."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class SBOMError(Exception):
    """Error during SBOM generation."""


class SBOM:
    """Software Bill of Materials for an environment."""

    def __init__(
        self,
        packages: list[dict[str, Any]],
        python_version: str,
        created_at: str | None = None,
    ) -> None:
        """Initialize SBOM.

        Args:
            packages: List of package dictionaries
            python_version: Python version string
            created_at: ISO timestamp (defaults to now)
        """
        self.packages = packages
        self.python_version = python_version
        self.created_at = created_at or datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation
        """
        return {
            "bomFormat": "EasyEnvBOM",
            "specVersion": "1.0",
            "version": 1,
            "metadata": {
                "timestamp": self.created_at,
                "tools": [{"name": "EasyEnv", "version": "0.1.0"}],
            },
            "components": [
                {
                    "type": "library",
                    "name": "python",
                    "version": self.python_version,
                }
            ]
            + self.packages,
        }

    def export(self, path: Path) -> None:
        """Export SBOM to JSON file.

        Args:
            path: Path to write SBOM
        """
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> SBOM:
        """Load SBOM from JSON file.

        Args:
            path: Path to SBOM file

        Returns:
            SBOM instance

        Raises:
            SBOMError: If loading fails
        """
        if not path.exists():
            raise SBOMError(f"SBOM file not found: {path}")

        try:
            with open(path) as f:
                data = json.load(f)

            components = data.get("components", [])
            python_component = next((c for c in components if c.get("name") == "python"), None)
            python_version = (
                python_component.get("version", "unknown") if python_component else "unknown"
            )

            packages = [c for c in components if c.get("name") != "python"]

            return cls(
                packages=packages,
                python_version=python_version,
                created_at=data.get("metadata", {}).get("timestamp"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise SBOMError(f"Invalid SBOM format: {e}") from e


class SBOMGenerator:
    """Generates SBOM from environments."""

    @staticmethod
    def parse_package_line(line: str) -> dict[str, Any] | None:
        """Parse package line from pip freeze format.

        Args:
            line: Package line (e.g., "requests==2.32.3")

        Returns:
            Package dictionary or None if invalid
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        # Handle different formats
        if "==" in line:
            name, version = line.split("==", 1)
            return {
                "type": "library",
                "name": name.strip(),
                "version": version.strip(),
            }
        if "@" in line and "git+" in line:
            # VCS package
            parts = line.split("@", 1)
            name = parts[0].strip()
            return {
                "type": "library",
                "name": name,
                "version": "vcs",
                "source": line,
            }
        # Unknown format, best effort
        return {
            "type": "library",
            "name": line,
            "version": "unknown",
        }

    @staticmethod
    def generate_from_env(env_path: Path) -> SBOM:
        """Generate SBOM from environment.

        Args:
            env_path: Path to environment

        Returns:
            SBOM instance

        Raises:
            SBOMError: If generation fails
        """
        python_bin = env_path / "bin" / "python"

        # Get Python version
        try:
            result = subprocess.run(
                [str(python_bin), "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            python_version = result.stdout.strip().replace("Python ", "")
        except Exception as e:
            raise SBOMError(f"Failed to get Python version: {e}") from e

        # Get installed packages using UV pip freeze (works with UV-created venvs)
        try:
            # Try UV pip freeze first (works with UV environments)
            result = subprocess.run(
                ["uv", "pip", "freeze", "--python", str(python_bin)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            package_lines = result.stdout.splitlines()
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to standard pip list if UV is not available
            try:
                result = subprocess.run(
                    [str(python_bin), "-m", "pip", "list", "--format=freeze"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                package_lines = result.stdout.splitlines()
            except Exception as e:
                raise SBOMError(f"Failed to list packages: {e}") from e

        # Parse packages
        packages = []
        for line in package_lines:
            pkg = SBOMGenerator.parse_package_line(line)
            if pkg:
                packages.append(pkg)

        return SBOM(packages=packages, python_version=python_version)

    @staticmethod
    def generate_and_save(env_path: Path, output_path: Path) -> None:
        """Generate SBOM and save to file.

        Args:
            env_path: Path to environment
            output_path: Path to write SBOM

        Raises:
            SBOMError: If generation fails
        """
        sbom = SBOMGenerator.generate_from_env(env_path)
        sbom.export(output_path)
