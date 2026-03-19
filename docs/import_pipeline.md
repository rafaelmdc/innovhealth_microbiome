# Import Pipeline

The current import pipeline is a preview-first import workflow with validation before any database write and provenance captured on the confirmed records.

## Supported import types

- `taxon`
- `study`
- `group`
- `comparison`
- `metadata_variable`
- `metadata_value`
- `qualitative_finding`
- `quantitative_finding`
- `alpha_metric`
- `beta_metric`
- `excel_workbook`

## Excel workbook support

The admin import screen also accepts the curator Excel workbook described in `docs/excel_import_contract.md`.

Workbook behavior:

- reads the known workbook sheets in memory
- ignores helper sheets
- imports only rows linked to papers with `status = complete`
- validates cross-sheet workbook IDs before any write
- resolves workbook taxa into canonical `Taxon` rows before findings are mapped
- converts workbook rows into the current study/group/comparison/finding/metric/metadata import shape
- preserves the existing preview/confirm/result workflow

## Service layout

The importer implementation now lives in the `imports.services` package.

- `imports/services/__init__.py`: stable public API used by views and tests
- `imports/services/csv_preview.py`: CSV preview/validation logic
- `imports/services/workbook.py`: workbook parsing, section validation, and workbook import execution
- `imports/services/runners.py`: record creation runners
- `imports/services/helpers.py`, `constants.py`, `types.py`: shared support code

## Resolution rules

- studies resolve by `study_doi` first, then `study_title`
- groups resolve by study reference plus `group_name`
- comparisons resolve by study reference plus `group_a_name` and `group_b_name`, preferring an exact `comparison_label` match when available
- taxa resolve by `taxon_ncbi_taxonomy_id` when present, otherwise `taxon_scientific_name`
- workbook organism identifiers still map to canonical `Taxon` rows after resolution

Taxon resolution behavior:

- preview attempts resolver-backed lineage lookup first
- when resolver-backed lineage is unavailable, exact matches to existing local curated `Taxon` rows are accepted as local taxonomy resolutions
- preview rows carry canonical name, rank, taxid, lineage summary, resolver status, and review flag
- confirm writes the previewed lineage payload rather than recomputing a different taxon resolution

Review-required taxon behavior:

- taxon rows marked `review_required=True` remain visible in preview
- confirming the import does not block the whole batch
- review-required taxon rows are skipped on write
- workbook qualitative and quantitative rows that reference those taxon IDs are skipped during preview and therefore never reach the write phase

## Validation rules

- required columns are checked per import type
- duplicate rows are detected before write
- metadata values must populate exactly one typed field
- quantitative values must be numeric
- comparison groups must resolve to existing distinct groups
- workbook preview is the source of truth for confirmed taxonomy writes
- skipped workbook rows are surfaced explicitly in preview so partial imports are visible before confirmation
