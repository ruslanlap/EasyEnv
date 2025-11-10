# Changelog

All notable changes to EasyEnv will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2024-11-10

### Added
- **Welcome screen** shown on first run with quick start guide
- `welcome` command to show welcome screen anytime
- **`python` command** to manage Python versions (install, list, uninstall)
- QUICKSTART.md guide for new users
- Improved error messages with actionable instructions
- Better help text with examples for all commands
- Auto-help when running CLI without arguments
- Python 3.13 detection in doctor command

### Fixed
- Friendly error message when Python version not found
- Detailed installation instructions in error messages
- Doctor command now shows quick start guide when no Python available
- Doctor now properly detects if Python is usable by uv (not just installed)
- Better error messages explaining when system Python needs uv installation

### Changed
- Enhanced `doctor` command with better formatting and instructions
- Improved `run` and `prepare` commands with usage examples
- Better UX for first-time users

## [0.1.1] - 2024-11-10

### Fixed
- CI workflow: updated all commands from `easyenv` to `easyenv-cli`
- Documentation updated with correct package name

## [0.1.0] - 2024-11-10

### Added
- Complete CLI implementation with all core commands
- DSL and YAML spec parsing
- Hash-based caching with LRU eviction
- UV integration for fast environment creation
- Lock file export/import for reproducibility
- SBOM generation for all environments
- Template system for frequently-used environments
- Optional Textual-based TUI for cache browsing
- Comprehensive test suite with pytest
- Full documentation (README + Advanced guide)
- GitHub Actions CI workflow

### Fixed
- SBOM generation now works with UV-created virtual environments
- Exit code handling in CLI run command

---

## Release Template

When preparing a release, copy this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Fixed
- Bug fixes

### Changed
- Changes to existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Security
- Security fixes
```

[Unreleased]: https://github.com/ruslanlap/EasyEnv/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ruslanlap/EasyEnv/releases/tag/v0.1.0
