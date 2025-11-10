"""UV integration for environment creation and management."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from easyenv.spec import EnvSpec


class UVError(Exception):
    """Error during UV operations."""


class UVIntegration:
    """Handles UV venv creation and package installation."""

    @staticmethod
    def check_uv_available() -> tuple[bool, str | None]:
        """Check if UV is available.

        Returns:
            Tuple of (is_available, version_or_error)
        """
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            version = result.stdout.strip()
            return True, version
        except FileNotFoundError:
            return False, "UV not found. Install from https://astral.sh/uv"
        except subprocess.CalledProcessError as e:
            return False, f"UV error: {e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "UV command timed out"

    @staticmethod
    def check_python_available(python_version: str) -> tuple[bool, str | None]:
        """Check if requested Python version is available.

        Args:
            python_version: Python version string (e.g., "3.12")

        Returns:
            Tuple of (is_available, path_or_error)
        """
        # Try to find Python with UV
        try:
            result = subprocess.run(
                ["uv", "python", "find", python_version],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                python_path = result.stdout.strip()
                return True, python_path
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Fallback: try system python
        try:
            result = subprocess.run(
                [f"python{python_version}", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, f"python{python_version}"
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return False, f"Python {python_version} not found"

    @staticmethod
    def create_venv(env_path: Path, python_version: str, verbose: bool = False) -> None:
        """Create virtual environment with UV.

        Args:
            env_path: Path where venv should be created
            python_version: Python version (e.g., "3.12")
            verbose: Enable verbose output

        Raises:
            UVError: If venv creation fails
        """
        env_path.mkdir(parents=True, exist_ok=True)

        # Try to find the best Python path for this version
        python_path = UVIntegration._find_python_path(python_version)
        if python_path:
            cmd = ["uv", "venv", str(env_path), "--python", python_path]
        else:
            cmd = ["uv", "venv", str(env_path), "--python", python_version]

        try:
            result = subprocess.run(
                cmd,
                capture_output=not verbose,
                text=True,
                check=True,
                timeout=120,
            )
            if verbose and result.stdout:
                print(result.stdout)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else "Unknown error"

            # Check if it's a Python not found error
            if "No interpreter found" in stderr or "Python downloads are set to 'never'" in stderr:
                error_msg = (
                    f"Python {python_version} is not available for uv to use.\n\n"
                    f"[Quick Fix]\n"
                    f"Install Python {python_version} using uv (recommended):\n"
                    f"  easyenv-cli python install {python_version}\n"
                    f"  # or directly: uv python install {python_version}\n\n"
                    f"[Alternative]\n"
                    f"If Python {python_version} is already installed on your system but uv can't find it,\n"
                    f"you may need to install it via uv for proper integration.\n\n"
                    f"[Other Options]\n"
                    f"• Use a different Python version: Run 'easyenv-cli doctor' to see what's available\n"
                    f"• Install from system package manager (may require uv installation after):\n"
                    f"  - Ubuntu/Debian: sudo apt install python{python_version}\n"
                    f"  - macOS: brew install python@{python_version}\n\n"
                    f"After installing, try your command again."
                )
                raise UVError(error_msg) from e

            raise UVError(f"Failed to create venv: {stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise UVError("Venv creation timed out") from e

    @staticmethod
    def install_packages(
        env_path: Path,
        packages: list[str],
        verbose: bool = False,
        offline: bool = False,
    ) -> None:
        """Install packages using UV pip.

        Args:
            env_path: Path to venv
            packages: List of package specifications
            verbose: Enable verbose output
            offline: Offline mode (no network)

        Raises:
            UVError: If installation fails
        """
        if not packages:
            return

        # Use uv pip install
        cmd = ["uv", "pip", "install", "--python", str(env_path / "bin" / "python")]

        if offline:
            cmd.append("--offline")

        cmd.extend(packages)

        try:
            result = subprocess.run(
                cmd,
                capture_output=not verbose,
                text=True,
                check=True,
                timeout=600,  # 10 minutes for large packages
            )
            if verbose and result.stdout:
                print(result.stdout)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else "Unknown error"
            raise UVError(f"Failed to install packages: {stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise UVError("Package installation timed out") from e

    @staticmethod
    def freeze_packages(env_path: Path) -> list[str]:
        """Freeze installed packages.

        Args:
            env_path: Path to venv

        Returns:
            List of package specifications

        Raises:
            UVError: If freeze fails
        """
        cmd = ["uv", "pip", "freeze", "--python", str(env_path / "bin" / "python")]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else "Unknown error"
            raise UVError(f"Failed to freeze packages: {stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise UVError("Package freeze timed out") from e

    @staticmethod
    def get_python_version(env_path: Path) -> str:
        """Get Python version from venv.

        Args:
            env_path: Path to venv

        Returns:
            Python version string

        Raises:
            UVError: If version check fails
        """
        python_bin = env_path / "bin" / "python"
        try:
            result = subprocess.run(
                [str(python_bin), "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise UVError(f"Failed to get Python version: {e}") from e

    @staticmethod
    def run_scripts(
        env_path: Path,
        scripts: list[str],
        env_vars: dict[str, str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Run post-install scripts.

        Args:
            env_path: Path to venv
            scripts: List of shell commands to run
            env_vars: Optional environment variables
            verbose: Enable verbose output

        Raises:
            UVError: If script execution fails
        """
        env = os.environ.copy()

        # Add venv to PATH
        env["PATH"] = f"{env_path / 'bin'}:{env.get('PATH', '')}"
        env["VIRTUAL_ENV"] = str(env_path)

        # Add custom env vars
        if env_vars:
            env.update(env_vars)

        for script in scripts:
            try:
                result = subprocess.run(
                    script,
                    shell=True,
                    capture_output=not verbose,
                    text=True,
                    check=True,
                    timeout=300,
                    env=env,
                    cwd=env_path,
                )
                if verbose and result.stdout:
                    print(result.stdout)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr if e.stderr else "Unknown error"
                raise UVError(f"Script failed: {script}\nError: {stderr}") from e
            except subprocess.TimeoutExpired as e:
                raise UVError(f"Script timed out: {script}") from e

    @staticmethod
    def prepare_environment(
        env_path: Path,
        spec: EnvSpec,
        verbose: bool = False,
        offline: bool = False,
    ) -> None:
        """Prepare complete environment from spec.

        Args:
            env_path: Path where environment should be created
            spec: Environment specification
            verbose: Enable verbose output
            offline: Offline mode

        Raises:
            UVError: If environment preparation fails
        """
        # Create venv
        UVIntegration.create_venv(env_path, spec.python, verbose=verbose)

        # Install packages
        if spec.packages:
            UVIntegration.install_packages(
                env_path, spec.packages, verbose=verbose, offline=offline
            )

        # Run post-install scripts
        if "post_install" in spec.scripts:
            UVIntegration.run_scripts(
                env_path,
                spec.scripts["post_install"],
                env_vars=spec.env,
                verbose=verbose,
            )

    @staticmethod
    def _verify_python_version(path: str, expected_version: str) -> bool:
        """Verify that Python at path matches expected version."""
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return result.returncode == 0 and expected_version in result.stdout
        except Exception:
            return False

    @staticmethod
    def _find_python_path(python_version: str) -> str | None:
        """Find the best Python path for a given version.

        Args:
            python_version: Python version (e.g., "3.12")

        Returns:
            Full path to Python executable or None if not found
        """
        try:
            # Try to get from uv python list
            result = subprocess.run(
                ["uv", "python", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if python_version not in line or "<download available>" in line:
                        continue

                    parts = line.split()
                    if len(parts) >= 2:
                        path = parts[-1]
                        if (
                            path.startswith("/")
                            and "python" in path
                            and UVIntegration._verify_python_version(path, python_version)
                        ):
                            return path

            # Fallback: try common system paths
            for path in [
                f"/usr/bin/python{python_version}",
                f"/usr/local/bin/python{python_version}",
            ]:
                if UVIntegration._verify_python_version(path, python_version):
                    return path

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return None
