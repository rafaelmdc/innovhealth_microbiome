# Import Pipeline

The current import pipeline is a create-only import workflow with preview and validation before any database write.

## Supported import types

- `organism`
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
- comparisons resolve by study reference plus `group_a_name`, `group_b_name`, and `comparison_label`
- organisms resolve by `organism_ncbi_taxonomy_id` when present, otherwise `organism_scientific_name`

## Validation rules

- required columns are checked per import type
- duplicate rows are detected before write
- metadata values must populate exactly one typed field
- quantitative values must be numeric
- comparison groups must resolve to existing distinct groups
