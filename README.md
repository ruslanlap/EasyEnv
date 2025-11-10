# EasyEnv

**Ephemeral, reproducible, cached development environments**

EasyEnv is a CLI/TUI tool for creating "one-off" but reproducible and cached development environments. One command → ready env → run user command → keep system clean.

## Features

- 🚀 **Instant ephemeral environments** - Create isolated Python environments on-demand
- 🔒 **Reproducible builds** - Lock files ensure byte-for-byte reproducibility
- 💾 **Smart caching** - Reuse environments automatically with hash-based deduplication
- 🧹 **Zero global pollution** - Everything isolated in `~/.easyenv/cache`
- 📦 **Powered by uv** - Lightning-fast package installation
- 🎯 **Simple DSL** - Human-readable specs: `py=3.12 pkgs:requests==2.32.3`
- 📊 **SBOM generation** - Automatic software bill of materials
- 🖥️ **Optional TUI** - Browse and manage cached environments

## Installation

```bash
# Install uv first (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install EasyEnv
pip install easyenv
# or
pipx install easyenv
```

## Quick Start

### Run command in ephemeral environment

```bash
# Basic usage
easyenv run "py=3.12 pkgs:requests==2.32.3" -- python -c "import requests; print('✓')"

# Multiple packages
easyenv run "py=3.11 pkgs:requests,numpy,pandas" -- python script.py

# With version constraints
easyenv run "py=3.12 pkgs:requests==2.32.3,pendulum~=3.0" -- python app.py
```

### Prepare environment without running

```bash
# Pre-build for later use
easyenv prepare "py=3.12 pkgs:ruff==0.7.2"
```

### Using YAML specs

Create `env.yaml`:

```yaml
python: "3.12"
packages:
  - "requests==2.32.3"
  - "pendulum~=3.0"
  - "numpy>=1.24.0"
scripts:
  post_install:
    - "python -c 'import requests; print(requests.__version__)'"
env:
  PANDAS_IGNORE_WARNING: "1"
  DEBUG: "true"
```

Run it:

```bash
easyenv run env.yaml -- python my_script.py
```

### Templates

```bash
# Save frequently-used specs as templates
easyenv template add datasci "py=3.12 pkgs:numpy,pandas,matplotlib"
easyenv template add testing "py=3.11 pkgs:pytest,coverage,ruff"

# Use templates
easyenv use datasci -- jupyter lab
easyenv use testing -- pytest tests/

# List templates
easyenv template list
```

### Cache management

```bash
# List cached environments
easyenv list

# Show disk usage
easyenv du

# Purge old environments
easyenv purge --older-than 30d --dry-run
easyenv purge --max-size 8GB

# Remove specific age
easyenv purge --older-than 7d
```

### Lock files for reproducibility

```bash
# Export lock file
easyenv run "py=3.12 pkgs:requests" -- python -c "print('ok')"
easyenv lock export abc123def456 -o production.lock.json

# Import lock file (reproduces exact environment)
easyenv lock import production.lock.json
```

### Diagnostics

```bash
# Check setup
easyenv doctor
```

### TUI (Terminal UI)

```bash
# Launch interactive cache browser
easyenv tui
```

## DSL Syntax

The EasyEnv DSL is a simple, space-separated format:

```
py=<version> pkgs:<pkg1>,<pkg2> extras:<label1>,<label2> flags:<k=v>
```

### Components

- **`py=<version>`** (required) - Python version (e.g., `3.12`, `3.11`)
- **`pkgs:<packages>`** - Comma-separated package specs with version constraints
  - `requests==2.32.3` - Exact version
  - `numpy>=1.24.0` - Minimum version
  - `pandas~=2.0` - Compatible version
- **`extras:<labels>`** - Custom labels for grouping
- **`flags:<k=v>`** - Key-value flags for future extensions

### Examples

```bash
# Simple
py=3.12 pkgs:requests

# Multiple packages with versions
py=3.11 pkgs:requests==2.32.3,numpy>=1.24.0,pandas~=2.0

# With extras
py=3.12 pkgs:pytest,coverage extras:testing,ci

# Order doesn't matter
extras:dev pkgs:ruff py=3.12
```

## YAML Format

For complex environments, use YAML:

```yaml
python: "3.12"

packages:
  - "requests==2.32.3"
  - "numpy>=1.24.0"
  - "pandas~=2.0"

extras:
  - "dev"
  - "testing"

scripts:
  post_install:
    - "python -c 'import requests; print(requests.__version__)'"
    - "pytest --version"

env:
  DEBUG: "true"
  LOG_LEVEL: "info"
  CUSTOM_VAR: "value"

flags:
  optimize: "true"
```

## How It Works

1. **Parse spec** - DSL or YAML → normalized specification
2. **Compute hash** - Stable hash from spec + platform + Python/UV versions
3. **Check cache** - Reuse if environment exists, otherwise create
4. **Create environment** - Use `uv` to create venv and install packages
5. **Run command** - Execute with PATH pointing to environment
6. **Keep clean** - No global modifications, all isolated in cache

### Cache Structure

```
~/.easyenv/cache/
├── index.db           # SQLite index
├── abc123def456/      # Environment (hash-based)
│   ├── bin/          # Virtual environment
│   ├── meta.json     # Metadata
│   ├── bom.json      # SBOM
│   └── spec.yaml     # Original spec
└── xyz789ghi012/
    └── ...
```

## CI Integration

### GitHub Actions Example

```yaml
name: Test with EasyEnv
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install EasyEnv
        run: pipx install easyenv

      - name: Run tests
        run: |
          easyenv run "py=3.12 pkgs:pytest,coverage" -- pytest -v

      - name: Lint
        run: |
          easyenv run "py=3.12 pkgs:ruff" -- ruff check .
```

## Configuration

EasyEnv can be configured via `~/.config/easyenv/config.toml`:

```toml
# Custom cache directory
cache_dir = "/custom/path/to/cache"

# Default Python version
default_python = "3.12"

# Purge policies
purge_older_than_days = 30
purge_max_size_gb = 10.0

# Defaults
verbose = false
offline = false

# Templates
[templates]
datasci = "py=3.12 pkgs:numpy,pandas,matplotlib"
webdev = "py=3.11 pkgs:flask,requests"
```

## Advanced Usage

### Offline mode

```bash
# Prepare environments first
easyenv prepare "py=3.12 pkgs:requests" --offline

# Use offline (no network access)
easyenv run "py=3.12 pkgs:requests" --offline -- python script.py
```

### Custom index URLs

```bash
# Use private PyPI mirror
export UV_INDEX_URL="https://pypi.company.com/simple"
easyenv run "py=3.12 pkgs:internal-package" -- python script.py
```

### Verbose output

```bash
# See what's happening
easyenv run "py=3.12 pkgs:requests" -v -- python script.py
```

## Comparison

| Tool | Ephemeral | Cached | Reproducible | Speed | Global Install |
|------|-----------|--------|--------------|-------|----------------|
| **EasyEnv** | ✅ | ✅ | ✅ | ⚡ | ❌ |
| venv | ❌ | ❌ | ⚠️ | 🐌 | ❌ |
| Docker | ✅ | ✅ | ✅ | 🐌 | ⚠️ |
| nix | ✅ | ✅ | ✅ | ⚡ | ⚠️ |

## Roadmap

- [ ] Node/Bun runtime support
- [ ] Template registry (git-based)
- [ ] GitHub Actions cache integration
- [ ] Web-based cache browser
- [ ] Docker backend (optional)
- [ ] PowerToys Run / Flow Launcher integration

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (for environment creation)
- Linux, macOS, or Windows (WSL)

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/easyenv
cd easyenv

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/easyenv

# Linting
ruff check .
```

## Releases

See [CHANGELOG.md](CHANGELOG.md) for release history.

For maintainers: See [docs/RELEASE.md](docs/RELEASE.md) for release instructions.

### Installation from PyPI

```bash
# Stable release
pip install easyenv

# Specific version
pip install easyenv==0.1.0

# From source
pip install git+https://github.com/ruslanlap/EasyEnv.git
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please open an issue or PR.

## Credits

Built with:
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Textual](https://textual.textualize.io/) - TUI framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

**EasyEnv** - *One command, ready environment, clean system.* 🚀
