# Changelog

All notable changes to LineageHub are documented here.

## Unreleased

- No unreleased changes.

## 0.5.0 — Local Demo UI and Repository Polish

### Added

- Optional Streamlit local demo UI
- Dataset and job catalog views in the UI
- Dataset detail and job detail views
- Lineage graph visualization support
- Incident ranking view
- Metadata validation view
- Export preview/download controls
- GitHub Actions CI workflow
- Demo walkthrough documentation

### Changed

- README now describes shipped behavior rather than future Phase 4/5 work.
- Repository cleanup improved presentation quality.
- Documentation now links to local demo and portfolio workflows.

### Notes

- LineageHub remains local-first and standalone.
- No external integrations, authentication, or production deployment layer are included in this release.

## 0.4.0 — Catalog and Metadata Quality

### Added

- Dataset and job catalog commands (`datasets list` / `show`, `jobs list` / `show`)
- Optional dataset catalog metadata fields (owner, description, tags, criticality, system)
- Metadata validation (`validate`, `doctor`) and directed cycle detection (`graph cycles`)
- JSON export commands (`export lineage`, `export incidents`, including ranked incidents)
- Criticality-weighted blast-radius scoring for incident summarize and rank
- Read-only API routes for catalog, validation, graph cycles, and export snapshots

### Changed

- Incident scoring uses criticality-weighted blast radius (not affected-count alone)
- JSON output helpers centralized to keep CLI and API payloads aligned

### Notes

- LineageHub remains local-first and standalone; no external system connectors in this release.
