# Final Verification Checklist

Recorded when closing LineageHub as a portfolio project (target release **v0.5.0**).

## Release

- Target release: **v0.5.0**
- `pyproject.toml` version: **0.5.0**
- `CHANGELOG.md`: includes **0.5.0 — Local Demo UI and Repository Polish**

## Environment

- Python: **3.10+** (CI also runs **3.12**)
- Installation: `pip install -e ".[dev,api,ui]"`

## Automated Tests

| Command | Result |
|---------|--------|
| `pytest` | PASS (174 tests, local Python 3.12) |

## CLI Verification

Commands to run against sample data:

- [ ] `lineagehub load examples/sample_lineage.json`
- [ ] `lineagehub load-runs examples/sample_runs.json`
- [ ] `lineagehub datasets list`
- [ ] `lineagehub datasets show sales_dashboard`
- [ ] `lineagehub jobs list`
- [ ] `lineagehub jobs show clean_orders_job`
- [ ] `lineagehub incidents rank --json`
- [ ] `lineagehub validate`
- [ ] `lineagehub graph cycles`
- [ ] `lineagehub export lineage --format json`
- [ ] `lineagehub export incidents --ranked`

## Streamlit UI Verification

```bash
streamlit run scripts/lineagehub_app.py
```

Manual checks:

- [ ] Dataset catalog renders
- [ ] Dataset detail renders
- [ ] Job detail renders
- [ ] Lineage graph or edge list / DOT fallback renders
- [ ] Incident ranking renders
- [ ] Metadata validation renders
- [ ] Export preview/download works

## GitHub Actions

| Item | Status |
|------|--------|
| Workflow | `.github/workflows/ci.yml` |
| Python versions | 3.10, 3.12 |
| CI on `main` | Confirm green after push (pytest fix included) |

## Notes

Known limitations (intentional for this release):

- UI is local-only; not a hosted product
- No authentication or multi-tenancy
- No external integrations (IngestFlow, SentinelDQ, OpenLineage, etc.)
- No production deployment or HA layer

Screenshots for README **Demo Preview** are optional; capture per [demo_walkthrough.md](demo_walkthrough.md) if desired.
