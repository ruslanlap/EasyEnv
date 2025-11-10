# EasyEnv CLI - Quick Start Guide

## First Time Setup

### 1. Check Your System

```bash
easyenv-cli doctor
```

This will show:
- ✓ Available Python versions
- ✓ UV installation status
- ✓ Cache directory

### 2. Install Python (if needed)

If `doctor` shows no Python versions available:

```bash
# Install Python 3.11 using uv (recommended)
uv python install 3.11

# Or Python 3.12
uv python install 3.12

# Verify installation
easyenv-cli doctor
```

## Basic Usage

### Run a Simple Command

```bash
# Use Python 3.11 (if available)
easyenv-cli run "py=3.11 pkgs:requests" -- python -c "import requests; print('✓ Works!')"
```

### Install Multiple Packages

```bash
easyenv-cli run "py=3.11 pkgs:requests,numpy,pandas" -- python script.py
```

### Run a Script

```bash
# Create a test script
echo "import requests; print(f'Requests version: {requests.__version__}')" > test.py

# Run it in isolated environment
easyenv-cli run "py=3.11 pkgs:requests==2.32.3" -- python test.py
```

## Common Commands

### Prepare Environment (without running)

```bash
easyenv-cli prepare "py=3.11 pkgs:pytest,coverage"
```

### List Cached Environments

```bash
easyenv-cli list
```

### Check Disk Usage

```bash
easyenv-cli du
```

### Clean Old Environments

```bash
# Dry run (see what would be deleted)
easyenv-cli purge --older-than 30d --dry-run

# Actually delete
easyenv-cli purge --older-than 30d
```

## Troubleshooting

### "Python X.XX not found"

**Solution**: Install the required Python version:
```bash
uv python install 3.11
```

### "UV not found"

**Solution**: Install UV:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "No cached environments"

This is normal for first-time use. Create one:
```bash
easyenv-cli prepare "py=3.11 pkgs:requests"
```

## Examples

### Data Science

```bash
easyenv-cli run "py=3.11 pkgs:numpy,pandas,matplotlib" -- python analysis.py
```

### Web Development

```bash
easyenv-cli run "py=3.11 pkgs:flask,requests" -- python app.py
```

### Testing

```bash
easyenv-cli run "py=3.11 pkgs:pytest,pytest-cov" -- pytest tests/
```

## Need More Help?

- Full documentation: `README.md`
- Check setup: `easyenv-cli doctor`
- Command help: `easyenv-cli COMMAND --help`
- Browse cache: `easyenv-cli tui`

## Quick Reference

| Command | Description |
|---------|-------------|
| `doctor` | Check system setup |
| `run` | Run command in environment |
| `prepare` | Pre-build environment |
| `list` | Show cached environments |
| `du` | Show disk usage |
| `purge` | Clean old environments |
| `template` | Manage templates |
| `tui` | Launch interactive browser |
