# Release Process

This document describes how to release EasyEnv to PyPI.

## Prerequisites

### 1. PyPI Account Setup

1. Create accounts on:
   - **TestPyPI**: https://test.pypi.org/account/register/
   - **PyPI**: https://pypi.org/account/register/

2. Verify your email addresses on both platforms

### 2. Configure Trusted Publishing (Recommended)

Trusted publishing uses OpenID Connect (OIDC) to securely publish without API tokens.

#### On TestPyPI:

1. Go to https://test.pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI Project Name**: `easyenv`
   - **Owner**: `ruslanlap` (your GitHub username)
   - **Repository name**: `EasyEnv`
   - **Workflow name**: `release.yml`
   - **Environment name**: `testpypi`

#### On PyPI:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher with the same settings but:
   - **Environment name**: `pypi`

### 3. Configure GitHub Environments

1. Go to your repository: https://github.com/ruslanlap/EasyEnv/settings/environments
2. Create two environments:
   - **Name**: `testpypi`
   - **Name**: `pypi`
3. (Optional) Add protection rules:
   - Required reviewers
   - Wait timer
   - Deployment branches (only tags matching `v*`)

## Release Workflow

The release happens in 3 stages:

```
Build → TestPyPI → PyPI
```

### Automatic Release (Recommended)

**Triggered by**: Creating a GitHub Release

1. **Update version** in `pyproject.toml`:
   ```toml
   [project]
   name = "easyenv"
   version = "0.1.0"  # ← Update this
   ```

2. **Commit and push**:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.1.0"
   git push
   ```

3. **Create and push tag**:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. **Create GitHub Release**:
   - Go to: https://github.com/ruslanlap/EasyEnv/releases/new
   - Select tag: `v0.1.0`
   - Release title: `v0.1.0`
   - Description: Copy from CHANGELOG or write release notes
   - Click "Publish release"

5. **Monitor workflow**:
   - Watch: https://github.com/ruslanlap/EasyEnv/actions
   - The workflow will:
     1. Build the package
     2. Publish to TestPyPI (verify at https://test.pypi.org/project/easyenv/)
     3. Publish to PyPI (verify at https://pypi.org/project/easyenv/)

### Manual Release

**Triggered by**: Manual workflow dispatch

1. Go to: https://github.com/ruslanlap/EasyEnv/actions/workflows/release.yml
2. Click "Run workflow"
3. Enter version (e.g., `0.1.0`)
4. Click "Run workflow"

## Testing Before Release

### Local Build Test

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build package
python -m build

# Check package
twine check dist/*

# Test installation locally
pip install dist/easyenv-0.1.0-py3-none-any.whl
easyenv --help
```

### TestPyPI Installation Test

After publishing to TestPyPI:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ easyenv

# Test it works
easyenv doctor
easyenv run "py=3.12 pkgs:requests" -- python -c "import requests; print('OK')"
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0): Breaking changes
- **Minor** (0.1.0): New features, backward compatible
- **Patch** (0.1.1): Bug fixes, backward compatible

### Pre-releases

For pre-releases, use:
- Alpha: `0.1.0a1`, `0.1.0a2`
- Beta: `0.1.0b1`, `0.1.0b2`
- Release Candidate: `0.1.0rc1`, `0.1.0rc2`

## Rollback / Yanking a Release

If you need to yank a release (mark it as broken):

1. Go to PyPI project page: https://pypi.org/project/easyenv/
2. Click on the version to yank
3. Click "Options" → "Yank release"
4. Provide a reason

**Note**: Yanked releases can still be installed explicitly but won't be discovered by pip.

## Troubleshooting

### "Project already exists" error

The first time you publish, you need to either:
1. Use trusted publishing (recommended - no manual setup needed)
2. Or create the project manually on PyPI first

### Build fails

Check:
- `pyproject.toml` is valid
- All required fields are filled
- Version number follows PEP 440

### TestPyPI publish succeeds but PyPI fails

Common reasons:
- Version already exists on PyPI
- Package name already taken
- Trusted publishing not configured correctly

## Alternative: Manual Upload

If automated publishing fails, you can upload manually:

```bash
# Build
python -m build

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI (after testing)
twine upload dist/*
```

You'll need API tokens for this approach:
- TestPyPI: https://test.pypi.org/manage/account/token/
- PyPI: https://pypi.org/manage/account/token/

Configure in `~/.pypirc`:

```ini
[testpypi]
username = __token__
password = pypi-...

[pypi]
username = __token__
password = pypi-...
```

## Post-Release Checklist

After a successful release:

- ✅ Verify package on PyPI: https://pypi.org/project/easyenv/
- ✅ Test installation: `pip install easyenv`
- ✅ Update documentation if needed
- ✅ Announce release (Twitter, Discord, etc.)
- ✅ Close milestone if using GitHub milestones

## Resources

- **PyPI Help**: https://pypi.org/help/
- **Trusted Publishing Guide**: https://docs.pypi.org/trusted-publishers/
- **Python Packaging Guide**: https://packaging.python.org/
- **Semantic Versioning**: https://semver.org/
