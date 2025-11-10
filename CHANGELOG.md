# Changelog

All notable changes to EasyEnv will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed
- N/A

### Removed
- N/A

## [0.1.0] - YYYY-MM-DD (Unreleased)

### Added
- Initial release of EasyEnv
- Core commands: run, prepare, list, du, purge
- Template management
- Lock file support
- Doctor diagnostics
- TUI interface

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
