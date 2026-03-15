# Excel Import Contract and Workbook Organization

## Purpose

This document describes how the human curation Excel workbook is organized so the codebase agent can:

- map each sheet to the correct import contract
- generate import scripts that validate and load the data into the new schema
- preserve relational links between papers, groups, comparisons, organisms, findings, diversity entries, and metadata

This is the source of truth for the human workbook structure.

Important:
- The import system should be tolerant of blanks where fields are optional.
- The import system should validate IDs and relationships across sheets.
- The import system should not assume every paper has every sheet populated.
- Organism taxonomy resolution is **not** part of the first import step.

A second script will later be added to resolve organism names to:
- cleaned / canonical names
- taxonomic rank where possible
- NCBI taxonomy IDs

For now, organisms are entered only as written by the human curator.

---

## Workbook overview

The Excel workbook contains these sheets:

1. `paper`
2. `groups`
3. `comparissons`
4. `qualitative_findings`
5. `quantitative_findings`
6. `diversity_metrics`
7. `organisms`
8. `extra_metadata`

Optional helper sheets may also exist, such as:
- `instructions`
- `controlled_values`

Import scripts should ignore helper sheets unless explicitly asked to parse them.

---

## Global import rules

### 1. Only import complete papers
Only upload or import information for papers where:

- `paper.status = complete`

Rows linked to papers with any other status should be skipped.

### 2. IDs are the primary linking mechanism
The workbook is relational.

The importer must use IDs to join rows across sheets:
- `paper_id`
- `group_id`
- `comparison_id`
- `organism_id`

The importer should not rely on names alone for joins.

### 3. Preserve human wording where relevant
Fields such as:
- `group_name_as_written`
- `organism_as_written`
- `metric_as_written`
- `value_as_written`
- `where_found`

should be preserved exactly as entered, unless normalization is explicitly part of the import logic.

### 4. Blank values are allowed where fields are optional
Do not fail import only because optional fields are empty.

### 5. Validate referential integrity
The importer must check that:
- every `paper_id` used outside `paper` exists in `paper`
- every `group_id` used outside `groups` exists in `groups`
- every `comparison_id` used outside `comparissons` exists in `comparissons`
- every `organism_id` used outside `organisms` exists in `organisms`

### 6. Reserved values should be validated
The importer should validate controlled fields against the reserved keyword list provided below.

### 7. Organism taxonomy resolution is deferred
The first import step should only use the `organisms` sheet as provided.

Do not require:
- `ncbi_id`
- `suggested_clean_name`
- `rank_if_known`
- `resolved`

to be fully populated during first import.

A later script will handle organism resolution.

---

## Sheet contracts

## 1. `paper`

### Headers
```text
paper_id    doi    authors    year    title    country    topic    status    reviwer    notes
```

### Meaning
Stores one row per paper.

### Notes for importer
- `paper_id` is the primary workbook identifier for the paper.
- `authors` is comma-separated text.
- only import papers with `status = complete`
- `reviwer` is spelled exactly as it appears in the sheet and should be handled as-is unless the workbook is later corrected

### Suggested mapping
- `paper_id` -> workbook-level import identifier
- `doi` -> `Study.doi`
- `authors` -> raw author string or parsed later
- `year` -> `Study.year`
- `title` -> `Study.title`
- `country` -> `Study.country`
- `topic` -> optional study topic field or notes
- `notes` -> `Study.notes`

---

## 2. `groups`

### Headers
```text
group_id    paper_id    group_name_as_written    condition    group_type    body_site    sample_size    age    women_percent    age2    where_found    notes
```

### Meaning
Stores one row per study arm, cohort, subgroup, or analysis group.

### Notes for importer
- `group_id` is the workbook identifier for the group.
- `paper_id` must exist in `paper`.
- `group_name_as_written` should be preserved exactly.
- `age2` currently exists in the workbook and should be preserved as raw metadata or notes unless there is already a defined semantic meaning for it in the codebase.

### Suggested mapping
- `group_id` -> workbook import identifier
- `paper_id` -> FK to `Study`
- `group_name_as_written` -> `Group.name`
- `condition` -> `Group.condition`
- `group_type` -> `Group.group_type`
- `body_site` -> `Group.body_site`
- `sample_size` -> `Group.sample_size`
- `age`, `women_percent`, `age2` -> either direct fields if supported or metadata/EAV
- `where_found` -> provenance text if stored
- `notes` -> `Group.notes`

### Controlled values
`group_type` allowed values:
- `case`
- `control`
- `subtype`
- `treatment`
- `follow_up`
- `responder`
- `non_responder`
- `other`

---

## 3. `comparissons`

### Headers
```text
comparison_id    paper_id    target_group_id    reference_group_id    target_condition    reference_condition    comparison_type    notes
```

### Meaning
Stores one row per standardized comparison.

### Notes for importer
- Sheet name is currently spelled `comparissons` and should be handled exactly as written unless the workbook is later corrected.
- `target_group_id` and `reference_group_id` must exist in `groups`.
- This sheet defines directionality for qualitative findings.

### Suggested mapping
- `comparison_id` -> workbook import identifier
- `paper_id` -> FK to `Study`
- `target_group_id` -> FK to `Group` as target
- `reference_group_id` -> FK to `Group` as reference
- `target_condition` -> optional stored field or derived note
- `reference_condition` -> optional stored field or derived note
- `comparison_type` -> `Comparison.comparison_type`
- `notes` -> `Comparison.notes`

### Controlled values
`comparison_type` allowed values:
- `case_vs_control`
- `severity_vs_mild`
- `responder_vs_non_responder`
- `subtype_vs_subtype`
- `treatment_vs_baseline`
- `other`

---

## 4. `qualitative_findings`

### Headers
```text
finding_id    paper_id    comparison_id    organism_id    organism_as_writiten    direction    finding_type    where_found    notes
```

### Meaning
Stores one row per directional taxon finding inside a defined comparison.

### Notes for importer
- `comparison_id` must exist in `comparissons`.
- `organism_id` must exist in `organisms`.
- `organism_as_writiten` is misspelled in the workbook and should be handled as-is unless corrected later.
- `direction` is relative to the target vs reference logic in `comparissons`.

### Suggested mapping
- `finding_id` -> workbook import identifier
- `paper_id` -> FK to `Study`
- `comparison_id` -> FK to `Comparison`
- `organism_id` -> FK to `Organism`
- `organism_as_writiten` -> preserve as raw text if needed for validation/auditing
- `direction` -> `QualitativeFinding.direction`
- `finding_type` -> `QualitativeFinding.finding_type`
- `where_found` -> `QualitativeFinding.source`
- `notes` -> `QualitativeFinding.notes`

### Controlled values
`direction` allowed values:
- `increased_in_target`
- `decreased_in_target`

`finding_type` allowed values:
- `relative_direction`

---

## 5. `quantitative_findings`

### Headers
```text
quant_finding_id    paper_id    group_id    organism_id    value_type    unit    value    where_found    notes
```

### Meaning
Stores one row per exact numeric value for one organism in one group.

### Notes for importer
- `group_id` must exist in `groups`.
- `organism_id` must exist in `organisms`.
- This sheet is for direct numeric values only.
- `value` should be parsed as numeric when possible.

### Suggested mapping
- `quant_finding_id` -> workbook import identifier
- `paper_id` -> FK to `Study`
- `group_id` -> FK to `Group`
- `organism_id` -> FK to `Organism`
- `value_type` -> `QuantitativeFinding.value_type`
- `unit` -> `QuantitativeFinding.unit`
- `value` -> `QuantitativeFinding.value`
- `where_found` -> `QuantitativeFinding.source`
- `notes` -> `QuantitativeFinding.notes`

### Controlled values
`value_type` allowed values:
- `relative_abundance`

---

## 6. `diversity_metrics`

### Headers
```text
diversity_id    paper_id    comparison_id    group_id    diversity_category    metric_as_written    value    unit    where_found    notes
```

### Meaning
Stores one row per exact alpha or beta diversity metric value.

### Notes for importer
- For alpha diversity, `group_id` will usually be filled.
- For beta diversity, `comparison_id` will usually be filled.
- direct numeric values only

### Suggested mapping
- `diversity_id` -> workbook import identifier
- `paper_id` -> FK to `Study`
- `comparison_id` -> FK to `Comparison` when applicable
- `group_id` -> FK to `Group` when applicable
- `diversity_category` -> alpha/beta category
- `metric_as_written` -> stored metric name
- `value` -> metric numeric value
- `unit` -> optional metric unit
- `where_found` -> provenance/source
- `notes` -> notes

### Controlled values
`diversity_category` allowed values:
- `alpha`
- `beta`

---

## 7. `organisms`

### Headers
```text
organism_id    organism_as_written    suggested_clean_name    rank_if_known    notes    ncbi_id    resolved
```

### Meaning
Stores one row per taxon referenced in the workbook.

### Notes for importer
- For first-pass import, the required fields are mainly:
  - `organism_id`
  - `organism_as_written`
- The rest may be blank initially.
- `suggested_clean_name`, `rank_if_known`, `ncbi_id`, and `resolved` should be preserved if present, but must not be required for initial import.

### Suggested mapping
- `organism_id` -> workbook import identifier
- `organism_as_written` -> `Organism.scientific_name` or raw source name field
- `suggested_clean_name` -> optional future canonical field
- `rank_if_known` -> optional rank field
- `notes` -> `Organism.notes`
- `ncbi_id` -> optional taxonomy ID
- `resolved` -> optional resolution status

### Important future step
A later script will be added to automatically resolve organism names to cleaned names, taxonomic rank, and NCBI taxonomy IDs.

That organism-resolution script is **not** part of the initial workbook importer and should be treated as a separate pipeline stage.

---

## 8. `extra_metadata`

### Headers
```text
paper_id    group_id    field_name    value_as_written    unit    where_found    notes
```

### Meaning
Stores extra metadata fields that do not fit directly into the core sheets.

### Notes for importer
- `paper_id` must exist in `paper`.
- `group_id` should usually exist in `groups`, though the importer may allow blanks if later workflows support paper-level metadata rows.
- `field_name` should map cleanly into the metadata/EAV system.

### Suggested mapping
- `paper_id` -> FK to `Study`
- `group_id` -> FK to `Group`
- `field_name` -> `MetadataVariable.name`
- `value_as_written` -> typed or raw value in `MetadataValue`
- `unit` -> metadata unit if stored
- `where_found` -> provenance text if stored
- `notes` -> notes

---

## Controlled values reference

### `paper.status`
Allowed values:
- `todo`
- `in_progress`
- `complete`
- `needs_review`

### `groups.group_type`
Allowed values:
- `case`
- `control`
- `subtype`
- `treatment`
- `follow_up`
- `responder`
- `non_responder`
- `other`

### `comparissons.comparison_type`
Allowed values:
- `case_vs_control`
- `severity_vs_mild`
- `responder_vs_non_responder`
- `subtype_vs_subtype`
- `treatment_vs_baseline`
- `other`

### `qualitative_findings.direction`
Allowed values:
- `increased_in_target`
- `decreased_in_target`

### `qualitative_findings.finding_type`
Allowed values:
- `relative_direction`

### `quantitative_findings.value_type`
Allowed values:
- `relative_abundance`

### `diversity_metrics.diversity_category`
Allowed values:
- `alpha`
- `beta`

---

## Recommended importer behavior

The generated import script should:

1. load the workbook
2. detect the required sheets by their current names
3. load `paper` first
4. import only papers with `status = complete`
5. load `groups`
6. load `comparissons`
7. load `organisms`
8. load `qualitative_findings`
9. load `quantitative_findings`
10. load `diversity_metrics`
11. load `extra_metadata`
12. validate controlled values
13. validate foreign keys and sheet relationships
14. collect and report row-level errors clearly
15. skip helper sheets such as `instructions` or `controlled_values`

The importer should support:
- validation mode
- preview mode
- import mode

---

## Important pipeline note

Organism resolution is a separate later step.

The initial importer should:
- ingest organism rows as they are
- create organism records from `organism_as_written`
- preserve unresolved values
- avoid blocking import because taxonomy enrichment is not finished

A later script will:
- map `organism_as_written` to cleaned names
- populate `ncbi_id`
- improve or validate taxonomic rank
- mark rows as resolved when appropriate

This later resolution script should be designed as a separate enrichment/update process, not part of the initial workbook import.
