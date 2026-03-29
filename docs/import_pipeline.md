# Import Pipeline

The current import pipeline is an admin-only, preview-first workflow. Uploaded files are parsed and validated before any database write, and confirmed writes create provenance-aware `ImportBatch` records.

## Entry points

Routes:

- `/imports/`
  upload form
- `/imports/preview/`
  session-backed preview
- `/imports/confirm/`
  confirmed write
- `/imports/result/<batch_id>/`
  import result summary

The upload form supports two source formats:

- CSV contract file
- Excel workbook

For CSV uploads, the curator selects an explicit import type. Workbook uploads always use the workbook contract automatically.

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

## Preview workflow

Preview is the source of truth for the write phase.

1. The uploaded file is parsed in memory.
2. Required headers and row-level validation rules are applied.
3. Foreign-key style references are resolved where the contract requires them.
4. Duplicate rows are identified before write.
5. A session-safe preview payload is stored in the user session.
6. Confirm uses that preview payload directly instead of re-parsing the file a second time.

Imports remain create-only. Preview validation is expected to surface duplicates and contract errors before confirmation.

## Excel workbook support

The admin import screen also accepts the curator Excel workbook described in `excel_import_contract.md`.

Workbook behavior:

- reads the known workbook sheets in memory
- ignores helper sheets
- imports only rows linked to papers with `status = complete`
- validates cross-sheet workbook IDs before any write
- resolves workbook taxa into canonical `Taxon` rows before findings are mapped
- converts workbook rows into the current study, group, comparison, finding, metric, and metadata import shape
- preserves the same preview, confirm, and result flow used by CSV imports

## Service layout

The importer implementation lives in the `imports.services` package.

Public entry points:

- `imports/services/__init__.py`
  stable public API exposing `build_preview()` and `run_import()`

Shared support:

- `imports/services/constants.py`
  importer constants and controlled vocabularies
- `imports/services/helpers.py`
  shared parsing, coercion, and ORM resolution helpers
- `imports/services/types.py`
  dataclasses used while building preview payloads

CSV path:

- `imports/services/csv_preview.py`
  CSV contract parsing and preview validation
- `imports/services/runners.py`
  create-only write runners for confirmed CSV previews

Workbook path:

- `imports/services/workbook.py`
  workbook entry points used by the public API
- `imports/services/workbook_common.py`
  shared workbook preview state and helpers
- `imports/services/workbook_sections.py`
  sheet-specific preview builders for the core workbook sections
- `imports/services/workbook_metadata.py`
  workbook-to-EAV metadata staging logic
- `imports/services/workbook_runners.py`
  confirmed workbook write execution

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
