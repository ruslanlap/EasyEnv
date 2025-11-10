"""Process runner for executing commands in environments."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from easyenv.spec import EnvSpec


class RunnerError(Exception):
    """Error during command execution."""


class EnvRunner:
    """Executes commands inside prepared environments."""

    def __init__(self, env_path: Path, spec: EnvSpec) -> None:
        """Initialize runner.

        Args:
            env_path: Path to environment
            spec: Environment specification
        """
        self.env_path = env_path
        self.spec = spec
        self.python_bin = env_path / "bin" / "python"
        self.bin_dir = env_path / "bin"

    def prepare_environment_vars(
        self, additional_env: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Prepare environment variables for execution.

        Args:
            additional_env: Additional environment variables

        Returns:
            Complete environment dictionary
        """
        env = os.environ.copy()

        # Set VIRTUAL_ENV
        env["VIRTUAL_ENV"] = str(self.env_path)

        # Prepend bin directory to PATH
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        # Remove PYTHONHOME if set (can interfere with venv)
        env.pop("PYTHONHOME", None)

        # Set reproducibility vars
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        # Apply spec env vars
        env.update(self.spec.env)

        # Apply additional env vars
        if additional_env:
            env.update(additional_env)

        return env

    def run(
        self,
        command: list[str],
        cwd: Path | None = None,
        additional_env: dict[str, str] | None = None,
        timeout: int | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run command in environment.

        Args:
            command: Command and arguments to execute
            cwd: Working directory (defaults to current dir)
            additional_env: Additional environment variables
            timeout: Timeout in seconds
            check: Raise exception on non-zero exit

        Returns:
            CompletedProcess result

        Raises:
            RunnerError: If command execution fails
        """
        if not command:
            raise RunnerError("Empty command")

        env = self.prepare_environment_vars(additional_env)

        if cwd is None:
            cwd = Path.cwd()

        try:
            result = subprocess.run(
                command,
                env=env,
                cwd=str(cwd),
                check=check,
                timeout=timeout,
                text=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise RunnerError(
                f"Command failed with exit code {e.returncode}: {' '.join(command)}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RunnerError(f"Command timed out: {' '.join(command)}") from e
        except FileNotFoundError as e:
            raise RunnerError(f"Command not found: {command[0]}") from e

    def run_interactive(
        self,
        command: list[str],
        cwd: Path | None = None,
        additional_env: dict[str, str] | None = None,
    ) -> int:
        """Run command interactively (inherit stdio).

        Args:
            command: Command and arguments to execute
            cwd: Working directory (defaults to current dir)
            additional_env: Additional environment variables

        Returns:
            Exit code

        Raises:
            RunnerError: If command execution fails
        """
        if not command:
            raise RunnerError("Empty command")

        env = self.prepare_environment_vars(additional_env)

        if cwd is None:
            cwd = Path.cwd()

        try:
            # Use subprocess.call for interactive mode
            exit_code = subprocess.call(
                command,
                env=env,
                cwd=str(cwd),
            )
            return exit_code
        except FileNotFoundError as e:
            raise RunnerError(f"Command not found: {command[0]}") from e
        except KeyboardInterrupt:
            return 130  # Standard exit code for SIGINT

    def run_python(
        self,
        script: str,
        args: list[str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run Python script in environment.

        Args:
            script: Python code or script path
            args: Additional arguments
            cwd: Working directory

        Returns:
            CompletedProcess result

        Raises:
            RunnerError: If execution fails
        """
        cmd = [str(self.python_bin), "-c", script]
        if args:
            cmd.extend(args)

        return self.run(cmd, cwd=cwd)

    def run_module(
        self,
        module: str,
        args: list[str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run Python module in environment.

        Args:
            module: Module name (e.g., "pytest")
            args: Module arguments
            cwd: Working directory

        Returns:
            CompletedProcess result

        Raises:
            RunnerError: If execution fails
        """
        cmd = [str(self.python_bin), "-m", module]
        if args:
            cmd.extend(args)

        return self.run(cmd, cwd=cwd)

    def check_command_available(self, command: str) -> bool:
        """Check if command is available in environment.

        Args:
            command: Command name to check

        Returns:
            True if command is available
        """
        cmd_path = self.bin_dir / command
        if cmd_path.exists() and cmd_path.is_file():
            return True

        # Check in PATH
        env = self.prepare_environment_vars()
        try:
            subprocess.run(
                ["which", command],
                env=env,
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_installed_packages(self) -> list[str]:
        """Get list of installed packages.

        Returns:
            List of package names and versions

        Raises:
            RunnerError: If listing fails
        """
        # Try UV pip freeze first (works with UV environments)
        try:
            result = subprocess.run(
                ["uv", "pip", "freeze", "--python", str(self.python_bin)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to standard pip list
            try:
                result = subprocess.run(
                    [str(self.python_bin), "-m", "pip", "list", "--format=freeze"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            except subprocess.CalledProcessError as e:
                raise RunnerError(f"Failed to list packages: {e.stderr}") from e
            except subprocess.TimeoutExpired as e:
                raise RunnerError("Package listing timed out") from e
