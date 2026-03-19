# Schema

## Overview

This project stores curated microbiome literature data using a compact Django/PostgreSQL schema designed for:

- paper-level study records
- analyzable study groups or cohorts
- explicit group-to-group comparisons
- qualitative taxon findings
- quantitative per-group taxon values
- lightweight metadata through a slim EAV layer
- provenance-aware CSV imports

## Main models

### Study

Publication-level record.

Fields:

- `doi`
- `title`
- `journal`
- `year`
- `country`
- `notes`
- `created_at`
- `updated_at`

Rules:

- `doi` is unique when present

### Group

Study arm, cohort, subgroup, or other extracted analytical unit.

Fields:

- `study`
- `name`
- `condition`
- `sample_size`
- `cohort`
- `site`
- `notes`
- `created_at`
- `updated_at`

Rules:

- unique `(study, name)`

### Comparison

Directional comparison between two groups.

Fields:

- `study`
- `group_a`
- `group_b`
- `label`
- `notes`
- `created_at`
- `updated_at`

Rules:

- `group_a != group_b`
- unique `(study, group_a, group_b, label)`
- both groups must belong to the selected study

### Taxon

Canonical taxon record.

Fields:

- `scientific_name`
- `rank`
- `ncbi_taxonomy_id`
- `parent`
- `is_active`
- `notes`
- `created_at`
- `updated_at`

Rules:

- `ncbi_taxonomy_id` is unique when present
- taxonomy uses a self-referential parent link

### TaxonClosure

Ancestor/descendant traversal table.

Fields:

- `ancestor`
- `descendant`
- `depth`

Rules:

- unique `(ancestor, descendant)`
- self rows are stored with `depth = 0`

### TaxonName

Alias and synonym table linked to `Taxon`.

Fields:

- `taxon`
- `name`
- `name_class`
- `source`
- `is_preferred`
- `created_at`
- `updated_at`

### QualitativeFinding

Directional finding for one taxon in one comparison.

Fields:

- `comparison`
- `taxon`
- `direction`
- `source`
- `import_batch`
- `notes`
- `created_at`
- `updated_at`

Rules:

- unique `(comparison, taxon, direction, source)`

### QuantitativeFinding

Numeric value for one taxon in one group.

Fields:

- `group`
- `taxon`
- `value_type`
- `value`
- `unit`
- `source`
- `import_batch`
- `notes`
- `created_at`
- `updated_at`

Rules:

- unique `(group, taxon, value_type, source)`

### MetadataVariable

Slim metadata descriptor.

Fields:

- `name`
- `value_type`
- `display_name`
- `is_filterable`
- `created_at`
- `updated_at`

### MetadataValue

Slim metadata value linked to `Group`.

Fields:

- `group`
- `variable`
- `value_text`
- `value_float`
- `value_int`
- `value_bool`
- `created_at`
- `updated_at`

Rules:

- unique `(group, variable)`
- exactly one typed value field may be populated

### ImportBatch

Import audit and status record.

Fields:

- `name`
- `source_file`
- `import_type`
- `status`
- `created_at`
- `notes`
- `success_count`
- `error_count`

## Optional models

### AlphaMetric

Metric stored for one group.

Fields:

- `group`
- `metric`
- `value`
- `source`
- `import_batch`
- `notes`
- `created_at`
- `updated_at`

### BetaMetric

Metric stored for one comparison.

Fields:

- `comparison`
- `metric`
- `value`
- `source`
- `import_batch`
- `notes`
- `created_at`
- `updated_at`

## Removed from the central model

The following are no longer part of the core schema:

- `Sample`
- `CoreMetadata`
- `RelativeAssociation`
- organism-organism abundance modeling
