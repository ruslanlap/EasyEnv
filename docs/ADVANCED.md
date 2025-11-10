# EasyEnv Advanced Documentation

## Table of Contents

1. [Architecture](#architecture)
2. [Cache Management](#cache-management)
3. [Reproducibility](#reproducibility)
4. [Security Considerations](#security-considerations)
5. [Offline Mode](#offline-mode)
6. [Custom Package Indexes](#custom-package-indexes)
7. [Environment Variables](#environment-variables)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)
10. [Integration Patterns](#integration-patterns)

## Architecture

### Components

```
┌─────────────┐
│     CLI     │  Typer-based command interface
└──────┬──────┘
       │
┌──────▼──────┐
│  DSL Parser │  Parse specs (DSL/YAML)
└──────┬──────┘
       │
┌──────▼──────┐
│   Cache     │  Hash computation, metadata, LRU
│  Manager    │
└──────┬──────┘
       │
┌──────▼──────┐
│     UV      │  venv creation, package install
│ Integration │
└──────┬──────┘
       │
┌──────▼──────┐
│   Runner    │  Process execution in env
└─────────────┘
```

### Hash Computation

Hash includes:
- Normalized spec (sorted packages, extras, flags)
- Platform (linux, darwin, win32)
- Python version (major.minor)
- UV version

This ensures:
- Same spec → same hash (reproducible)
- Cross-platform isolation
- Version compatibility

### Cache Layout

```
~/.easyenv/cache/
├── index.db              # SQLite index
│   └── environments      # Table: hash, spec, metadata
├── abc123def456/         # Environment directory
│   ├── bin/             # Virtual environment binaries
│   ├── lib/             # Python packages
│   ├── meta.json        # Cache metadata
│   ├── bom.json         # Software Bill of Materials
│   └── spec.yaml        # Original specification
└── xyz789ghi012/
    └── ...
```

## Cache Management

### LRU Eviction

EasyEnv uses Least Recently Used (LRU) eviction:

1. Environments tracked by `last_used` timestamp
2. Updated on every `run` or `prepare`
3. Purge removes oldest first when over size limit

### Purge Strategies

#### By Age

```bash
# Remove environments not used in 30 days
easyenv purge --older-than 30d

# Weekly cleanup
easyenv purge --older-than 7d --dry-run
easyenv purge --older-than 7d
```

#### By Size

```bash
# Keep total cache under 8GB
easyenv purge --max-size 8GB

# Aggressive cleanup (2GB limit)
easyenv purge --max-size 2GB
```

#### Combined

```bash
# Remove old AND keep under size limit
easyenv purge --older-than 30d --max-size 10GB
```

### Automated Cleanup

Add to crontab:

```cron
# Daily cleanup: remove >30 days, keep under 8GB
0 2 * * * easyenv purge --older-than 30d --max-size 8GB
```

Or systemd timer:

```ini
# ~/.config/systemd/user/easyenv-purge.timer
[Unit]
Description=EasyEnv cache purge

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/easyenv-purge.service
[Unit]
Description=EasyEnv cache purge

[Service]
Type=oneshot
ExecStart=/usr/local/bin/easyenv purge --older-than 30d --max-size 8GB
```

Enable:

```bash
systemctl --user enable --now easyenv-purge.timer
```

## Reproducibility

### Lock Files

Lock files capture:
- Original spec
- **Resolved packages** (with exact versions and hashes)
- Python version (full)
- UV version
- Platform
- Timestamp

#### Export

```bash
# After creating environment
easyenv run "py=3.12 pkgs:requests" -- python -c "print('ok')"

# Find hash
easyenv list  # Get hash (e.g., abc123def456)

# Export
easyenv lock export abc123def456 -o production.lock.json
```

Or from spec:

```bash
easyenv lock export "py=3.12 pkgs:requests" -o dev.lock.json
```

#### Import

```bash
# Reproduces exact environment
easyenv lock import production.lock.json

# Use imported environment
easyenv lock import dev.lock.json
# ... then run commands
```

### Reproducibility Guarantees

**Same platform + same lock → identical environment**

Lock files ensure:
- ✅ Exact package versions
- ✅ Exact dependency resolution
- ✅ Same Python version
- ✅ Same UV version
- ⚠️ Platform-specific (Linux lock ≠ macOS lock)

### Cross-Platform

For cross-platform reproducibility:

1. Generate locks per platform
2. Use platform-specific locks
3. Or use Docker backend (future)

Example CI matrix:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    steps:
      - run: easyenv lock import ${{ matrix.os }}.lock.json
```

## Security Considerations

### Package Sources

By default, EasyEnv uses PyPI via UV. For security:

#### Use private indexes

```bash
export UV_INDEX_URL="https://pypi.company.com/simple"
easyenv run "py=3.12 pkgs:internal-pkg" -- python app.py
```

#### Domain allowlisting

```bash
# Only allow company domains
export UV_INDEX_URL="https://pypi.company.com/simple"
export UV_NO_INDEX=1  # Disable public PyPI
```

### Offline Mode

Prevent network access after preparation:

```bash
# Build environment online
easyenv prepare "py=3.12 pkgs:requests"

# Run offline (no network, uses cache)
easyenv run "py=3.12 pkgs:requests" --offline -- python app.py
```

### SBOM Generation

Every environment includes `bom.json`:

```json
{
  "bomFormat": "EasyEnvBOM",
  "specVersion": "1.0",
  "metadata": {
    "timestamp": "2024-01-01T00:00:00",
    "tools": [{"name": "EasyEnv", "version": "0.1.0"}]
  },
  "components": [
    {"type": "library", "name": "python", "version": "3.12.0"},
    {"type": "library", "name": "requests", "version": "2.32.3"},
    {"type": "library", "name": "certifi", "version": "2023.7.22"}
  ]
}
```

Use for:
- Vulnerability scanning
- License compliance
- Dependency auditing

### Environment Isolation

EasyEnv sets:

```bash
PYTHONHASHSEED=0           # Reproducible hashing
PYTHONDONTWRITEBYTECODE=1  # No .pyc files
```

Each environment is isolated:
- No access to global packages
- No modification of system Python
- Clean PATH injection

## Offline Mode

### Preparation

```bash
# Online: prepare all environments
easyenv prepare "py=3.12 pkgs:requests,numpy,pandas"
easyenv prepare "py=3.11 pkgs:pytest,coverage"
```

### Usage

```bash
# Offline: use cached environments
easyenv run "py=3.12 pkgs:requests" --offline -- python script.py
```

### Air-Gapped Systems

1. **Build lock files online**:
   ```bash
   easyenv prepare "py=3.12 pkgs:requests,numpy"
   easyenv lock export <hash> -o offline.lock.json
   ```

2. **Transfer to air-gapped system**:
   - Copy `offline.lock.json`
   - Copy UV cache (if needed)

3. **Import offline**:
   ```bash
   easyenv lock import offline.lock.json --offline
   ```

## Custom Package Indexes

### Private PyPI

```bash
# Set index URL
export UV_INDEX_URL="https://pypi.company.com/simple"
export UV_EXTRA_INDEX_URL="https://pypi.org/simple"  # Fallback

easyenv run "py=3.12 pkgs:internal-package" -- python app.py
```

### Authenticated Indexes

UV supports credentials:

```bash
export UV_INDEX_URL="https://user:token@pypi.company.com/simple"
```

Or use `.netrc`:

```
machine pypi.company.com
login user
password token
```

## Environment Variables

### EasyEnv Variables

- `EASYENV_CACHE_DIR` - Custom cache directory
- `EASYENV_CONFIG` - Custom config file path

### UV Variables

EasyEnv respects UV environment variables:

- `UV_INDEX_URL` - Package index URL
- `UV_EXTRA_INDEX_URL` - Additional index
- `UV_NO_INDEX` - Disable default index
- `UV_PYTHON` - Python executable path
- `UV_CACHE_DIR` - UV cache directory

### Spec-Level Variables

Set in YAML:

```yaml
python: "3.12"
packages:
  - "pandas"
env:
  PANDAS_IGNORE_WARNING: "1"
  CUSTOM_VAR: "value"
```

## Troubleshooting

### UV Not Found

```
Error: UV not found. Install from https://astral.sh/uv
```

**Solution**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart shell
```

### Python Version Not Found

```
Error: Python 3.12 not found
```

**Solution**:

```bash
# Let UV install Python
uv python install 3.12

# Or use system Python
apt install python3.12  # Debian/Ubuntu
brew install python@3.12  # macOS
```

### Cache Corruption

```
Error: Failed to load metadata
```

**Solution**:

```bash
# Remove specific environment
rm -rf ~/.easyenv/cache/<hash>

# Or rebuild index
rm ~/.easyenv/cache/index.db
easyenv list  # Rebuilds index
```

### Disk Space Issues

```
Error: No space left on device
```

**Solution**:

```bash
# Check usage
easyenv du

# Aggressive purge
easyenv purge --max-size 2GB
```

## Performance Tuning

### Parallel Preparation

Prepare multiple environments in parallel:

```bash
easyenv prepare "py=3.12 pkgs:requests" &
easyenv prepare "py=3.11 pkgs:numpy" &
easyenv prepare "py=3.12 pkgs:pandas" &
wait
```

### UV Cache

UV maintains its own cache. Share across machines:

```bash
# Copy UV cache to shared storage
rsync -av ~/.cache/uv/ /mnt/shared/uv-cache/

# Use shared cache
export UV_CACHE_DIR=/mnt/shared/uv-cache
```

### Template Pre-warming

Pre-warm common templates:

```bash
# Create templates
easyenv template add web "py=3.12 pkgs:flask,requests"
easyenv template add data "py=3.12 pkgs:numpy,pandas"

# Pre-build
easyenv prepare "py=3.12 pkgs:flask,requests"
easyenv prepare "py=3.12 pkgs:numpy,pandas"
```

## Integration Patterns

### Pre-commit Hooks

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff
        name: Ruff
        entry: easyenv run "py=3.12 pkgs:ruff" -- ruff check
        language: system
        types: [python]
```

### Makefile

```makefile
.PHONY: test lint format

test:
	easyenv run "py=3.12 pkgs:pytest,coverage" -- pytest

lint:
	easyenv run "py=3.12 pkgs:ruff" -- ruff check .

format:
	easyenv run "py=3.12 pkgs:ruff" -- ruff format .
```

### Task Runners

#### just

```just
test:
  easyenv run "py=3.12 pkgs:pytest" -- pytest

lint:
  easyenv run "py=3.12 pkgs:ruff" -- ruff check .
```

#### Task (go-task)

```yaml
version: '3'
tasks:
  test:
    cmds:
      - easyenv run "py=3.12 pkgs:pytest" -- pytest
  lint:
    cmds:
      - easyenv run "py=3.12 pkgs:ruff" -- ruff check .
```

### CI/CD Patterns

#### Matrix Testing

```yaml
strategy:
  matrix:
    python: [3.11, 3.12]
    packages:
      - "pytest==7.4.0"
      - "pytest==8.0.0"
jobs:
  test:
    steps:
      - run: |
          easyenv run "py=${{ matrix.python }} pkgs:${{ matrix.packages }}" -- pytest
```

#### Cached Dependencies

```yaml
- name: Cache EasyEnv
  uses: actions/cache@v3
  with:
    path: ~/.easyenv/cache
    key: easyenv-${{ hashFiles('requirements.txt') }}
```

---

For more help, see:
- [README](../README.md)
- [GitHub Issues](https://github.com/yourusername/easyenv/issues)
