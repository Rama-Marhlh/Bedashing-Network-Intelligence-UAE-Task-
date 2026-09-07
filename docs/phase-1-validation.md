# Phase 1 validation report

Date: 2026-09-02

## Scope

The baseline covers eight canonical analytical files in `app_data`, nine analysis outputs,
and seven decision outputs. `app_data/app_manifest.json` is intentionally excluded because
Phase 1 upgrades its metadata contract.

The machine-readable baseline is `tests/data_contract/phase1_baseline.json` and is enforced
by `test_legacy_analytical_outputs_are_unchanged`.

## Result

- Frozen analytical and decision files checked: 24
- Files with changed SHA-256 values: 0
- Decision scores or recommendations changed: no
- Legacy pipeline scripts changed or moved: no
- Canonical shortlist changed: no
- Original manifest SHA-256: `6550139dd1f871ef5f5bd365d9d48aa72b72b9b947e73d8f9725b4a5cc4e0049`
- Phase 1 manifest SHA-256: `f17dbcf91b862b2a4a2ece35fcfac00a06c26f0077d216d099f8fbe9f71fa9e1`

The manifest changed because its schema moved from 1.0 to 1.1, the existing top-ten
shortlist was added to the declared file set, and SHA-256 checksums were added.

## Contract validation

- Branches: 24 positive, unique IDs
- Catchments: 72; one 5/10/15-minute feature for every current branch
- Competitors: 2,367
- Whitespace cells: 5,548
- Growth clusters: 171
- Growth shortlist: 10; all H3 references resolve
- Python/Pydantic tests: 5 passed
- TypeScript/Zod tests: 6 passed
- Ruff lint and formatting: passed
- ESLint: passed
- TypeScript strict checking: passed

The value 24 is asserted only as a current-snapshot quality check. It is not a permanent
schema constraint.
